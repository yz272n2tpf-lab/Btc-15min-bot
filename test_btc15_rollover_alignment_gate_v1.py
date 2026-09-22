import unittest
from datetime import datetime,timezone,timedelta
from btc15_rollover_handoff_model_v1 import Staged
from btc15_rollover_alignment_gate_v1 import valid_15m
class T(unittest.TestCase):
 def test_exact(self):
  o=datetime(2026,9,22,17,0,tzinfo=timezone.utc);self.assertTrue(valid_15m(Staged("X",o,o+timedelta(minutes=15))))
 def test_bad_duration(self):
  o=datetime(2026,9,22,17,0,tzinfo=timezone.utc);self.assertFalse(valid_15m(Staged("X",o,o+timedelta(minutes=14))))
 def test_off_boundary(self):
  o=datetime(2026,9,22,17,1,tzinfo=timezone.utc);self.assertFalse(valid_15m(Staged("X",o,o+timedelta(minutes=15))))
