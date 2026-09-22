import unittest
from datetime import datetime,timezone,timedelta
from btc15_rollover_stage_selector_v1 import choose
class T(unittest.TestCase):
 def test_nearest_future_exact_series(self):
  n=datetime(2026,9,22,15,0,tzinfo=timezone.utc)
  rows=[{"ticker":"KXBTC15M-LATE","open_time":(n+timedelta(minutes=30)).isoformat(),"close_time":(n+timedelta(minutes=45)).isoformat()},
        {"ticker":"OTHER","open_time":(n+timedelta(minutes=5)).isoformat(),"close_time":(n+timedelta(minutes=20)).isoformat()},
        {"ticker":"KXBTC15M-NEXT","open_time":(n+timedelta(minutes=15)).isoformat(),"close_time":(n+timedelta(minutes=30)).isoformat()}]
  self.assertEqual(choose(rows,n)[2],"KXBTC15M-NEXT")
 def test_reject_current_or_bad_window(self):
  n=datetime(2026,9,22,15,0,tzinfo=timezone.utc)
  rows=[{"ticker":"KXBTC15M-CUR","open_time":n.isoformat(),"close_time":(n+timedelta(minutes=15)).isoformat()},
        {"ticker":"KXBTC15M-BAD","open_time":(n+timedelta(minutes=15)).isoformat(),"close_time":n.isoformat()}]
  self.assertIsNone(choose(rows,n))
