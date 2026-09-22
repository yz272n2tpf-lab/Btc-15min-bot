import unittest
from datetime import datetime,timezone,timedelta
from btc15_rollover_handoff_model_v1 import Staged
from btc15_rollover_stage_immutability_gate_v1 import same_stage
class T(unittest.TestCase):
 def setUp(self):
  self.o=datetime(2026,9,22,21,0,tzinfo=timezone.utc);self.a=Staged("A",self.o,self.o+timedelta(minutes=15))
 def test_same(self):self.assertTrue(same_stage(self.a,Staged("A",self.o,self.o+timedelta(minutes=15))))
 def test_ticker_mutation(self):self.assertFalse(same_stage(self.a,Staged("B",self.o,self.o+timedelta(minutes=15))))
 def test_open_mutation(self):self.assertFalse(same_stage(self.a,Staged("A",self.o+timedelta(minutes=15),self.o+timedelta(minutes=30))))
