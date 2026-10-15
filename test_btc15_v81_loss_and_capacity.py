"""Fail-closed capacity and recorder loss accounting tests (offline only)."""
import tempfile
import unittest
from pathlib import Path

from candidates.early_recording_20261012.archive import BUDGET, read_archive
from ops.live_recording.capture import RoleArchive
from ops.live_recording.recorder_queue import RecorderOffPathProofWriter
from ops.live_recording.v81_capacity_review import review_v81

MiB = 1024**2
OBSERVED_FAILED_WINDOW = dict(
    elapsed=15.134490864351392, records=5904, raw_bytes=5683274,
    compressed_bytes=3587665, failure='DRAIN_TIMEOUT', stopped=False,
    writer=dict(losses=dict(QUEUE_BYTES=1470), archive_failed=False)
)


class V81CapacityReview(unittest.TestCase):
    def test_failed_window_excludes_both_existing_profiles_and_never_authorizes(self):
        r = review_v81(OBSERVED_FAILED_WINDOW)
        self.assertEqual(r['sample_records'], 5904)
        self.assertEqual(r['observed_losses']['QUEUE_BYTES'], 1470)
        self.assertFalse(r['qualified_24h'])
        self.assertEqual(r['status'], 'NO_GO_UNQUALIFIED')
        self.assertTrue(r['uncertainty']['startup_failure_window_only'])
        self.assertTrue(r['uncertainty']['batched_codec_not_measured'])
        for profile in ('preflight', 'day'):
            result = r['profiles'][profile]
            self.assertFalse(result['extrapolated_limits_within_profile'])
            self.assertIn('RECORD_CAP_EXTRAPOLATION_EXCEEDED', result['blockers'])
            self.assertIn('OLD_CODEC_COMPRESSED_CAP_EXTRAPOLATION_EXCEEDED',
                          result['blockers'])
            self.assertGreater(result['projected']['admitted_demand_lower_bound'],
                               result['projected']['recorded_records'])
        self.assertEqual(r['profiles']['preflight']['reviewed_limits']['records'], 74996)
        self.assertEqual(r['profiles']['day']['reviewed_limits']['records'], 1499996)

    def test_measurement_missing_or_bad_is_rejected(self):
        for bad in (dict(OBSERVED_FAILED_WINDOW, elapsed=0),
                    dict(OBSERVED_FAILED_WINDOW, compressed_bytes=-1),
                    dict(OBSERVED_FAILED_WINDOW, writer=dict(losses={'QUEUE_BYTES':-1}))):
            with self.assertRaises(ValueError):
                review_v81(bad)

    def test_fast_unqualified_window_is_not_certification(self):
        benign=dict(elapsed=15, records=10, raw_bytes=9000,
                    compressed_bytes=2000,
                    failure=None, stopped=True, writer=dict(losses={}))
        r=review_v81(benign)
        self.assertFalse(r['qualified_24h'])
        self.assertEqual(r['status'], 'NO_GO_UNQUALIFIED')
        self.assertIn('SHORT_SAMPLE_NOT_24H_QUALIFICATION', r['hard_blockers'])


class RecorderLossAccounting(unittest.TestCase):
    def new_writer(self, root, limit=8192):
        archive=RoleArchive(Path(root)/'source', role='v81',
                            evidence_class='FIXTURE', source_binding='synthetic-loss-accounting',
                            budget=dict(BUDGET, max_total_bytes=64*MiB))
        writer=RecorderOffPathProofWriter(
            Path(root)/'unused', lambda p,w:w.identity, 2*MiB,
            archive=archive, queue_size=64, queue_bytes=limit,
            admission_limits=dict(queue_size=64,queue_bytes=limit))
        return writer,archive

    def test_repeated_health_polls_do_not_invent_evidence_losses(self):
        with tempfile.TemporaryDirectory() as d:
            writer,archive=self.new_writer(d)
            self.assertEqual([writer.status()['losses'] for _ in range(75)], [{}]*75)
            self.assertTrue(writer.close(timeout=3))
            self.assertEqual(writer.status()['losses'], {})
            self.assertEqual(read_archive(archive.path)['gaps'], [])

    def test_real_admission_drop_remains_visible_after_repeated_polls(self):
        with tempfile.TemporaryDirectory() as d:
            writer,archive=self.new_writer(d, limit=4096)
            self.assertFalse(writer.submit_observation(
                'BRTI_READ', raw=b'X'*7000, received_at=1.0))
            for _ in range(75):
                self.assertEqual(writer.status()['losses'], {'QUEUE_BYTES':1})
            self.assertTrue(writer.close(timeout=4))
            self.assertEqual(writer.status()['losses'], {'QUEUE_BYTES':1})
            result=read_archive(archive.path)
            self.assertTrue(any(g['reason']=='EVIDENCE_GAP' for g in result['gaps']))
            self.assertFalse(any(g['reason']=='UNCLOSED_OR_INCOMPLETE_SESSION' for g in result['gaps']))
            self.assertEqual(result['records'][-1]['kind'],'STOP')


if __name__ == '__main__':
    unittest.main()
