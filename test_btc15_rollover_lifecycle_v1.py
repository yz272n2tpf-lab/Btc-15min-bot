import unittest
from datetime import datetime,timezone,timedelta
from btc15_rollover_handoff_model_v1 import Staged
from btc15_rollover_lifecycle_v1 import step
class T(unittest.TestCase):
 def setUp(self):
  self.o=datetime(2026,9,22,18,0,tzinfo=timezone.utc);self.s=Staged("NEXT",self.o,self.o+timedelta(minutes=15))
 def test_preopen_never_publish(self):
  r=step("CUR",self.s,self.o-timedelta(seconds=1),["NEXT"],"NEXT","NEXT",True,True);self.assertFalse(r["publish"]);self.assertEqual(r["active"],"CUR")
 def test_verified_but_book_missing(self):
  r=step("CUR",self.s,self.o,["NEXT"],"NEXT","NEXT",False,True);self.assertFalse(r["publish"])
 def test_full_ready(self):
  r=step("CUR",self.s,self.o,["NEXT"],"NEXT","NEXT",True,True);self.assertTrue(r["publish"]);self.assertEqual(r["active"],"NEXT")
