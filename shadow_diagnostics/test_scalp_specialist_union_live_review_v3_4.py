#!/usr/bin/env python3
import unittest
from unittest.mock import patch

import scalp_specialist_union_live_review_v3_4 as v


class LiveReviewV34Tests(unittest.TestCase):
    def test_compact_role_separates_validation_from_holdout(self):
        role = {
            "validation_selection": {
                "model":"LOGISTIC","core_threshold":.8,"rescue_threshold":.6,
                "n":30,"plus10_rate":.95,"true_contract_coverage":.50,
                "affordable_true_contract_coverage_le50":.30,"avg_entry_ask_c":49.0,"avg_minutes_left":9.0,
            },
            "holdout": {
                "n":20,"plus5_rate":.9,"plus10_rate":.8,"plus20_rate":.4,
                "true_contract_coverage":.45,"affordable_true_contract_coverage_le50":.25,
                "avg_entry_ask_c":48.0,"avg_minutes_left":8.5,"core_plus10_rate":.85,
                "coverage_rescue_plus10_rate":.7,"core_true_contract_coverage":.3,"coverage_gain_from_rescue":.15,
            },
        }
        out = v.compact_role(role)
        self.assertEqual(out["validation"]["plus10_rate"], .95)
        self.assertEqual(out["holdout"]["plus10_rate"], .8)
        self.assertEqual(out["validation"]["core_threshold"], .8)
        self.assertNotIn("core_threshold", out["holdout"])

    def test_failed_v33_state_never_reveals_tier_holdout(self):
        with patch.object(v.v33, "analyze_rows", return_value={"ok":False,"status":"FAIL_CLOSED","orders":False}):
            out = v.analyze_rows([], sha="abc", source_bytes=1)
        self.assertFalse(out["ok"])
        self.assertNotIn("tiered_validation_freeze", out)
        self.assertEqual(out["version"], v.VERSION)

    def test_missing_validation_frontier_fails_closed(self):
        base = {"ok":True,"status":"RESEARCH_SNAPSHOT_READY","orders":False,"multiobjective_pareto":{"pareto_frontier":[]}}
        with patch.object(v.v33, "analyze_rows", return_value=base):
            out = v.analyze_rows([], sha="abc", source_bytes=1)
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], "FAIL_CLOSED_NO_VALIDATION_FRONTIER_FOR_TIER_FREEZE")
        self.assertFalse(out["automatic_promotion"])

    def test_successful_analysis_uses_validation_frontier_then_report_only_holdout(self):
        frontier = [{"name":"frozen","n":20,"covered_contracts":10,"plus10_rate":.95,"true_contract_coverage":.5}]
        base = {
            "ok":True,"status":"RESEARCH_SNAPSHOT_READY","orders":False,
            "multiobjective_pareto":{"pareto_frontier":frontier},
        }
        audit = {
            "version":"TIER_TEST","roles":{
                "PRECISION_CORE":{"validation_selection":{"model":"LOGISTIC","n":20,"plus10_rate":.95},"holdout":{"n":10,"plus10_rate":.8}},
                "BALANCED_90":{"validation_selection":{"model":"LOGISTIC","n":20,"plus10_rate":.91},"holdout":{"n":12,"plus10_rate":.75}},
                "COVERAGE_FRONTIER":{"validation_selection":{"model":"LOGISTIC","n":20,"plus10_rate":.85},"holdout":{"n":15,"plus10_rate":.7}},
            }
        }
        with patch.object(v.v33, "analyze_rows", return_value=base), \
             patch.object(v.adapter, "adapt_rows", return_value=[]), \
             patch.object(v.union_v1, "full_contract_universe", return_value={"A":{"contract":"A"}}), \
             patch.object(v.union_v1, "split_universe", return_value={"A":"DEVELOPMENT"}), \
             patch.object(v.q, "build_serial_opportunities", return_value=[]), \
             patch.object(v.union_v1, "calibrate_lane_cuts", return_value={}), \
             patch.object(v.union_v1, "lane_tags"), \
             patch.object(v.tiered, "audit", return_value=audit) as tier_audit:
            out = v.analyze_rows([], sha="abc", source_bytes=1)

        tier_audit.assert_called_once()
        self.assertEqual(out["tiered_holdout_summary"]["PRECISION_CORE"]["holdout"]["plus10_rate"], .8)
        self.assertTrue(out["tiered_holdout_summary"]["retuning_after_holdout_prohibited"])
        self.assertTrue(out["tiered_holdout_summary"]["forward_freeze_required_before_any_promotion"])
        self.assertFalse(out["automatic_promotion"])


if __name__ == "__main__":
    unittest.main()
