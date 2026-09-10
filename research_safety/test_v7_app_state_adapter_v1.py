import unittest
from v7_app_state_adapter_v1 import adapt_event

class AdapterTests(unittest.TestCase):
    def test_watch_to_entry_to_hold_to_take_profit_to_exit(self):
        common = {"lane":"MOMENTUM_EXPANSION","ticker":"T","side":"UP"}
        w = adapt_event({**common,"event":"watch"}, None)
        e = adapt_event({**common,"event":"entry"}, w["state"])
        h = adapt_event({**common,"event":"hold"}, e["state"])
        p = adapt_event({**common,"event":"take_profit"}, h["state"])
        x = adapt_event({**common,"event":"exit"}, p["state"])
        self.assertEqual([w["state"],e["state"],h["state"],p["state"],x["state"]], ["SCALP WATCH","ENTRY","HOLD","TAKE PROFIT","EXIT"])
        self.assertFalse(x["orders_enabled"])

    def test_reversal_lane_supported(self):
        r = adapt_event({"event":"watch","lane":"ULTRA_CHEAP_REVERSAL"}, None)
        self.assertTrue(r["research_only"])

    def test_invalid_transition_fails_closed(self):
        with self.assertRaises(ValueError):
            adapt_event({"event":"hold","lane":"MOMENTUM_EXPANSION"}, None)

    def test_execution_fields_forbidden(self):
        with self.assertRaises(ValueError):
            adapt_event({"event":"entry","lane":"MOMENTUM_EXPANSION","quantity":1}, None)

    def test_unknown_lane_fails_closed(self):
        with self.assertRaises(ValueError):
            adapt_event({"event":"watch","lane":"OTHER"}, None)

if __name__ == "__main__":
    unittest.main()
