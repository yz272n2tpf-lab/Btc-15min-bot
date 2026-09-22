import unittest
from datetime import datetime,timezone,timedelta
import btc15_rollover_prediscovery_shadow_v1 as p
class T(unittest.TestCase):
 def test_next_only_future(self):
  t=datetime(2026,9,22,12,0,tzinfo=timezone.utc)
  rows=[{"ticker":"KXBTC15M-A","open_time":(t-timedelta(minutes=15)).isoformat(),"close_time":t.isoformat()},
        {"ticker":"KXBTC15M-B","open_time":(t+timedelta(minutes=15)).isoformat(),"close_time":(t+timedelta(minutes=30)).isoformat()}]
  q=p.choose_next(rows,t);self.assertEqual(q[2]["ticker"],"KXBTC15M-B")
