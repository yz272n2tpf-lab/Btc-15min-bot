"""Lossless V81 recorder-only batching regressions; offline synthetic data ONLY."""
import gzip
import hashlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from btc15_quote_proof_offpath_v1 import OffPathProofWriter
from candidates.early_recording_20261012.archive import BUDGET, read_archive
from ops.live_recording.batched_journal import BatchedCompressedJournal
from ops.live_recording.capture import RoleArchive

MIB = 1024 * 1024


class V81Batching(unittest.TestCase):
    def archive(self, root):
        archive = RoleArchive(
            Path(root) / 'v81-source', role='v81',
            evidence_class='FIXTURE', source_binding='synthetic-v81-rate-fixture',
            budget=dict(BUDGET, max_total_bytes=64 * MIB))
        self.assertIsInstance(archive.journal, BatchedCompressedJournal)
        return archive

    def test_main_and_information_keep_original_journal_and_proof_owner(self):
        from btc15_information_journal_v1 import CompressedJournal
        from btc15_quote_proof_offpath_v1 import OffPathProofWriter as NativeProofWriter
        from ops.live_recording.recorder_queue import RecorderOffPathProofWriter
        self.assertIsNot(NativeProofWriter, RecorderOffPathProofWriter)
        with tempfile.TemporaryDirectory() as directory:
            for role in ('main','information'):
                archive=RoleArchive(
                    Path(directory) / role, role=role,
                    evidence_class='FIXTURE', source_binding='isolation-'+role,
                    budget=dict(BUDGET,max_total_bytes=64*MIB))
                self.assertIs(type(archive.journal), CompressedJournal)
            v81=self.archive(directory)
            self.assertIs(type(v81.journal), BatchedCompressedJournal)

    def test_batches_preserve_exact_hash_chain_and_reduce_fsync(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = self.archive(directory)
            original_fsync = os.fsync
            calls = []
            def counted(fd):
                calls.append(fd)
                return original_fsync(fd)
            with patch('ops.live_recording.batched_journal.os.fsync', side_effect=counted):
                archive.start()
                for i in range(1400):
                    # Similar field size to observed V81 intake, no real source data.
                    archive.write('FIXTURE_OBSERVATION', dict(n=i, payload=('BTC15-%06d-' % i) * 65))
                archive.write('STOP', dict(clean=True))
                archive.close()
            self.assertLess(len(calls), 100, 'must not fsync once per event')
            self.assertEqual(archive.journal.durable_records, 1402)
            self.assertEqual(archive.journal.pending_records, 0)
            report = read_archive(archive.path, max_decoded_bytes=32 * MIB)
            self.assertEqual(report['gaps'], [])
            self.assertEqual(len(report['records']), 1402)
            self.assertEqual(report['records'][0]['kind'], 'START')
            self.assertEqual(report['records'][-1]['kind'], 'STOP')
            self.assertEqual(
                [r['payload']['n'] for r in report['records'] if r['kind']=='FIXTURE_OBSERVATION'],
                list(range(1400)))

    def test_idle_flush_is_durable_without_a_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = self.archive(directory)
            archive.start()
            archive.write('FIXTURE_OBSERVATION', dict(n=1))
            self.assertGreater(archive.journal.pending_records, 0)
            archive.journal._last_flush -= 1
            archive.journal.flush_due()
            self.assertEqual(archive.journal.pending_records, 0)
            self.assertEqual(archive.journal.durable_records, 2)
            archive.write('STOP', dict(clean=True))
            archive.close()
            self.assertEqual(read_archive(archive.path)['gaps'], [])

    def test_partial_gzip_write_fails_closed_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = self.archive(directory)
            archive.start()
            archive.write('FIXTURE_OBSERVATION', dict(n=1, payload='x' * 12000))
            real_write = os.write
            invoked = [0]
            def broken(fd, raw):
                invoked[0] += 1
                if invoked[0] == 1:
                    real_write(fd, raw[:8])
                    raise OSError('synthetic filesystem interruption')
                return real_write(fd, raw)
            with patch('ops.live_recording.batched_journal.os.write', side_effect=broken):
                with self.assertRaisesRegex(OSError, 'synthetic filesystem interruption'):
                    archive.journal.flush()
            self.assertTrue(archive.journal.failed)
            original = [p for p in archive.journal.directory.glob('*.jsonl.gz')]
            self.assertEqual(len(original), 1)
            digest = hashlib.sha256(original[0].read_bytes()).hexdigest()
            with self.assertRaises(OSError):
                archive.write('FIXTURE_OBSERVATION', dict(n=2))
            self.assertEqual(hashlib.sha256(original[0].read_bytes()).hexdigest(), digest)
            # Do not call close() on a failed journal; no seal is claimed.
            archive._lock_file.close()

    def test_segment_rollover_retains_all_events_and_reader_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = RoleArchive(
                Path(directory) / 'v81-multisegment', role='v81',
                evidence_class='FIXTURE', source_binding='synthetic-rollover',
                budget=dict(BUDGET, segment_bytes=32*1024, max_total_bytes=64*MIB))
            archive.start()
            for i in range(2600):
                archive.write('FIXTURE_OBSERVATION', dict(
                    n=i, payload=hashlib.sha256(str(i).encode()).hexdigest()*10))
            archive.write('STOP', dict(clean=True))
            archive.close()
            segments = list(archive.journal.directory.glob('*.jsonl.gz'))
            self.assertGreater(len(segments), 1)
            self.assertTrue(all(0 < p.stat().st_size <= 32*1024 for p in segments))
            report = read_archive(archive.path, max_decoded_bytes=32*MIB)
            self.assertEqual(report['gaps'], [])
            self.assertEqual(len(report['records']), 2602)
            self.assertEqual(archive.journal.durable_records, 2602)

    def test_high_entropy_quote_bursts_with_delayed_fsync(self):
        # Source-like workload shape, NOT a replay of the unavailable original.
        # Every 10th observation is a larger incompressible quote message.
        import base64
        import random
        from ops.live_recording.recorder_queue import RecorderOffPathProofWriter
        with tempfile.TemporaryDirectory() as directory:
            archive=self.archive(directory)
            original_fsync=os.fsync
            def delayed(fd):
                time.sleep(.004)
                return original_fsync(fd)
            rng=random.Random(20261014)
            accepted=0
            began=time.monotonic()
            with patch('ops.live_recording.batched_journal.os.fsync', side_effect=delayed):
                writer=RecorderOffPathProofWriter(
                    Path(directory)/'unused',lambda p,w:w.identity,2*MIB,
                    archive=archive,queue_size=16384,queue_bytes=32*MIB,
                    admission_limits=dict(queue_size=16384,queue_bytes=32*MIB))
                for i in range(6000):
                    n=16384 if i%10==0 else 900
                    raw=base64.b64encode(rng.randbytes(n))
                    if writer.submit_observation(
                        'QUOTE_RECEIVE',raw=raw,received_at=float(i),
                        ticker='SYNTHETIC_NO_REAL_MARKET'):
                        accepted+=1
                    if i%400==399:
                        time.sleep(.8)
                done=writer.close(timeout=60)
            self.assertTrue(done)
            self.assertEqual(accepted,6000)
            self.assertFalse(writer.archive_failed)
            self.assertEqual(writer.status()['losses'],{})
            self.assertEqual(archive.journal.pending_records,0)
            self.assertEqual(archive.journal.durable_records,archive.journal.records)
            verified=read_archive(archive.path,max_decoded_bytes=96*MIB)
            self.assertEqual(verified['gaps'],[])
            self.assertEqual(sum(x['kind']=='QUOTE_RECEIVE' for x in verified['records']),6000)
            print('V81_HIGH_ENTROPY_OFFLINE | events=6000 elapsed=%.2fs compressed=%d peak_queued=%d loss=0' % (
                time.monotonic()-began,archive.journal.stored_bytes,
                writer.peak_queued_bytes),flush=True)

    def test_sustained_live_like_intake_without_dropped_offpath_events(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = self.archive(directory)
            writer = OffPathProofWriter(
                Path(directory) / 'unused', lambda p,w:w.identity, 2 * MIB,
                archive=archive, queue_size=16384, queue_bytes=32 * MIB,
                admission_limits=dict(queue_size=16384, queue_bytes=32 * MIB))
            accepted = 0
            began = time.monotonic()
            try:
                # 9,000 synthetic events in ~15 seconds (~600 per second),
                # above the approximately 390 records/s seen before failure.
                for i in range(9000):
                    payload = ('{"quote":%d,"pad":"%s"}' % (i,'abcde'*150)).encode()
                    if writer.submit_observation(
                        'BRTI_READ', raw=payload, received_at=float(i),
                        receipt_basis='SYNTHETIC_WORKLOAD_NOT_LIVE_SOURCE'):
                        accepted += 1
                    if i % 300 == 299:
                        time.sleep(.5)
            finally:
                closed = writer.close(timeout=60)
            elapsed = time.monotonic() - began
            self.assertTrue(closed, 'bounded offline writer must finish')
            self.assertEqual(accepted, 9000)
            self.assertFalse(writer.archive_failed)
            self.assertFalse(writer.status()['losses'])
            self.assertFalse(archive.journal.failed)
            self.assertEqual(archive.journal.pending_records, 0)
            self.assertEqual(archive.journal.durable_records, archive.journal.records)
            self.assertEqual(archive.journal.records, 9002) # START, input, STOP
            review = read_archive(archive.path, max_decoded_bytes=96*MIB)
            self.assertEqual(review['gaps'], [])
            self.assertEqual(len(review['records']), 9002)
            self.assertEqual(sum(x['kind']=='BRTI_READ' for x in review['records']), 9000)
            print('V81_BATCHED_OFFLINE | events=9000 elapsed=%.2fs, committed=%d, compressed=%d, losses=0, segments=%d' %
                  (elapsed, archive.journal.durable_records, archive.journal.stored_bytes,
                   len(list(archive.journal.directory.glob('*.jsonl.gz')))), flush=True)


if __name__=='__main__':
    unittest.main()
