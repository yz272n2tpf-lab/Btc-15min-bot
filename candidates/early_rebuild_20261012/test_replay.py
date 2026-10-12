"""Focused causal measurement and missing-observation tests."""
import unittest
from .test_engine import fixture
from .replay import first_observed,contract_replay

class ReplayIntegrity(unittest.TestCase):
    def test_first_delayed_quote_not_future_maximum(self):
        seq=[fixture(t,ask=ask) for t,ask in ((11,.40),(16,.70),(21,.90))]
        self.assertEqual(first_observed(seq,0,10)['time'],11)
    def test_old_quote_late_receipt_not_delayed_execution(self):
        r=fixture(5);r['received']=12
        self.assertIsNone(first_observed([r],0,10))
    def test_missing_quote_no_interpolation(self):
        self.assertIsNone(first_observed([fixture(9),fixture(21)],0,10))
    def test_actual_elapsed_not_requested_delay(self):
        seq=[fixture(t) for t in (0,5,10,15,20,25,30,35,40,45,53,58,63,68)]
        rr,_,tt=contract_replay('A',seq)
        up=next(r for r in rr if r['setup']['side']=='UP')
        self.assertEqual(up['delayed_recheck']['actual_observed_elapsed'],13)
        self.assertEqual(tt,0);self.assertIsNone(up['hypothetical_after_cost'])
    def test_source_gap_cancels_pending_simulation(self):
        seq=[fixture(t) for t in range(0,46,5)]+[fixture(80),fixture(85)]
        rr,_,tt=contract_replay('A',seq)
        self.assertTrue(any(r['status']=='CANCELED_BEFORE_SIMULATION' for r in rr))
        self.assertEqual(tt,0)
    def test_primary_exception_never_simulated_without_support(self):
        seq=[fixture(t,ask=.56) for t in range(0,181,5)]
        rr,_,tt=contract_replay('A',seq)
        self.assertTrue(rr);self.assertTrue(all(r['observational_qualification'] is None for r in rr))
        self.assertEqual(tt,0)

if __name__=='__main__':unittest.main()
