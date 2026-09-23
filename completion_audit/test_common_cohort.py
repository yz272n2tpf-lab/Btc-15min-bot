import copy
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from cohort_registry import identity
from evaluate_common_cohort import evaluate


class RegisteredEvaluation(unittest.TestCase):
    def setUp(self):
        self.manifest=dict(cohort_id='test',registered_utc='2026-09-23T19:00:00Z',signal_only=True,orders=False,
            revisions={'clean':{'run_id':'test'}},windows=[dict(role='untouched_holdout',
            start_utc='2026-09-23T20:30:00Z',end_utc='2026-09-23T21:00:00Z',scheduled_slots=2)])
        self.manifest['canonical_content_sha256_excluding_this_field']=identity(self.manifest)

    def test_holdout_refuses_outcome_evaluation_before_end(self):
        # Nonexistent file also proves the holdout check happens before reading evidence.
        with self.assertRaisesRegex(ValueError,'sealed'):
            evaluate(self.manifest,'untouched_holdout','absent',[],datetime(2026,9,23,20,45,tzinfo=timezone.utc))

    def test_policy_manifest_tampering_is_rejected(self):
        changed=copy.deepcopy(self.manifest);changed['orders']=True
        with self.assertRaisesRegex(ValueError,'identity'):
            evaluate(changed,'untouched_holdout','absent',[])

    def test_empty_closed_universe_retains_every_missing_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'empty.gz';path.write_bytes(b'')
            result=evaluate(self.manifest,'untouched_holdout',path,[],datetime(2026,9,23,21,tzinfo=timezone.utc))
        self.assertEqual(len(result['universe_registry']),2)
        self.assertFalse(result['baseline_certified'])
        self.assertFalse(result['main']['signal_only_all'])


if __name__=='__main__':unittest.main()
