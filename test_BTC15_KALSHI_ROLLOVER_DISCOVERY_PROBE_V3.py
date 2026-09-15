#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import BTC15_KALSHI_ROLLOVER_DISCOVERY_PROBE_V3 as m


class RolloverProbeV3Tests(unittest.TestCase):
    def setUp(self):
        with m.LOCK:
            m.EVIDENCE.clear()

    def test_pre_cutoff_boundary_is_ignored(self):
        now = datetime(2026, 9, 15, 19, 45, 2, tzinfo=timezone.utc)
        self.assertIsNone(m.probe_once(now))
        self.assertEqual(m.EVIDENCE, {})

    def test_cutoff_boundary_is_eligible_but_placeholders_not_usable(self):
        now = datetime(2026, 9, 15, 20, 0, 2, tzinfo=timezone.utc)
        exact = {
            "http": 200,
            "exists": True,
            "returned_ticker": m.v2.ticker_for_boundary(datetime(2026, 9, 15, 20, 0, tzinfo=timezone.utc)),
            "identity_match": True,
            "status": "active",
            "active": True,
            "quotes_valid": False,
            "open_time": "2026-09-15T20:00:00Z",
            "close_time": "2026-09-15T20:15:00Z",
            "yes_bid": 0.0,
            "yes_ask": 0.0,
            "no_bid": 1.0,
            "no_ask": 1.0,
            "error": None,
        }
        broad = {"http": 200, "includes_target": False, "active_target": False, "count": 1, "error": None}
        with patch.object(m.v2.v1, "broad_open_search", return_value=broad), patch.object(m.v2.v1, "exact_market_fetch", return_value=exact):
            row = m.probe_once(now)
        self.assertIsNotNone(row)
        ev = next(iter(m.EVIDENCE.values()))
        self.assertIsNone(ev.first_exact_active_quoted_offset)
        self.assertTrue(ev.direct_identity_match_all)
        self.assertTrue(ev.direct_clock_match_all)

    def test_gate_rows_include_only_summarized_v3_evidence(self):
        ev = m.v2.BoundaryEvidence("2026-09-15T20:00:00Z", "T")
        ev.first_exact_active_quoted_offset = 10.0
        ev.first_broad_active_offset = 30.0
        ev.summary_printed = True
        with m.LOCK:
            m.EVIDENCE[ev.boundary_utc] = ev
        rows = m._gate_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["exact_active_quoted"], 10.0)
        self.assertEqual(rows[0]["broad_active"], 30.0)

    def test_empty_store_starts_collecting(self):
        s = m.gate.score(m._gate_rows())
        self.assertEqual(s["status"], "COLLECTING_FRESH_OPERATIONAL_REPLICATION")
        self.assertEqual(s["rollovers"], 0)
        self.assertFalse(s["pass"])
        self.assertFalse(s["orders"])


if __name__ == "__main__":
    unittest.main()
