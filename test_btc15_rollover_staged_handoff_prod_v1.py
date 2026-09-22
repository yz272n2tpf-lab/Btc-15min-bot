import ast,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
import btc15_rollover_production_canary_v1 as c
class T(unittest.TestCase):
 def setUp(self):
  c._state={'staged':None,'last_report':None};self.o=datetime(2026,9,22,22,0,tzinfo=timezone.utc);c._state['staged']={'ticker':'KXBTC15M-X','open':self.o,'close':self.o+timedelta(minutes=15)}
 def test_preopen_blocked(self):self.assertIsNone(c.eligible(self.o-timedelta(microseconds=1)))
 def test_at_open_eligible(self):self.assertEqual(c.eligible(self.o)['ticker'],'KXBTC15M-X')
 def test_at_close_expired(self):self.assertIsNone(c.eligible(self.o+timedelta(minutes=15)))
 def test_core_syntax_and_exact_fetch(self):
  s=Path('bot_two_output_build_v4_13_profit_protection_shadow.py').read_text();ast.parse(s);self.assertIn('kalshi_get("/trade-api/v2/markets/" + _staged["ticker"])',s);self.assertIn('== _staged["ticker"]',s)
