import unittest
from v81_exit_candidate import Lifecycle,Policy


class ExitLifecycle(unittest.TestCase):
    def life(self,policy=None,side='UP'):
        return Lifecycle(policy or Policy('test',.05,.02),'KXBTC15M-A',side,.35,1000.,1001.,1900.)
    def quote(self,ts,bid,ticker='KXBTC15M-A'):
        return dict(observed_ts=ts,ticker=ticker,brti_source_ts=ts-1,
                    quote_validated_at_observation=True,up_bid=bid,down_bid=bid)
    def test_both_directions_arm_then_protect_using_bid(self):
        for side in ('UP','DOWN'):
            life=self.life(side=side)
            self.assertEqual(life.update(self.quote(1002,.41))['status'],'ARMED')
            result=life.update(self.quote(1003,.39))
            self.assertEqual(result['status'],'PROTECT');self.assertAlmostEqual(result['exit_bid_minus_entry_ask'],.04)
            self.assertFalse(result['realized_profit']);self.assertFalse(result['actual_exit_advice_published'])
    def test_stale_quote_cannot_arm_or_trigger(self):
        life=self.life();row=self.quote(1002,.60);row['brti_source_ts']=995
        self.assertEqual(life.update(row)['status'],'WAIT_QUALIFICATION');self.assertFalse(life.armed)
        row=self.quote(1003,.60);row['quote_validated_at_observation']=False
        self.assertEqual(life.update(row)['status'],'WAIT_QUALIFICATION');self.assertFalse(life.armed)
    def test_no_cross_contract_bid_leakage(self):
        life=self.life();self.assertEqual(life.update(self.quote(1002,.99,'KXBTC15M-B'))['status'],'WRONG_CONTRACT_WAIT')
        self.assertIsNone(life.peak)
    def test_stop_and_target_are_connected_and_terminal(self):
        p=Policy('stop-target',stop=.10,target=.08)
        self.assertEqual(self.life(p).update(self.quote(1002,.25))['status'],'STOP')
        life=self.life(p);result=life.update(self.quote(1002,.43))
        self.assertEqual(result['status'],'TARGET');self.assertIs(life.update(self.quote(1003,.05)),result)
    def test_late_horizon_does_not_fabricate_exit_fill(self):
        result=self.life().update(self.quote(1181,.90))
        self.assertEqual(result['status'],'HORIZON');self.assertIsNone(result['exit_bid_minus_entry_ask'])
        self.assertEqual(result['horizon_delay_seconds'],1)
    def test_negative_excursions_are_not_clamped_to_zero(self):
        life=self.life();life.update(self.quote(1002,.34));life.update(self.quote(1003,.30))
        self.assertAlmostEqual(life.peak,-.01);self.assertAlmostEqual(life.trough,-.05)
    def test_stale_entry_is_not_recreated_from_latched_event(self):
        with self.assertRaises(ValueError):Lifecycle(Policy('none'),'KXBTC15M-A','UP',.35,1000,1004,1900)
    def test_future_or_out_of_order_observations_do_not_update_peak(self):
        life=self.life();life.update(self.quote(1003,.36))
        self.assertEqual(life.update(self.quote(1002,.90))['status'],'OUT_OF_ORDER')
        row=self.quote(1004,.99);row['brti_source_ts']=1005
        self.assertEqual(life.update(row)['status'],'WAIT_QUALIFICATION');self.assertAlmostEqual(life.peak,.01)


if __name__=='__main__':unittest.main()
