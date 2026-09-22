#!/usr/bin/env python3
"""Offline negative-path tests for rollover staging/handoff."""
import unittest
from datetime import datetime,timezone,timedelta
from btc15_rollover_handoff_model_v1 import Staged,transition
from btc15_rollover_stage_selector_v1 import choose
class Negative(unittest.TestCase):
 def setUp(self):
  self.o=datetime(2026,9,22,16,0,tzinfo=timezone.utc)
 def test_empty_unopened(self): self.assertIsNone(choose([],self.o))
 def test_malformed_metadata(self): self.assertIsNone(choose([{"ticker":"KXBTC15M-X"}],self.o))
 def test_wrong_series(self):
  r=[{"ticker":"NOTBTC","open_time":(self.o+timedelta(minutes=15)).isoformat(),"close_time":(self.o+timedelta(minutes=30)).isoformat()}]
  self.assertIsNone(choose(r,self.o))
 def test_indefinite_open_delay_holds(self):
  s=Staged("NEXT",self.o,self.o+timedelta(minutes=15))
  for sec in (1,30,60,300):
   a,h,x=transition("CURRENT",s,self.o+timedelta(seconds=sec),[])
   self.assertEqual((a,h,x),("CURRENT",s,"HOLD_UNVERIFIED"))
 def test_wrong_open_ticker_never_advances(self):
  s=Staged("NEXT",self.o,self.o+timedelta(minutes=15))
  a,h,x=transition("CURRENT",s,self.o+timedelta(seconds=45),["WRONG"])
  self.assertEqual((a,h,x),("CURRENT",s,"HOLD_UNVERIFIED"))
