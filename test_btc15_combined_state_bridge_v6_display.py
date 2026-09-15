#!/usr/bin/env python3
import unittest

import btc15_combined_state_bridge_v6_display as m


class DisplayBridgeV6Tests(unittest.TestCase):
    def combined(self, *, state="PASS"):
        return {
            "version": "BTC15_COMBINED_STATE_BRIDGE_V5",
            "contract": "KXBTC15M-TEST",
            "manual_execution_only": True,
            "orders": False,
            "order_action": None,
            "numeric_flip_risk_validated": False,
            "scalp_lifecycle_metadata_only": True,
            "scalp_ended_unarmed_is_actionable_exit": False,
            "scalp_armed_no_exit_reset_allowed": False,
            "scalp": {"state": state, "side": "DOWN" if state != "PASS" else None},
            "scalp_opportunity_index": 3,
        }

    def scalp(self, *, entry=None, scanning=True, terminal=True):
        hist = []
        if terminal:
            hist.append({
                "candidate_id": "c2",
                "opportunity_index": 2,
                "terminal_state": "EXIT",
                "terminal_time_utc": "2026-09-15T13:25:42+00:00",
                "actionable_exit": True,
                "side": "DOWN",
                "entry_price": 0.70,
                "exit_gain": 0.05,
                "peak_exec_gain": 0.23,
            })
        return {
            "version": "GENERALIZED_SCALP_INTEGRATION_V5",
            "contract": "KXBTC15M-TEST",
            "manual_execution_only": True,
            "orders": False,
            "order_action": None,
            "armed_no_exit_reset_allowed": False,
            "state": "PASS" if scanning else "ACTIVE",
            "entry_price": entry,
            "opportunity_index": 3,
            "scanning_for_next": scanning,
            "terminal_history": hist,
        }

    def test_completed_scalp_persists_as_nonactionable_display_memory(self):
        out = m.enrich_display_state(self.combined(), self.scalp())
        self.assertEqual(out["version"], "BTC15_COMBINED_STATE_BRIDGE_V6")
        self.assertTrue(out["scalp_last_completed_available"])
        self.assertEqual(out["scalp_last_completed_opportunity_index"], 2)
        self.assertEqual(out["scalp_last_completed_side"], "DOWN")
        self.assertEqual(out["scalp_last_completed_entry_price"], 0.70)
        self.assertTrue(out["scalp_hold_completed_while_scanning"])
        self.assertFalse(out["scalp_completed_display_actionable"])
        self.assertTrue(out["scalp_last_completed_is_display_memory_only"])
        self.assertFalse(out["orders"])
        self.assertIsNone(out["order_action"])

    def test_entry_guidance_is_display_only_and_does_not_filter(self):
        cases = [
            (0.30, "IDEAL"),
            (0.45, "GOOD"),
            (0.70, "TOO_EXPENSIVE"),
            (0.10, "LOW_PRICE"),
        ]
        for entry, zone in cases:
            with self.subTest(entry=entry):
                out = m.enrich_display_state(self.combined(state="ACTIVE"), self.scalp(entry=entry, scanning=False))
                self.assertEqual(out["scalp_current_entry_guidance"]["zone"], zone)
                self.assertTrue(out["scalp_entry_guidance_is_display_only"])
                self.assertFalse(out["scalp_entry_price_filter_applied"])
                self.assertFalse(out["orders"])

    def test_above_50c_says_dont_chase_without_invalidating_signal(self):
        out = m.enrich_display_state(self.combined(state="ACTIVE"), self.scalp(entry=0.70, scanning=False))
        self.assertIn("DON'T CHASE", out["scalp_current_entry_guidance"]["label"])
        self.assertEqual(out["scalp"]["state"], "ACTIVE")
        self.assertFalse(out["scalp_entry_price_filter_applied"])

    def test_ended_unarmed_history_stays_nonactionable(self):
        s = self.scalp()
        s["terminal_history"][-1].update({
            "terminal_state": "ENDED_UNARMED",
            "actionable_exit": False,
            "entry_price": 0.34,
        })
        out = m.enrich_display_state(self.combined(), s)
        self.assertEqual(out["scalp_last_completed_state"], "ENDED_UNARMED")
        self.assertFalse(out["scalp_last_completed_actionable_exit"])
        self.assertFalse(out["scalp_completed_display_actionable"])

    def test_fail_closed_if_upstream_safety_is_broken(self):
        c = self.combined()
        c["orders"] = True
        with self.assertRaises(ValueError):
            m.enrich_display_state(c, self.scalp())

    def test_fail_closed_on_contract_mismatch(self):
        s = self.scalp()
        s["contract"] = "OTHER"
        with self.assertRaises(ValueError):
            m.enrich_display_state(self.combined(), s)


if __name__ == "__main__":
    unittest.main()
