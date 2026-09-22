import unittest
from btc15_rollover_promotion_gate_v1 import ready
class T(unittest.TestCase):
 def base(self):return dict(shadow_consecutive_passes=4,exact_ticker_matches=4,early_activations=0,early_publications=0,orders=0,regression_suite_pass=True,core_runtime_mapped=True)
 def test_ready(self):self.assertTrue(ready(self.base()))
 def test_each_safety_block(self):
  for k,v in [("shadow_consecutive_passes",2),("exact_ticker_matches",2),("early_activations",1),("early_publications",1),("orders",1),("regression_suite_pass",False),("core_runtime_mapped",False)]:
   d=self.base();d[k]=v;self.assertFalse(ready(d),k)
