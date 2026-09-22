import unittest
import btc15_rollover_evidence_snapshot_v1 as e
class T(unittest.TestCase):
 def test_gate_intentionally_closed(self):
  self.assertEqual(e.EVIDENCE["shadow_consecutive_passes"],4)
  self.assertFalse(e.ready(e.EVIDENCE))
