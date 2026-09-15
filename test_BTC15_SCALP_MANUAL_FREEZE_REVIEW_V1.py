#!/usr/bin/env python3
import unittest

import BTC15_SCALP_MANUAL_FREEZE_REVIEW_V1 as m


class ManualFreezeReviewTests(unittest.TestCase):
    def good(self):
        return {
            "orders": False,
            "manual_execution_only": True,
            "blueprint_review": {
                "version": "BTC15_SCALP_BLUEPRINT_REVIEW_GATE_V1_2",
                "status": "NOT_READY_TO_FREEZE",
                "orders": False,
                "manual_execution_only": True,
                "auto_freeze_allowed": False,
                "blockers": ["TIMER_VISUAL_ACCEPTANCE_PENDING"],
                "timer_valid_samples": 48,
                "failed_prearm_lifecycle_resolved": True,
                "lifecycle_armed_no_exit_preserved_blocking": True,
                "protected_exit_records": 34,
                "first_crossing_ok_rate": 1.0,
                "price_is_telemetry_only_required": True,
                "ended_unarmed_must_remain_nonactionable": True,
                "armed_no_exit_must_remain_protected": True,
                "stop_loss_rule_required": False,
            },
        }

    def test_visual_pass_can_only_make_manual_review_eligible(self):
        out = m.compose_manual_review(self.good(), timer_visual_accepted=True)
        self.assertTrue(out["manual_freeze_review_eligible"])
        self.assertEqual(out["status"], "READY_FOR_MANUAL_FREEZE_REVIEW")
        self.assertFalse(out["auto_freeze_allowed"])
        self.assertFalse(out["production_change_allowed"])
        self.assertFalse(out["strategy_change_allowed"])
        self.assertFalse(out["orders"])
        self.assertIsNone(out["order_action"])

    def test_without_explicit_visual_pass_remains_blocked(self):
        out = m.compose_manual_review(self.good(), timer_visual_accepted=False)
        self.assertFalse(out["manual_freeze_review_eligible"])
        self.assertIn("TIMER_VISUAL_ACCEPTANCE_NOT_CONFIRMED", out["blocking_reasons"])

    def test_any_other_blocker_remains_blocked(self):
        s = self.good()
        s["blueprint_review"]["blockers"] = [
            "TIMER_VISUAL_ACCEPTANCE_PENDING",
            "PROTECTION_FIRST_4C_CROSSING_MISMATCH",
        ]
        out = m.compose_manual_review(s, timer_visual_accepted=True)
        self.assertFalse(out["manual_freeze_review_eligible"])
        self.assertIn("EXISTING_REVIEW_HAS_NONVISUAL_OR_MULTIPLE_BLOCKERS", out["blocking_reasons"])

    def test_bad_safety_envelope_cannot_pass(self):
        s = self.good()
        s["orders"] = True
        s["blueprint_review"]["auto_freeze_allowed"] = True
        out = m.compose_manual_review(s, timer_visual_accepted=True)
        self.assertFalse(out["manual_freeze_review_eligible"])
        self.assertIn("CONSOLIDATED_ORDER_FLAG_INVALID", out["blocking_reasons"])
        self.assertIn("AUTO_FREEZE_MUST_REMAIN_DISABLED", out["blocking_reasons"])

    def test_insufficient_timer_or_protection_evidence_cannot_pass(self):
        s = self.good()
        s["blueprint_review"]["timer_valid_samples"] = 19
        s["blueprint_review"]["first_crossing_ok_rate"] = 0.99
        out = m.compose_manual_review(s, timer_visual_accepted=True)
        self.assertFalse(out["manual_freeze_review_eligible"])
        self.assertIn("TIMER_SAMPLE_MINIMUM_NOT_PRESERVED", out["blocking_reasons"])
        self.assertIn("PROTECTION_FIRST_CROSSING_NOT_PERFECT", out["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
