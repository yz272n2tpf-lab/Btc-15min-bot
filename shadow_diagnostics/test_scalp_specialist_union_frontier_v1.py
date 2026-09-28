#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

import scalp_specialist_union_frontier_v1 as s


class SpecialistUnionCoverageTests(unittest.TestCase):
    def snap(self, contract, seconds_left, ts):
        return {
            "record_type": "SNAPSHOT",
            "contract": contract,
            "seconds_left": seconds_left,
            "timestamp_utc": ts,
        }

    def test_quiet_contract_stays_in_true_coverage_denominator(self):
        rows = [
            self.snap("A", 890, "2026-09-16T00:00:10Z"),
            self.snap("A", 30, "2026-09-16T00:14:30Z"),
            self.snap("B", 885, "2026-09-16T00:15:15Z"),
            self.snap("B", 20, "2026-09-16T00:29:40Z"),  # B is quiet: no candidate rows.
            self.snap("C", 500, "2026-09-16T00:36:40Z"),  # Partial observation, excluded fail-closed.
            self.snap("C", 10, "2026-09-16T00:44:50Z"),
        ]
        u = s.full_contract_universe(rows)
        self.assertEqual(set(u), {"A", "B"})
        self.assertIn("B", u)

    def test_lane_tags_separate_lag_momentum_reversal_and_reentry(self):
        base = {
            "btc_brti_agree5": 1.0,
            "btc_brti_agree15": 1.0,
            "momentum_floor15": 20.0,
            "ask_move15": 0.01,
            "btc_move30_side": 30.0,
            "acceleration": 5.0,
            "structure_ok": 1.0,
            "btc_against_side": 0.0,
            "brti_against_side": 0.0,
            "dual_reversal_evidence": 0.0,
        }
        opps = [
            {**base, "contract": "A", "opportunity_index": 1, "side": "UP", "timestamp": datetime(2026, 9, 16, 0, 1, tzinfo=timezone.utc)},
            {**base, "contract": "A", "opportunity_index": 2, "side": "DOWN", "timestamp": datetime(2026, 9, 16, 0, 5, tzinfo=timezone.utc)},
            {**base, "contract": "A", "opportunity_index": 3, "side": "DOWN", "timestamp": datetime(2026, 9, 16, 0, 8, tzinfo=timezone.utc)},
        ]
        cuts = {
            "lag_momentum_floor15_min": 10.0,
            "lag_abs_ask15_max": 0.02,
            "momentum_btc30_min": 20.0,
            "momentum_acceleration_min": 0.0,
        }
        s.lane_tags(opps, cuts)
        self.assertIn("KALSHI_LAG", opps[0]["lane_tags"])
        self.assertIn("MOMENTUM", opps[0]["lane_tags"])
        self.assertEqual(opps[1]["primary_lane"], "REVERSAL_RECROSS")
        self.assertEqual(opps[2]["primary_lane"], "REENTRY_CONTINUATION")

    def test_true_coverage_uses_all_observed_contracts(self):
        rows = [
            {
                "contract": "A", "entry_ask": 0.35, "seconds_left": 500,
                "plus10": 1, "plus20": 0, "peak_gain": 0.14, "adverse_gain": -0.01,
                "protected_exit_gain": 0.08, "t10_sec": 40,
            },
            {
                "contract": "B", "entry_ask": 0.70, "seconds_left": 400,
                "plus10": 1, "plus20": 0, "peak_gain": 0.12, "adverse_gain": -0.02,
                "protected_exit_gain": 0.07, "t10_sec": 55,
            },
        ]
        z = s.score_with_true_coverage(rows, {"A", "B", "C", "D"})
        self.assertAlmostEqual(z["true_contract_coverage"], 0.50)
        self.assertAlmostEqual(z["affordable_true_contract_coverage_le50"], 0.25)

    def test_core_plus_rescue_preserves_coverage_without_forcing_every_contract(self):
        scored = [
            {"contract": "A", "specialist_union": True, "quality_prob": 0.91},
            {"contract": "A", "specialist_union": True, "quality_prob": 0.86},
            {"contract": "B", "specialist_union": True, "quality_prob": 0.56},
            {"contract": "C", "specialist_union": True, "quality_prob": 0.40},
        ]
        z = s.select_core_rescue(scored, {"A", "B", "C", "D"}, 0.80, 0.50)
        self.assertEqual(sum(r["selection_tier"] == "CORE" for r in z), 2)
        self.assertEqual(sum(r["selection_tier"] == "COVERAGE_RESCUE" for r in z), 1)
        self.assertEqual({r["contract"] for r in z}, {"A", "B"})
        self.assertNotIn("C", {r["contract"] for r in z})
        self.assertNotIn("D", {r["contract"] for r in z})


if __name__ == "__main__":
    unittest.main()
