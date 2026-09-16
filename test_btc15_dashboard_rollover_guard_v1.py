#!/usr/bin/env python3
import copy
import unittest

import btc15_dashboard_rollover_guard_v1 as guard


def model(contract, *, lifecycle="PASS", action="WATCHING FOR SCALP", opp=None,
          completed=0, tracking=False, manual=False, scanning=False):
    return {
        "version": "TEST",
        "contract": contract,
        "card_order": ["FINAL_OUTCOME", "EARLY_OPPORTUNITY", "CONTRACT_TIME_LEFT", "SCALP_OPPORTUNITY", "FLIP_RISK"],
        "cards": {
            "FINAL_OUTCOME": {"id": "FINAL_OUTCOME", "action": "FINAL CALL NOT READY"},
            "EARLY_OPPORTUNITY": {"id": "EARLY_OPPORTUNITY", "action": "EARLY WATCH"},
            "CONTRACT_TIME_LEFT": {"id": "CONTRACT_TIME_LEFT", "primary": "14:59"},
            "SCALP_OPPORTUNITY": {
                "id": "SCALP_OPPORTUNITY",
                "action": action,
                "underlying_lifecycle_state": lifecycle,
                "opportunity_index": opp,
                "serial_opportunities_completed": completed,
                "tracking_only": tracking,
                "manual_entry_path_available": manual,
                "scanning_for_next": scanning,
            },
            "FLIP_RISK": {"id": "FLIP_RISK", "primary": "NOT CALIBRATED"},
        },
        "safety": {"orders": False, "order_action": None},
    }


class DashboardRolloverGuardV1Tests(unittest.TestCase):
    def test_same_contract_does_not_create_history(self):
        prev = model("C1", lifecycle="PROTECT", opp=2, completed=1, manual=True)
        cur = model("C1", lifecycle="PROTECT", opp=2, completed=1, manual=True)
        out = guard.apply_rollover_guard(prev, cur)
        self.assertFalse(out["rollover"]["rollover_detected"])
        self.assertIsNone(out["historical_scalp"])

    def test_new_contract_is_preserved_byte_for_byte_semantically(self):
        prev = model("C1", lifecycle="EXIT", action="EXIT NOW · PROTECT PROFITS", opp=2, completed=2, manual=True)
        cur = model("C2", lifecycle="ACTIVE", action="DOWN #1 · ENTRY AVAILABLE", opp=1, completed=0, manual=True)
        original = copy.deepcopy(cur)
        out = guard.apply_rollover_guard(prev, cur)
        self.assertTrue(out["rollover"]["rollover_detected"])
        self.assertEqual(out["current"], original)
        self.assertEqual(out["current"]["cards"]["SCALP_OPPORTUNITY"]["action"], "DOWN #1 · ENTRY AVAILABLE")

    def test_old_protected_exit_becomes_historical_non_actionable(self):
        prev = model("C1", lifecycle="EXIT", action="EXIT NOW · PROTECT PROFITS", opp=2, completed=2, manual=True)
        cur = model("C2")
        out = guard.apply_rollover_guard(prev, cur)
        hist = out["historical_scalp"]
        self.assertIsNotNone(hist)
        self.assertEqual(hist["headline"], "#2 COMPLETE · PROTECTED EXIT")
        self.assertEqual(hist["terminal_kind"], "PROTECTED_EXIT")
        self.assertTrue(hist["historical_only"])
        self.assertFalse(hist["actionable"])
        self.assertIsNone(hist["order_action"])
        self.assertFalse(hist["orders"])

    def test_old_protect_does_not_leak_protect_instruction(self):
        prev = model("C1", lifecycle="PROTECT", action="PROTECT PROFITS", opp=3, completed=2, manual=True)
        cur = model("C2")
        hist = guard.apply_rollover_guard(prev, cur)["historical_scalp"]
        self.assertEqual(hist["headline"], "#3 ENDED · CONTRACT ROLLED")
        text = (hist["headline"] + " " + hist["detail"]).upper()
        self.assertNotIn("PROTECT PROFITS", text)
        self.assertNotIn("EXIT NOW", text)
        self.assertNotIn("HOLD ·", text)
        self.assertFalse(hist["actionable"])

    def test_old_tracking_only_never_invents_position(self):
        prev = model(
            "C1", lifecycle="EXIT", action="UP #1 · TRACKING ONLY",
            opp=1, completed=1, tracking=True, manual=False,
        )
        cur = model("C2")
        hist = guard.apply_rollover_guard(prev, cur)["historical_scalp"]
        self.assertEqual(hist["headline"], "#1 ENDED · TRACKING ONLY")
        self.assertEqual(hist["terminal_kind"], "TRACKING_ONLY_ENDED")
        self.assertFalse(hist["manual_position_assumed"])
        self.assertIn("no manual position assumed", hist["detail"].lower())

    def test_no_prior_scalp_context_produces_no_history(self):
        prev = model("C1", lifecycle="PASS", opp=None, completed=0, scanning=False)
        cur = model("C2")
        out = guard.apply_rollover_guard(prev, cur)
        self.assertTrue(out["rollover"]["rollover_detected"])
        self.assertIsNone(out["historical_scalp"])

    def test_completed_scanning_context_can_remain_historical(self):
        prev = model("C1", lifecycle="PASS", opp=None, completed=2, scanning=True)
        cur = model("C2")
        hist = guard.apply_rollover_guard(prev, cur)["historical_scalp"]
        self.assertEqual(hist["headline"], "#2 COMPLETE · PREVIOUS CONTRACT")
        self.assertFalse(hist["actionable"])

    def test_missing_current_contract_does_not_revive_previous_action(self):
        prev = model("C1", lifecycle="EXIT", action="EXIT NOW · PROTECT PROFITS", opp=1, completed=1, manual=True)
        cur = model(None)
        out = guard.apply_rollover_guard(prev, cur)
        self.assertFalse(out["rollover"]["rollover_detected"])
        self.assertFalse(out["rollover"]["current_contract_authoritative"])
        self.assertIsNone(out["historical_scalp"])
        self.assertEqual(out["current"], cur)

    def test_safety_is_explicit(self):
        out = guard.apply_rollover_guard(model("C1"), model("C2"))
        self.assertTrue(out["manual_execution_only"])
        self.assertFalse(out["orders"])
        self.assertIsNone(out["order_action"])
        self.assertFalse(out["rollover"]["signal_filtering"])
        self.assertFalse(out["rollover"]["signal_suppression"])
        self.assertFalse(out["rollover"]["historical_context_actionable"])


if __name__ == "__main__":
    unittest.main()
