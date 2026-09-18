"""Independent offline batch probes: own fixtures, hash oracle and fault driver.

No unit-test helpers or producer modules are imported. All writes target fresh
synthetic temporary directories. Network transports outside the fixture fail.
"""
import copy
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import stat
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import requests
from integrity_sentinel.recorder_core_v1 import AppendOnlyHashChainLedger, MAX_BATCH_ROWS, MAX_BATCH_BYTES, BATCH_WRITE_BYTES
from integrity_sentinel.nextgen_body_store_v1 import NextgenBodyStore
from integrity_sentinel.membership_batch_v2 import BatchedMembershipLedger
from integrity_sentinel.runtime_v1 import RecorderRuntime, SourceConfig, Handler

CID = 'KXBTC15M-26SEP171200-00'
SOURCE = SourceConfig('nextgen_membership', 'https://batch-offline.up.railway.app/audit', 'membership')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def raw_rows(count=3072):
    return [{'record_type': 'SYNTHETIC_BATCH_TEST', 'n': n, 'payload': 'x' * 1050} for n in range(count)]


def oracle(bodies):
    previous, rows = '0' * 64, []
    for seq, body in enumerate(bodies, 1):
        digest = hashlib.sha256(previous.encode() + b'\0' + canonical({'sequence': seq, 'body': body})).hexdigest()
        rows.append({'sequence': seq, 'previous_hash': previous, 'record_hash': digest, 'body': body})
        previous = digest
    return b''.join(canonical(row) + b'\n' for row in rows)


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(root).rglob('*') if p.is_file()}


def synthetic_body(count=3072):
    records = [{'contract': CID, 'side': 'UP', 'opportunity_index': n, 'entry_ask': .45,
                'decision_reason': 'SYNTHETIC_BATCH_ONLY', 'padding': 'x' * 350} for n in range(count)]
    return json.dumps({'ok': True, 'orders': False, 'audit_records': {'offline_family': {'offline_lane': records}}}).encode()


class Transport(requests.adapters.BaseAdapter):
    def __init__(self, raw): self.raw, self.calls = raw, 0
    def send(self, request, **kwargs):
        assert request.method == 'GET' and request.url == SOURCE.url
        self.calls += 1
        response = requests.Response()
        response.request, response.url, response.status_code = request, request.url, 200
        response.raw = io.BytesIO(self.raw)
        return response
    def close(self): pass


def runtime(root, count=3072):
    expected = {'sources': {SOURCE.name: {'service_id': 'synthetic', 'deployment_id': 'synthetic',
        'branch': 'fixture', 'commit_sha': 'c' * 40, 'start_command': 'python offline.py',
        'role': 'observer', 'cutoff_utc': {'not_applicable': True, 'reason': 'offline synthetic'}}}}
    actual = copy.deepcopy(expected)
    actual['captured_at_utc'] = '2026-01-01T00:00:00Z'
    r = RecorderRuntime(root, [SOURCE], expected_manifest=expected, actual_snapshot=actual)
    r._thread = threading.current_thread()
    r.session.trust_env = False
    adapter = Transport(synthetic_body(count))
    r.session.mount('https://', adapter)
    return r, adapter


def fresh_child(root, kind, expected, pipe):
    try:
        before = snapshot(root)
        path = Path(root) / ('membership.jsonl' if kind == 'runtime' else 'ledger.jsonl')
        ledger = (BatchedMembershipLedger(path, NextgenBodyStore(root), allow_failed_open=True)
                  if kind == 'runtime' else AppendOnlyHashChainLedger(path, allow_failed_open=True))
        status = ledger.status()
        assert status.chain_valid is expected, status
        assert snapshot(root) == before
        if not expected:
            try: ledger.append({'forbidden': True})
            except (ValueError, OSError): pass
            else: raise AssertionError('failed ledger accepted append')
            assert snapshot(root) == before
        pipe.send({'ok': True, 'records': status.records, 'pid': os.getpid()})
    except BaseException as exc:
        pipe.send({'error': repr(exc)})
    finally: pipe.close()


def fresh(root, kind, expected):
    context = multiprocessing.get_context('spawn')
    reader, writer = context.Pipe(duplex=False)
    p = context.Process(target=fresh_child, args=(str(root), kind, expected, writer))
    p.start()
    writer.close()
    assert reader.poll(30), 'fresh verification timeout'
    result = reader.recv()
    p.join(10)
    assert p.exitcode == 0 and result.get('ok') and result['pid'] != os.getpid(), result
    reader.close()
    return result


