#!/usr/bin/env python3
import unittest

import BTC15_SCALP_COLLECTOR_FIELD_SOURCE_MAP_V1 as m


class CollectorFieldSourceMapTests(unittest.TestCase):
    def test_maps_exact_field_tokens_without_selecting_rules(self):
        source = """
accel = btc5 - btc15
btc5_norm = btc5 / recent_btc_range60
row = {"accel": accel, "btc5_norm": btc5_norm, "confirm_count": 2}
"""
        out = m.map_source(source, ("accel", "btc5", "btc5_norm", "confirm_count"))
        self.assertGreaterEqual(len(out["fields"]["accel"]), 2)
        self.assertGreaterEqual(len(out["fields"]["btc5"]), 2)
        self.assertGreaterEqual(len(out["fields"]["btc5_norm"]), 2)
        self.assertEqual(len(out["fields"]["confirm_count"]), 1)
        self.assertFalse(out["orders"])
        self.assertFalse(out["strategy_rule_selected"])
        self.assertFalse(out["auto_promote_allowed"])

    def test_word_boundaries_do_not_confuse_btc5_with_btc5_norm(self):
        out = m.map_source("btc5_norm = 1\n", ("btc5", "btc5_norm"))
        self.assertEqual(out["fields"]["btc5"], [])
        self.assertEqual(len(out["fields"]["btc5_norm"]), 1)


if __name__ == "__main__":
    unittest.main()
