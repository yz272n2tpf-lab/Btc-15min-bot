import unittest
import replay_btc15_rollover_live_evidence_v1 as r
class T(unittest.TestCase):
 def test_four_proven_cases(self): self.assertEqual(len(r.replay()),4)
