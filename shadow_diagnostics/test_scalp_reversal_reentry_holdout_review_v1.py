#!/usr/bin/env python3
import unittest
import scalp_reversal_reentry_holdout_review_v1 as h


class ReversalReentryHoldoutReviewTests(unittest.TestCase):
    def test_fixed_lanes_only_and_no_selection(self):
        result = {
            "status":"REVERSAL_REENTRY_LADDER_READY",
            "baseline_candidate_gate_unchanged":True,
            "legacy_protection_lifecycle_unchanged":True,
            "serial_meta":{"serial_candidate_count":10},
            "validation":{"REENTRY_CONTINUATION":{"plus10_rate":.8},"REVERSAL_RECROSS":{"plus10_rate":.7}},
            "holdout":{"REENTRY_CONTINUATION":{"plus10_rate":.1},"REVERSAL_RECROSS":{"plus10_rate":1.0}},
        }
        out = h.compact(result)
        self.assertEqual(out["fixed_lanes"], ["REENTRY_CONTINUATION","REVERSAL_RECROSS"])
        self.assertFalse(out["holdout_used_for_selection"])
        self.assertTrue(out["retuning_after_holdout_prohibited"])
        self.assertFalse(out["automatic_selection"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])
        self.assertEqual(out["coverage_scope"], "SERIAL_ELIGIBLE_CONTRACTS_ONLY")

    def test_bad_analysis_fails_closed(self):
        out = h.compact({"status":"BAD"})
        self.assertEqual(out["status"], "FAIL_CLOSED_BAD_ANALYSIS")


if __name__ == "__main__":
    unittest.main()
