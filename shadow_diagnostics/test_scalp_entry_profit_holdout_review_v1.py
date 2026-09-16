#!/usr/bin/env python3
import unittest
import scalp_entry_profit_holdout_review_v1 as h


class EntryProfitHoldoutReviewTests(unittest.TestCase):
    def test_holdout_report_only_for_validation_selected_roles(self):
        # Validation prefers RUNNER; holdout would prefer LEGACY. Report must
        # still reveal RUNNER because holdout cannot select anything.
        result = {
            "policy_grid":[
                {"entry_policy":"IMMEDIATE","exit_policy":"RUNNER_10_4",
                 "validation":{"signals":50,"true_contract_coverage":1.0,"plus10_rate":.80,
                               "avg_executable_exit_gain_c":10,"entry_le50_rate":.45,
                               "avg_opportunities_per_covered_contract":1.5,"positive_exit_rate":.8},
                 "holdout":{"signals":50,"true_contract_coverage":1.0,"plus10_rate":.40}},
                {"entry_policy":"IMMEDIATE","exit_policy":"LEGACY_5_4",
                 "validation":{"signals":50,"true_contract_coverage":1.0,"plus10_rate":.75,
                               "avg_executable_exit_gain_c":9,"entry_le50_rate":.45,
                               "avg_opportunities_per_covered_contract":1.4,"positive_exit_rate":.8},
                 "holdout":{"signals":50,"true_contract_coverage":1.0,"plus10_rate":1.0}},
            ]
        }
        out = h.role_report(result)
        self.assertEqual(out["roles"]["FULL_RETENTION_QUALITY"]["exit_policy"], "RUNNER_10_4")
        self.assertEqual(out["roles"]["FULL_RETENTION_QUALITY"]["holdout"]["plus10_rate"], .40)
        self.assertFalse(out["holdout_used_for_selection"])
        self.assertTrue(out["retuning_after_holdout_prohibited"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])

    def test_coverage_is_labeled_baseline_contract_retention(self):
        result = {"policy_grid":[{
            "entry_policy":"IMMEDIATE","exit_policy":"RUNNER_10_4",
            "validation":{"signals":50,"true_contract_coverage":1.0,"plus10_rate":.8,
                          "avg_executable_exit_gain_c":10,"entry_le50_rate":.5,
                          "avg_opportunities_per_covered_contract":1.5,"positive_exit_rate":.8},
            "holdout":{"signals":45,"true_contract_coverage":.9,"plus10_rate":.7},
        }]}
        out = h.role_report(result)
        r = out["roles"]["FULL_RETENTION_QUALITY"]
        self.assertEqual(r["coverage_scope"], "BASELINE_QUALIFIED_SIGNAL_CONTRACTS")
        self.assertEqual(r["holdout_baseline_contract_retention"], .9)


if __name__ == "__main__":
    unittest.main()
