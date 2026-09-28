"""Post-startup ingress regression: frozen native loop, synthetic 2020 data only.

No external feeds, credentials, strategy writes, cohort files, or scoring.
The historical candle cache ends before the current contract's export window.
"""
import ast
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import tempfile
import threading
import subprocess
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import btc15_information_native_offpath_candidate as native
from btc15_information_install_v1 import assemble
from btc15_information_service_v1 import (
    DurablePublisher, HealthMirror, LocalIngress, response, step,
)
from btc15_information_v1 import (
    FIELDS, FairAssessment, InformationPublisher, Unavailable, check_anchor,
    identity, pack, unpack, validate,
)
from completion_audit.isolated_decision_v2 import FrozenRuntime, stable
from test_btc15_information_v1 import provider
from test_btc15_isolated_decision_v2 import OPEN, completed, fixture


def late_input(offset):
    opened = OPEN + (offset // 900) * 900
    closed = opened + 900
    wall = datetime.fromtimestamp(closed, ZoneInfo('America/New_York'))
    ticker = 'KXBTC15M-' + wall.strftime('%y%b%d%H%M').upper() + '-15'
    inp = fixture(offset, ticker=ticker, btc=100080 + (int(offset) % 45))
    inp['market'].update(open_time=datetime.fromtimestamp(opened, timezone.utc).isoformat(),
                         close_time=datetime.fromtimestamp(closed, timezone.utc).isoformat())
    return inp


class LateRig:
    def __init__(self, initial, offset=1200, history=True):
        self.runtime = initial.fork()
        # These are the native ingestion function and its original source/receipt
        # clocks. No fabricated candle, shifted timestamp, or model substitution.
        if history:
            for when in range(max(300, int(offset)-1200), int(offset), 5):
                inp = late_input(when)
                self.runtime.ns['_ec_append_btc_tick'](
                    inp['btc_source'], inp['btc_received'], inp['btc'])
        self.at = OPEN + offset
        inp = late_input(offset)
        self.output = self.runtime.step(inp)
        self.provider = provider(inp)
        self.export = native.NativeExport(clock=lambda: self.at, epoch='native-owner',
                                          provider_reader=lambda: self.provider)
        self.export.offer(self.runtime.ns)


class DiagnosticBoundaryTests(unittest.TestCase):
    def assert_wait(self, pub, ingress, reason):
        out = unpack(response(pub, ingress, '/information', lambda: 100.)[1])
        self.assertEqual(out['status'], 'WAIT')
        self.assertEqual(out['reason'], reason)
        self.assertTrue(out['signal_only']); self.assertFalse(out['orders'])
        metadata = {'schema', 'authority', 'status', 'reason', 'signal_only', 'orders', 'checked_ts'}
        self.assertTrue(all(out[k] is None for k in set(FIELDS)-metadata))

    def test_capture_failure_is_input_boundary_and_redacts(self):
        ingress = SimpleNamespace(capture=lambda: (_ for _ in ()).throw(OSError('private detail')),
                                  health=lambda: {})
        pub = InformationPublisher(evaluator=object())
        self.assertFalse(step(pub, ingress, lambda: 100.))
        self.assert_wait(pub, ingress, 'INPUT_UNAVAILABLE')

    def test_worker_health_failure_has_its_own_boundary(self):
        ingress = SimpleNamespace(capture=lambda: b'{}',
                                  health=lambda: (_ for _ in ()).throw(OSError('private detail')))
        pub = InformationPublisher(evaluator=object())
        self.assertFalse(step(pub, ingress, lambda: 100.))
        self.assertEqual(pub.reason, 'HEALTH_UNAVAILABLE')

    def test_public_health_failure_is_health_boundary(self):
        ingress = SimpleNamespace(health=lambda: (_ for _ in ()).throw(OSError('private detail')))
        self.assert_wait(InformationPublisher(evaluator=object()), ingress, 'HEALTH_UNAVAILABLE')

    def test_public_read_failure_is_read_boundary(self):
        pub = SimpleNamespace(read=lambda *a: (_ for _ in ()).throw(RuntimeError('private detail')))
        self.assert_wait(pub, SimpleNamespace(health=lambda: {}), 'READ_UNAVAILABLE')


class PostStartupRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.initial = FrozenRuntime(completed())
        cls.fair = FairAssessment()

    def make(self, offset=1200):
        rig = LateRig(self.initial, offset)
        self.assertIsNotNone(rig.runtime.ns['_ec_live'])
        self.assertEqual(len(rig.runtime.ns['_unified_rows']), 2)
        self.assertIsNotNone(rig.export.anchor, rig.export.last_offer_error)
        raw = rig.export.capture()
        self.assertEqual(unpack(raw)['anchor']['completed'], [])
        return rig, raw

    def test_original_completed_bound_is_the_reproduced_blocker(self):
        rig = LateRig(self.initial)
        original_check = check_anchor
        failures = []
        def original_bound(a):
            if not isinstance(a['completed'], list) or not 1 <= len(a['completed']) <= 32:
                failures.append('COMPLETED_BOUND')
                raise Unavailable('COMPLETED_BOUND')
            return original_check(a)
        with patch.object(native, 'check_anchor', original_bound):
            rig.export.offer(rig.runtime.ns)
        self.assertEqual(failures, ['COMPLETED_BOUND'])
        self.assertIsNone(rig.export.anchor)
        self.assertIsNotNone(rig.runtime.ns['_ec_live'])
        self.assertEqual(len(rig.runtime.ns['_unified_rows']), 2)

    def test_empty_cache_slice_preserves_exact_native_features_and_probabilities(self):
        for offset in (1200, 1500, 1620, 1799.75, 2100, 3000, 6600):
            with self.subTest(offset=offset):
                rig, raw = self.make(offset)
                before = stable(rig.runtime.snapshot())
                f, q = validate(raw, rig.export.health(), rig.at)
                with patch.object(self.fair, 'build', wraps=self.fair.build) as build:
                    result = self.fair.evaluate(f, q)
                actual_features = self.fair.build(*build.call_args.args, **build.call_args.kwargs)
                self.assertEqual(actual_features, rig.output['inputs'][0]['features'])
                self.assertEqual(result['probability_up'], rig.runtime.ns['_ec_live']['up_fair'])
                # Existing information arithmetic derives DOWN as 1-UP; native
                # retains flip directly. Only the final binary rounding differs.
                self.assertAlmostEqual(result['probability_down'], rig.runtime.ns['_ec_live']['down_fair'], delta=1e-15)
                self.assertEqual(result['probability_up_change_since_native'], 0.)
                self.assertEqual(stable(rig.runtime.snapshot()), before)

    def test_available_pipeline_identity_guard_phases_and_read_only_journal(self):
        rows = []
        with tempfile.TemporaryDirectory() as td:
            installed = assemble(Path(td)/'installed')
            spec = importlib.util.spec_from_file_location('late_proxy', installed/'btc15_information_proxy_v1.py')
            proxy = importlib.util.module_from_spec(spec); spec.loader.exec_module(proxy)
            for offset, phase in ((1200, 'NORMAL'), (1500, '5M_CAUTION'), (1620, '3M_GUARD')):
                with self.subTest(offset=offset):
                    rig, _ = self.make(offset)
                    path = Path(td)/('frames-'+str(offset)+'.jsonl')
                    pub = DurablePublisher(self.fair, journal_path=path)
                    before = stable(rig.runtime.snapshot())
                    server = native.server_for(rig.export)
                    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
                    try:
                        ingress = LocalIngress(server.server_port)
                        self.assertTrue(step(pub, ingress, lambda: rig.at))
                        mirror = HealthMirror(ingress); mirror.refresh()
                        raw = response(pub, mirror, '/information', lambda: rig.at)[1]
                        out = unpack(proxy.closed(raw, rig.at))
                        native_id = proxy.identity_projection(out, rig.at)
                        self.assertEqual(out['status'], 'AVAILABLE')
                        self.assertEqual(out['protection_phase'], phase)
                        self.assertIsInstance(out['flip_risk_pct'], float)
                        self.assertLessEqual(out['brti_age_seconds'], 5.)
                        for key in ('ticker', 'anchor_id', 'native_epoch'):
                            self.assertEqual(out[key], native_id[key])
                        self.assertEqual(native_id['schema'], 'BTC15_INFORMATION_IDENTITY_V1')
                        rows.append(dict(frame=out, identity=native_id))
                        self.assertTrue(out['signal_only']); self.assertFalse(out['orders'])
                        self.assertEqual(len(path.read_bytes().splitlines()), 1)
                        self.assertEqual(stable(rig.runtime.snapshot()), before)
                    finally:
                        server.shutdown(); server.server_close(); thread.join(2)
        # Exercise the exact already-qualified preview script without editing
        # that branch or requiring a live browser, feed, or production request.
        root = Path(__file__).resolve().parent
        source = subprocess.check_output([
            'git', 'show', '9626115d3e017c235c55eaaae97b09e057992eb2:BTC15_RECOVERED_V11_INFORMATION_SEAM_V1.py'
        ], cwd=root, text=True)
        tree = ast.parse(source)
        script = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'SCRIPT' for t in n.targets))
        result = subprocess.run(['node', str(root/'test_btc15_information_ingress_preview.js')],
                                input=json.dumps(dict(script=script, rows=rows)), text=True,
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_missing_or_gapped_tick_support_still_fails_closed(self):
        rig, raw = self.make()
        for select in (lambda ts: ts[-1:], lambda ts: [r for r in ts if r[1] > OPEN+1050]):
            f = unpack(raw); f['anchor']['ticks'] = select(f['anchor']['ticks'])
            f['anchor_id'] = identity(pack(f['anchor']))
            health = dict(rig.export.health(), anchor_id=f['anchor_id'])
            pub = InformationPublisher(self.fair)
            self.assertFalse(pub.offer(pack(f), lambda: health, lambda: rig.at))
            self.assertEqual(pub.reason, 'FEATURE_SUPPORT_UNAVAILABLE')
            self.assertIsNone(pub.latest)
        no_history = LateRig(self.initial, history=False)
        self.assertIsNone(no_history.runtime.ns['_ec_live'])
        self.assertIsNone(no_history.export.anchor)

    def test_evaluation_or_journal_fault_is_not_misdiagnosed_as_health(self):
        rig, _ = self.make()
        pub = InformationPublisher(self.fair)
        with patch.object(self.fair, 'evaluate', side_effect=OSError('private detail')):
            self.assertFalse(step(pub, rig.export, lambda: rig.at))
        self.assertEqual(pub.reason, 'PUBLISH_UNAVAILABLE')
        self.assertIsNone(pub.latest)
        with tempfile.TemporaryDirectory() as td:
            pub = DurablePublisher(self.fair, journal_path=Path(td)/'frames.jsonl')
            with patch('btc15_information_service_v1.os.open', side_effect=OSError('private detail')):
                self.assertFalse(step(pub, rig.export, lambda: rig.at))
            self.assertEqual(pub.reason, 'PUBLISH_UNAVAILABLE')
            self.assertIsNone(pub.latest)

    def test_all_original_clocks_owners_and_provenance_still_reject(self):
        rig, raw = self.make()
        for field, value, reason in (
            ('source', rig.at-5.000001, 'BRTI_STALE_OR_NONCAUSAL'),
            ('received', rig.at+.000001, 'BRTI_STALE_OR_NONCAUSAL'),
        ):
            f = unpack(raw); f['brti'][field] = value
            with self.assertRaisesRegex(Unavailable, reason):
                validate(pack(f), rig.export.health(), rig.at)
        health = rig.export.health()
        for field in ('native_epoch', 'anchor_id', 'ticker', 'brti_epoch', 'quote_epoch'):
            with self.subTest(field=field), self.assertRaises(Unavailable):
                validate(raw, dict(health, **{field: 'different'}), rig.at)
        with self.assertRaisesRegex(Unavailable, 'SOURCE_HEALTH_OR_OWNER_CHANGED'):
            validate(raw, dict(health, observed=rig.at-1.000001), rig.at)
        for change in ('future_btc', 'future_tick', 'stale_btc', 'empty_ticks', 'quote_sequence', 'candle_oversize'):
            f = unpack(raw)
            if change == 'future_btc': f['anchor']['btc']['received'] = rig.at+.1
            if change == 'future_tick': f['anchor']['ticks'][-1][1] = rig.at+.1
            if change == 'stale_btc':
                f['anchor']['btc']['source'] = rig.at-10.000001
                f['anchor']['ticks'][-1][0] = rig.at-10.000001
            if change == 'empty_ticks': f['anchor']['ticks'] = []
            if change == 'quote_sequence': f['proof']['events'][-1]['seq'] += 2
            if change == 'candle_oversize': f['anchor']['completed'] = [[1]*7]*33
            f['anchor_id'] = identity(pack(f['anchor']))
            with self.subTest(change=change), self.assertRaises((ValueError, KeyError)):
                validate(pack(f), dict(health, anchor_id=f['anchor_id']), rig.at)

    def test_rollover_outage_recovery_and_owner_locks_do_not_reuse_numeric_values(self):
        rig, raw = self.make()
        pub = InformationPublisher(self.fair)
        self.assertTrue(step(pub, rig.export, lambda: rig.at))
        metadata = {'schema', 'authority', 'status', 'reason', 'signal_only', 'orders', 'checked_ts'}
        def redacted():
            out = unpack(response(pub, rig.export, '/information', lambda: rig.at)[1])
            self.assertEqual(out['status'], 'WAIT')
            self.assertTrue(all(out[k] is None for k in set(FIELDS)-metadata))
        for lock in (rig.provider.lock, rig.runtime.ns['_brti_delivery'].lock):
            held = threading.Event(); release = threading.Event()
            def hold():
                with lock:
                    held.set(); release.wait(5)
            thread = threading.Thread(target=hold); thread.start()
            try:
                self.assertTrue(held.wait(2)); redacted()
            finally:
                release.set(); thread.join(2)
        rig.provider.book.valid = False; redacted()
        rig.provider.book.valid = True
        self.assertEqual(unpack(response(pub, rig.export, '/information', lambda: rig.at)[1])['status'], 'AVAILABLE')
        rig.at += 2.600001; redacted()  # Original BRTI exceeds five seconds.
        rig.at = OPEN+1800; redacted()  # Original contract expired.
        nxt, _ = self.make(2100)
        self.assertTrue(step(pub, nxt.export, lambda: nxt.at))
        out = unpack(response(pub, nxt.export, '/information', lambda: nxt.at)[1])
        self.assertEqual(out['status'], 'AVAILABLE')
        self.assertNotEqual(out['ticker'], unpack(raw)['anchor']['ticker'])


if __name__ == '__main__':
    unittest.main()