def crash_child(root, stage):
    ledger = AppendOnlyHashChainLedger(Path(root) / 'ledger.jsonl')
    real_write, real_sync = os.write, os.fsync
    def write(fd, raw):
        if os.readlink('/proc/self/fd/' + str(fd)) == str(ledger.path):
            if stage == 'partial':
                real_write(fd, bytes(raw).split(b'\n')[0] + b'\n')
                os._exit(71)  # Complete-looking valid prefix; never adopt it.
        return real_write(fd, raw)
    def sync(fd):
        real_sync(fd)
        if stage == 'after_ledger_fsync' and os.readlink('/proc/self/fd/' + str(fd)) == str(ledger.path):
            os._exit(71)
    with patch('os.write', side_effect=write), patch('os.fsync', side_effect=sync):
        if stage == 'before_cleanup':
            ledger._finish_durability = lambda: os._exit(71)
        ledger.append_batch(raw_rows())
    os._exit(72)


def concurrent_child(root, n, ready, start):
    ledger = AppendOnlyHashChainLedger(Path(root) / 'ledger.jsonl')
    ready.put(n)
    start.wait(10)
    if n % 2:
        for i in range(10): ledger.append({'writer': n, 'n': i})
    else:
        ledger.append_batch([{'writer': n, 'n': i} for i in range(100)])


