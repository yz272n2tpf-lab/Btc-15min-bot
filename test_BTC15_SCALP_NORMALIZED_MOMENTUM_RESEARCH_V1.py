#!/usr/bin/env python3
import unittest

import BTC15_SCALP_NORMALIZED_MOMENTUM_RESEARCH_V1 as m


class NormalizedMomentumResearchTests(unittest.TestCase):
    def records(self):
        rows = []
        # Ten chronological contracts, four serial opportunities each. The first
        # six contracts (24 records) become DEVELOPMENT; final four (16) HOLDOUT.
        for c in range(10):
            for j in range(4):
                i = c * 4 + j
                split_i = i if c < 6 else i - 24
                if c < 6:
                    # Development: 18/24 winners. Four of six losers have the
                    # lowest btc5_norm values; all winners are >=0.50.
                    winner = i < 18
                    if winner:
                        b5n = 0.50 + 0.01 * (i % 10)
                    else:
                        loser_rank = i - 18
                        b5n = [0.10, 0.20, 0.30, 0.40, 0.60, 0.70][loser_rank]
                else:
                    # Holdout: 12/16 winners. Three of four losers are below the
                    # development-derived 0.50 floor, so a good nominee retains
                    # all winners and >80% of selections.
                    winner = split_i < 12
                    if winner:
                        b5n = 0.55 + 0.01 * (split_i % 8)
                    else:
                        loser_rank = split_i - 12
                        b5n = [0.20, 0.30, 0.40, 0.65][loser_rank]
                rows.append({
                    "contract": f"C{c:02d}",
                    "candidate_id": f"x{i:02d}",
                    "timestamp_utc": f"2026-09-{15 + c//8:02d}T{c%8:02d}:{j:02d}:00Z",
                    "plus10": winner,
                    "plus20": winner and j % 2 == 0,
                    "btc5_norm": b5n,
                    # Deliberately uninformative second predeclared feature.
                    "btc15_norm": 0.50,
                })
        return rows

    def test_development_nomination_and_holdout_support_require_retention(self):
        out = m.analyze_records(self.records())
        self.assertEqual(out["development_n"], 24)
        self.assertEqual(out["holdout_n"], 16)
        nominee = out["development_nominee"]
        self.assertIsNotNone(nominee)
        self.assertEqual(nominee["feature"], "btc5_norm")
        self.assertGreaterEqual(nominee["plus10_winner_retention"], .90)
        self.assertGreaterEqual(nominee["selected_share_retained"], .80)
        self.assertGreaterEqual(nominee["plus10_precision_lift"], .03)
        self.assertTrue(out["holdout_review_ready"])
        self.assertTrue(out["holdout_supports_nominee"])
        hold = out["holdout_nominee"]
        self.assertGreaterEqual(hold["plus10_winner_retention"], .90)
        self.assertGreaterEqual(hold["selected_share_retained"], .80)
        self.assertGreaterEqual(hold["plus10_precision_lift"], .05)

    def test_holdout_rejects_nominee_that_drops_too_many_winners(self):
        rows = self.records()
        # Force two holdout winners below the development floor. Development is
        # unchanged, so the same nominee must face a genuinely worse holdout.
        holdout = [r for r in rows if r["contract"] >= "C06"]
        winner_rows = [r for r in holdout if r["plus10"]]
        winner_rows[0]["btc5_norm"] = 0.10
        winner_rows[1]["btc5_norm"] = 0.20
        out = m.analyze_records(rows)
        self.assertIsNotNone(out["development_nominee"])
        self.assertTrue(out["holdout_review_ready"])
        self.assertFalse(out["holdout_supports_nominee"])
        self.assertLess(out["holdout_nominee"]["plus10_winner_retention"], .90)

    def test_no_dev_nominee_when_precision_does_not_improve(self):
        rows = self.records()
        # Make both features constant in development, so every floor keeps the
        # entire development sample and precision lift is exactly zero.
        for r in rows:
            if r["contract"] < "C06":
                r["btc5_norm"] = 0.50
                r["btc15_norm"] = 0.50
        out = m.analyze_records(rows)
        self.assertIsNone(out["development_nominee"])
        self.assertFalse(out["holdout_review_ready"])
        self.assertFalse(out["holdout_supports_nominee"])

    def test_safety_envelope_never_promotes_or_adds_price_time_rules(self):
        out = m.analyze_records(self.records())
        self.assertEqual(out["features_predeclared"], ["btc5_norm", "btc15_norm"])
        self.assertFalse(out["orders"])
        self.assertTrue(out["manual_execution_only"])
        self.assertFalse(out["entry_price_filter_applied"])
        self.assertFalse(out["fixed_time_window_applied"])
        self.assertFalse(out["protected_thresholds_changed"])
        self.assertFalse(out["stop_loss_rule_selected"])
        self.assertFalse(out["raw_btc_or_brti_level_filter_applied"])
        self.assertFalse(out["auto_promote_allowed"])
        self.assertFalse(out["actionable_now"])


if __name__ == "__main__":
    unittest.main()
