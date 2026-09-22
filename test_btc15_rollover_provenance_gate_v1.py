import unittest
from btc15_rollover_provenance_gate_v1 import provenance_ok
class T(unittest.TestCase):
 def test_all_match(self): self.assertTrue(provenance_ok("A","A","A","A"))
 def test_quote_mismatch(self): self.assertFalse(provenance_ok("A","A","B","A"))
 def test_target_mismatch(self): self.assertFalse(provenance_ok("A","A","A","B"))
 def test_active_mismatch(self): self.assertFalse(provenance_ok("A","B","B","B"))
