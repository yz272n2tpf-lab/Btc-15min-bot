import unittest
from datetime import datetime,timezone,timedelta
import btc15_rollover_production_canary_v1 as c
class T(unittest.TestCase):
 def setUp(self):c._state={"staged":None,"last_report":None};self.n=datetime(2026,9,22,19,0,tzinfo=timezone.utc)
 def parse(self,x):return datetime.fromisoformat(x)
 def test_observe_only_stage_and_compare(self):
  o=self.n+timedelta(minutes=15);m={"ticker":"KXBTC15M-NEXT","open_time":o.isoformat(),"close_time":(o+timedelta(minutes=15)).isoformat()}
  c.observe(lambda *a,**k:{"markets":[m]},self.parse,self.n,lambda x:None)
  self.assertEqual(c._state["staged"]["ticker"],"KXBTC15M-NEXT");self.assertTrue(c.compare("KXBTC15M-NEXT",o,lambda x:None))
 def test_mismatch_visible(self):
  c._state["staged"]={"ticker":"A","open":self.n,"close":self.n+timedelta(minutes=15)};self.assertFalse(c.compare("B",self.n,lambda x:None))
