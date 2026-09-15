#!/usr/bin/env python3
import csv
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import BTC15_FINAL_FORWARD_SCORECARD_V1 as m


class FinalForwardScorecardTests(unittest.TestCase):
    def test_price_bands_keep_expensive_lock_separate(self):
        self.assertEqual(m.price_band(0.30), "25-35C")
        self.assertEqual(m.price_band(0.45), "36-50C")
        self.assertEqual(m.price_band(0.70), "51-70C")
        self.assertEqual(m.price_band(0.80), "71-85C")
        self.assertEqual(m.price_band(0.94), ">85C")

    def test_extract_lock_uses_protected_main_authority(self):
        row = {
            "contract": "TEST-1",
            "timer": {"seconds_left": 420.0},
            "market": {
                "target": 100000.0,
                "up_bid": 0.93,
                "up_ask": 0.94,
                "down_bid": 0.06,
                "down_ask": 0.07,
            },
            "final": {
                "ready": True,
                "side": "UP",
                "confidence": 0.92,
                "recorded_final_call": False,
            },
        }
        rec = m.extract_first_lock(row, datetime(2026, 9, 15, 16, 50, tzinfo=timezone.utc))
        self.assertIsNotNone(rec)
        self.assertEqual(rec["side"], "UP")
        self.assertAlmostEqual(rec["minutes_left"], 7.0)
        self.assertAlmostEqual(rec["preferred_ask"], 0.94)
        self.assertFalse(rec["ask_at_or_below_50c"])
        self.assertEqual(rec["price_band"], ">85C")
        self.assertFalse(rec["orders"])
        self.assertTrue(rec["manual_execution_only"])

    def test_non_locked_final_is_not_recorded(self):
        row = {
            "contract": "TEST-2",
            "timer": {"seconds_left": 600.0},
            "market": {"up_ask": 0.40, "down_ask": 0.61},
            "final": {
                "ready": False,
                "side": "UP",
                "confidence": 0.89,
                "recorded_final_call": False,
            },
        }
        self.assertIsNone(m.extract_first_lock(row))

    def test_historical_summary_reports_accuracy_coverage_price_and_timing(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            calls = td / "calls.csv"
            manifest = td / "manifest.csv"
            with manifest.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=["ticker"])
                w.writeheader()
                for t in ["A", "B", "C", "D"]:
                    w.writerow({"ticker": t})
            with calls.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(
                    fh,
                    fieldnames=["ticker", "preferred_ask", "remaining", "preferred_fair", "correct"],
                )
                w.writeheader()
                w.writerow({"ticker": "A", "preferred_ask": 0.30, "remaining": 6, "preferred_fair": 0.91, "correct": "True"})
                w.writerow({"ticker": "B", "preferred_ask": 0.94, "remaining": 4, "preferred_fair": 0.95, "correct": "True"})
            s = m.summarize_historical(calls, manifest)
            self.assertEqual(s["universe_contracts"], 4)
            self.assertEqual(s["qualified_final_calls"], 2)
            self.assertAlmostEqual(s["qualified_accuracy"], 1.0)
            self.assertAlmostEqual(s["final_only_coverage"], 0.5)
            self.assertEqual(s["ask_le_50c_n"], 1)
            self.assertAlmostEqual(s["ask_le_50c_rate"], 0.5)
            self.assertEqual(s["by_price_band"][">85C"]["n"], 1)

    def test_live_summary_does_not_confuse_final_coverage_with_union(self):
        state = {
            "observed_contracts": ["A", "B"],
            "lock_records": {
                "A": {
                    "contract": "A",
                    "side": "UP",
                    "preferred_ask": 0.94,
                    "minutes_left": 7.0,
                    "ask_at_or_below_50c": False,
                }
            },
            "settlements": {"A": "UP"},
        }
        s = m.summarize_live_snapshot(state)
        self.assertAlmostEqual(s["qualified_accuracy"], 1.0)
        self.assertAlmostEqual(s["final_only_coverage"], 0.5)
        self.assertEqual(s["ask_le_50c_n"], 0)
        self.assertFalse(s["numeric_flip_risk_validated"])
        self.assertFalse(s["protected_final_thresholds_changed"])
        self.assertFalse(s["price_filter_applied"])
        self.assertFalse(s["auto_promote_allowed"])
        self.assertFalse(s["production_behavior_changed"])
        self.assertFalse(s["orders"])
        self.assertTrue(s["manual_execution_only"])

    def test_live_cutoff_is_prefrozen(self):
        self.assertEqual(m.LIVE_CUTOFF_RAW, "2026-09-15T16:45:00Z")
        self.assertGreaterEqual(m.MIN_LIVE_OBSERVED_SMOKE, 20)
        self.assertGreaterEqual(m.MIN_LIVE_SETTLED_LOCKS_SMOKE, 10)


if __name__ == "__main__":
    unittest.main()
