import unittest
from datetime import datetime,timezone,timedelta
from btc15_rollover_monotonic_gate_v1 import monotonic
class T(unittest.TestCase):
 def test_first(self): self.assertTrue(monotonic(None,datetime.now(timezone.utc)))
 def test_forward(self):
  a=datetime(2026,9,22,19,0,tzinfo=timezone.utc);self.assertTrue(monotonic(a,a+timedelta(minutes=15)))
 def test_same_blocked(self):
  a=datetime(2026,9,22,19,0,tzinfo=timezone.utc);self.assertFalse(monotonic(a,a))
 def test_backward_blocked(self):
  a=datetime(2026,9,22,19,0,tzinfo=timezone.utc);self.assertFalse(monotonic(a,a-timedelta(minutes=15)))
