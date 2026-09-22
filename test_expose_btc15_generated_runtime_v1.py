import unittest
import expose_btc15_generated_runtime_v1 as x
class T(unittest.TestCase):
 def test_exposes_without_exec(self):
  s=x.extract()
  self.assertIn("python",s.lower() if "python" in s.lower() else s.lower())
  self.assertNotIn("os.execv",open(x.__file__,encoding="utf-8").read())
