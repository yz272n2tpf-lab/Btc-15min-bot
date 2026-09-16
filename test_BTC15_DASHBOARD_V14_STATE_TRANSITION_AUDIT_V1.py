#!/usr/bin/env python3
import unittest

import BTC15_DASHBOARD_V14_STATE_TRANSITION_AUDIT_V1 as audit


class V14StateTransitionAuditTests(unittest.TestCase):
    def _case(self, name):
        return next(x for x in audit.transition_matrix() if x["case"] == name)

    def test_matrix_is_complete_and_unique(self):
        rows = audit.transition_matrix()
        self.assertEqual(len(rows), 15)
        self.assertEqual(len({x["case"] for x in rows}), 15)

    def test_wait_states_never_imply_position(self):
        for name in (
            "PASS_READY",
            "PASS_STALE",
            "PASS_BAD_ENVELOPE",
            "PASS_CONTRACT_SYNC",
            "PASS_SCALP_SYNC",
            "PASS_SOURCE_STALE",
            "PASS_NOT_READY",
        ):
            row = self._case(name)
            self.assertEqual(row["pill"], "WATCHING")
            self.assertFalse(row["position_assumed"])
            self.assertFalse(row["user_exit_instruction"])

    def test_affordable_lifecycle_copy_is_action_ordered(self):
        active = self._case("ACTIVE_AFFORDABLE")
        protect = self._case("PROTECT_AFFORDABLE")
        exit_row = self._case("EXIT_AFFORDABLE")
        self.assertEqual((active["pill"], active["main"]), ("ACTIVE", "HOLD · MOVE STILL BUILDING"))
        self.assertEqual((protect["pill"], protect["main"]), ("PROTECT", "PROTECT PROFITS"))
        self.assertEqual((exit_row["pill"], exit_row["main"]), ("EXIT", "EXIT NOW · PROTECT PROFITS"))
        self.assertFalse(active["user_exit_instruction"])
        self.assertFalse(protect["user_exit_instruction"])
        self.assertTrue(exit_row["user_exit_instruction"])

    def test_too_expensive_backend_states_never_imply_manual_position(self):
        for name in (
            "ACTIVE_TOO_EXPENSIVE",
            "PROTECT_TOO_EXPENSIVE",
            "EXIT_TOO_EXPENSIVE",
        ):
            row = self._case(name)
            self.assertEqual(row["pill"], "TRACKING")
            self.assertEqual(row["main"], "TRACKING ONLY · DON'T CHASE")
            self.assertEqual(row["protection_row"], "TRACKING ONLY · NO POSITION ASSUMED")
            self.assertFalse(row["position_assumed"])
            self.assertFalse(row["user_exit_instruction"])

    def test_completed_unarmed_is_not_an_exit(self):
        row = self._case("COMPLETED_NO_PROTECTED_EXIT")
        self.assertIn("NO PROTECTED EXIT", row["main"])
        self.assertIn("SCANNING", row["main"])
        self.assertFalse(row["position_assumed"])
        self.assertFalse(row["user_exit_instruction"])

    def test_completed_protected_exit_is_history_not_new_instruction(self):
        row = self._case("COMPLETED_PROTECTED_EXIT")
        self.assertIn("PROTECTED EXIT", row["main"])
        self.assertIn("SCANNING", row["main"])
        self.assertFalse(row["position_assumed"])
        self.assertFalse(row["user_exit_instruction"])

    def test_generated_v14_retains_transition_and_stability_safety(self):
        result = audit.audit_generated_v14()
        self.assertEqual(result["generated_html_audit"], "PASS")
        self.assertTrue(result["single_canonical_timer"])
        self.assertFalse(result["expensive_backend_states_imply_position"])
        self.assertFalse(result["completed_unarmed_is_exit"])
        self.assertFalse(result["numeric_flip_risk_exposed"])
        self.assertFalse(result["strategy_changed"])
        self.assertTrue(result["manual_execution_only"])
        self.assertFalse(result["orders"])


if __name__ == "__main__":
    unittest.main()
