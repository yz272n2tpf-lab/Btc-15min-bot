import copy
import unittest
from cohort_registry import identity,utc
from run_frozen_forward_shadow import window


class FrozenWindowTests(unittest.TestCase):
    def setUp(self):
        self.c=dict(registered_utc='2026-09-23T20:00:00Z',orders=False,signal_only=True,windows=[
            dict(role='development_tuning',start_utc='2026-09-23T21:15:00Z',end_utc='2026-09-24T21:15:00Z',scheduled_slots=96),
            dict(role='untouched_holdout',start_utc='2026-09-25T21:15:00Z',end_utc='2026-10-09T21:15:00Z',scheduled_slots=1344)])
        self.c['canonical_content_sha256_excluding_this_field']=identity(self.c)
        self.p=dict(cohort_manifest_sha256=self.c['canonical_content_sha256_excluding_this_field'],
                    registered_utc='2026-09-23T21:20:00Z',start_utc='2026-09-23T21:45:00Z')

    def test_late_candidate_start_remains_explicit(self):
        start,end,declared=window(self.p,self.c,'development_tuning',utc('2026-09-23T22:00:00Z'))
        self.assertEqual(start,utc(self.p['start_utc']))
        self.assertEqual(declared['scheduled_slots'],96)

    def test_holdout_not_opened_early(self):
        with self.assertRaisesRegex(ValueError,'sealed'):
            window(self.p,self.c,'untouched_holdout',utc('2026-09-26T21:15:00Z'))

    def test_changed_manifest_rejected(self):
        c=copy.deepcopy(self.c);c['windows'][0]['scheduled_slots']=95
        with self.assertRaisesRegex(ValueError,'identity mismatch'):
            window(self.p,c,'development_tuning',utc('2026-09-23T22:00:00Z'))

    def test_policy_cannot_relabel_past_inputs(self):
        self.p['registered_utc']='2026-09-23T22:00:00Z'
        with self.assertRaisesRegex(ValueError,'prospectively'):
            window(self.p,self.c,'development_tuning',utc('2026-09-23T22:00:00Z'))


if __name__=='__main__':unittest.main()
