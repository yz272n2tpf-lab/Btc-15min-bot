import unittest
import btc15_rollover_change_scope_gate_v1 as g
class T(unittest.TestCase):
 def test_reject_protected(self): self.assertEqual(g.classify(["protected_early_rule.py"]),["protected_early_rule.py"])
 def test_allow_regression_artifact(self): self.assertEqual(g.classify(["btc15_rollover_handoff_model_v1.py"]),[])
