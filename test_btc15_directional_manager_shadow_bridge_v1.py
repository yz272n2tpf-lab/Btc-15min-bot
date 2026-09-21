import unittest
from btc15_directional_manager_shadow_bridge_v1 import shadow_cycle
class T(unittest.TestCase):
 def fixture(self):
  return {"contract":"KXBTC15M-X","timer":{"seconds_left":500},"market":{"target":100.0,"up_bid":.29,"up_ask":.30,"down_bid":.69,"down_ask":.70},
  "early":{"ready":True,"side":"UP","ask":.30,"fair":.80,"edge":.10},
  "final":{"ready":False,"recorded_final_call":False}}
 def test_parity(self):
  d=shadow_cycle(self.fixture())
  self.assertEqual(d["contract"],"KXBTC15M-X");self.assertEqual(d["seconds_left"],500);self.assertEqual(d["kalshi"]["target"],100.0)
  self.assertEqual(d["position"]["action"],"BUY");self.assertFalse(d["safety"]["orders_enabled"])
