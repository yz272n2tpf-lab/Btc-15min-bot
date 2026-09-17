"""Independent offline probes: fresh fixtures, real Requests redirect machinery,
real loopback health HTTP, temporary synthetic ledgers, no production access.
Does not import the regression tests or their helpers.
"""
from contextlib import contextmanager
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from urllib.error import HTTPError
from unittest.mock import patch

import requests
from integrity_sentinel.runtime_v1 import RecorderRuntime, SourceConfig, Handler, validate_source_url
from integrity_sentinel.recorder_core_v1 import AppendOnlyHashChainLedger, membership_events
from integrity_sentinel.control_attestation_v1 import compare_manifest, load_manifest
from integrity_sentinel.source_adapters_v1 import adapt_main, adapt_brti_shared

ID_A = 'KXBTC15M-26SEP171200-00'
ID_B = 'KXBTC15M-26SEP171215-00'


class OfflineTransport(requests.adapters.BaseAdapter):
    def __init__(self):
        self.calls = []
        self.overrides = {}

    def send(self, request, **kwargs):
        self.calls.append((request.method, request.url))
        assert request.method == 'GET'
        assert request.url.startswith('https://probe.up.railway.app/')
        name = request.url.rsplit('/', 1)[-1]
        obj = {'ok': True, 'contract_id': ID_A}
        if name == 'combined_membership':
            obj = {'ok': True, 'scorecard': {'contract_rows': []}}
        code, raw, headers = self.overrides.get(name, (200, json.dumps(obj).encode(), {}))
        if isinstance(raw, Exception):
            raise raw
        r = requests.Response()
        r.request = request
        r.url = request.url
        r.status_code = code
        r.headers.update(headers)
        r._content, r._content_consumed = raw, True
        return r

    def close(self):
        pass


@contextmanager
def fixture(control_change=None):
    with tempfile.TemporaryDirectory(prefix='sentinel-offline-probe-') as td, patch.dict(os.environ, {}, clear=True):
        sources = [SourceConfig(n, 'https://probe.up.railway.app/' + n, k) for n, k in
                   [('production_main', 'telemetry'), ('scalp_combined', 'telemetry'),
                    ('combined_membership', 'membership')]]
        expected = {'sources': {s.name: {'service_id': 's-' + s.name, 'deployment_id': 'd',
            'branch': 'frozen', 'commit_sha': 'f' * 40, 'start_command': 'python source.py',
            'role': 'observer', 'cutoff_utc': '2026-09-01T00:00:00Z'} for s in sources}}
        actual = copy.deepcopy(expected)
        actual['captured_at_utc'] = '2026-09-01T00:00:00Z'
        if control_change:
            expected, actual = control_change(expected, actual)
        r = RecorderRuntime(td, sources, expected_manifest=expected, actual_snapshot=actual)
        r._thread = threading.current_thread()
        transport = OfflineTransport()
        r.session.trust_env = False
        r.session.mount('https://', transport)
        yield r, transport
        r.session.close()


def endpoint(r, path='/health'):
    server = ThreadingHTTPServer(('127.0.0.1', 0), type('ProbeHandler', (Handler,), {'runtime': r}))
    worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
    worker.start()
    try:
        try:
            reply = urlopen(f'http://127.0.0.1:{server.server_port}{path}', timeout=2)
        except HTTPError as exc:
            reply = exc
        with reply:
            return reply.status, json.loads(reply.read())
    finally:
        server.shutdown()
        worker.join(timeout=2)
        server.server_close()


def fail_health(r):
    code, obj = endpoint(r)
    assert code == 503 and obj['ok'] is False
    code, obj = endpoint(r, '/state')
    assert code == 200 and obj['ok'] is False


def redirect_probe(targets):
    for target in targets:
        with fixture() as (r, transport):
            transport.overrides['production_main'] = (302, b'redirect-body', {'Location': target})
            _, obs = r.fetch(r.sources[0])
            assert obs['error_type'] == 'RedirectBlocked'
            assert len(transport.calls) == 1, transport.calls
            assert base64.b64decode(obs['body_base64']) == b'redirect-body'


def source_probe(payload=None, unavailable=False):
    with fixture() as (r, transport):
        r.run_cycle()
        assert endpoint(r)[0] == 200
        transport.overrides['production_main'] = (503 if unavailable else 200,
            json.dumps(payload or {'ok': False}).encode(), {})
        r.run_cycle()
        fail_health(r)


def write_probe():
    with fixture() as (r, transport):
        r.run_cycle()
        with patch.object(r.membership, 'append', side_effect=OSError('injected write failure')):
            r.run_cycle()
        fail_health(r)
        assert r.state['recorder']['last_exception_type'] == 'OSError'
        r.run_cycle()
        assert endpoint(r)[0] == 200
        assert r.state['recorder']['failure_count'] == 1


