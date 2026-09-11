#!/usr/bin/env python3
import unittest

from unified_scalp_tightening_stability_gate_v1 import evaluate_report


def base_report(*, decision="TIGHTEN", contracts=None, min_contracts=3, blocked_success=0, blocked_fast=0):
    if contracts is None:
        contracts = ["F1", "F2", "F3", "F4"]
    return {
        "schema": "unified-scalp-tightening-candidate-audit-v1",
        "current_architecture": "ONE_UNIFIED_SCALP_EXPANSION_ENGINE",
        "research_only": True,
        "signal_only": True,
        "production_promotion": "NOT_PERFORMED",
        "qualification_threshold_change_performed": False,
        "frozen_final_early_ladders_changed": False,
        "price_rule_feature_allowed": False,
        "price_zones_are_diagnostic_only": True,
        "cheap_price_override": False,
        "legacy_reversal_graduation_allowed": False,
        "proposal_errors": [],
        "unknown_lane_records": 0,
        "research_candidate_min_independent_failure_contracts": min_contracts,
        "would_block_failure_contracts": contracts,
        "would_block_success_n": blocked_success,
        "would_block_fast_success_n": blocked_fast,
        "by_diagnostic_price_zone": {
            "3_7C": {"n": 2}, "7_15C": {"n": 3}, "15_30C": {"n": 4}, "30_45C": {"n": 5}
        },
        "decision": {"candidate_tightening": decision},
    }


class TighteningStabilityGateTests(unittest.TestCase):
    def test_exact_minimum_becomes_more_data_under_loco(self):
        report = evaluate_report(base_report(contracts=["F1", "F2", "F3"]))
        self.assertEqual(report["decision"]["candidate_tightening"], "MORE_DATA")
        self.assertEqual(report["leave_one_out_min_support"], 2)
        self.assertTrue(all(not fold["passes_min_support"] for fold in report["leave_one_out_folds"]))

    def test_minimum_plus_one_survives_loco(self):
        report = evaluate_report(base_report(contracts=["F1", "F2", "F3", "F4"]))
        self.assertEqual(report["decision"]["candidate_tightening"], "TIGHTEN")
        self.assertEqual(report["leave_one_out_min_support"], 3)
        self.assertTrue(all(fold["passes_min_support"] for fold in report["leave_one_out_folds"]))
        self.assertFalse(report["qualification_threshold_change_performed"])

    def test_fast_winner_is_rejected(self):
        report = evaluate_report(base_report(blocked_success=1, blocked_fast=1))
        self.assertEqual(report["decision"]["candidate_tightening"], "REJECT")

    def test_nonfast_winner_counterexample_requires_more_data(self):
        report = evaluate_report(base_report(blocked_success=1, blocked_fast=0))
        self.assertEqual(report["decision"]["candidate_tightening"], "MORE_DATA")

    def test_price_or_cheap_override_fails_closed(self):
        source = base_report()
        source["cheap_price_override"] = True
        source["price_rule_feature_allowed"] = True
        report = evaluate_report(source)
        self.assertEqual(report["decision"]["candidate_tightening"], "REJECT")
        self.assertIn("CHEAP_PRICE_OVERRIDE_FORBIDDEN", report["stability_errors"])
        self.assertIn("PRICE_RULE_FEATURE_FORBIDDEN", report["stability_errors"])

    def test_legacy_reversal_graduation_fails_closed(self):
        source = base_report()
        source["legacy_reversal_graduation_allowed"] = True
        report = evaluate_report(source)
        self.assertEqual(report["decision"]["candidate_tightening"], "REJECT")
        self.assertIn("LEGACY_REVERSAL_GRADUATION_FORBIDDEN", report["stability_errors"])

    def test_duplicate_contract_support_fails_closed(self):
        report = evaluate_report(base_report(contracts=["F1", "F1", "F2", "F3", "F4"]))
        self.assertEqual(report["decision"]["candidate_tightening"], "REJECT")
        self.assertIn("FAILURE_CONTRACTS_NOT_UNIQUE_OR_EMPTY", report["stability_errors"])

    def test_diagnostic_price_zones_do_not_change_verdict(self):
        source = base_report()
        source["by_diagnostic_price_zone"] = {"3_7C": {"n": 999, "success": 999}}
        report = evaluate_report(source)
        self.assertEqual(report["decision"]["candidate_tightening"], "TIGHTEN")
        self.assertTrue(report["price_zones_are_diagnostic_only"])
        self.assertFalse(report["cheap_price_override"])

    def test_upstream_more_data_cannot_be_promoted(self):
        report = evaluate_report(base_report(decision="MORE_DATA", contracts=["F1", "F2", "F3", "F4", "F5"]))
        self.assertEqual(report["decision"]["candidate_tightening"], "MORE_DATA")

    def test_production_or_frozen_ladder_change_fails_closed(self):
        source = base_report()
        source["production_promotion"] = "PERFORMED"
        source["frozen_final_early_ladders_changed"] = True
        report = evaluate_report(source)
        self.assertEqual(report["decision"]["candidate_tightening"], "REJECT")
        self.assertIn("PRODUCTION_PROMOTION_FORBIDDEN", report["stability_errors"])
        self.assertIn("FROZEN_LADDER_CHANGE_FORBIDDEN", report["stability_errors"])


if __name__ == "__main__":
    unittest.main()
