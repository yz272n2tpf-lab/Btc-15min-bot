import ast,unittest
from pathlib import Path
P=Path('bot_two_output_build_v4_13_rollover_prediscovery_integration_shadow.py')
class T(unittest.TestCase):
 def test_canary_wired(self):
  s=P.read_text(encoding='utf-8');ast.parse(s);self.assertIn('rollover_canary.observe(kalshi_get, parse_dt, now)',s);self.assertIn('rollover_canary.compare(_selected.get("ticker"), now)',s)
 def test_canary_module_has_no_order_api(self):
  s=Path('btc15_rollover_production_canary_v1.py').read_text(encoding='utf-8').lower()
  for x in ('create_order','place_order','submit_order'):self.assertNotIn(x,s)
