import unittest
from btc15_signal_integration_v1 import EarlyState,FinalState,ScalpState
from btc15_directional_position_manager_v1 import compose_position_view
class T(unittest.TestCase):
 def v(self,**kw):
  x=dict(contract="C",early=EarlyState(),final=FinalState(),scalp=ScalpState());x.update(kw);return compose_position_view(**x)
 def test_early_buy(self): self.assertEqual(self.v(early=EarlyState("QUALIFIED","UP",.3,.8,.1,500)).action,"BUY")
 def test_hold(self): self.assertEqual(self.v(position_open=True).action,"HOLD")
 def test_protect(self): self.assertEqual(self.v(scalp=ScalpState("PROTECT","DOWN",.2,.4,.3,.2,200)).action,"PROTECT PROFITS")
 def test_exit(self): self.assertEqual(self.v(scalp=ScalpState("EXIT","DOWN",.2,.1,.3,-.1,100)).action,"EXIT")
 def test_no_orders(self): self.assertFalse(self.v().orders)
