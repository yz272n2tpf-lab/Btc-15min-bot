import copy,json,unittest
from pathlib import Path
from candidates.early_opportunity_20261011.lifecycle import Candidate
from btc15_v2_product.directional import qualify
from audit.existing_evidence_20261011.replay_candidates import final_predicates_from_recorded_inputs

class CandidateReplayTests(unittest.TestCase):
    def test_real_native_origin_is_replayed_without_profile_substitution(self):
        r=json.loads(Path(__file__).with_name('early_native_replay_frame.json').read_text());f=r['frame'];before=copy.deepcopy(f)
        qualify(f,r['decision_ts']);out=Candidate().process(f,r['decision_ts'])
        self.assertEqual(out['opportunity']['reasons'],['VALIDATED_OPPORTUNITY_EVIDENCE_REQUIRED'])
        self.assertTrue(out['opportunity']['baseline']['ready']);self.assertFalse(out['opportunity']['ready'])
        self.assertIsNone(out['origin']);self.assertFalse(out['actionable']);self.assertEqual(f,before)

    def test_unknown_capture_time_cannot_force_lock_across_distance_boundary(self):
        # Synthetic timing boundary only: source has >360s/$75; receipt <360s/$50.
        frame=dict(ticker='test',decision_utc='2026-10-11T14:08:59Z',target=83000,btc_price=83060,
                   features=dict(remaining=361/60,dist_over_range5=2))
        state=dict(market=dict(brti_value=83060,up_bid=.8,up_ask=.81,down_bid=.19,down_ask=.2),
                   final=dict(side='UP',confidence=.95))
        from audit.existing_evidence_20261011.evaluate import epoch
        cut=epoch(frame['decision_utc'])
        self.assertIsNone(final_predicates_from_recorded_inputs(state,frame,cut+2)[0])
        gates,_=final_predicates_from_recorded_inputs(state,frame,cut+.1)
        self.assertFalse(gates['gap_ok'])

if __name__=='__main__':unittest.main()
