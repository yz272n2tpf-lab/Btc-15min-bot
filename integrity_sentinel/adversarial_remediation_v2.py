"""Dedicated offline V2 probes, independent of the unittest fixtures.

Durability injection and reopen run in separate, exited Python interpreters.
Sources use an in-memory Requests adapter; endpoint checks use loopback only.
All mutated files are temporary synthetic fixtures, never source evidence.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

import requests

from integrity_sentinel.adversarial_hardening_v1 import endpoint
from integrity_sentinel.recorder_core_v1 import AppendOnlyHashChainLedger
from integrity_sentinel.runtime_v1 import RecorderRuntime, SourceConfig


URL = 'https://v2-offline.up.railway.app/state'
RAW = b'{"ok":true,"contract_id":"KXBTC15M-26SEP171200-00"}'


class FirstResponseTransport(requests.adapters.BaseAdapter):
    def __init__(self, code=200, body=RAW, location=None):
        self.code, self.body, self.location = code, body, location
        self.calls = []

    def send(self, request, **kwargs):
        self.calls.append({'method': request.method, 'url': request.url})
        assert self.calls[-1] == {'method': 'GET', 'url': URL}, self.calls
        assert kwargs['verify'] is True and kwargs['timeout'] == 2.5
        assert kwargs['stream'] is True
        response = requests.Response()
        response.request, response.url = request, request.url
        response.status_code = self.code
        response.headers['X-Offline-Evidence'] = 'first-response'
        if self.location is not None:
            response.headers['Location'] = self.location
        response.raw = io.BytesIO(self.body)
        return response

    def close(self):
        pass


def open_runtime(root, transport=None):
    source = SourceConfig('production_main', URL, 'telemetry')
    expected = {'sources': {source.name: {
        'service_id': 'offline-service', 'deployment_id': 'offline-deployment',
        'branch': 'fixture', 'commit_sha': 'd' * 40, 'start_command': 'python fixture.py',
        'role': 'observer', 'cutoff_utc': {'not_applicable': True, 'reason': 'offline probe'}}}}
    actual = json.loads(json.dumps(expected))
    actual['captured_at_utc'] = '2026-01-01T00:00:00Z'
    r = RecorderRuntime(root, [source], expected_manifest=expected, actual_snapshot=actual)
    r._thread = threading.current_thread()
    transport = transport or FirstResponseTransport()
    r.session.trust_env = False
    r.session.mount('https://', transport)
    r.session.mount('http://', transport)
    return r, transport


def failed_endpoints(r):
    code, health = endpoint(r)
    state_code, state = endpoint(r, '/state')
    assert code == 503 and health['ok'] is False
    assert state_code == 200 and state['ok'] is False
    return {'health_status': code, 'state_ok': state['ok']}


def files_digest(root):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).iterdir())}


def durability_stage(root, stage, name):
    # A child stage is restricted to a temp fixture deliberately created by run().
    assert root.parent.name.startswith('sentinel-v2-process-probe-')
    assert (root.parent / 'OFFLINE_SYNTHETIC_FIXTURE').read_text() == 'no source evidence'
    before = files_digest(root) if root.exists() else None
    r, transport = open_runtime(root)
    ledger = getattr(r, name)
    if stage == 'inject':
        r.run_cycle()
        assert endpoint(r)[0] == 200
        expected_seq = ledger.status().last_sequence + 1
        original_fsync = os.fsync
        hits = []

        def injected(fd):
            anchor = json.loads(ledger.anchor_path.read_bytes())
            if (stat.S_ISDIR(os.fstat(fd).st_mode) and
                    anchor['committed'] is True and anchor['sequence'] == expected_seq):
                hits.append(anchor)
                raise OSError('V2 final checkpoint directory fsync failure')
            original_fsync(fd)

        with patch('integrity_sentinel.recorder_core_v1.os.fsync', side_effect=injected):
            try:
                ledger.append({'record_type': 'SYNTHETIC_DURABILITY_PROBE'})
            except OSError:
                pass
            else:
                raise AssertionError('injected final directory fsync was accepted')
        assert len(hits) == 1
        row = json.loads(ledger.path.read_bytes().splitlines()[-1])
        anchor = json.loads(ledger.anchor_path.read_bytes())
        assert row['sequence'] == expected_seq == anchor['sequence']
        assert row['record_hash'] == anchor['record_hash']
        assert anchor['bytes'] == ledger.path.stat().st_size and anchor['committed'] is True
        assert ledger.status().chain_valid is False
        assert ledger.status().durability_uncertain is True
        result = {'injected_final_fsync_failures': len(hits), 'complete_row_and_anchor': True,
                  'after_failure': failed_endpoints(r)}
    else:
        assert before == files_digest(root), 'startup changed synthetic evidence'
        assert ledger.status().chain_valid is False and ledger.status().durability_uncertain is True
        try:
            AppendOnlyHashChainLedger(ledger.path)
        except ValueError:
            pass
        else:
            raise AssertionError('strict reopen accepted uncertain ledger')
        result = {'after_reopen': failed_endpoints(r)}
        # Everything except the unresolved durability fault is available. The
        # ordinary cycle must refuse writes; it cannot clear the persistent fault.
        r.run_cycle()
        result['after_subsequent_cycle'] = failed_endpoints(r)
        assert not transport.calls, 'blocked recorder attempted source polling'
        assert before == files_digest(root), 'reopen/cycle mutated synthetic evidence'
        assert ledger.status().chain_valid is False
        assert r.state['recorder']['failure_count'] >= 2
        result.update(evidence_unchanged=True, cycle_source_requests=0,
                      failure_count=r.state['recorder']['failure_count'])
    result.update(pid=os.getpid(), ledger=name, files=files_digest(root))
    r.session.close()
    return result


def fresh_process_probe(name):
    with tempfile.TemporaryDirectory(prefix='sentinel-v2-process-probe-') as td:
        parent = Path(td)
        (parent / 'OFFLINE_SYNTHETIC_FIXTURE').write_text('no source evidence')
        reports = []
        # Each subprocess exits before its successor is created: no objects,
        # monkeypatches, counters, or Python memory survive into reopen.
        for stage in ('inject', 'reopen', 'reopen'):
            command = [sys.executable, '-m', 'integrity_sentinel.adversarial_remediation_v2',
                       '--stage', stage, '--root', str(parent / 'data'), '--ledger', name]
            process = subprocess.run(command, text=True, capture_output=True, timeout=30,
                                     env={'PYTHONDONTWRITEBYTECODE': '1'})
            assert process.returncode == 0, process.stdout + process.stderr
            reports.append(json.loads(process.stdout))
        assert len({r['pid'] for r in reports}) == 3
        assert reports[0]['files'] == reports[1]['files'] == reports[2]['files']
        return {'separate_processes': 3, 'stages': reports}


def redirects_probe(targets):
    results = []
    for location in targets:
        for code in (301, 302):
            for raw in (RAW, b'{invalid-first-body'):
                with tempfile.TemporaryDirectory(prefix='sentinel-v2-redirect-probe-') as td:
                    adapter = FirstResponseTransport(code, raw, location)
                    r, _ = open_runtime(td, adapter)
                    r.run_cycle()
                    failed_endpoints(r)
                    assert adapter.calls == [{'method': 'GET', 'url': URL}], adapter.calls
                    bodies = [row['body'] for row in r.telemetry._iter_records()]
                    obs = next(b for b in bodies if b.get('record_type') == 'SOURCE_OBSERVATION')
                    assert obs['request_url'] == obs['response_url'] == URL and obs['method'] == 'GET'
                    assert obs['http_status'] == code
                    assert obs['headers'] == {'X-Offline-Evidence': 'first-response', 'Location': location}
                    assert base64.b64decode(obs['body_base64']) == raw
                    assert obs['body_bytes'] == len(raw)
                    assert obs['body_sha256'] == hashlib.sha256(raw).hexdigest()
                    assert obs['body_complete'] is True
                    assert obs['completed_at_utc'] >= obs['started_at_utc']
                    assert obs['latency_ms'] >= 0
                    assert obs['parse_outcome'] == ('OBJECT' if raw == RAW else 'MALFORMED_JSON')
                    assert obs['parse_error'] == (None if raw == RAW else 'JSONDecodeError')
                    assert obs['error_type'] == 'RedirectBlocked'
                    assert r.telemetry.status().chain_valid is True
                    assert r.public_state()['provider_evidence'] == {
                        'kalshi': 'INSUFFICIENT', 'coinbase': 'INSUFFICIENT'}
                    results.append({'location': location, 'http_status': code,
                        'parse_outcome': obs['parse_outcome'], 'source_requests': 1,
                        'redirect_hops': 0, 'complete_envelope_retained': True})
                    r.session.close()
    return {'cases': len(results), 'results': results}


def run():
    probes = [
        ('final directory fsync / telemetry / fresh processes', lambda: fresh_process_probe('telemetry')),
        ('final directory fsync / membership / fresh processes', lambda: fresh_process_probe('membership')),
        ('malformed Location', lambda: redirects_probe(['https://[broken', 'https://example.org/\xff'])),
        ('Kalshi Location', lambda: redirects_probe(['https://external-api.kalshi.com/trade-api/v2/markets'])),
        ('Coinbase Location', lambda: redirects_probe(['https://api.exchange.coinbase.com/products/BTC-USD/ticker'])),
        ('HTTP Location', lambda: redirects_probe(['http://v2-offline.up.railway.app/state'])),
        ('non-Railway Location', lambda: redirects_probe(['https://example.org/state'])),
        ('alternate Railway Location', lambda: redirects_probe(['https://other.up.railway.app/state'])),
        ('other blocked destinations', lambda: redirects_probe([
            'https://www.cfbenchmarks.com/data/indices/BRTI',
            'https://v2-offline.up.railway.app:444/state',
            'https://@v2-offline.up.railway.app/state',
            'https://user@v2-offline.up.railway.app/state', URL + '#fragment',
            URL + '\r\ninvalid', 'https://v2-offline.up.railway.app\\@example.org/state'])),
    ]
    results = []
    for name, probe in probes:
        try:
            detail = probe()
            results.append({'probe': name, 'result': 'PASS', 'detail': detail})
        except Exception as exc:
            results.append({'probe': name, 'result': 'FAIL', 'error': type(exc).__name__ + ': ' + str(exc)})
    report = {'passed': sum(r['result'] == 'PASS' for r in results), 'total': len(results),
              'network': 'offline Requests adapter; health endpoints loopback only', 'results': results}
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] == report['total'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=('inject', 'reopen'))
    parser.add_argument('--root', type=Path)
    parser.add_argument('--ledger', choices=('telemetry', 'membership'))
    args = parser.parse_args()
    with patch.dict(os.environ, {}, clear=True), patch.object(
            requests.adapters.HTTPAdapter, 'send', side_effect=AssertionError('real source network forbidden')):
        if args.stage:
            print(json.dumps(durability_stage(args.root, args.stage, args.ledger)))
        else:
            raise SystemExit(run())
