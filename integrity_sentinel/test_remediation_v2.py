"""Offline regressions for persistent acknowledgment faults and first responses."""
import base64
import gc
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from unittest.mock import patch

import requests

from integrity_sentinel.recorder_core_v1 import AppendOnlyHashChainLedger
from integrity_sentinel.runtime_v1 import Handler, NoRedirectSession, RecorderRuntime, SourceConfig


URL = 'https://remediation.up.railway.app/state'
CID = 'KXBTC15M-26SEP171200-00'
BODY = b'{"ok":true,"contract_id":"KXBTC15M-26SEP171200-00"}'
SOURCE = SourceConfig('production_main', URL, 'telemetry')


def controls():
    expected = {'sources': {SOURCE.name: {
        'service_id': 'synthetic', 'deployment_id': 'synthetic', 'branch': 'fixture',
        'commit_sha': 'a' * 40, 'start_command': 'python fixture.py', 'role': 'observer',
        'cutoff_utc': {'not_applicable': True, 'reason': 'synthetic fixture'}}}}
    actual = json.loads(json.dumps(expected))
    actual['captured_at_utc'] = '2026-01-01T00:00:00Z'
    return expected, actual


class StreamingAdapter(requests.adapters.BaseAdapter):
    def __init__(self, code=200, raw=BODY, location=None):
        self.code, self.raw, self.location = code, raw, location
        self.calls = []

    def send(self, request, **kwargs):
        self.calls.append((request.method, request.url, kwargs))
        if request.method != 'GET' or request.url != URL:
            raise AssertionError('unexpected request or redirect hop')
        reply = requests.Response()
        reply.request, reply.url, reply.status_code = request, request.url, self.code
        reply.headers['X-First-Response'] = 'retained'
        if self.location is not None:
            reply.headers['Location'] = self.location
        reply.raw = io.BytesIO(self.raw)
        return reply

    def close(self):
        pass


def runtime(root, adapter=None):
    expected, actual = controls()
    r = RecorderRuntime(root, [SOURCE], expected_manifest=expected, actual_snapshot=actual)
    r._thread = threading.current_thread()
    r.session.trust_env = False
    transport = adapter or StreamingAdapter()
    r.session.mount('https://', transport)
    r.session.mount('http://', transport)
    return r, transport


def endpoint(r, path):
    handler = object.__new__(Handler)
    handler.runtime, handler.path = r, path
    handler._json = lambda code, body: (code, body)
    return handler.do_GET()


