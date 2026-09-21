import unittest
from btc15_signal_integration_v1 import EarlyState,FinalState,ScalpState
from btc15_dashboard_state_contract_v1 import build_dashboard_contract
class T(unittest.TestCase):
 def test_contract(self):
  m={"contract":"C","seconds_left":500,"kalshi_target":1,"up_bid":.2,"up_ask":.3,"down_bid":.7,"down_ask":.8,
     "early":EarlyState("QUALIFIED","UP",.3,.8,.1,500),"final":FinalState()}
  d=build_dashboard_contract(m,ScalpState())
  self.assertEqual(d["position"]["action"],"BUY");self.assertFalse(d["safety"]["orders_enabled"]);self.assertTrue(d["safety"]["manual_execution_only"])
 def test_exit_surfaces(self):
  m={"contract":"C","early":EarlyState(),"final":FinalState()}
  d=build_dashboard_contract(m,ScalpState("EXIT","DOWN",.2,.1,.3,-.1,100))
  self.assertEqual(d["position"]["action"],"EXIT")
