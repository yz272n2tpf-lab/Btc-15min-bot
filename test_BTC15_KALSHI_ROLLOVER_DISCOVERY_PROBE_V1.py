#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

import BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V1 as p


class RolloverDiscoveryProbeTests(unittest.TestCase):
    def test_pre_boundary_window_targets_upcoming_rollover(self):
        now = datetime(2026, 9, 15, 18, 44, 45, tzinfo=timezone.utc)
        boundary, offset = p.boundary_context(now)
        self.assertEqual(boundary, datetime(2026, 9, 15, 18, 45, 0, tzinfo=timezone.utc))
        self.assertEqual(offset, -15.0)

    def test_post_boundary_window_targets_just_started_contract(self):
        now = datetime(2026, 9, 15, 18, 45, 2, tzinfo=timezone.utc)
        boundary, offset = p.boundary_context(now)
        self.assertEqual(boundary, datetime(2026, 9, 15, 18, 45, 0, tzinfo=timezone.utc))
        self.assertEqual(offset, 2.0)

    def test_outside_probe_window_returns_none(self):
        now = datetime(2026, 9, 15, 18, 46, 30, tzinfo=timezone.utc)
        self.assertIsNone(p.boundary_context(now))

    def test_exact_ticker_for_1830_utc_rollover(self):
        boundary = datetime(2026, 9, 15, 18, 30, 0, tzinfo=timezone.utc)
        self.assertEqual(p.ticker_for_boundary(boundary), "KXBTC15M-26SEP151445-45")

    def test_exact_ticker_for_1845_utc_rollover(self):
        boundary = datetime(2026, 9, 15, 18, 45, 0, tzinfo=timezone.utc)
        self.assertEqual(p.ticker_for_boundary(boundary), "KXBTC15M-26SEP151500-00")

    def test_market_active_uses_open_close_clock(self):
        market = {
            "open_time": "2026-09-15T18:45:00Z",
            "close_time": "2026-09-15T19:00:00Z",
        }
        self.assertFalse(p._market_active(market, datetime(2026, 9, 15, 18, 44, 59, tzinfo=timezone.utc)))
        self.assertTrue(p._market_active(market, datetime(2026, 9, 15, 18, 45, 0, tzinfo=timezone.utc)))
        self.assertFalse(p._market_active(market, datetime(2026, 9, 15, 19, 0, 0, tzinfo=timezone.utc)))

    def test_quotes_require_all_four_valid_prices(self):
        good = {
            "yes_bid_dollars": "0.44", "yes_ask_dollars": "0.46",
            "no_bid_dollars": "0.54", "no_ask_dollars": "0.56",
        }
        self.assertTrue(p._quotes_valid(good))
        bad = dict(good)
        bad["yes_ask_dollars"] = None
        self.assertFalse(p._quotes_valid(bad))

    def test_evidence_records_first_offsets_only(self):
        ev = p.BoundaryEvidence("2026-09-15T18:45:00Z", "KXBTC15M-26SEP151500-00")
        ev.update(-10.0, {"includes_target": False, "active_target": False}, {"exists": True, "active": False, "quotes_valid": True})
        ev.update(2.0, {"includes_target": True, "active_target": True}, {"exists": True, "active": True, "quotes_valid": True})
        ev.update(4.0, {"includes_target": True, "active_target": True}, {"exists": True, "active": True, "quotes_valid": True})
        self.assertEqual(ev.first_exact_exists_offset, -10.0)
        self.assertEqual(ev.first_exact_quoted_offset, -10.0)
        self.assertEqual(ev.first_exact_active_offset, 2.0)
        self.assertEqual(ev.first_broad_includes_offset, 2.0)
        self.assertEqual(ev.first_broad_active_offset, 2.0)


if __name__ == "__main__":
    unittest.main()
