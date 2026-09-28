import copy
import unittest
from ladder_contribution import contribution


def call(ticker,side='UP',when='2026-09-23T21:20:00Z',result='yes',mfe=.05):
    return dict(contract=ticker,side=side,observed_utc=when,official_result=result,
        entry_ask=.35,minutes_remaining=10,
        sampled_bid_path=dict(sample_count=2,observed_mfe=mfe,observed_mae=-.02))


class ContributionTests(unittest.TestCase):
    def setUp(self):
        self.report=dict(cohort_id='fixture',phase='development_tuning',universe_registry=[
            dict(ticker=t,official_identified=t is not None) for t in ['A','B','C','D',None]],
            lanes=dict(early=dict(calls=[call('A'),call('B')]),
                       final=dict(calls=[call('B',when='2026-09-23T21:23:00Z')]),
                       scalp=dict(calls=[call('C',side='DOWN',mfe=-.01)])))

    def test_unique_union_and_missing_denominators(self):
        r=contribution(self.report)
        self.assertEqual(r['union_call_contracts'],3)
        self.assertEqual(r['scheduled_contract_slots'],5)
        self.assertEqual(r['no_call_official_contracts'],['D'])
        self.assertEqual(r['ladders']['early']['unique_contracts'],['A'])
        self.assertEqual(r['ladders']['final']['unique_contracts'],[])
        self.assertEqual(r['ladders']['early']['scheduled_coverage'],.4)

    def test_pair_time_and_opposite_direction_retained(self):
        self.report['lanes']['final']['calls'][0]['side']='DOWN'
        p=contribution(self.report)['pair_relationships']['early+final']
        self.assertEqual(p['opposite_side'],1)
        self.assertEqual(p['right_minus_left_call_seconds']['median'],180)

    def test_labels_do_not_change_call_selection_or_union(self):
        before=contribution(self.report)
        for lane in self.report['lanes'].values():
            for c in lane['calls']:c['official_result']='no'
        after=contribution(self.report)
        self.assertEqual(before['union_call_contracts'],after['union_call_contracts'])
        self.assertEqual(before['first_observed_lane'],after['first_observed_lane'])

    def test_negative_mfe_and_missing_path_not_wins(self):
        self.report['lanes']['early']['calls'][0]['sampled_bid_path']=dict(sample_count=0)
        r=contribution(self.report)
        self.assertEqual(r['ladders']['early']['path_missing_contracts'],1)
        self.assertEqual(r['ladders']['scalp']['observed_nonpositive_movement'],1)
        self.assertEqual(r['ladders']['scalp']['sampled_mfe']['max'],-.01)

    def test_duplicate_and_outside_calls_rejected(self):
        for c in [call('B'),call('OUTSIDE')]:
            r=copy.deepcopy(self.report);r['lanes']['final']['calls'].append(c)
            with self.assertRaises(ValueError):contribution(r)


if __name__=='__main__':unittest.main()
