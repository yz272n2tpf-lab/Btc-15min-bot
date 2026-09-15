#!/usr/bin/env python3
import unittest

import BTC15_SCALP_TRIGGER_TIGHTENING_RESEARCH_V1 as t


class TighteningResearchTests(unittest.TestCase):
    def rec(self, contract, ts, btc30, plus10, plus20=False, ask=.31, left=600):
        return {
            "contract": contract,
            "timestamp_utc": ts,
            "btc30": btc30,
            "plus10": plus10,
            "plus20": plus20,
            "entry_ask": ask,
            "seconds_left": left,
        }

    def test_price_and_time_are_never_filters(self):
        rows = []
        for i in range(20):
            c = f"C{i:02d}"
            rows.append(self.rec(c, f"2026-09-15T00:{i:02d}:00Z", 30, i % 2 == 0, ask=.88 if i == 0 else .07, left=130 if i == 1 else 800))
        out = t.analyze_records(rows)
        self.assertFalse(out["entry_price_filter_applied"])
        self.assertTrue(out["price_is_telemetry_only"])
        self.assertFalse(out["fixed_time_window_applied"])
        self.assertTrue(out["seconds_left_is_telemetry_only"])
        self.assertFalse(out["orders"])

    def test_nominee_requires_precision_gain_and_90pct_winner_retention(self):
        rows = []
        # 12 DEVELOPMENT contracts: 10 winners all >=25; 2 losers at btc30=15.
        for i in range(12):
            btc = 25 if i < 10 else 15
            win = i < 10
            rows.append(self.rec(f"D{i:02d}", f"2026-09-15T00:{i:02d}:00Z", btc, win))
        # 8 HOLDOUT contracts with enough sample at 25.
        for i in range(8):
            rows.append(self.rec(f"H{i:02d}", f"2026-09-15T01:{i:02d}:00Z", 25, i < 6))
        out = t.analyze_records(rows)
        self.assertIn(out["development_nominee_btc30_min"], {20.0, 25.0})
        self.assertTrue(out["holdout_review_ready"])
        self.assertFalse(out["auto_promote_allowed"])
        self.assertFalse(out["actionable_now"])

    def test_threshold_that_kills_too_many_winners_is_not_nominated(self):
        rows = []
        # Development baseline has 10 winners, but only 6 survive >=40.
        for i in range(12):
            btc = 50 if i < 6 else 20
            win = i < 10
            rows.append(self.rec(f"D{i:02d}", f"2026-09-15T00:{i:02d}:00Z", btc, win))
        for i in range(8):
            rows.append(self.rec(f"H{i:02d}", f"2026-09-15T01:{i:02d}:00Z", 20, i < 6))
        out = t.analyze_records(rows)
        self.assertNotEqual(out["development_nominee_btc30_min"], 40.0)
        self.assertFalse(out["protected_thresholds_changed"])

    def test_no_precision_gain_means_no_nominee(self):
        rows = []
        for i in range(20):
            rows.append(self.rec(f"C{i:02d}", f"2026-09-15T00:{i:02d}:00Z", 50 if i % 2 else 20, i % 2 == 0))
        out = t.analyze_records(rows)
        self.assertIsNone(out["development_nominee_btc30_min"])
        self.assertIsNone(out["holdout_nominee"])


if __name__ == "__main__":
    unittest.main()
