import unittest
from structural_batch import v81_calls, passage, probability, outcome_calls


class StructuralSafetyTests(unittest.TestCase):
    def row(self, t=100., **kw):
        row=dict(t=t,source_t=t,ticker='A',side='UP',target=100.,ask=.35,bid=.34,
                 btc_age=1.,features_ready=True,brti_fresh=True,left=5.,receipt_left=5.,
                 btc5=30.,btc15=30.,btc30=10.,brti5=30.,brti15=20.,accel=20.,
                 ask5=0.,ask15=0.,structure_ok=True)
        return dict(row,**kw)

    def test_sequence_arms_before_lag_entry_without_losing_direction(self):
        arm=self.row(100.,ask5=.04,ask15=.06)
        eligible=self.row(101.,btc5=1.,btc15=2.,brti5=1.,accel=0.)
        confirmed=dict(eligible,t=102.,source_t=102.)
        self.assertEqual(len(v81_calls([arm,eligible,confirmed],'sequence')[0]),1)
        self.assertEqual(v81_calls([arm,eligible,confirmed],'baseline')[0],[])

    def test_source_staleness_clears_sequence_and_confirmation(self):
        rows=[self.row(100.,ask5=.04),self.row(101.,btc_age=11.),
              self.row(102.,btc5=1.,brti5=1.,accel=0.),self.row(103.,btc5=1.,brti5=1.,accel=0.)]
        self.assertEqual(v81_calls(rows,'sequence')[0],[])

    def test_reverse_direction_clears_arm(self):
        rows=[self.row(100.,ask5=.04),self.row(101.,btc5=-1.),
              self.row(102.,btc5=1.,brti5=1.,accel=0.),self.row(103.,btc5=1.,brti5=1.,accel=0.)]
        self.assertEqual(v81_calls(rows,'sequence')[0],[])

    def test_gap_and_contract_rollover_cannot_confirm(self):
        self.assertEqual(v81_calls([self.row(100.),self.row(105.)],'baseline')[0],[])
        self.assertEqual(v81_calls([self.row(100.),self.row(101.,ticker='B')],'baseline')[0],[])

    def point(self,t,bid,**kw):
        return dict(dict(t=t,up_bid=bid,up_ask=.35,target=100.),**kw)

    def test_target_after_stop_is_not_a_scalp_win(self):
        r=self.row();clean={'A':[self.point(101.,.23),self.point(102.,.50)]}
        self.assertEqual(passage(r,clean)['result'],'stop')

    def test_unpriced_gap_does_not_become_a_win(self):
        self.assertEqual(passage(self.row(),{'A':[self.point(101.,.34),self.point(120.,.50)]})['result'],'gap_censored')

    def test_missing_entry_and_target_mismatch_not_fills(self):
        self.assertEqual(passage(self.row(),{'A':[self.point(101.,.50,up_ask=.51)]})['result'],'entry_not_confirmed')
        self.assertEqual(passage(self.row(),{'A':[self.point(101.,.50,target=101.)]})['result'],'target_mismatch')

    def test_direction_symmetric_features_preserve_probability_complement(self):
        model=dict(name='distance_motion',features=['z','m15'],scale=[2.,3.],coef=[1.,.5])
        self.assertAlmostEqual(probability(dict(z=3.,m15=6.),model)+probability(dict(z=-3.,m15=-6.),model),1.)

    def test_final_never_replaces_authority_with_high_probability(self):
        r=dict(self.row(),p_existing=.99,brti_authority=False,brti_gap=100.,signed_gap=100.,
               up_bid=.8,up_ask=.81,down_bid=.19,down_ask=.20)
        self.assertEqual(outcome_calls([r],dict(name='existing'),'final'),[])


if __name__=='__main__':unittest.main()
