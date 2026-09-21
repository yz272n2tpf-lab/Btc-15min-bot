import unittest
import btc15_rollover_alternate_discovery_probe_v1 as p
class T(unittest.TestCase):
 def test_tickers_nested(self):
  x={"events":[{"markets":[{"ticker":"KXBTC15M-A"},{"ticker":"OTHER"}]},{"ticker":"KXBTC15M-B"}]}
  self.assertEqual(p.tickers(x),["KXBTC15M-A","KXBTC15M-B"])
 def test_no_order_surface(self):
  self.assertFalse(hasattr(p,"place_order"))
if __name__=="__main__":unittest.main()
