#!/usr/bin/env python3
from __future__ import annotations

import unittest

import BTC15_SCALP_LADDER_SELECTOR_V1 as s


class SelectorTests(unittest.TestCase):
    def test_secondary_viability_gate(self):
        m = {
            "n": 12,
            "plus5_rate": .80,
            "plus10_rate": .60,
            "median_peak_gain": .10,
            "avg_adverse_gain": -.10,
        }
        self.assertTrue(s.opportunity_viable(m))
        m2 = dict(m, plus5_rate=.79)
        self.assertFalse(s.opportunity_viable(m2))

    def test_failed_selector_uses_validation_metrics_and_tiebreak(self):
        rows = []
        # Cell A: 12 rows, 1 recovery (8.3%), avg trigger -5c.
        for i in range(12):
            rows.append({
                "adverse_trigger_cents":"5",
                "min_elapsed_sec":"20",
                "would_recover_to_plus5":"true" if i == 0 else "false",
                "gain_at_trigger":"-0.05",
                "best_gain_after_trigger":"0.02",
            })
        # Cell B: same recovery but less-negative trigger, should win tie-break.
        for i in range(12):
            rows.append({
                "adverse_trigger_cents":"3",
                "min_elapsed_sec":"30",
                "would_recover_to_plus5":"true" if i == 0 else "false",
                "gain_at_trigger":"-0.03",
                "best_gain_after_trigger":"0.02",
            })
        chosen, _ = s.select_failed(rows)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["adverse_trigger_cents"], 3.0)
        self.assertEqual(chosen["min_elapsed_sec"], 30.0)

    def test_failed_selector_rejects_high_recovery(self):
        rows = []
        for i in range(12):
            rows.append({
                "adverse_trigger_cents":"5",
                "min_elapsed_sec":"20",
                "would_recover_to_plus5":"true" if i < 3 else "false",
                "gain_at_trigger":"-0.05",
                "best_gain_after_trigger":"0.02",
            })
        chosen, _ = s.select_failed(rows)
        self.assertIsNone(chosen)

    def test_report_only_cannot_enter_selection_helper(self):
        # The selector helper has no split input at all; callers must pre-filter VALIDATION.
        rows = [{
            "adverse_trigger_cents":"5",
            "min_elapsed_sec":"20",
            "would_recover_to_plus5":"false",
            "gain_at_trigger":"-0.05",
            "best_gain_after_trigger":"0.01",
        }] * 12
        chosen, _ = s.select_failed(rows)
        self.assertIsNotNone(chosen)


if __name__ == "__main__":
    unittest.main()
