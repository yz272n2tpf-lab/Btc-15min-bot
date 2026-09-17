"""Independent offline black-box storage probes; no unit fixture imports.

Synthetic Requests adapter, public health handler, independent SHA-256 and
ledger inspection. Faults affect temporary local data only. No live service.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import copy
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import threading
from unittest.mock import patch

import requests
from integrity_sentinel.runtime_v1 import RecorderRuntime, SourceConfig, Handler
from integrity_sentinel.recorder_core_v1 import AppendOnlyHashChainLedger

CID = 'KXBTC15M-26SEP171200-00'
HOST = 'https://independent-storage-offline.up.railway.app/'
NAMES = ('production_main', 'brti_shared', 'scalp_combined', 'early_membership',
         'final_membership', 'combined_membership', 'nextgen_membership')
SOURCES = [SourceConfig(n, HOST + ('audit' if n == 'nextgen_membership' else n),
                       'telemetry' if i < 3 else 'membership') for i, n in enumerate(NAMES)]


def synthetic_audit(records_per_lane=1, revision=0):
    """Real producer's family->lane->records topology, invented exact IDs/data.

    Field shapes follow frozen Nextgen source; no producer is imported/run and
    no prices, strategy outputs or evidence are taken from a live service.
    """
    families = ('scalp2_economics_v2', 'candidate_verify_v2', 'watch_exit_v2', 'selective_pullback_v2')
    rows = []
    for n in range(records_per_lane):
        rows.append({'contract': f'KXBTC15M-26SEP{17 + n // 96:02d}{(n % 96) // 4:02d}{(n % 4) * 15:02d}-00',
            'side': 'UP' if n % 2 else 'DOWN', 'opportunity_index': 1 + n % 2,
            'entry_ask': .45, 'entry_elapsed_sec': 15.0, 'decision_reason': 'SYNTHETIC_OFFLINE',
            'protected_exit_observed': True, 'gross_protected_gain_c': 12.0,
            'one_lot_taker_taker_net_c': 8.5, 'ten_lot_taker_taker_net_c': 9.0,
            'armed': True, 'warning': True, 'warning_time_sec': 42.0, 'exit': True,
            'exit_time_sec': 49.0, 'exit_gain': .12, 'lead': 7.0,
            'recovered_new_high_after_warning': False, 'warning_without_exit': False,
            'unresolved_warning': False, 'legacy_economics_exit_matches_watch': True})
    obj = {'version': 'SYNTHETIC_NEXTGEN_V2', 'window_id': 'a' * 64,
           'source_sha256': hashlib.sha256(str(revision).encode()).hexdigest(),
           'audit_records': {family: {f'OFFLINE_LANE_{lane}': rows for lane in range(4)} for family in families},
           'ok': True, 'orders': False, 'automatic_promotion': False, 'certifiable_evidence': False}
    return json.dumps(obj, separators=(',', ':')).encode()


def controls():
    expected = {'sources': {s.name: {'service_id': 'offline-' + s.name, 'deployment_id': 'synthetic',
        'branch': 'fixture', 'commit_sha': 'b' * 40, 'start_command': 'python offline.py',
        'role': 'observer', 'cutoff_utc': {'not_applicable': True, 'reason': 'offline synthetic'}} for s in SOURCES}}
    actual = copy.deepcopy(expected)
    actual['captured_at_utc'] = '2026-01-01T00:00:00Z'
    return expected, actual


class MemoryTransport(requests.adapters.BaseAdapter):
    def __init__(self, raw=None):
        self.audit = raw or synthetic_audit()
        self.code, self.partial, self.calls = 200, False, []

    def send(self, request, **kwargs):
        assert request.method == 'GET' and request.url in {s.url for s in SOURCES}
        self.calls.append(request.url)
        name = next(s.name for s in SOURCES if s.url == request.url)
        watchdog = {'healthy': True, 'observer_worker_alive': True, 'observer_age_sec': .5,
                    'observer_stale_sec': 60, 'observer_last_exception': None}
        obj = {'ok': True, 'contract_id': CID}
        if name == 'brti_shared':
            obj = {'ok': True, 'age_ms': 10, 'clean_for_qualification': True}
        elif name == 'early_membership':
            obj = {'ok': True, 'watchdog': watchdog, 'live': {'call_records': [], 'settled_records': []}}
        elif name == 'final_membership':
            obj = {'ok': True, 'watchdog': watchdog, 'live': {'lock_records': [], 'settled_records': []}}
        elif name == 'combined_membership':
            obj = {'ok': True, 'scorecard': {'contract_rows': []}}
        raw = self.audit if name == 'nextgen_membership' else json.dumps(obj).encode()
        response = requests.Response()
        response.request, response.url = request, request.url
        response.status_code = self.code if name == 'nextgen_membership' else 200
        response.headers['X-Request-Ordinal'] = str(len(self.calls))
        response.headers['Content-Type'] = 'application/json'
        response.raw = io.BytesIO(raw)
        if self.partial and name == 'nextgen_membership':
            def interrupted(**kw):
                yield raw
                raise requests.exceptions.ChunkedEncodingError('offline partial response')
            response.iter_content = interrupted
        return response

    def close(self):
        pass


def runtime(root, raw=None):
    expected, actual = controls()
    r = RecorderRuntime(root, SOURCES, expected_manifest=expected, actual_snapshot=actual)
    r._thread = threading.current_thread()
    adapter = MemoryTransport(raw)
    r.session.trust_env = False
    r.session.mount('https://', adapter)
    return r, adapter


def endpoint(r):
    handler = object.__new__(Handler)
    handler.runtime, handler.path = r, '/health'
    handler._json = lambda code, obj: (code, obj)
    return handler.do_GET()


def observations(r):
    return [row for row in r.membership._iter_records()
            if row['body'].get('record_type') == 'SOURCE_OBSERVATION' and row['body']['source'] == 'nextgen_membership']


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory(prefix='offline-body-adversarial-') as td:
        r, adapter = runtime(td)
        try:
            yield r, adapter
        finally:
            r.session.close()


def positive(r):
    r.run_cycle()
    assert endpoint(r)[0] == 200, endpoint(r)[1]['health_failures']
    assert r.public_state()['certifiable_evidence'] is False


def independent_resolve(r, obs):
    digest = obs['body_sha256']
    raw = (r.root / 'nextgen-bodies-v1' / (digest + '.body')).read_bytes()
    assert len(raw) == obs['body_bytes'] and hashlib.sha256(raw).hexdigest() == digest
    assert obs['body_ref'] == {'scheme': 'NEXTGEN_SHA256_V1', 'sha256': digest, 'bytes': len(raw)}
    return raw


def repeat_probe():
    with fixture() as (r, a):
        for _ in range(4): positive(r)
        obs = observations(r)
        assert len(obs) == 4 and len({o['body']['observation_id'] for o in obs}) == 4
        assert len(list((r.root / 'nextgen-bodies-v1').glob('*.body'))) == 1
        assert all(independent_resolve(r, o['body']) == a.audit for o in obs)
        assert len({o['body']['headers']['X-Request-Ordinal'] for o in obs}) == 4
        assert all(o['body']['body_complete'] and o['body']['parse_outcome'] == 'OBJECT' for o in obs)
        assert len(a.calls) == 28


def change_probe():
    with fixture() as (r, a):
        positive(r)
        old = a.audit
        a.audit += b' '
        positive(r)
        assert len(list((r.root / 'nextgen-bodies-v1').glob('*.body'))) == 2
        assert independent_resolve(r, observations(r)[0]['body']) == old
        assert independent_resolve(r, observations(r)[1]['body']) == a.audit


def error_probe(mode):
    with fixture() as (r, a):
        positive(r)
        if mode == 'http': a.code = 503  # SAME valid body, still cannot reuse.
        elif mode == 'partial': a.partial = True
        elif mode == 'malformed': a.audit = b'{broken\xff'
        elif mode == 'wrong-type': a.audit = b'[]'
        elif mode == 'health': a.audit = a.audit.replace(b'"ok":true', b'"ok":false')
        positive_count = len(observations(r))
        r.run_cycle()
        assert endpoint(r)[0] == 503
        obs = observations(r)[-1]['body']
        assert len(observations(r)) == positive_count + 1
        assert 'body_ref' not in obs and base64.b64decode(obs['body_base64']) == a.audit
        assert obs['body_sha256'] == hashlib.sha256(a.audit).hexdigest()
        assert len(list((r.root / 'nextgen-bodies-v1').glob('*.body'))) == 1


def reopen_child(root, expected_health, pipe):
    try:
        r, a = runtime(root)
        r.run_cycle()
        result = {'health': endpoint(r)[0], 'calls': len(a.calls), 'files': snapshot(Path(root)), 'pid': os.getpid()}
        assert result['health'] == expected_health, result
        pipe.send(result)
    except BaseException as exc:
        pipe.send({'error': repr(exc)})
    finally:
        pipe.close()


def process_reopen(root, health):
    context = multiprocessing.get_context('spawn')
    reader, writer = context.Pipe(duplex=False)
    p = context.Process(target=reopen_child, args=(str(root), health, writer))
    p.start()
    writer.close()
    assert reader.poll(20), 'reopen process timed out'
    result = reader.recv()
    p.join(20)
    assert p.exitcode == 0 and 'error' not in result, result
    return result


def corrupt_probe(mode):
    with fixture() as (r, a):
        positive(r)
        root = r.root / 'nextgen-bodies-v1'
        p = next(root.glob('*.body'))
        if mode == 'missing': p.unlink()
        elif mode in ('modified', 'truncated'):
            p.chmod(0o600)
            p.write_bytes(a.audit[:-1] if mode == 'truncated' else a.audit.replace(b'SYNTHETIC', b'XYNTHETIC', 1))
        elif mode == 'catalog': (root / 'catalog.jsonl').unlink()
        elif mode == 'reference':
            obs = copy.deepcopy(observations(r)[0]['body'])
            obs['body_ref']['sha256'] = 'f' * 64
            AppendOnlyHashChainLedger(r.membership.path).append(obs)
        assert endpoint(r)[0] == 503
        before = snapshot(r.root)
        for _ in range(2):
            result = process_reopen(r.root, 503)
            assert result['files'] == before and result['calls'] == 0


def restart_probe():
    with fixture() as (r, a):
        positive(r)
        digest = observations(r)[0]['body']['body_sha256']
        result = process_reopen(r.root, 200)
        assert result['pid'] != os.getpid() and result['calls'] == 7
        assert len(observations(r)) == 2
        assert next((r.root / 'nextgen-bodies-v1').glob('*.body')).name == digest + '.body'


def concurrency_probe():
    with fixture() as (r, a):
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda _: r.membership_cycle(), range(18)))
        assert r.membership.status().chain_valid
        assert len(observations(r)) == 18
        assert len({o['body']['observation_id'] for o in observations(r)}) == 18
        assert len(list((r.root / 'nextgen-bodies-v1').glob('*.body'))) == 1


def provenance_probe():
    with fixture() as (r, a):
        positive(r)
        a.audit = a.audit.replace(b'"entry_ask":0.45', b'"entry_ask":0.46')
        positive(r)
        parents = {o['body']['observation_id']: o for o in observations(r)}
        events = [o['body'] for o in r.membership._iter_records() if o['body'].get('record_type') == 'STRATEGY_MEMBERSHIP']
        assert len(events) == 32
        for event in events:
            parent = parents[event['observation_id']]
            assert event['observation_record_hash'] == parent['record_hash']
            assert event['observation_body_sha256'] == parent['body']['body_sha256']
            payload = json.loads(independent_resolve(r, parent['body']))
            _, family, lane = event['container'].split('/')
            assert event['record'] in payload['audit_records'][family][lane]
            assert event['contract_id'] == event['record']['contract']


def durability_probe(target, operation):
    with fixture() as (r, a):
        # Observe fsync/write failure for the new immutable body or the ledger
        # reference; complete-looking bytes may never masquerade as committed.
        real = getattr(os, operation)
        hits = []
        def injected(fd, *args):
            path = os.readlink('/proc/self/fd/' + str(fd))
            hit = path.endswith('.body') if target == 'body' else (path == str(r.membership.path)
                and any((r.root / 'nextgen-bodies-v1').glob('*.body')))
            if hit:
                hits.append(path)
                if operation == 'write':
                    return real(fd, args[0][:-1])
                raise OSError('independent injected durability failure')
            return real(fd, *args)
        with patch('os.' + operation, side_effect=injected):
            r.run_cycle()
        assert hits and endpoint(r)[0] == 503
        before = snapshot(r.root)
        for _ in range(2):
            result = process_reopen(r.root, 503)
            assert result['files'] == before and result['calls'] == 0


def fsync_boundary_probe():
    # Sweep every body publication fsync boundary, including catalog and final
    # directory acknowledgement. Pre-intent failure may reopen an unchanged
    # empty store; once intent exists every boundary must remain blocked.
    from integrity_sentinel.nextgen_body_store_v1 import NextgenBodyStore
    with tempfile.TemporaryDirectory() as td:
        count = []
        real = os.fsync
        with patch('os.fsync', side_effect=lambda fd: (count.append(fd), real(fd))[1]):
            NextgenBodyStore(td).put(synthetic_audit())
    for fail_at in range(1, len(count) + 1):
        with tempfile.TemporaryDirectory() as td:
            store = NextgenBodyStore(td)
            calls = []
            def fail(fd):
                calls.append(fd)
                if len(calls) == fail_at: raise OSError('fsync boundary')
                return real(fd)
            with patch('os.fsync', side_effect=fail):
                try: store.put(synthetic_audit())
                except OSError: pass
                else: raise AssertionError('injection missed')
            before = snapshot(Path(td))
            reopened = NextgenBodyStore(td)
            if fail_at == 1:
                assert reopened.verify() == {}  # No intent or evidence exists.
            else:
                try: reopened.verify()
                except (OSError, ValueError): pass
                else: raise AssertionError('unacknowledged body adopted')
            assert snapshot(Path(td)) == before
    return {'fsync_boundaries': len(count)}


def run():
    probes = [('identical observations', repeat_probe), ('one byte changed', change_probe),
              *[(m + ' never reuses', lambda m=m: error_probe(m)) for m in ('http', 'partial', 'malformed', 'wrong-type', 'health')],
              *[(m + ' fails two fresh processes', lambda m=m: corrupt_probe(m)) for m in ('missing', 'modified', 'truncated', 'catalog', 'reference')],
              ('valid process restart', restart_probe), ('concurrent observations', concurrency_probe),
              ('exact membership provenance', provenance_probe),
              *[(t + ' ' + op + ' failure', lambda t=t, op=op: durability_probe(t, op))
                for t in ('body', 'reference') for op in ('write', 'fsync')],
              ('every body fsync boundary', fsync_boundary_probe)]
    results = []
    with patch.dict(os.environ, {}, clear=True), patch.object(requests.adapters.HTTPAdapter, 'send',
            side_effect=AssertionError('real network forbidden')):
        for name, fn in probes:
            try:
                detail = fn()
                results.append({'probe': name, 'result': 'PASS', 'detail': detail})
            except Exception as exc:
                results.append({'probe': name, 'result': 'FAIL', 'error': repr(exc)})
    report = {'passed': sum(r['result'] == 'PASS' for r in results), 'total': len(results),
              'network': 'synthetic transport only', 'results': results}
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] == report['total'] else 1


if __name__ == '__main__':
    raise SystemExit(run())
