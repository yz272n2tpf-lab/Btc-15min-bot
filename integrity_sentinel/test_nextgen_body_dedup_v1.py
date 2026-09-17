"""Offline unit/regression tests; faults touch disposable synthetic data only."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import requests
from integrity_sentinel.nextgen_body_store_v1 import NextgenBodyStore, NextgenMembershipLedger
from integrity_sentinel.recorder_core_v1 import AppendOnlyHashChainLedger
from integrity_sentinel.runtime_v1 import RecorderRuntime, SourceConfig

CID = 'KXBTC15M-26SEP171200-00'
URL = 'https://unit-offline.up.railway.app/audit'
BODY = ('{"ok":true,"audit_records":{"watch":{"lane":[{"contract_id":"' + CID + '","side":"UP"}]}}}').encode()
SOURCES = [SourceConfig('production_main', URL + '?main', 'telemetry'),
           SourceConfig('nextgen_membership', URL, 'membership')]


def make_runtime(root):
    expected = {'sources': {s.name: {'service_id': 'fixture', 'deployment_id': 'fixture',
        'branch': 'offline', 'commit_sha': 'a' * 40, 'start_command': 'python offline.py',
        'role': 'observer', 'cutoff_utc': {'not_applicable': True, 'reason': 'synthetic'}} for s in SOURCES}}
    actual = json.loads(json.dumps(expected))
    actual['captured_at_utc'] = '2026-01-01T00:00:00Z'
    r = RecorderRuntime(root, SOURCES, expected_manifest=expected, actual_snapshot=actual)
    r._thread = threading.current_thread()
    r.session.get = Mock(side_effect=lambda url, **kw: reply(url, BODY if url == URL else
                        json.dumps({'ok': True, 'contract_id': CID}).encode()))
    return r


def reply(url, raw, status=200, partial=False):
    r = requests.Response()
    r.url, r.status_code = url, status
    r._content, r._content_consumed = raw, True
    r.headers['X-Fixture'] = str(status)
    if partial:
        def chunks(**kw):
            yield raw
            raise requests.exceptions.ChunkedEncodingError('synthetic interruption')
        r.iter_content = chunks
    return r


class BodyDedupTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        network = patch.object(requests.adapters.HTTPAdapter, 'send', side_effect=AssertionError('network forbidden'))
        network.start()
        self.addCleanup(network.stop)
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        self.r = make_runtime(self.root)
        self.addCleanup(self.r.session.close)

    def observations(self):
        return [row for row in self.r.membership._iter_records() if row['body']['record_type'] == 'SOURCE_OBSERVATION']

    def healthy(self):
        self.r.run_cycle()
        self.assertTrue(self.r.public_state()['ok'], self.r.public_state()['health_failures'])

    def broken_on_reopen(self):
        self.assertFalse(self.r.public_state()['ok'])
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        fresh = make_runtime(self.root)
        self.addCleanup(fresh.session.close)
        fresh.run_cycle()
        self.assertFalse(fresh.public_state()['ok'])
        self.assertFalse(fresh.membership.status().chain_valid)
        fresh.session.get.assert_not_called()
        self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_identical_envelopes_unique_body_and_exact_provenance(self):
        self.healthy()
        self.healthy()
        rows = self.observations()
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['body']['observation_id'], rows[1]['body']['observation_id'])
        self.assertEqual(len(list(self.r.nextgen_bodies.root.glob('*.body'))), 1)
        for row in rows:
            obs = row['body']
            self.assertEqual(self.r.nextgen_bodies.resolve(obs), BODY)
            self.assertIsNone(obs['payload'])
            self.assertIsNone(obs['body_base64'])
            for key in ('headers', 'request_url', 'response_url', 'latency_ms', 'body_complete',
                        'started_at_utc', 'completed_at_utc', 'http_status', 'parse_outcome', 'source_failures'):
                self.assertIn(key, obs)
        events = [row['body'] for row in self.r.membership._iter_records() if row['body']['record_type'] == 'STRATEGY_MEMBERSHIP']
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['observation_record_hash'], rows[0]['record_hash'])
        self.assertEqual(events[0]['observation_body_sha256'], hashlib.sha256(BODY).hexdigest())
        self.assertEqual(events[0]['observation_id'], rows[0]['body']['observation_id'])

    def test_changed_body_creates_object_and_correct_new_event(self):
        self.healthy()
        changed = BODY.replace(b'UP', b'DN')
        self.r.session.get.side_effect = lambda url, **kw: reply(url, changed)
        self.r.membership_cycle()
        self.assertEqual(len(list(self.r.nextgen_bodies.root.glob('*.body'))), 2)
        events = [x['body'] for x in self.r.membership._iter_records() if x['body']['record_type'] == 'STRATEGY_MEMBERSHIP']
        self.assertEqual(events[-1]['observation_body_sha256'], hashlib.sha256(changed).hexdigest())
        self.assertEqual(events[-1]['record']['side'], 'DN')

    def test_one_byte_whitespace_change_is_new_object(self):
        self.healthy()
        self.r.session.get.side_effect = lambda url, **kw: reply(url, BODY + b' ')
        self.r.membership_cycle()
        self.assertEqual(len(list(self.r.nextgen_bodies.root.glob('*.body'))), 2)

    def test_error_partial_malformed_never_reuse_even_identical_good_bytes(self):
        self.healthy()
        for raw, status, partial in ((BODY, 503, False), (b'{bad', 200, False),
                                     (BODY, 200, True), (b'[1]', 200, False), (b'', 204, False)):
            with self.subTest(status=status, partial=partial, raw=raw):
                self.r.session.get.side_effect = lambda url, **kw: reply(url, raw, status, partial)
                self.r.membership_cycle()
                obs = self.observations()[-1]['body']
                self.assertNotIn('body_ref', obs)
                self.assertEqual(base64.b64decode(obs['body_base64']), raw)
                self.assertEqual(obs['body_sha256'], hashlib.sha256(raw).hexdigest())
                self.assertFalse(self.r.public_state()['ok'])
                self.assertEqual(len(list(self.r.nextgen_bodies.root.glob('*.body'))), 1)

    def test_missing_body(self):
        self.healthy()
        next(self.r.nextgen_bodies.root.glob('*.body')).unlink()
        self.broken_on_reopen()

    def test_modified_body(self):
        self.healthy()
        p = next(self.r.nextgen_bodies.root.glob('*.body'))
        p.chmod(0o600)
        p.write_bytes(BODY.replace(b'UP', b'DN'))
        self.broken_on_reopen()

    def test_truncated_body(self):
        self.healthy()
        p = next(self.r.nextgen_bodies.root.glob('*.body'))
        p.chmod(0o600)
        p.write_bytes(BODY[:-1])
        self.broken_on_reopen()

    def test_symlink_body(self):
        self.healthy()
        p = next(self.r.nextgen_bodies.root.glob('*.body'))
        other = self.root / 'same-bytes'
        other.write_bytes(BODY)
        p.unlink()
        p.symlink_to(other)
        self.broken_on_reopen()

    def test_restart_validates_and_reuses(self):
        self.healthy()
        p = next(self.r.nextgen_bodies.root.glob('*.body'))
        before = p.stat()
        self.r = make_runtime(self.root)
        self.addCleanup(self.r.session.close)
        self.healthy()
        self.assertEqual((before.st_ino, before.st_mtime_ns), (p.stat().st_ino, p.stat().st_mtime_ns))
        self.assertEqual(len(self.observations()), 2)

    def test_catalog_missing(self):
        self.healthy()
        self.r.nextgen_bodies.catalog_path.unlink()
        self.broken_on_reopen()

    def test_orphan_unknown_object(self):
        self.healthy()
        (self.r.nextgen_bodies.root / ('0' * 64 + '.body')).write_bytes(b'unknown')
        self.broken_on_reopen()

    def test_forged_ledger_reference_fails_even_valid_chain(self):
        self.healthy()
        obs = dict(self.observations()[0]['body'])
        obs['body_sha256'] = '0' * 64
        # Deliberately use the old generic ledger to construct a valid-chain
        # mismatch. The body-aware ledger must independently reject it.
        AppendOnlyHashChainLedger(self.r.membership.path).append(obs)
        self.broken_on_reopen()

    def test_missing_reference_marker_fails_even_valid_chain(self):
        self.healthy()
        obs = dict(self.observations()[0]['body'])
        del obs['body_ref']
        AppendOnlyHashChainLedger(self.r.membership.path).append(obs)
        self.broken_on_reopen()

    def test_false_membership_link_fails(self):
        self.healthy()
        event = dict(list(self.r.membership._iter_records())[1]['body'])
        event['observation_body_sha256'] = 'f' * 64
        AppendOnlyHashChainLedger(self.r.membership.path).append(event)
        self.broken_on_reopen()

    def test_body_write_failure_leaves_durable_intent(self):
        real_write = os.write
        def fail(fd, raw):
            if os.readlink('/proc/self/fd/' + str(fd)).endswith('.body'):
                return real_write(fd, raw[:-1])
            return real_write(fd, raw)
        with patch('os.write', side_effect=fail):
            self.r.run_cycle()
        self.assertTrue(self.r.nextgen_bodies.pending.exists())
        self.assertEqual(self.observations(), [])
        self.broken_on_reopen()

    def test_reference_write_failure_retains_object_and_blocks_reopen(self):
        real_write = os.write
        def fail(fd, raw):
            if os.readlink('/proc/self/fd/' + str(fd)) == str(self.r.membership.path):
                return real_write(fd, raw[:-1])
            return real_write(fd, raw)
        with patch('os.write', side_effect=fail):
            self.r.run_cycle()
        self.assertEqual(len(list(self.r.nextgen_bodies.root.glob('*.body'))), 1)
        self.broken_on_reopen()

    def test_concurrent_same_body_across_store_instances(self):
        stores = [NextgenBodyStore(self.root) for _ in range(12)]
        with ThreadPoolExecutor(max_workers=12) as pool:
            refs = list(pool.map(lambda s: s.put(BODY), stores))
        self.assertEqual(len({json.dumps(r, sort_keys=True) for r in refs}), 1)
        self.assertEqual(len(list(self.r.nextgen_bodies.root.glob('*.body'))), 1)
        self.assertEqual(len(list(AppendOnlyHashChainLedger(self.r.nextgen_bodies.catalog_path)._iter_records())), 1)

    def test_concurrent_observations_remain_distinct(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: self.r.membership_cycle(), range(16)))
        self.assertEqual(len(self.observations()), 16)
        self.assertEqual(len({x['body']['observation_id'] for x in self.observations()}), 16)
        self.assertTrue(self.r.membership.status().chain_valid)
        self.assertEqual(len(list(self.r.nextgen_bodies.root.glob('*.body'))), 1)

    def test_scope_and_cadence_unchanged(self):
        self.assertEqual((self.r.poll_sec, self.r.membership_poll_sec), (5., 10.))
        self.healthy()
        obs = next(r['body'] for r in self.r.telemetry._iter_records() if r['body']['record_type'] == 'SOURCE_OBSERVATION')
        self.assertNotIn('body_ref', obs)
        self.assertIsInstance(obs['payload'], dict)
        self.assertIsInstance(obs['body_base64'], str)

    def test_disk_guard_prevents_object_and_reference_writes(self):
        self.healthy()
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch('integrity_sentinel.runtime_v1.storage_status', return_value={'storage_ok': False}):
            self.r.run_cycle()
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_body_payload_mismatch_rejected(self):
        _, obs = self.r.fetch(SOURCES[-1])
        obs.update(source_failures=[], record_type='SOURCE_OBSERVATION')
        obs['payload']['ok'] = False
        with self.assertRaises(ValueError):
            self.r.nextgen_bodies.compact(obs)
        self.assertFalse(self.r.nextgen_bodies.root.exists())


if __name__ == '__main__':
    unittest.main()
