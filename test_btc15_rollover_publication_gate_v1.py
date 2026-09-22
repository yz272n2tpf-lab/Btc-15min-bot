import unittest
from btc15_rollover_publication_gate_v1 import may_publish
class T(unittest.TestCase):
 def test_all_required(self): self.assertTrue(may_publish(handoff_verified=True,alignment_ok=True,provenance_ok=True,book_ready=True,source_fresh=True))
 def test_each_failure_blocks(self):
  keys=["handoff_verified","alignment_ok","provenance_ok","book_ready","source_fresh"]
  for k in keys:
   d={x:True for x in keys};d[k]=False
   self.assertFalse(may_publish(**d),k)
