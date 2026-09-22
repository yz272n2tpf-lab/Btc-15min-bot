import unittest
from btc15_rollover_idempotency_gate_v1 import accept_once
class T(unittest.TestCase):
 def test_first_accept(self): self.assertEqual(accept_once(None,"A"),("A",True))
 def test_duplicate_blocked(self): self.assertEqual(accept_once("A","A"),("A",False))
 def test_next_accept(self): self.assertEqual(accept_once("A","B"),("B",True))
 def test_empty_blocked(self): self.assertEqual(accept_once("A",None),("A",False))
