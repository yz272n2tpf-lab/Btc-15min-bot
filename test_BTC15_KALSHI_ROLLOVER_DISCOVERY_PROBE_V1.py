#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

import BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V1 as p

TARGET = "KXBTC15M-26SEP151500-00"


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
        self.assertIsNone(p.boundary_context(datetime(2026, 9, 15, 18, 46, 30, tzinfo=timezone.utc)))

    def test_exact_ticker_for_1830_utc_rollover(self):
        boundary = datetime(2026, 9, 15, 18, 30, 0, tzinfo=timezone.utc)
        self.assertEqual(p.ticker_for_boundary(boundary), "KXBTC15M-26SEP151445-45")

    def test_exact_ticker_for_1845_utc_rollover(self):
        boundary = datetime(2026, 9, 15, 18, 45, 0, tzinfo=timezone.utc)
        self.assertEqual(p.ticker_for_boundary(boundary), TARGET)

    def test_market_active_uses_open_close_clock(self):
        market = {"open_time": "2026-09-15T18:45:00Z", "close_time": "2026-09-15T19:00:00Z"}
        self.assertFalse(p._market_active(market, datetime(2026, 9, 15, 18, 44, 59, tzinfo=timezone.utc)))
        self.assertTrue(p._market_active(market, datetime(2026, 9, 15, 18, 45, 0, tzinfo=timezone.utc)))
        self.assertFalse(p._market_active(market, datetime(2026, 9, 15, 19, 0, 0, tzinfo=timezone.utc)))

    def test_clock_match_requires_exact_expected_window(self):
        boundary = datetime(2026, 9, 15, 18, 45, 0, tzinfo=timezone.utc)
        good = {"open_time": "2026-09-15T18:45:00Z", "close_time": "2026-09-15T19:00:00Z"}
        bad = {"open_time": "2026-09-15T18:30:00Z", "close_time": "2026-09-15T18:45:00Z"}
        self.assertTrue(p._clock_matches(good, boundary))
        self.assertFalse(p._clock_matches(bad, boundary))

    def test_quotes_require_all_four_valid_prices(self):
        good = {"yes_bid_dollars": "0.44", "yes_ask_dollars": "0.46", "no_bid_dollars": "0.54", "no_ask_dollars": "0.56"}
        self.assertTrue(p._quotes_valid(good))
        bad = dict(good)
        bad["yes_ask_dollars"] = None
        self.assertFalse(p._quotes_valid(bad))

    def _exact(self, *, active, identity=True, clock=True):
        return {
            "exists": True,
            "identity_match": identity,
            "active": active,
            "quotes_valid": True,
            "open_time": "2026-09-15T18:45:00Z" if clock else "2026-09-15T18:30:00Z",
            "close_time": "2026-09-15T19:00:00Z" if clock else "2026-09-15T18:45:00Z",
        }

    def test_evidence_records_first_offsets_and_active_quoted(self):
        ev = p.BoundaryEvidence("2026-09-15T18:45:00Z", TARGET)
        ev.update(-10.0, {"includes_target": False, "active_target": False}, self._exact(active=False))
        ev.update(2.0, {"includes_target": True, "active_target": True}, self._exact(active=True))
        ev.update(4.0, {"includes_target": True, "active_target": True}, self._exact(active=True))
        self.assertEqual(ev.first_exact_exists_offset, -10.0)
        self.assertEqual(ev.first_exact_quoted_offset, -10.0)
        self.assertEqual(ev.first_exact_active_offset, 2.0)
        self.assertEqual(ev.first_exact_active_quoted_offset, 2.0)
        self.assertEqual(ev.first_broad_includes_offset, 2.0)
        self.assertEqual(ev.first_broad_active_offset, 2.0)
        self.assertTrue(ev.direct_clock_match_all)
        self.assertTrue(ev.direct_identity_match_all)
        self.assertFalse(ev.wrong_clock_seen)
        self.assertFalse(ev.wrong_identity_seen)

    def test_wrong_clock_is_sticky_failure(self):
        ev = p.BoundaryEvidence("2026-09-15T18:45:00Z", TARGET)
        ev.update(1.0, {"includes_target": False, "active_target": False}, self._exact(active=True, clock=False))
        ev.update(3.0, {"includes_target": True, "active_target": True}, self._exact(active=True))
        self.assertFalse(ev.direct_clock_match_all)
        self.assertTrue(ev.wrong_clock_seen)
        self.assertEqual(ev.first_exact_active_quoted_offset, 3.0)

    def test_wrong_identity_is_sticky_and_cannot_count_active_quoted(self):
        ev = p.BoundaryEvidence("2026-09-15T18:45:00Z", TARGET)
        ev.update(1.0, {"includes_target": False, "active_target": False}, self._exact(active=True, identity=False))
        self.assertIsNone(ev.first_exact_active_quoted_offset)
        ev.update(3.0, {"includes_target": True, "active_target": True}, self._exact(active=True))
        self.assertEqual(ev.first_exact_active_quoted_offset, 3.0)
        self.assertFalse(ev.direct_identity_match_all)
        self.assertTrue(ev.wrong_identity_seen)


if __name__ == "__main__":
    unittest.main()