def liveness_probe():
    with fixture() as (r, transport):
        r.run_cycle()
        r._last_success_mono -= 1000
        fail_health(r)
        r.run_cycle()
        r._thread = threading.Thread()
        fail_health(r)


def ledger_probe(mode):
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / 'synthetic.jsonl'
        ledger = AppendOnlyHashChainLedger(path)
        ledger.append({'case': 1})
        ledger.append({'case': 2})
        if mode == 'short':
            real = os.write
            def short(fd, body):
                if os.readlink(f'/proc/self/fd/{fd}') == str(path):
                    return real(fd, body[:-8])
                return real(fd, body)
            with patch('os.write', side_effect=short):
                try:
                    ledger.append({'case': 3})
                except OSError:
                    pass
                else:
                    raise AssertionError('short write accepted')
            assert ledger._sequence == 2
        elif mode == 'newline':
            path.write_bytes(path.read_bytes().rstrip(b'\n'))
        elif mode == 'tail':
            path.write_bytes(path.read_bytes().splitlines(keepends=True)[0])
        elif mode == 'truncate':
            path.write_bytes(b'')
        assert ledger.status().chain_valid is False
        for attempt in (lambda: AppendOnlyHashChainLedger(path), lambda: ledger.append({'case': 4})):
            try:
                attempt()
            except (ValueError, OSError):
                pass
            else:
                raise AssertionError('broken ledger accepted')


def blank_control_probe():
    with fixture() as (r, _):
        for value in (None, '', '   '):
            expected = {'sources': {'s': {field: value for field in
                ('service_id', 'deployment_id', 'branch', 'commit_sha', 'start_command', 'role', 'cutoff_utc')}}}
            assert compare_manifest(expected, expected)['control_plane_pass'] is not True
            p = r.root / 'blank-manifest.json'
            p.write_text(json.dumps(expected))
            try:
                load_manifest(p)
            except ValueError:
                pass
            else:
                raise AssertionError('blank manifest accepted')
        assert compare_manifest({'sources': {}}, {})['control_plane_pass'] is not True


def actual_control_probe(mismatch=False):
    def change(expected, actual):
        if mismatch:
            actual['sources']['production_main']['branch'] = 'drift'
        else:
            actual = None
        return expected, actual
    with fixture(change) as (r, _):
        r.run_cycle()
        fail_health(r)
        assert r.state['control_attestation']['control_plane_pass'] is (False if mismatch else None)


def combined_probe():
    payload = {'scorecard': {'contract_rows': [{'contract': ID_A, 'early_side': 'UP'}]}}
    rows = membership_events('combined_membership', payload)
    assert len(rows) == 1 and rows[0]['contract_id'] == ID_A


def nextgen_probe():
    for leaf in ([{'contract': ID_A, 'lane': 'V1_IMMEDIATE'}],
                 {'records': [{'contract': ID_A, 'lane': 'V1_IMMEDIATE'}]}):
        payload = {'audit_records': {'candidate_verify_v2': {'V1_IMMEDIATE': leaf}}}
        rows = membership_events('nextgen_membership', payload)
        assert len(rows) == 1 and rows[0]['contract_id'] == ID_A
        assert 'candidate_verify_v2/V1_IMMEDIATE' in rows[0]['container']


def retention_probe(code, raw, outcome):
    with fixture() as (r, transport):
        transport.overrides['production_main'] = (code, raw, {'X-Provenance': 'offline'})
        r.run_cycle()
        bodies = [row['body'] for row in r.telemetry._iter_records()]
        obs = next(b for b in bodies if b.get('source') == 'production_main')
        assert obs['http_status'] == code and obs['parse_outcome'] == outcome
        assert base64.b64decode(obs['body_base64']) == raw
        assert obs['body_sha256'] == hashlib.sha256(raw).hexdigest()
        assert obs['headers']['X-Provenance'] == 'offline'
        assert all(obs[k] is not None for k in ('started_at_utc', 'completed_at_utc', 'latency_ms', 'request_url'))
        fail_health(r)


def empty_membership_probe():
    with fixture() as (r, _):
        r.membership_cycle()
        rows = list(r.membership._iter_records())
        assert len(rows) == 1
        assert rows[0]['body']['payload']['scorecard']['contract_rows'] == []
        assert rows[0]['body']['body_sha256']


def kalshi_probe():
    n = adapt_main({'source_age_sec': 0, 'market_age_sec': 0})
    assert 'kalshi_age_sec' not in n and n['kalshi_freshness_status'] == 'UNKNOWN'


def coinbase_probe():
    with fixture() as (r, _):
        r.run_cycle()
        s = r.public_state()
        assert s['provider_evidence']['coinbase'] == 'INSUFFICIENT'
        assert s['certifiable_evidence'] is False
        assert adapt_main({'source_age_sec': 0})['coinbase_freshness_status'] == 'UNKNOWN'


