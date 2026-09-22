import tempfile,unittest
from pathlib import Path
import btc15_volume_retention_planner_v1 as p
class T(unittest.TestCase):
 def test_read_only_plan(self):
  with tempfile.TemporaryDirectory() as d:
   for n in p.FILES.values(): Path(d,n).write_text("x"*10)
   q=p.plan(d);self.assertFalse(q["mutations"]);self.assertFalse(q["orders"]);self.assertEqual(len(q["files"]),3)
