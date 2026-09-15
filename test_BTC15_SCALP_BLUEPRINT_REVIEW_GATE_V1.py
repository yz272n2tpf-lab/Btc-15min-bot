#!/usr/bin/env python3
import unittest

import BTC15_SCALP_BLUEPRINT_REVIEW_GATE_V1 as g


class ReviewGateTests(unittest.TestCase):
    def forward(self):
        return {
            "status": "READY_FOR_REVIEW",
            "completed_serial_opportunities": 25,
            "max_opportunities_in_one_contract": 4,
            "meaningful_10c_rate": .76,
            "orders": False,
            "manual_execution_only": True,
            "review_gate": {"met": True},
            "blueprint": {
                "entry_price_filter_applied": False,
                "price_zone_trigger": False,
                "high_price_cutoff_selected": False,
                "orders": False,
            },
            "failed_primary": {"completed_failed_primary_n": 0},
            "timer_audit": {
                "samples_valid": 200,
                "samples_total": 220,
                "contract_match_rate": 1.0,
                "canonical_clock_rate": 1.0,
                "within_5s_rate": .95,
            },
            "entry_price_bands": {
                "70-80c": {"n": 5, "plus10_rate": .8, "plus20_rate": .4, "median_peak_gain": .16},
                "80c+": {"n": 2, "plus10_rate": .5, "plus20_rate": 0.0, "median_peak_gain": .10},
            },
        }

    def coverage(self):
        return {
            "orders": False,
            "post_exit_missed_qualified": 0,
            "failed_prearm_blocked_candidates": 0,
        }

    def protection(self):
        return {
            "orders": False,
            "protected_exit_records": 20,
            "first_crossing_ok_rate": 1.0,
        }

    def test_actual_forward_schema_is_understood(self):
        out = g.compose_review(
            self.forward(), self.coverage(), self.protection(),
            timer_visual_accepted=True,
        )
        self.assertEqual(out["completed_serial_opportunities"], 25)
        self.assertEqual(out["max_opportunities_in_one_contract"], 4)
        self.assertNotIn("FORWARD_SAMPLE_NOT_READY", out["blockers"])
        self.assertNotIn("MULTI_SCALP_RESET_NOT_OBSERVED", out["blockers"])
        self.assertFalse(out["auto_freeze_allowed"])

    def test_failed_prearm_is_hard_freeze_blocker(self):
        f = self.forward(); f["failed_primary"] = {"completed_failed_primary_n": 2}
        c = self.coverage(); c["failed_prearm_blocked_candidates"] = 3
        out = g.compose_review(f, c, self.protection(), timer_visual_accepted=True)
        self.assertIn("FAILED_PREARM_CLOSE_RESET_RULE_UNRESOLVED", out["blockers"])
        self.assertEqual(out["status"], "NOT_READY_TO_FREEZE")

    def test_true_post_exit_miss_is_hard_blocker(self):
        c = self.coverage(); c["post_exit_missed_qualified"] = 1
        out = g.compose_review(self.forward(), c, self.protection(), timer_visual_accepted=True)
        self.assertIn("POST_EXIT_QUALIFIED_SCALP_MISSED", out["blockers"])

    def test_protection_must_hit_first_observed_four_cent_crossing(self):
        p = self.protection(); p["first_crossing_ok_rate"] = .95
        out = g.compose_review(self.forward(), self.coverage(), p, timer_visual_accepted=True)
        self.assertIn("PROTECTION_FIRST_4C_CROSSING_MISMATCH", out["blockers"])

    def test_visual_timer_acceptance_remains_required(self):
        out = g.compose_review(self.forward(), self.coverage(), self.protection())
        self.assertIn("TIMER_VISUAL_ACCEPTANCE_PENDING", out["blockers"])

    def test_high_price_sample_never_auto_becomes_filter(self):
        f = self.forward(); f["entry_price_bands"]["80c+"]["n"] = 50
        out = g.compose_review(f, self.coverage(), self.protection(), timer_visual_accepted=True)
        self.assertTrue(out["high_price_audit"]["80c+"]["enough_sample_to_even_discuss_cutoff"])
        self.assertTrue(out["high_price_audit"]["80c+"]["price_is_telemetry_only"])
        self.assertFalse(out["auto_freeze_allowed"])

    def test_unapproved_price_suppression_blocks_review(self):
        f = self.forward(); f["blueprint"]["entry_price_filter_applied"] = True
        out = g.compose_review(f, self.coverage(), self.protection(), timer_visual_accepted=True)
        self.assertIn("UNAPPROVED_PRICE_SUPPRESSION_PRESENT", out["blockers"])

    def test_ten_cent_rate_is_reported_without_invented_threshold(self):
        out = g.compose_review(self.forward(), self.coverage(), self.protection(), timer_visual_accepted=True)
        self.assertAlmostEqual(out["meaningful_10c_rate"], .76)
        self.assertIn("TEN_CENT_TARGET_NOT_HIT_BY_EVERY_SELECTED_SCALP", out["review_items"])
        self.assertIn("TEN_CENT_ACCEPTANCE_PERCENTAGE_NOT_YET_FROZEN", out["review_items"])


if __name__ == "__main__":
    unittest.main()
