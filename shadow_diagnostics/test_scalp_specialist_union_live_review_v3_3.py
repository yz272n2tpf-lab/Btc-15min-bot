#!/usr/bin/env python3
import unittest
from unittest.mock import patch

import scalp_specialist_union_live_review_v3_3 as v


class LiveReviewV33Tests(unittest.TestCase):
    def test_compact_summary_keeps_decision_metrics_only(self):
        state = {
            "ok": True, "status": "RESEARCH_SNAPSHOT_READY", "source_sha256": "abc",
            "source_rows": 10, "full_observed_contracts": 3, "serial_opportunities": 4,
            "baseline": {"plus10_rate": .7},
            "specialist_union": {"lane_breakdown": {"KALSHI_LAG":{"n":2}}, "validation_selected_candidate":{"n":2}, "untouched_holdout_result":{"n":1}},
            "normalized_kalshi_lag": {"validation_selected_candidate":{"n":2}, "untouched_holdout_result":{"n":1}},
            "multiobjective_pareto": {"input_rows":5,"eligible_rows":4,"pareto_rows":2,"pareto_frontier":[{"n":2}]},
            "lane_complementarity": {"unique_lane_coverage":[{"lane":"KALSHI_LAG"}], "pairwise_overlap":[]},
            "schema_adapter": {"ready": True}, "schema_adaptation":"PASS_EXPLICIT_ALIASES_AND_UNITS_ONLY",
        }
        out = v.compact_summary(state)
        self.assertEqual(out["baseline"]["plus10_rate"], .7)
        self.assertEqual(out["pareto"]["pareto_rows"], 2)
        self.assertTrue(out["schema_ready"])
        self.assertFalse(out["orders"])
        self.assertNotIn("raw_schema_probe", out)

    def test_analyze_preserves_v32_result(self):
        base = {"ok": True, "status":"TEST", "orders":False, "schema_adapter":{"ready":True}}
        with patch.object(v.v32, "analyze_rows", return_value=base):
            out = v.analyze_rows([], sha="abc", source_bytes=1)
        self.assertEqual(out["status"], "TEST")
        self.assertEqual(out["version"], v.VERSION)
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
