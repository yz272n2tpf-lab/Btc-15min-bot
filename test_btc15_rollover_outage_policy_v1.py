import unittest
from datetime import datetime,timezone,timedelta
from btc15_rollover_handoff_model_v1 import Staged
from btc15_rollover_outage_policy_v1 import outage_action
class T(unittest.TestCase):
 def setUp(self):
  self.o=datetime(2026,9,22,22,0,tzinfo=timezone.utc);self.s=Staged("A",self.o,self.o+timedelta(minutes=15))
 def test_preopen(self):self.assertEqual(outage_action(self.s,self.o-timedelta(seconds=1)),"HOLD_PREOPEN")
 def test_during_window(self):self.assertEqual(outage_action(self.s,self.o+timedelta(minutes=5)),"HOLD_VERIFY_RETRY")
 def test_expire(self):self.assertEqual(outage_action(self.s,self.s.close_time),"EXPIRE_FAIL_CLOSED")
