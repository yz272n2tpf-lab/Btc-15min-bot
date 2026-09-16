#!/usr/bin/env python3
import unittest
from unittest.mock import patch

import scalp_specialist_union_live_review_v3 as v3


class LiveReviewV3Tests(unittest.TestCase):
    def test_failed_base_stays_fail_closed(self):
        base = {"ok": False, "status": "FAIL_CLOSED_SOURCE_OR_ANALYSIS_ERROR", "orders": False}
        out = v3.augment_analysis([], base)
        self.assertFalse(out["ok"])
        self.assertEqual(out["version"], v3.VERSION)
        self.assertFalse(out["orders"])

    def test_pareto_and_complementarity_are_added_without_promotion(self):
        universe = {"A": {}, "B": {}, "C": {}}
        split = {"A": "DEVELOPMENT", "B": "VALIDATION", "C": "HOLDOUT"}
        opps = [
            {"contract": "A", "split": "DEVELOPMENT", "lane_tags": ["MOMENTUM"]},
            {"contract": "B", "split": "VALIDATION", "lane_tags": ["KALSHI_LAG"]},
            {"contract": "C", "split": "HOLDOUT", "lane_tags": ["REENTRY_CONTINUATION"]},
        ]
        frontier = [
            {"name": "STRONG", "n": 20, "plus10_rate": .94, "true_contract_coverage": .92,
             "affordable_true_contract_coverage_le50": .80, "avg_entry_ask_c": 35, "avg_minutes_left": 7.0},
            {"name": "DOMINATED", "n": 20, "plus10_rate": .90, "true_contract_coverage": .90,
             "affordable_true_contract_coverage_le50": .70, "avg_entry_ask_c": 40, "avg_minutes_left": 6.0},
        ]
        base = {"ok": True, "status": "RESEARCH_SNAPSHOT_READY", "orders": False}

        def tag(rows, cuts):
            for r in rows:
                r.setdefault("lane_tags", ["MOMENTUM"])
                r["specialist_union"] = True
                r["primary_lane"] = r["lane_tags"][0]

        with patch.object(v3.union_v1, "full_contract_universe", return_value=universe), \
             patch.object(v3.union_v1, "split_universe", return_value=split), \
             patch.object(v3.q, "build_serial_opportunities", return_value=opps), \
             patch.object(v3.union_v1, "calibrate_lane_cuts", return_value={}), \
             patch.object(v3.union_v1, "lane_tags", side_effect=tag), \
             patch.object(v3.union_v2, "model_frontier", return_value=(frontier, None, None, [])), \
             patch.object(v3.complement, "unique_lane_coverage", return_value=[{"lane": "MOMENTUM"}]), \
             patch.object(v3.complement, "pairwise_overlap", return_value=[]), \
             patch.object(v3.complement, "subset_frontier", return_value=[]):
            out = v3.augment_analysis([], base)

        self.assertTrue(out["ok"])
        self.assertFalse(out["automatic_promotion"])
        self.assertEqual(out["multiobjective_pareto"]["pareto_rows"], 1)
        self.assertEqual(out["multiobjective_pareto"]["pareto_frontier"][0]["name"], "STRONG")
        self.assertIn("lane_complementarity", out)
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
