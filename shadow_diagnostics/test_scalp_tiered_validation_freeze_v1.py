#!/usr/bin/env python3
import unittest
from unittest.mock import patch

import scalp_tiered_validation_freeze_v1 as t


class TieredValidationFreezeTests(unittest.TestCase):
    def row(self, name, plus10, coverage, n=30, contracts=20, ask=50.0, affordable=.40, minutes=9.0):
        return {
            "name": name,
            "model": "LOGISTIC",
            "core_threshold": .8,
            "rescue_threshold": .6,
            "n": n,
            "covered_contracts": contracts,
            "plus10_rate": plus10,
            "true_contract_coverage": coverage,
            "affordable_true_contract_coverage_le50": affordable,
            "avg_entry_ask_c": ask,
            "avg_minutes_left": minutes,
        }

    def test_roles_are_selected_from_validation_by_fixed_definitions(self):
        frontier = [
            self.row("precision", .97, .48, affordable=.25),
            self.row("balanced", .91, .82, affordable=.38),
            self.row("coverage", .86, .89, affordable=.45),
            self.row("tiny_perfect", 1.00, .20, n=4, contracts=3),
        ]
        roles = t.select_roles(frontier)
        self.assertEqual(roles["PRECISION_CORE"]["name"], "precision")
        self.assertEqual(roles["BALANCED_90"]["name"], "balanced")
        self.assertEqual(roles["COVERAGE_FRONTIER"]["name"], "coverage")

    def test_precision_core_must_clear_40_percent_coverage(self):
        frontier = [
            self.row("too_narrow", .99, .39),
            self.row("eligible", .95, .41),
        ]
        roles = t.select_roles(frontier)
        self.assertEqual(roles["PRECISION_CORE"]["name"], "eligible")

    def test_balanced_requires_90_percent_plus10(self):
        frontier = [
            self.row("wide_but_low_quality", .899, .88),
            self.row("balanced", .90, .75),
        ]
        roles = t.select_roles(frontier)
        self.assertEqual(roles["BALANCED_90"]["name"], "balanced")
        self.assertEqual(roles["COVERAGE_FRONTIER"]["name"], "wide_but_low_quality")

    def test_minimum_sample_and_contract_requirements_fail_closed(self):
        frontier = [
            self.row("too_few_signals", .99, .80, n=11, contracts=20),
            self.row("too_few_contracts", .99, .80, n=30, contracts=7),
        ]
        roles = t.select_roles(frontier)
        self.assertIsNone(roles["PRECISION_CORE"])
        self.assertIsNone(roles["BALANCED_90"])
        self.assertIsNone(roles["COVERAGE_FRONTIER"])

    def test_audit_freezes_validation_configs_before_holdout(self):
        frontier = [
            self.row("precision", .97, .48),
            self.row("balanced", .91, .82),
            self.row("coverage", .86, .89),
        ]
        seen = []
        def fake_eval(opps, split, config):
            seen.append(config["name"])
            return {"holdout_is_report_only": True, "frozen_name": config["name"]}, []

        with patch.object(t, "evaluate_holdout", side_effect=fake_eval):
            out = t.audit([], {}, frontier)

        self.assertEqual(seen, ["precision", "balanced", "coverage"])
        self.assertEqual(out["roles"]["PRECISION_CORE"]["holdout"]["frozen_name"], "precision")
        self.assertEqual(out["roles"]["BALANCED_90"]["holdout"]["frozen_name"], "balanced")
        self.assertEqual(out["roles"]["COVERAGE_FRONTIER"]["holdout"]["frozen_name"], "coverage")
        self.assertTrue(out["holdout_is_report_only"])
        self.assertTrue(out["forward_freeze_required_before_any_promotion"])
        self.assertFalse(out["automatic_promotion"])


if __name__ == "__main__":
    unittest.main()
