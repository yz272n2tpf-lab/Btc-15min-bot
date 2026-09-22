import unittest
from datetime import datetime,timezone,timedelta
from btc15_rollover_handoff_model_v1 import Staged,transition
class T(unittest.TestCase):
 def setUp(self):
  self.o=datetime(2026,9,22,15,0,tzinfo=timezone.utc);self.s=Staged("NEXT",self.o,self.o+timedelta(minutes=15))
 def test_never_early(self): self.assertEqual(transition("CUR",self.s,self.o-timedelta(milliseconds=1),["NEXT"]),("CUR",self.s,"HOLD_PREOPEN"))
 def test_hold_missing(self): self.assertEqual(transition("CUR",self.s,self.o+timedelta(seconds=40),[]),("CUR",self.s,"HOLD_UNVERIFIED"))
 def test_exact_handoff(self): self.assertEqual(transition("CUR",self.s,self.o,["NEXT"]),("NEXT",None,"VERIFIED_HANDOFF"))
 def test_wrong_ticker_fails_closed(self): self.assertEqual(transition("CUR",self.s,self.o,["OTHER"]),("CUR",self.s,"HOLD_UNVERIFIED"))
