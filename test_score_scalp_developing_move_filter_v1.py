import unittest
import score_scalp_developing_move_filter_v1 as s
class T(unittest.TestCase):
 def r(self,e,left,b15): return {"entry_ask":e,"seconds_left":left,"btc_move_15s":b15}
 def test_exact_bounds(self):
  self.assertTrue(s.qualifies(self.r(.02,180,35)))
  self.assertTrue(s.qualifies(self.r(.50,180,-35)))
 def test_rejects_outside(self):
  self.assertFalse(s.qualifies(self.r(.019,180,10)))
  self.assertFalse(s.qualifies(self.r(.51,180,10)))
  self.assertFalse(s.qualifies(self.r(.20,179.9,10)))
  self.assertFalse(s.qualifies(self.r(.20,180,35.01)))
 def test_no_orders(self):
  self.assertFalse("orders" in s.__dict__ and s.__dict__["orders"])
if __name__=="__main__": unittest.main()
