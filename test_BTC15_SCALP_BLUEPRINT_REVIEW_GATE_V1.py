#!/usr/bin/env python3
import unittest

import BTC15_SCALP_BLUEPRINT_REVIEW_GATE_V1 as g


class ReviewGateTests(unittest.TestCase):
    def base(self):
        return {
            "opportunity_count": 20,
            "max_opportunity_index": 3,
            "orders": False,
            "manual_execution_only": True,
            "entry_price_is_telemetry_only": True,
            "failed_primary_cut_actionable": False,
            "timer_summary": {
                "samples_valid": 20,
                "contract_match_rate": 1.0,
                "canonical_clock_rate": 1.0,
                "within_5s_rate": 1.0,
            },
            "price_bands": {
                "70-80c": {"n": 5, "plus10_rate": .8, "plus20_rate": .4, "median_peak_gain": .16},
                "80c+": {"n": 2, "plus10_rate": .5, "plus20_rate": 0.0, "median_peak_gain": .10},
            },
        }

    def test_ready_never_auto_freezes(self):
        out = g.evaluate(self.base())
        self.assertTrue(out["collection_ready_for_full_review"])
        self.assertFalse(out["auto_freeze_allowed"])
        self.assertFalse(out["high_price_audit"]["70-80c"]["enough_sample_to_even_discuss_cutoff"])

    def test_under_20_waits(self):
        x = self.base(); x["opportunity_count"] = 19
        out = g.evaluate(x)
        self.assertFalse(out["collection_ready_for_full_review"])
        self.assertFalse(out["structural_checks"]["forward_sample_at_least_20"])

    def test_requires_serial_reset_proof(self):
        x = self.base(); x["max_opportunity_index"] = 1
        out = g.evaluate(x)
        self.assertFalse(out["collection_ready_for_full_review"])
        self.assertFalse(out["structural_checks"]["serial_reset_observed"])

    def test_high_price_never_becomes_gate_automatically(self):
        x = self.base(); x["price_bands"]["80c+"]["n"] = 50
        out = g.evaluate(x)
        self.assertTrue(out["high_price_audit"]["80c+"]["enough_sample_to_even_discuss_cutoff"])
        self.assertTrue(out["high_price_audit"]["80c+"]["price_is_telemetry_only"])
        self.assertFalse(out["auto_freeze_allowed"])

    def test_timer_alignment_is_required(self):
        x = self.base(); x["timer_summary"]["within_5s_rate"] = .95
        out = g.evaluate(x)
        self.assertFalse(out["timer_checks"]["backend_timer_within_5s_all_valid_samples"])


if __name__ == "__main__":
    unittest.main()
