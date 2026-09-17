"""Offline adversarial regressions for all remediation reproductions."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import requests
from integrity_sentinel.control_attestation_v1 import (
    REQUIRED_IDENTITY_FIELDS, compare_manifest, load_manifest)
from integrity_sentinel.recorder_core_v1 import AppendOnlyHashChainLedger, membership_events
from integrity_sentinel.runtime_v1 import RecorderRuntime, SourceConfig, Handler, validate_source_url
from integrity_sentinel.source_adapters_v1 import adapt_source, adapt_brti_shared

CID = 'KXBTC15M-26SEP171200-00'
OTHER = 'KXBTC15M-26SEP171215-00'
URL = 'https://test.up.railway.app/state'
SOURCES = [SourceConfig('production_main', URL, 'telemetry'),
           SourceConfig('scalp_combined', URL + '?scalp', 'telemetry'),
           SourceConfig('combined_membership', URL + '?membership', 'membership')]


def controls(sources=SOURCES):
    expected = {'sources': {s.name: dict(zip(REQUIRED_IDENTITY_FIELDS,
        ['svc-' + s.name, 'dep', 'branch', 'abc', 'python app.py', 'source',
         {'not_applicable': True, 'reason': 'no cutoff for fixture'}])) for s in sources}}
    actual = copy.deepcopy(expected)
    actual['captured_at_utc'] = '2026-01-01T00:00:00Z'
    return expected, actual


def response(url, payload=None, *, raw=None, status=200, headers=None):
    r = requests.Response()
    r.status_code = status
    r.url = url
    r._content = raw if raw is not None else json.dumps(payload).encode()
    r._content_consumed = True
    r.headers.update(headers or {'X-Test': 'provenance'})
    return r


class RuntimeHardeningTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        expected, actual = controls()
        self.runtime = RecorderRuntime(self.temp.name, SOURCES,
            expected_manifest=expected, actual_snapshot=actual)
        self.runtime._thread = threading.current_thread()
        self.payloads = {s.url: {'ok': True, 'contract_id': CID} for s in SOURCES}
        self.payloads[SOURCES[-1].url] = {'ok': True, 'scorecard': {'contract_rows': []}}
        self.runtime.session.get = Mock(side_effect=lambda url, **kw: response(url, self.payloads[url]))

    def healthy(self):
        self.runtime.run_cycle()
        self.assertTrue(self.runtime.public_state()['ok'], self.runtime.public_state()['health_failures'])

    def endpoint(self, path):
        handler = object.__new__(Handler)
        handler.runtime = self.runtime
        handler.path = path
        handler._json = lambda code, obj: (code, obj)
        return handler.do_GET()

    def unhealthy(self):
        code, body = self.endpoint('/health')
        self.assertEqual(code, 503)
        self.assertIs(body['ok'], False)
        code, body = self.endpoint('/state')
        self.assertEqual(code, 200)
        self.assertIs(body['ok'], False)

    def redirect(self, target):
        self.runtime.session.get = Mock(return_value=response(URL, {}, status=302,
            headers={'Location': target}))
        _, obs = self.runtime.fetch(SOURCES[0])
        self.assertEqual(obs['error_type'], 'RedirectBlocked')
        self.assertEqual(obs['http_status'], 302)
        self.runtime.session.get.assert_called_once()
        self.assertIs(self.runtime.session.get.call_args.kwargs['allow_redirects'], False)
        self.assertEqual(obs['headers']['Location'], target)

    def test_01_redirect_kalshi(self):
        self.redirect('https://external-api.kalshi.com/trade-api/v2/markets')

    def test_02_redirect_coinbase(self):
        self.redirect('https://api.exchange.coinbase.com/products/BTC-USD/ticker')

    def test_03_redirect_http_and_other_hosts(self):
        for target in ('http://test.up.railway.app/state', 'https://example.org/',
                       'https://another.up.railway.app/state', 'https://@test.up.railway.app/'):
            with self.subTest(target=target):
                self.redirect(target)

    def test_04_required_telemetry_unavailable(self):
        self.healthy()
        original = self.runtime.session.get.side_effect
        self.runtime.session.get.side_effect = lambda url, **kw: (
            response(url, {'error': 'offline'}, status=503) if url == URL else original(url, **kw))
        self.runtime.run_cycle()
        self.unhealthy()
        self.assertFalse(self.runtime.state['source_status']['production_main']['ok'])

    def test_partial_transfer_preserves_known_status_and_received_bytes(self):
        reply = response(URL, raw=b'')
        def chunks(**kwargs):
            yield b'{"partial":'
            raise requests.exceptions.ChunkedEncodingError('interrupted')
        reply.iter_content = chunks
        self.runtime.session.get = Mock(return_value=reply)
        _, obs = self.runtime.fetch(SOURCES[0])
        self.assertEqual(obs['http_status'], 200)
        self.assertEqual(base64.b64decode(obs['body_base64']), b'{"partial":')
        self.assertIs(obs['body_complete'], False)
        self.assertEqual(obs['error_type'], 'ChunkedEncodingError')

    def test_explicit_provider_age_and_source_timestamp_stale(self):
        for bad in ({'kalshi_age_sec': 999}, {'coinbase_age_sec': 999},
                    {'updated_utc': '2026-01-01T00:00:00Z'},
                    {'coinbase_success_timestamp_utc': 'bad-date'}):
            self.payloads[URL] = {'contract_id': CID, **bad}
            self.runtime.run_cycle()
            self.unhealthy()

    def test_recorder_loop_death_overrides_previous_success(self):
        from integrity_sentinel.runtime_v1 import _loop
        self.healthy()
        # Stop the infinite loop in its sleep, after it has recorded a cycle.
        def stop(_):
            raise SystemExit()
        with patch('integrity_sentinel.runtime_v1.time.sleep', side_effect=stop):
            worker = threading.Thread(target=_loop, args=(self.runtime,))
            worker.start()
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
        self.unhealthy()

    def test_05_explicit_http_200_failure_or_stale(self):
        for bad in ({'ok': False}, {'stale': True}, {'status': 'STALE'},
                    {'source_age_sec': 10000}, {'source_fresh': False},
                    {'live': {'ok': False}}):
            with self.subTest(bad=bad):
                self.payloads[URL] = {'contract_id': CID, **bad}
                self.runtime.run_cycle()
                self.unhealthy()

    def test_06_ledger_write_exception_health_and_recovery(self):
        self.healthy()
        with patch.object(self.runtime.telemetry, 'append', side_effect=OSError('write failed')):
            self.runtime.run_cycle()
        self.unhealthy()
        rec = self.runtime.state['recorder']
        self.assertEqual(rec['last_exception_type'], 'OSError')
        self.assertEqual(rec['failure_count'], 1)
        self.assertTrue(rec['last_failure_utc'])
        self.runtime.run_cycle()
        self.assertTrue(self.runtime.public_state()['ok'])
        self.assertEqual(rec['failure_count'], 1)

    def test_07_recorder_thread_dead_or_stale(self):
        self.healthy()
        self.runtime._thread = threading.Thread()
        self.unhealthy()
        self.runtime._thread = threading.current_thread()
        self.runtime._last_success_mono = time.monotonic() - 1000
        self.unhealthy()

    def test_12_blank_expectations_never_pass(self):
        expected, actual = controls()
        for bad in ({}, {'sources': {}}, {'sources': None}):
            self.assertIsNot(compare_manifest(bad, actual)['control_plane_pass'], True)
        for field in REQUIRED_IDENTITY_FIELDS:
            for blank in (None, '', '   ', False, 0, {}, []):
                bad = copy.deepcopy(expected)
                bad['sources']['production_main'][field] = blank
                with self.subTest(field=field, blank=blank):
                    self.assertIsNot(compare_manifest(bad, actual)['control_plane_pass'], True)
                    p = Path(self.temp.name) / 'manifest.json'
                    p.write_text(json.dumps(bad))
                    with self.assertRaises(ValueError):
                        load_manifest(p)

    def test_13_actual_snapshot_missing_or_uncaptured(self):
        expected, _ = controls()
        for actual in (None, {}, expected):
            with tempfile.TemporaryDirectory() as td:
                r = RecorderRuntime(td, SOURCES, expected_manifest=expected, actual_snapshot=actual)
                self.assertIsNot(r.state['control_attestation']['control_plane_pass'], True)
                self.assertFalse(r.public_state()['ok'])

    def test_14_control_mismatch(self):
        expected, actual = controls()
        actual['sources']['production_main']['deployment_id'] = 'different'
        with tempfile.TemporaryDirectory() as td:
            r = RecorderRuntime(td, SOURCES, expected_manifest=expected, actual_snapshot=actual)
            self.assertIs(r.state['control_attestation']['control_plane_pass'], False)
            self.assertFalse(r.public_state()['ok'])

    def assert_body_retained(self, raw, status, outcome):
        self.runtime.session.get = Mock(return_value=response(URL, raw=raw, status=status))
        self.runtime.telemetry_cycle()
        rows = [r['body'] for r in self.runtime.telemetry._iter_records()
                if r['body'].get('record_type') == 'SOURCE_OBSERVATION']
        obs = rows[0]
        self.assertEqual(base64.b64decode(obs['body_base64']), raw)
        self.assertEqual(obs['body_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(obs['body_bytes'], len(raw))
        self.assertEqual(obs['http_status'], status)
        self.assertEqual(obs['parse_outcome'], outcome)
        for key in ('headers', 'started_at_utc', 'completed_at_utc', 'latency_ms', 'source', 'request_url'):
            self.assertIsNotNone(obs[key])

    def test_17_http_error_body_retention(self):
        self.assert_body_retained(b'{"error":"rate limited"}', 429, 'OBJECT')

    def test_18_malformed_json_retains_http_status(self):
        self.assert_body_retained(b'broken\xffjson', 200, 'MALFORMED_JSON')

    def test_19_wrong_type_json_retention(self):
        self.assert_body_retained(b'[1,2,3]', 200, 'WRONG_TYPE')

    def test_20_empty_membership_observation(self):
        self.runtime.membership_cycle()
        rows = list(self.runtime.membership._iter_records())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['body']['payload']['scorecard']['contract_rows'], [])
        self.assertTrue(rows[0]['body']['body_sha256'])
        self.assertEqual(self.runtime.seen_membership, set())

    def test_21_generic_age_not_kalshi(self):
        row = adapt_source('production_main', {'source_age_sec': 0, 'market_age_sec': 0})
        self.assertNotIn('kalshi_age_sec', row)
        self.assertEqual(row['kalshi_freshness_status'], 'UNKNOWN')

    def test_22_coinbase_missing_stays_unknown(self):
        self.healthy()
        self.assertEqual(self.runtime.public_state()['provider_evidence'],
                         {'kalshi': 'INSUFFICIENT', 'coinbase': 'INSUFFICIENT'})
        self.assertEqual(adapt_source('production_main', {})['coinbase_freshness_status'], 'UNKNOWN')

    def test_23_low_disk_blocks_all_writes(self):
        self.healthy()
        before = {p: p.read_bytes() for p in Path(self.temp.name).iterdir()}
        with patch('integrity_sentinel.runtime_v1.storage_status', return_value={'storage_ok': False, 'state': 'FAIL'}):
            for cycle in (self.runtime.telemetry_cycle, self.runtime.membership_cycle):
                with self.assertRaises(OSError):
                    cycle()
            with self.assertRaises(OSError):
                self.runtime.membership.append({'x': 1})
            self.unhealthy()
        self.assertEqual(before, {p: p.read_bytes() for p in Path(self.temp.name).iterdir()})

    def test_24_invalid_contract_types(self):
        for value in (True, False, 1, 1.5, {}, [], None, '', ' ', 'BTC', 'KXBTC15M-', ' KXBTC15M-TEST'):
            with self.subTest(value=value):
                self.payloads[URL] = {'contract_id': value}
                self.runtime.run_cycle()
                self.unhealthy()
                self.assertEqual(self.runtime.state['source_status']['production_main']['error_type'], 'ValidationError')

    def test_25_within_payload_conflicts(self):
        for bad in ({'contract': CID, 'contract_id': OTHER},
                    {'contract': CID, 'market': {'ticker': OTHER}}):
            self.payloads[URL] = bad
            self.runtime.run_cycle()
            self.unhealthy()

    def test_26_cross_source_disagreement(self):
        self.payloads[SOURCES[1].url]['contract_id'] = OTHER
        self.runtime.run_cycle()
        self.unhealthy()
        rows = list(self.runtime.telemetry._iter_records())
        body = rows[-1]['body']
        self.assertEqual(body['record_type'], 'CONTRACT_AGREEMENT')
        self.assertIs(body['agreement'], False)
        self.assertEqual(set(body['contracts'].values()), {CID, OTHER})

    def test_27_invalid_brti_counters(self):
        for field in ('sequence', 'upstream_attempts', 'upstream_ok', 'upstream_errors', 'http_429',
                      'timeout_errors', 'http_errors', 'connection_errors', 'other_errors', 'consecutive_errors'):
            for bad in (True, False, -1, 1.2, '1', 'bad', None, [], {}, float('nan'), float('inf')):
                with self.subTest(field=field, bad=bad):
                    with self.assertRaises(ValueError):
                        adapt_brti_shared({field: bad})
        self.assertEqual(adapt_brti_shared({'sequence': 0})['brti_seq'], 0)

    def test_28_empty_userinfo(self):
        for syntax in ('@', ':@', 'user@', ':password@', 'user:@'):
            with self.subTest(syntax=syntax), self.assertRaises(ValueError):
                validate_source_url('https://' + syntax + 'test.up.railway.app/state')

    def test_membership_failure_makes_health_fail(self):
        self.healthy()
        self.payloads[SOURCES[-1].url] = {'ok': False}
        self.runtime.run_cycle()
        self.unhealthy()

    def test_source_observation_stale(self):
        self.healthy()
        self.runtime._source_mono['combined_membership'] -= 1000
        self.unhealthy()

    def test_disk_inspection_error(self):
        self.healthy()
        with patch('integrity_sentinel.runtime_v1.storage_status', side_effect=OSError('disk query failed')):
            self.unhealthy()
        self.unhealthy()  # sticky until a successful recording cycle
        self.runtime.run_cycle()
        self.assertTrue(self.runtime.public_state()['ok'])

    def test_unexpected_loop_exception_and_serialization(self):
        self.healthy()
        with patch.object(self.runtime, 'telemetry_cycle', side_effect=RuntimeError('unexpected')):
            self.runtime.run_cycle()
        self.unhealthy()
        self.assertEqual(self.runtime.state['recorder']['last_exception_type'], 'RuntimeError')
        with patch.object(self.runtime.telemetry, 'append', side_effect=ValueError('serialization')):
            self.runtime.run_cycle()
        self.unhealthy()

    def test_nonfinite_json_preserved(self):
        self.assert_body_retained(b'{"counter":NaN}', 200, 'MALFORMED_JSON')

    def test_config_bypass_revalidated_before_get(self):
        unsafe = SourceConfig('x', 'https://api.coinbase.com/', 'telemetry')
        _, obs = self.runtime.fetch(unsafe)
        self.runtime.session.get.assert_not_called()
        self.assertEqual(obs['error_type'], 'ValueError')

    def test_membership_event_provenance_and_dedup(self):
        self.payloads[SOURCES[-1].url] = {'scorecard': {'contract_rows': [{'contract': CID}]}}
        self.runtime.membership_cycle()
        self.runtime.membership_cycle()
        rows = list(self.runtime.membership._iter_records())
        self.assertEqual(len(rows), 3)  # two observations, one unique event
        self.assertEqual(rows[1]['body']['observation_record_hash'], rows[0]['record_hash'])
        self.assertEqual(rows[1]['body']['observation_id'], rows[0]['body']['observation_id'])


class LedgerHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'ledger.jsonl'
        self.ledger = AppendOnlyHashChainLedger(self.path)
        self.ledger.append({'n': 1})
        self.ledger.append({'n': 2})

    def rejected(self):
        self.assertFalse(self.ledger.status().chain_valid)
        with self.assertRaises((ValueError, OSError)):
            self.ledger.append({'n': 3})
        with self.assertRaises((ValueError, OSError)):
            AppendOnlyHashChainLedger(self.path)

    def test_08_short_os_write_does_not_advance(self):
        real_write = os.write
        def short(fd, data):
            if os.readlink('/proc/self/fd/' + str(fd)) == str(self.path):
                return real_write(fd, data[:7])
            return real_write(fd, data)
        with patch('integrity_sentinel.recorder_core_v1.os.write', side_effect=short):
            with self.assertRaises(OSError):
                self.ledger.append({'n': 3})
        self.assertEqual(self.ledger._sequence, 2)
        self.rejected()

    def test_09_missing_newline(self):
        self.path.write_bytes(self.path.read_bytes()[:-1])
        self.rejected()

    def test_10_complete_trailing_row_deleted(self):
        self.path.write_bytes(self.path.read_bytes().splitlines(keepends=True)[0])
        self.rejected()

    def test_11_full_truncation(self):
        self.path.write_bytes(b'')
        self.rejected()

    def test_missing_ledger_or_anchor(self):
        self.ledger.anchor_path.unlink()
        self.rejected()

    def test_ledger_removed_with_anchor_retained(self):
        self.path.unlink()
        self.rejected()

    def test_short_checkpoint_write(self):
        with patch('integrity_sentinel.recorder_core_v1.os.write', return_value=0):
            with self.assertRaises(OSError):
                self.ledger.append({'n': 3})
        self.assertEqual(self.ledger._sequence, 2)
        self.rejected()

    def test_ledger_fsync_failure_status_cannot_adopt_uncommitted_row(self):
        original = os.fsync
        def fail_ledger(fd):
            if os.readlink('/proc/self/fd/' + str(fd)) == str(self.path):
                raise OSError('ledger fsync failed')
            original(fd)
        with patch('integrity_sentinel.recorder_core_v1.os.fsync', side_effect=fail_ledger):
            with self.assertRaises(OSError):
                self.ledger.append({'n': 3})
        self.assertEqual(self.ledger._sequence, 2)
        self.assertFalse(self.ledger.status().chain_valid)
        self.assertEqual(self.ledger._sequence, 2)
        with self.assertRaises(ValueError):
            AppendOnlyHashChainLedger(self.path)

    def test_fsync_failure_does_not_advance(self):
        with patch('integrity_sentinel.recorder_core_v1.os.fsync', side_effect=OSError('fsync')):
            with self.assertRaises(OSError):
                self.ledger.append({'n': 3})
        self.assertEqual(self.ledger._sequence, 2)
        self.rejected()


class MembershipHardeningTests(unittest.TestCase):
    def test_15_combined_real_shape(self):
        payload = {'scorecard': {'contract_rows': [{'contract': CID, 'early_side': 'UP', 'final_side': 'UP'}]}}
        rows = membership_events('combined_membership', payload)
        self.assertEqual(rows[0]['contract_id'], CID)
        self.assertEqual(rows[0]['container'], 'scorecard.contract_rows')
        self.assertEqual(rows[0]['record'], payload['scorecard']['contract_rows'][0])

    def test_16_nextgen_real_shape_and_records_wrapper(self):
        for records in ([{'contract': CID}], {'records': [{'contract': CID}]}):
            payload = {'audit_records': {'candidate_verify_v2': {'V1_IMMEDIATE': records}}}
            rows = membership_events('nextgen_membership', payload)
            self.assertEqual(rows[0]['contract_id'], CID)
            self.assertIn('candidate_verify_v2/V1_IMMEDIATE', rows[0]['container'])

    def test_missing_membership_schema_is_not_empty_success(self):
        for payload in ({}, {'scorecard': {}}, {'scorecard': {'contract_rows': None}}):
            with self.assertRaises(ValueError):
                membership_events('combined_membership', payload)

    def test_membership_id_key_conflict(self):
        with self.assertRaises(ValueError):
            membership_events('final_membership', {'lock_records': {CID: {'contract': OTHER}}})

    def test_membership_wrong_type_and_missing_id(self):
        for row in ({'contract': False}, {}, 'bad'):
            with self.assertRaises(ValueError):
                membership_events('combined_membership', {'scorecard': {'contract_rows': [row]}})


if __name__ == '__main__':
    unittest.main()