class RemediationV2Tests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        network = patch.object(requests.adapters.HTTPAdapter, 'send',
                               side_effect=AssertionError('real network forbidden'))
        network.start()
        self.addCleanup(network.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def assert_unhealthy(self, r):
        self.assertEqual(endpoint(r, '/health')[0], 503)
        code, state = endpoint(r, '/state')
        self.assertEqual(code, 200)
        self.assertIs(state['ok'], False)
        self.assertIn('ledger_integrity_failed', state['health_failures'])

    def test_final_directory_fsync_fault_survives_new_runtime_and_cycle(self):
        for name in ('telemetry', 'membership'):
            with self.subTest(ledger=name), tempfile.TemporaryDirectory(dir=self.root) as td:
                r, _ = runtime(td)
                r.run_cycle()
                self.assertEqual(endpoint(r, '/health')[0], 200)
                ledger = getattr(r, name)
                target_sequence = ledger.status().last_sequence + 1
                real_fsync = os.fsync
                hits = []

                def fail_final(fd):
                    anchor = json.loads(ledger.anchor_path.read_bytes())
                    if (stat.S_ISDIR(os.fstat(fd).st_mode) and
                            anchor['sequence'] == target_sequence and anchor['committed'] is True):
                        hits.append(True)
                        raise OSError('injected final checkpoint directory fsync')
                    return real_fsync(fd)

                with patch('integrity_sentinel.recorder_core_v1.os.fsync', side_effect=fail_final):
                    with self.assertRaises(OSError):
                        ledger.append({'record_type': 'SYNTHETIC_FAULT'})
                self.assertEqual(len(hits), 1)
                self.assertEqual(json.loads(ledger.anchor_path.read_bytes())['sequence'], target_sequence)
                self.assertEqual(json.loads(ledger.path.read_bytes().splitlines()[-1])['sequence'], target_sequence)
                self.assert_unhealthy(r)
                before = {p.name: p.read_bytes() for p in Path(td).iterdir()}
                path = ledger.path
                r.session.close()
                del r, ledger, fail_final
                gc.collect()
                with self.assertRaises(ValueError):
                    AppendOnlyHashChainLedger(path)
                fresh, transport = runtime(td)
                self.assert_unhealthy(fresh)
                self.assertIs(getattr(fresh, name).status().durability_uncertain, True)
                fresh.run_cycle()  # All sources/storage are healthy; fault blocks recording.
                self.assert_unhealthy(fresh)
                self.assertEqual(transport.calls, [])
                self.assertEqual(before, {p.name: p.read_bytes() for p in Path(td).iterdir()})
                self.assertGreaterEqual(fresh.state['recorder']['failure_count'], 2)
                fresh.session.close()

    def test_marker_is_durable_before_anchor_or_ledger_mutation(self):
        ledger = AppendOnlyHashChainLedger(self.root / 'test.jsonl')
        before = (ledger.path.read_bytes(), ledger.anchor_path.read_bytes())
        real_fsync = os.fsync
        seen = []

        def fail_marker_directory(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                seen.append(json.loads(ledger.durability_path.read_bytes()))
                raise OSError('marker directory fsync failed')
            return real_fsync(fd)

        with patch('integrity_sentinel.recorder_core_v1.os.fsync', side_effect=fail_marker_directory):
            with self.assertRaises(OSError):
                ledger.append({'n': 1})
        self.assertEqual(len(seen), 1)
        self.assertEqual(before, (ledger.path.read_bytes(), ledger.anchor_path.read_bytes()))
        with self.assertRaises(ValueError):
            AppendOnlyHashChainLedger(ledger.path)

    def test_failed_fault_storage_never_mutates_ledger_or_anchor(self):
        for mode in ('short', 'file_fsync', 'open'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(dir=self.root) as td:
                ledger = AppendOnlyHashChainLedger(Path(td) / 'test.jsonl')
                before = (ledger.path.read_bytes(), ledger.anchor_path.read_bytes())
                if mode == 'short':
                    injection = patch('integrity_sentinel.recorder_core_v1.os.write', return_value=0)
                elif mode == 'file_fsync':
                    injection = patch('integrity_sentinel.recorder_core_v1.os.fsync', side_effect=OSError('fault storage'))
                else:
                    injection = patch('integrity_sentinel.recorder_core_v1.os.open', side_effect=OSError('cannot open'))
                with injection, self.assertRaises(OSError):
                    ledger.append({'n': 1})
                self.assertEqual(before, (ledger.path.read_bytes(), ledger.anchor_path.read_bytes()))
                self.assertFalse(ledger.status().chain_valid)
                if mode != 'open':
                    with self.assertRaises(ValueError):
                        AppendOnlyHashChainLedger(ledger.path)
                else:
                    # No marker or evidence mutation began: only the old acknowledged tail exists.
                    self.assertEqual(AppendOnlyHashChainLedger(ledger.path).status().records, 0)

    def test_marker_cleanup_failure_stays_fail_closed(self):
        ledger = AppendOnlyHashChainLedger(self.root / 'test.jsonl')
        with patch.object(Path, 'unlink', side_effect=OSError('cleanup failed')):
            with self.assertRaises(OSError):
                ledger.append({'n': 1})
        self.assertTrue(ledger.durability_path.exists())
        with self.assertRaises(ValueError):
            AppendOnlyHashChainLedger(ledger.path)

    def test_marker_content_cannot_make_uncertainty_healthy(self):
        for raw in (b'', b'broken', b'{"state":"HEALTHY"}'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory(dir=self.root) as td:
                ledger = AppendOnlyHashChainLedger(Path(td) / 'test.jsonl')
                ledger.durability_path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    AppendOnlyHashChainLedger(ledger.path)
                self.assertFalse(ledger.status().chain_valid)

    def test_initial_checkpoint_failure_keeps_marker_and_exposes_health(self):
        real_fsync = os.fsync

        def fail_final(fd):
            anchor = self.root / 'telemetry.jsonl.anchor.json'
            if stat.S_ISDIR(os.fstat(fd).st_mode) and anchor.exists():
                raise OSError('initial anchor acknowledgment failed')
            return real_fsync(fd)

        with patch('integrity_sentinel.recorder_core_v1.os.fsync', side_effect=fail_final):
            r, _ = runtime(self.root)
        self.assert_unhealthy(r)
        self.assertTrue(r.telemetry.durability_path.exists())
        r.session.close()
        fresh, _ = runtime(self.root)
        fresh.run_cycle()
        self.assert_unhealthy(fresh)
        fresh.session.close()

    def test_successful_restart_and_append_remain_healthy(self):
        r, _ = runtime(self.root)
        r.run_cycle()
        self.assertEqual(endpoint(r, '/health')[0], 200)
        r.session.close()
        fresh, _ = runtime(self.root)
        fresh.run_cycle()
        self.assertEqual(endpoint(fresh, '/health')[0], 200)
        self.assertFalse(fresh.telemetry.status().durability_uncertain)
        self.assertEqual(list(self.root.glob('*.durability-pending.json')), [])
        fresh.session.close()

    def assert_redirect_retained(self, location, code, raw):
        with tempfile.TemporaryDirectory(dir=self.root) as td:
            transport = StreamingAdapter(code, raw, location)
            r, _ = runtime(td, transport)
            r.run_cycle()
            self.assertEqual(endpoint(r, '/health')[0], 503)
            self.assertIs(endpoint(r, '/state')[1]['ok'], False)
            self.assertEqual(len(transport.calls), 1)
            method, url, settings = transport.calls[0]
            self.assertEqual((method, url), ('GET', URL))
            self.assertIs(settings['verify'], True)
            self.assertEqual(settings['timeout'], 2.5)
            self.assertIs(settings['stream'], True)
            obs = next(row['body'] for row in r.telemetry._iter_records()
                       if row['body'].get('record_type') == 'SOURCE_OBSERVATION')
            self.assertEqual(obs['request_url'], URL)
            self.assertEqual(obs['response_url'], URL)
            self.assertEqual(obs['method'], 'GET')
            self.assertEqual(obs['http_status'], code)
            self.assertEqual(obs['headers']['Location'], location)
            self.assertEqual(obs['headers']['X-First-Response'], 'retained')
            self.assertEqual(base64.b64decode(obs['body_base64']), raw)
            self.assertEqual(obs['body_sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(obs['body_bytes'], len(raw))
            self.assertIs(obs['body_complete'], True)
            self.assertTrue(obs['started_at_utc'])
            self.assertGreaterEqual(obs['completed_at_utc'], obs['started_at_utc'])
            self.assertGreaterEqual(obs['latency_ms'], 0)
            self.assertEqual(obs['parse_outcome'], 'OBJECT' if raw == BODY else 'MALFORMED_JSON')
            self.assertEqual(obs['parse_error'], None if raw == BODY else 'JSONDecodeError')
            self.assertEqual(obs['error_type'], 'RedirectBlocked')
            self.assertTrue(r.telemetry.status().chain_valid)
            r.session.close()

    def test_malformed_location_keeps_complete_first_response(self):
        for location in ('https://[broken', 'https://bad.example/\xff'):
            for code in (301, 302):
                for raw in (BODY, b'{broken-json'):
                    with self.subTest(location=location, code=code, raw=raw):
                        self.assert_redirect_retained(location, code, raw)

    def test_forbidden_redirect_destinations_keep_first_response(self):
        targets = (
            'https://external-api.kalshi.com/trade-api/v2/markets',
            'https://api.exchange.coinbase.com/products/BTC-USD/ticker',
            'https://www.cfbenchmarks.com/data/indices/BRTI',
            'http://remediation.up.railway.app/state', 'https://example.org/state',
            'https://alternate.up.railway.app/state',
            'https://remediation.up.railway.app:444/state',
            'https://user@remediation.up.railway.app/state',
            'https://@remediation.up.railway.app/state', URL + '#fragment',
            'https://remediation.up.railway.app\\@example.org/state',
            URL + '\r\ninvalid', '/relative', URL,
        )
        for location in targets:
            for code in (301, 302):
                with self.subTest(location=location, code=code):
                    self.assert_redirect_retained(location, code, BODY)

    def test_no_redirect_session_never_prepares_next_request(self):
        with NoRedirectSession() as session:
            transport = StreamingAdapter(302, BODY, 'https://[broken')
            session.trust_env = False
            session.mount('https://', transport)
            for follow in (False, True):
                with session.get(URL, allow_redirects=follow, timeout=1) as reply:
                    self.assertEqual(reply.status_code, 302)
                    self.assertEqual(reply.content, BODY)
                    self.assertEqual(reply.history, [])
                    self.assertIsNone(reply.next)
            self.assertEqual(len(transport.calls), 2)


if __name__ == '__main__':
    unittest.main()