class BatchThroughputAdversarial(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.network = patch.object(requests.adapters.HTTPAdapter, 'send', side_effect=AssertionError('network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.tmp = tempfile.TemporaryDirectory(prefix='sentinel-batch-offline-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def ledger(self): return AppendOnlyHashChainLedger(self.root / 'ledger.jsonl')

    def assert_failed(self, ledger):
        self.assertFalse(ledger.status().chain_valid)
        before = snapshot(self.root)
        for _ in range(2): fresh(self.root, 'core', False)
        self.assertEqual(snapshot(self.root), before)

    def test_3072_rows_one_verification_one_ledger_lock_seven_fsyncs(self):
        ledger = self.ledger()
        bodies = raw_rows()
        real_verify, real_flock, real_sync = ledger._verify_locked, __import__('fcntl').flock, os.fsync
        with patch.object(ledger, '_verify_locked', wraps=real_verify) as verify, \
             patch('fcntl.flock', wraps=real_flock) as flock, patch('os.fsync', wraps=real_sync) as sync:
            rows = ledger.append_batch(bodies)
            self.assertEqual(verify.call_count, 1)
            self.assertEqual(flock.call_count, 1)
            self.assertEqual(sync.call_count, 7)
        self.assertEqual(len(rows), 3072)
        self.assertEqual(ledger.path.read_bytes(), oracle(bodies))
        self.assertTrue(ledger.status().chain_valid)
        self.assertEqual(fresh(self.root, 'core', True)['records'], 3072)

    def test_zero_batch_no_writes(self):
        ledger = self.ledger()
        before = snapshot(self.root)
        with patch('os.write', side_effect=AssertionError('empty batch wrote')), patch('os.fsync', side_effect=AssertionError('empty batch fsync')):
            self.assertEqual(ledger.append_batch([]), [])
        self.assertEqual(snapshot(self.root), before)

    def test_one_row_and_exact_single_append_equivalence(self):
        ledger = self.ledger()
        self.assertEqual(ledger.append_batch([{'n': 1}])[0], AppendOnlyHashChainLedger(self.root / 'single.jsonl').append({'n': 1}))
        self.assertEqual(ledger.path.read_bytes(), (self.root / 'single.jsonl').read_bytes())

    def test_final_chain_equals_3072_repeated_individual_appends(self):
        # Real fsyncs and verification on both paths; no cached hash shortcut.
        bodies = [{'n': n, 'unicode': 'BTC→'} for n in range(3072)]
        batch = self.ledger()
        singles = AppendOnlyHashChainLedger(self.root / 'single.jsonl')
        prefix = {'preexisting': True}
        batch.append(prefix)
        singles.append(prefix)
        batch.append_batch(bodies)
        for body in bodies: singles.append(body)
        self.assertEqual(batch.path.read_bytes(), singles.path.read_bytes())
        self.assertEqual(batch.anchor_path.read_bytes(), singles.anchor_path.read_bytes())
        self.assertEqual(batch.path.read_bytes(), oracle([prefix, *bodies]))

    def test_admission_row_and_byte_bounds_no_partial_mutation(self):
        ledger = self.ledger()
        before = snapshot(self.root)
        for bodies in ([{'n': n} for n in range(MAX_BATCH_ROWS + 1)], [{'x': 'x' * MAX_BATCH_BYTES}]):
            with self.assertRaises(ValueError): ledger.append_batch(bodies)
            self.assertEqual(snapshot(self.root), before)
        # Encoding overhead also counts toward the same cap.
        with patch('integrity_sentinel.recorder_core_v1.MAX_BATCH_BYTES', 100), self.assertRaises(ValueError):
            ledger.append_batch([{'n': 1}])
        self.assertEqual(snapshot(self.root), before)

    def test_short_writes_beginning_middle_end(self):
        bodies = raw_rows()
        total = len(oracle(bodies))
        for target in (0, total // 2, total - 1):
            with self.subTest(byte_offset=target), tempfile.TemporaryDirectory() as td:
                ledger = AppendOnlyHashChainLedger(Path(td) / 'ledger.jsonl')
                real, written, hits = os.write, [0], []
                def short(fd, raw):
                    if os.readlink('/proc/self/fd/' + str(fd)) == str(ledger.path):
                        if written[0] <= target < written[0] + len(raw):
                            hits.append(target)
                            n = real(fd, raw[:target - written[0]])
                            written[0] += n
                            return n
                        written[0] += len(raw)
                    return real(fd, raw)
                with patch('os.write', side_effect=short), self.assertRaises(OSError): ledger.append_batch(bodies)
                self.assertEqual(hits, [target])
                self.assertEqual(ledger.path.stat().st_size, target)
                self.assertTrue(ledger.durability_path.exists())
                fresh(td, 'core', False)

    def test_partial_batch_crash_and_interrupted_ack_reopen(self):
        for stage in ('partial', 'after_ledger_fsync', 'before_cleanup'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as td:
                ledger = AppendOnlyHashChainLedger(Path(td) / 'ledger.jsonl')
                ctx = multiprocessing.get_context('spawn')
                p = ctx.Process(target=crash_child, args=(td, stage))
                p.start()
                p.join(30)
                self.assertEqual(p.exitcode, 71)
                self.assertTrue(ledger.durability_path.exists())
                if stage == 'partial': self.assertEqual(len(ledger.path.read_bytes().splitlines()), 1)
                for _ in range(2): fresh(td, 'core', False)

    def test_every_batch_fsync_boundary(self):
        for fail_at in range(1, 8):
            with self.subTest(fsync=fail_at), tempfile.TemporaryDirectory() as td:
                ledger = AppendOnlyHashChainLedger(Path(td) / 'ledger.jsonl')
                real, count = os.fsync, [0]
                def fault(fd):
                    count[0] += 1
                    if count[0] == fail_at: raise OSError('synthetic fsync failure')
                    return real(fd)
                with patch('os.fsync', side_effect=fault), self.assertRaises(OSError): ledger.append_batch(raw_rows())
                self.assertEqual(count[0], fail_at)
                self.assertTrue(ledger.durability_path.exists())
                fresh(td, 'core', False)

    def test_pending_and_committed_anchor_short_write(self):
        for committed in (False, True):
            with self.subTest(committed=committed), tempfile.TemporaryDirectory() as td:
                ledger = AppendOnlyHashChainLedger(Path(td) / 'ledger.jsonl')
                real, hits = os.write, []
                def fault(fd, raw):
                    path = os.readlink('/proc/self/fd/' + str(fd))
                    if path.endswith('.anchor.json.pending') and json.loads(bytes(raw))['committed'] is committed:
                        hits.append(True)
                        return real(fd, raw[:-1])
                    return real(fd, raw)
                with patch('os.write', side_effect=fault), self.assertRaises(OSError): ledger.append_batch(raw_rows())
                self.assertEqual(hits, [True])
                fresh(td, 'core', False)

    def test_anchor_replace_and_marker_cleanup_failure(self):
        for mode in ('pending_replace', 'committed_replace', 'cleanup'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                ledger = AppendOnlyHashChainLedger(Path(td) / 'ledger.jsonl')
                real, count = os.replace, [0]
                def replace(src, dst):
                    count[0] += 1
                    if count[0] == (1 if mode == 'pending_replace' else 2): raise OSError('replace failed')
                    return real(src, dst)
                injection = patch.object(ledger, '_finish_durability', side_effect=OSError('cleanup failed')) if mode == 'cleanup' else patch('os.replace', side_effect=replace)
                with injection, self.assertRaises(OSError): ledger.append_batch(raw_rows())
                fresh(td, 'core', False)

    def test_storage_exhaustion_during_chunk_write(self):
        ledger = self.ledger()
        real, hits = os.write, []
        def fault(fd, raw):
            if os.readlink('/proc/self/fd/' + str(fd)) == str(ledger.path):
                hits.append(True)
                if len(hits) == 2: raise OSError(28, 'synthetic ENOSPC')
            return real(fd, raw)
        with patch('os.write', side_effect=fault), self.assertRaises(OSError): ledger.append_batch(raw_rows())
        self.assertEqual(ledger.path.stat().st_size, BATCH_WRITE_BYTES)
        self.assert_failed(ledger)

    def test_low_disk_before_batch_leaves_only_acknowledged_prefix(self):
        ledger = self.ledger()
        before = snapshot(self.root)
        with patch.object(ledger, '_write_guard', side_effect=OSError('low disk')), self.assertRaises(OSError):
            ledger.append_batch(raw_rows())
        self.assertEqual(snapshot(self.root), before)
        # No durable intent or mutation existed. Runtime uses the envelope
        # obligation to additionally protect this pre-intent failure below.
        self.assertFalse(ledger.status().chain_valid)
        self.assertEqual(fresh(self.root, 'core', True)['records'], 0)

    def test_low_disk_during_batch(self):
        ledger = self.ledger()
        def guard():
            if ledger.path.stat().st_size > 0: raise OSError('low disk after first chunk')
        with patch.object(ledger, '_write_guard', side_effect=guard), self.assertRaises(OSError): ledger.append_batch(raw_rows())
        self.assertEqual(ledger.path.stat().st_size, BATCH_WRITE_BYTES)
        self.assert_failed(ledger)

    def test_concurrent_batch_and_single_appends_across_processes(self):
        ledger = self.ledger()
        ctx = multiprocessing.get_context('spawn')
        ready, start = ctx.Queue(), ctx.Event()
        workers = [ctx.Process(target=concurrent_child, args=(str(self.root), n, ready, start)) for n in range(4)]
        for p in workers: p.start()
        self.assertEqual({ready.get(timeout=15) for _ in workers}, set(range(4)))
        start.set()
        for p in workers:
            p.join(30)
            self.assertEqual(p.exitcode, 0)
        rows = [json.loads(line) for line in ledger.path.read_bytes().splitlines()]
        self.assertEqual(len(rows), 220)
        self.assertEqual(ledger.path.read_bytes(), oracle([r['body'] for r in rows]))
        for writer in (0, 2):
            indexes = [i for i, row in enumerate(rows) if row['body']['writer'] == writer]
            self.assertEqual(indexes, list(range(indexes[0], indexes[0] + 100)))
        fresh(self.root, 'core', True)

    def test_existing_corruption_is_not_masked_by_batch(self):
        ledger = self.ledger()
        ledger.append({'n': 0})
        ledger.path.write_bytes(ledger.path.read_bytes().replace(b'"n":0', b'"n":1'))
        before = snapshot(self.root)
        with self.assertRaises(ValueError): ledger.append_batch([{'n': 2}])
        self.assertEqual(snapshot(self.root), before)
        self.assert_failed(ledger)

    def test_runtime_3072_initial_and_duplicate_filtering_and_provenance(self):
        r, a = runtime(self.root)
        self.addCleanup(r.session.close)
        real = r.membership.append_batch
        batches = []
        def observe(events):
            batches.append(copy.deepcopy(events))
            return real(events)
        with patch.object(r.membership, 'append_batch', side_effect=observe):
            r.membership_cycle()
            r.membership_cycle()
        self.assertEqual([len(b) for b in batches], [3072])
        rows = [json.loads(line) for line in r.membership.path.read_bytes().splitlines()]
        self.assertEqual(r.membership.path.read_bytes(), oracle([row['body'] for row in rows]))
        obs, events = [row for row in rows if row['body']['record_type'] == 'SOURCE_OBSERVATION'], [row['body'] for row in rows if row['body']['record_type'] == 'STRATEGY_MEMBERSHIP']
        self.assertEqual(len(obs), 2)
        self.assertEqual(len(events), 3072)
        self.assertEqual(obs[1]['body']['membership_batch']['count'], 0)
        raw = a.raw
        digest = hashlib.sha256(raw).hexdigest()
        self.assertEqual((self.root / 'nextgen-bodies-v1' / (digest + '.body')).read_bytes(), raw)
        for event in events:
            self.assertEqual(event['observation_id'], obs[0]['body']['observation_id'])
            self.assertEqual(event['observation_record_hash'], obs[0]['record_hash'])
            self.assertEqual(event['observation_body_sha256'], digest)
            self.assertEqual(event['record_sha256'], sha(event['record']))
            self.assertEqual(event['contract_id'], event['record']['contract'])
            self.assertEqual(event['event_id'], sha({k: event[k] for k in ('source', 'container', 'contract_id', 'record')}))
        self.assertEqual(len(r.seen_membership), 3072)
        fresh(self.root, 'runtime', True)

    def test_runtime_one_event_and_zero_events(self):
        for count in (0, 1):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as td:
                r, _ = runtime(td, count)
                try:
                    r.membership_cycle()
                    self.assertEqual(len(r.seen_membership), count)
                    self.assertEqual(r.membership.status().records, 1 + count)
                    fresh(td, 'runtime', True)
                finally: r.session.close()

    def test_envelope_committed_but_batch_cannot_start_or_fails(self):
        for mode in ('low_disk', 'intent_open', 'short_write', 'admission', 'interruption'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                r, _ = runtime(td)
                original = r.membership.append_batch
                hits = []
                def fail(events):
                    hits.append(True)
                    # Independently inspect the durable parent anchor first.
                    anchor = json.loads(r.membership.anchor_path.read_bytes())
                    last = json.loads(r.membership.path.read_bytes().splitlines()[-1])
                    self.assertTrue(anchor['committed'])
                    self.assertEqual(anchor['record_hash'], last['record_hash'])
                    self.assertEqual(last['body']['membership_batch']['count'], 3072)
                    if mode == 'interruption': raise KeyboardInterrupt('between envelope and batch')
                    injection = (patch.object(r.membership, '_write_guard', side_effect=OSError('low disk')) if mode == 'low_disk' else
                        patch('os.open', side_effect=OSError('no intent inode')) if mode == 'intent_open' else
                        patch('os.write', return_value=0) if mode == 'short_write' else
                        patch('integrity_sentinel.recorder_core_v1.MAX_BATCH_ROWS', 3))
                    with injection: return original(events)
                with patch.object(r.membership, 'append_batch', side_effect=fail), self.assertRaises((OSError, ValueError, KeyboardInterrupt)):
                    r.membership_cycle()
                self.assertEqual(hits, [True])
                self.assertEqual(len(r.seen_membership), 0)
                self.assertFalse(r.membership.status().chain_valid)
                r.session.close()
                before = snapshot(td)
                for _ in range(2): fresh(td, 'runtime', False)
                reopened, adapter = runtime(td)
                try:
                    reopened.run_cycle()
                    self.assertEqual(adapter.calls, 0)
                    self.assertIn('ledger_integrity_failed', reopened.public_state()['health_failures'])
                    self.assertFalse(reopened.public_state()['orders'])
                    self.assertFalse(reopened.public_state()['certifiable_evidence'])
                    self.assertEqual(snapshot(td), before)
                finally: reopened.session.close()

    def test_corrupted_body_reference_blocks_batch_and_reopen(self):
        r, _ = runtime(self.root)
        original = r.membership.append_batch
        def corrupt_then_append(events):
            p = next((self.root / 'nextgen-bodies-v1').glob('*.body'))
            p.chmod(0o600)
            p.write_bytes(p.read_bytes()[:-1])
            return original(events)
        with patch.object(r.membership, 'append_batch', side_effect=corrupt_then_append), self.assertRaises(ValueError): r.membership_cycle()
        self.assertEqual(len(r.seen_membership), 0)
        r.session.close()
        fresh(self.root, 'runtime', False)

    def test_failed_large_runtime_batch_keeps_observation_and_no_seen_ids(self):
        for mode in ('ledger_write', 'ledger_fsync', 'final_directory', 'cleanup'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                r, _ = runtime(td)
                original = r.membership.append_batch
                hits = []
                def fail(events):
                    real_write, real_sync = os.write, os.fsync
                    def write(fd, raw):
                        if mode == 'ledger_write' and os.readlink('/proc/self/fd/' + str(fd)) == str(r.membership.path):
                            hits.append(True)
                            return real_write(fd, raw[:-1])
                        return real_write(fd, raw)
                    def sync(fd):
                        path = os.readlink('/proc/self/fd/' + str(fd))
                        anchor = json.loads(r.membership.anchor_path.read_bytes())
                        hit = (mode == 'ledger_fsync' and path == str(r.membership.path)) or (
                            mode == 'final_directory' and stat.S_ISDIR(os.fstat(fd).st_mode)
                            and anchor['sequence'] == 3073 and anchor['committed'])
                        if hit:
                            hits.append(True)
                            raise OSError('large runtime durability fault')
                        return real_sync(fd)
                    def cleanup():
                        hits.append(True)
                        raise OSError('large runtime acknowledgement interrupted')
                    with patch('os.write', side_effect=write), patch('os.fsync', side_effect=sync):
                        if mode == 'cleanup':
                            with patch.object(r.membership, '_finish_durability', side_effect=cleanup): return original(events)
                        return original(events)
                with patch.object(r.membership, 'append_batch', side_effect=fail), self.assertRaises(OSError): r.membership_cycle()
                self.assertEqual(hits, [True])
                self.assertEqual(len(r.seen_membership), 0)
                first = json.loads(r.membership.path.read_bytes().splitlines()[0])
                self.assertEqual(first['body']['record_type'], 'SOURCE_OBSERVATION')
                self.assertTrue(r.membership.durability_path.exists())
                r.session.close()
                fresh(td, 'runtime', False)

    def test_completed_batch_rejects_extra_event_and_missing_exact_id(self):
        r, _ = runtime(self.root, 1)
        r.membership_cycle()
        event = json.loads(r.membership.path.read_bytes().splitlines()[-1])['body']
        AppendOnlyHashChainLedger(r.membership.path).append(event)
        self.assertFalse(r.membership.status().chain_valid)
        r.session.close()
        fresh(self.root, 'runtime', False)

    def test_wrong_event_order_identity_count_and_parent_rejected(self):
        for mode in ('order', 'record', 'parent', 'body_sha', 'count', 'duplicate', 'missing_id'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                r, _ = runtime(td, 3)
                original = r.membership.append_batch
                def invalid(events):
                    if mode == 'order': events.reverse()
                    elif mode == 'record': events[0]['record']['entry_ask'] = .99
                    elif mode == 'parent': events[0]['observation_record_hash'] = 'f' * 64
                    elif mode == 'body_sha': events[0]['observation_body_sha256'] = 'f' * 64
                    elif mode == 'count': events.pop()
                    elif mode == 'missing_id':
                        events[0]['record'].pop('contract')
                        events[0]['contract_id'] = None
                    else: events[1] = copy.deepcopy(events[0])
                    return original(events)
                with patch.object(r.membership, 'append_batch', side_effect=invalid), self.assertRaises(ValueError): r.membership_cycle()
                self.assertEqual(len(r.membership.path.read_bytes().splitlines()), 1)
                r.session.close()
                fresh(td, 'runtime', False)

    def test_valid_prefix_cannot_complete_obligation_by_individual_append(self):
        r, _ = runtime(self.root, 3)
        captured = []
        def stop(events):
            captured.extend(events)
            raise OSError('stop before batch')
        with patch.object(r.membership, 'append_batch', side_effect=stop), self.assertRaises(OSError): r.membership_cycle()
        with self.assertRaises(ValueError): r.membership.append(captured[0])
        # Simulate a malicious complete-row prefix with coherent base anchor.
        # The new obligation gate must still reject it after fresh open.
        base = AppendOnlyHashChainLedger(r.membership.path)
        base.append(captured[0])
        r.session.close()
        fresh(self.root, 'runtime', False)


def run():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BatchThroughputAdversarial)
    started = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'suite': 'independent batch-throughput V2', 'tests': result.testsRun,
                      'failures': len(result.failures), 'errors': len(result.errors),
                      'seconds': time.perf_counter() - started, 'passed': result.wasSuccessful(),
                      'network': 'offline synthetic transport only'}, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__': raise SystemExit(run())
