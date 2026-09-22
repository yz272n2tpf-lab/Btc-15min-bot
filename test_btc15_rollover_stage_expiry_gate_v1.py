import unittest
from datetime import datetime,timezone,timedelta
from btc15_rollover_handoff_model_v1 import Staged
from btc15_rollover_stage_expiry_gate_v1 import stage_usable
class T(unittest.TestCase):
 def setUp(self):
  self.o=datetime(2026,9,22,20,0,tzinfo=timezone.utc);self.s=Staged("X",self.o,self.o+timedelta(minutes=15))
 def test_before_open_not_usable(self):self.assertFalse(stage_usable(self.s,self.o-timedelta(seconds=1)))
 def test_inside_window(self):self.assertTrue(stage_usable(self.s,self.o))
 def test_at_close_expired(self):self.assertFalse(stage_usable(self.s,self.s.close_time))
 def test_long_after_expired(self):self.assertFalse(stage_usable(self.s,self.s.close_time+timedelta(hours=1)))
