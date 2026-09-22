import ast, unittest
from pathlib import Path
P=Path("bot_two_output_build_v4_13_rollover_prediscovery_integration_shadow.py")
class T(unittest.TestCase):
 def test_syntax(self): ast.parse(P.read_text(encoding="utf-8"))
 def test_no_order_calls_added(self):
  s=P.read_text(encoding="utf-8"); block=s[s.index("# === ROLLOVER PRE-DISCOVERY"):s.index("# === ROLLOVER PRE-DISCOVERY INTEGRATION SHADOW V1 END ===")]
  for x in ("create_order","place_order","submit_order"): self.assertNotIn(x,block)
 def test_open_boundary_guard_present(self):
  s=P.read_text(encoding="utf-8"); self.assertIn('now<st["open"]',s); self.assertIn('now>=st["close"]',s)
