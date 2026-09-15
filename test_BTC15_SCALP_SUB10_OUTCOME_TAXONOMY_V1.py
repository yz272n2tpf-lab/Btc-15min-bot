#!/usr/bin/env python3
import unittest

import BTC15_SCALP_SUB10_OUTCOME_TAXONOMY_V1 as m


class Sub10OutcomeTaxonomyTests(unittest.TestCase):
    def test_decomposes_plus10_unarmed_and_smaller_armed_paths(self):
        rows = [
            {"peak_gain": .14, "adverse_gain": -.02, "terminal_kind": "PROTECTED_EXIT", "protected_exit_gain": .07},
            {"peak_gain": .07, "adverse_gain": -.01, "terminal_kind": "PROTECTED_EXIT", "protected_exit_gain": .02},
            {"peak_gain": .09, "adverse_gain": -.03, "terminal_kind": "ARMED_NO_VALIDATED_EXIT", "protected_exit_gain": None},
            {"peak_gain": .03, "adverse_gain": -.08, "terminal_kind": "ENDED_UNARMED", "protected_exit_gain": None},
        ]
        out = m.summarize_records(rows)
        self.assertEqual(out["n"], 4)
        self.assertEqual(out["plus5_n"], 3)
        self.assertEqual(out["plus10_n"], 1)
        self.assertEqual(out["unarmed_sub5_n"], 1)
        self.assertEqual(out["armed_sub10_n"], 2)
        self.assertEqual(out["armed_sub10_protected_exit_n"], 1)
        self.assertEqual(out["armed_sub10_no_validated_exit_n"], 1)
        self.assertEqual(out["positive_protected_exit_sub10_n"], 1)
        self.assertEqual(out["peak_band_counts"]["5_TO_LT_8C"], 1)
        self.assertEqual(out["peak_band_counts"]["8_TO_LT_10C"], 1)

    def test_plus5_is_not_promoted_to_validated_success(self):
        out = m.summarize_records([
            {"peak_gain": .06, "terminal_kind": "ARMED_NO_VALIDATED_EXIT"},
        ])
        self.assertTrue(out["plus10_is_reporting_target_not_entry_gate"])
        self.assertTrue(out["plus5_is_not_reclassified_as_validated_trade_success"])
        self.assertFalse(out["auto_promote_allowed"])
        self.assertFalse(out["actionable_now"])

    def test_safety_envelope_remains_read_only(self):
        out = m.summarize_records([])
        self.assertFalse(out["orders"])
        self.assertTrue(out["manual_execution_only"])
        self.assertFalse(out["entry_price_filter_applied"])
        self.assertFalse(out["fixed_time_window_applied"])
        self.assertFalse(out["protected_thresholds_changed"])
        self.assertFalse(out["stop_loss_rule_selected"])


if __name__ == "__main__":
    unittest.main()
