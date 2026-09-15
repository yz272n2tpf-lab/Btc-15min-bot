#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

import BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V2 as p


class RolloverDiscoveryProbeV2Tests(unittest.TestCase):
    def test_placeholder_zero_one_book_is_not_usable(self):
        m = {
            "yes_bid_dollars": "0.0000", "yes_ask_dollars": "0.0000",
            "no_bid_dollars": "1.0000", "no_ask_dollars": "1.0000",
        }
        self.assertFalse(p._usable_quotes(m))

    def test_normal_four_sided_book_is_usable(self):
        m = {
            "yes_bid_dollars": "0.4300", "yes_ask_dollars": "0.4400",
            "no_bid_dollars": "0.5600", "no_ask_dollars": "0.5700",
        }
        self.assertTrue(p._usable_quotes(m))

    def test_crossed_book_is_not_usable(self):
        m = {
            "yes_bid_dollars": "0.45", "yes_ask_dollars": "0.44",
            "no_bid_dollars": "0.55", "no_ask_dollars": "0.56",
        }
        self.assertFalse(p._usable_quotes(m))

    def test_missing_side_is_not_usable(self):
        m = {
            "yes_bid_dollars": "0.43", "yes_ask_dollars": "0.44",
            "no_bid_dollars": "0.56", "no_ask_dollars": None,
        }
        self.assertFalse(p._usable_quotes(m))

    def test_boundary_and_ticker_semantics_unchanged(self):
        now = datetime(2026, 9, 15, 18, 45, 2, tzinfo=timezone.utc)
        boundary, offset = p.boundary_context(now)
        self.assertEqual(boundary, datetime(2026, 9, 15, 18, 45, 0, tzinfo=timezone.utc))
        self.assertEqual(offset, 2.0)
        self.assertEqual(p.ticker_for_boundary(boundary), "KXBTC15M-26SEP151500-00")


if __name__ == "__main__":
    unittest.main()
