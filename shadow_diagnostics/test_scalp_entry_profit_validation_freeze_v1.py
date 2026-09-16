#!/usr/bin/env python3
import unittest
import scalp_entry_profit_validation_freeze_v1 as f


def row(entry, exitp, val, hold=None):
    return {"entry_policy":entry,"exit_policy":exitp,"validation":val,"holdout":hold or {}}


class EntryProfitValidationFreezeTests(unittest.TestCase):
    def test_holdout_cannot_change_full_retention_selection(self):
        grid = [
            row("IMMEDIATE","LEGACY_5_4", {"signals":50,"true_contract_coverage":1.0,"plus10_rate":.75,"avg_executable_exit_gain_c":9,"entry_le50_rate":.45}, {"plus10_rate":1.0}),
            row("IMMEDIATE","RUNNER_10_4", {"signals":50,"true_contract_coverage":1.0,"plus10_rate":.80,"avg_executable_exit_gain_c":10,"entry_le50_rate":.45}, {"plus10_rate":0.0}),
        ]
        roles = f.select_roles(grid)
        self.assertEqual(roles["FULL_RETENTION_QUALITY"]["exit_policy"], "RUNNER_10_4")
        self.assertEqual(roles["FULL_RETENTION_QUALITY"]["selection_source"], "VALIDATION_ONLY")

    def test_affordable_role_requires_all_selected_entries_le50_and_90pct_retention(self):
        grid = [
            row("AFFORDABLE_15","RUNNER_10_4", {"signals":40,"true_contract_coverage":.91,"plus10_rate":.72,"avg_executable_exit_gain_c":10,"entry_le50_rate":1.0}),
            row("IDEAL_25_35_60","RUNNER_10_4", {"signals":40,"true_contract_coverage":.50,"plus10_rate":.90,"avg_executable_exit_gain_c":12,"entry_le50_rate":1.0}),
        ]
        roles = f.select_roles(grid)
        self.assertEqual(roles["AFFORDABLE_COVERAGE"]["entry_policy"], "AFFORDABLE_15")

    def test_shortest_wait_breaks_affordable_tie(self):
        grid = [
            row("AFFORDABLE_60","RUNNER_10_4", {"signals":40,"true_contract_coverage":.91,"plus10_rate":.72,"avg_executable_exit_gain_c":10,"entry_le50_rate":1.0}),
            row("AFFORDABLE_15","RUNNER_10_4", {"signals":40,"true_contract_coverage":.91,"plus10_rate":.72,"avg_executable_exit_gain_c":10,"entry_le50_rate":1.0}),
        ]
        roles = f.select_roles(grid)
        self.assertEqual(roles["AFFORDABLE_COVERAGE"]["entry_policy"], "AFFORDABLE_15")

    def test_serial_role_maximizes_turnover_at_full_retention(self):
        grid = [
            row("IMMEDIATE","RUNNER_10_4", {"signals":60,"true_contract_coverage":1.0,"plus10_rate":.8,"avg_opportunities_per_covered_contract":1.5,"positive_exit_rate":.8,"avg_executable_exit_gain_c":11}),
            row("IMMEDIATE","PROTECT_5_2", {"signals":70,"true_contract_coverage":1.0,"plus10_rate":.74,"avg_opportunities_per_covered_contract":1.8,"positive_exit_rate":.81,"avg_executable_exit_gain_c":10.5}),
        ]
        roles = f.select_roles(grid)
        self.assertEqual(roles["SERIAL_PROTECTION"]["exit_policy"], "PROTECT_5_2")

    def test_audit_has_no_auto_promotion(self):
        out = f.audit([])
        self.assertFalse(out["holdout_used_for_selection"])
        self.assertTrue(out["retuning_after_holdout_prohibited"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