def disk_probe():
    with fixture() as (r, _):
        before = {p.name: p.read_bytes() for p in r.root.iterdir()}
        with patch('integrity_sentinel.runtime_v1.storage_status', return_value={'storage_ok': False, 'state': 'FAIL'}):
            r.run_cycle()
            try:
                r.membership_cycle()
            except OSError:
                pass
            else:
                raise AssertionError('membership wrote on low disk')
            fail_health(r)
        after = {p.name: p.read_bytes() for p in r.root.iterdir()}
        assert before == after


def ids_probe():
    for bad in (True, False, 22, .5, [], {}, None, '', 'not-btc', 'KXBTC15M-'):
        try:
            adapt_main({'contract_id': bad})
        except ValueError:
            pass
        else:
            raise AssertionError('invalid ID accepted: ' + repr(bad))


def conflict_probe():
    for payload in ({'contract': ID_A, 'ticker': ID_B},
                    {'contract_id': ID_A, 'market': {'contract': ID_B}}):
        source_probe(payload)


def cross_probe():
    with fixture() as (r, t):
        t.overrides['scalp_combined'] = (200, json.dumps({'ok': True, 'ticker': ID_B}).encode(), {})
        r.run_cycle()
        fail_health(r)
        agreement = list(r.telemetry._iter_records())[-1]['body']
        assert agreement['agreement'] is False and len(set(agreement['contracts'].values())) == 2


def counter_probe():
    for key in ('sequence', 'upstream_attempts', 'upstream_ok', 'upstream_errors', 'http_429',
                      'timeout_errors', 'http_errors', 'connection_errors', 'other_errors', 'consecutive_errors'):
        for value in (True, -1, .25, '2', {}, [], None, float('nan'), float('inf')):
            try:
                adapt_brti_shared({key: value})
            except ValueError:
                pass
            else:
                raise AssertionError('invalid counter accepted')


def userinfo_probe():
    for userinfo in ('@', ':@', 'name:@', ':pass@'):
        try:
            validate_source_url('https://' + userinfo + 'probe.up.railway.app/state')
        except ValueError:
            pass
        else:
            raise AssertionError('userinfo accepted')


def run():
    probes = [
        ('01 redirect to Kalshi', lambda: redirect_probe(['https://api.elections.kalshi.com/'])),
        ('02 redirect to Coinbase', lambda: redirect_probe(['https://api.coinbase.com/'])),
        ('03 redirect HTTP/non-Railway/approved-hop', lambda: redirect_probe([
            'http://probe.up.railway.app/state', 'https://example.org/', 'https://other.up.railway.app/state'])),
        ('04 required source unavailable', lambda: source_probe(unavailable=True)),
        ('05 HTTP-200 source failure/staleness', lambda: [source_probe(p) for p in
            ({'ok': False}, {'status': 'STALE'}, {'source_age_sec': 999}, {'kalshi_age_sec': 999})]),
        ('06 write failure then health and recovery', write_probe),
        ('07 recorder dead/stale', liveness_probe),
        ('08 short write', lambda: ledger_probe('short')),
        ('09 missing final newline', lambda: ledger_probe('newline')),
        ('10 complete tail deletion', lambda: ledger_probe('tail')),
        ('11 full truncation', lambda: ledger_probe('truncate')),
        ('12 blank/null control manifest', blank_control_probe),
        ('13 missing actual control capture', actual_control_probe),
        ('14 control mismatch', lambda: actual_control_probe(True)),
        ('15 real Combined membership shape', combined_probe),
        ('16 real Nextgen membership shapes', nextgen_probe),
        ('17 HTTP-error body retention', lambda: retention_probe(502, b'upstream error', 'MALFORMED_JSON')),
        ('18 malformed JSON retention', lambda: retention_probe(200, b'{oops', 'MALFORMED_JSON')),
        ('19 wrong-type JSON retention', lambda: retention_probe(200, b'[1,2]', 'WRONG_TYPE')),
        ('20 empty membership envelope', empty_membership_probe),
        ('21 generic age is not Kalshi', kalshi_probe),
        ('22 missing Coinbase freshness', coinbase_probe),
        ('23 low-disk membership block', disk_probe),
        ('24 invalid contract IDs', ids_probe),
        ('25 within-payload ID conflicts', conflict_probe),
        ('26 cross-source disagreement', cross_probe),
        ('27 invalid BRTI counters', counter_probe),
        ('28 empty user-info URLs', userinfo_probe),
    ]
    results = []
    for name, probe in probes:
        try:
            probe()
            results.append({'probe': name, 'result': 'PASS'})
        except Exception as exc:
            results.append({'probe': name, 'result': 'FAIL', 'error': type(exc).__name__ + ': ' + str(exc)})
    report = {'passed': sum(r['result'] == 'PASS' for r in results), 'total': len(results),
              'network': 'offline source transport; health HTTP on loopback only', 'results': results}
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] == report['total'] else 1


if __name__ == '__main__':
    raise SystemExit(run())
