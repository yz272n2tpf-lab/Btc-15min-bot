#!/usr/bin/env python3
import unittest
from unittest.mock import patch

import scalp_gap_recovery_live_review_v1 as v


class GapRecoveryLiveReviewTests(unittest.TestCase):
    def test_ready_analysis_is_read_only_and_compact(self):
        fake_report = {
            "status":"READY",
            "full_observed_contracts":272,
            "baseline_gap_summary":{"baseline_true_contract_coverage":242/272,"baseline_covered_contracts":242,"uncovered_contracts":30,"contracts_needed_to_reach_90pct":3},
            "complete_candidate_paths_in_uncovered_contracts":12,
            "all_candidate_path_summary":{"contracts_with_plus10":9},
            "by_gap_reason":{"BTC30_BELOW_BASELINE_15":{"contracts_with_plus10":4}},
            "descriptive_feature_separations":[{"feature":"btc_brti_agree15","normalized_median_difference":1.2}],
        }
        fake_base = {"ledger":[{"reason":"BTC30_BELOW_BASELINE_15","complete_candidate_paths":1,"hindsight_any_plus5":True,"hindsight_any_plus10":True,"hindsight_any_plus20":False,"hindsight_early_plus10":True,"hindsight_affordable_plus10":True,"hindsight_early_affordable_plus10":True,"hindsight_nonbaseline_plus10":True,"best_hindsight_peak_c":12.0}]}
        with patch.object(v.audit, "analyze", return_value=fake_report), patch.object(v.audit, "candidate_rows", return_value=([], fake_base)):
            out = v.analyze_rows([], sha="abc", source_bytes=123)
        self.assertTrue(out["ok"])
        self.assertFalse(out["orders"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["threshold_selection"])
        self.assertEqual(out["source_sha256"], "abc")
        self.assertIn("BTC30_BELOW_BASELINE_15", out["reason_recoverability"])
        compact = v.compact(out)
        self.assertEqual(compact["contracts_needed_to_reach_90pct"], 3)
        self.assertTrue(compact["development_only"])

    def test_failed_feature_audit_fails_closed(self):
        with patch.object(v.audit, "analyze", return_value={"status":"FAIL_CLOSED","orders":False}):
            out = v.analyze_rows([], sha="abc", source_bytes=1)
        self.assertFalse(out["ok"])
        self.assertFalse(out["orders"])
        self.assertTrue(out["shadow_only"])


if __name__ == "__main__":
    unittest.main()
