import unittest
import btc15_rollover_static_regression_gate_v1 as g
class T(unittest.TestCase):
 def test_current_branch(self): self.assertEqual(g.scan(),[])
