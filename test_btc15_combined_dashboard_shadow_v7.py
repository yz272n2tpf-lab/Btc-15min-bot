#!/usr/bin/env python3
import unittest

import btc15_combined_dashboard_shadow_v7 as m


class CombinedDashboardShadowV7Tests(unittest.TestCase):
    def main_state(self):
        return {
            "contract": "KXBTC15M-X",
            "timer": {"seconds_left": 300.0},
            "market": {
                "target": 78000.0,
                "up_bid": 0.33,
                "up_ask": 0.35,
                "down_bid": 0.65,
                "down_ask": 0.67,
            },
            "early": {"ready": True, "side": "UP", "ask": 0.35, "fair": 0.80, "edge": 0.10},
            "final": {"ready": False, "recorded_final_call": False, "side": "UP", "confidence": 0.88},
        }

    def safe_v6(self):
        return {
            "version": "BTC15_COMBINED_STATE_BRIDGE_V6",
            "manual_execution_only": True,
            "orders": False,
            "order_action": None,
            "numeric_flip_risk_validated": False,
            "contract": "KXBTC15M-X",
            "canonical_seconds_left": 299.2,
            "early": {"state": "QUALIFIED", "side": "UP", "ask": 0.35, "fair": 0.80, "edge": 0.10},
            "final": {"state": "WATCH", "side": "UP", "fair": None},
            "scalp": {"state": "PASS", "side": None},
            "scalp_contract_aligned": True,
            "scalp_source_fresh": True,
            "scalp_integration_ready": True,
            "scalp_block_reason": None,
            "context_labels": [],
            "scalp_management_message": "WATCHING FOR NEXT QUALIFIED SCALP",
            "scalp_lifecycle_metadata_only": True,
            "scalp_ended_unarmed_is_actionable_exit": False,
            "scalp_armed_no_exit_reset_allowed": False,
            "scalp_display_metadata_only": True,
            "scalp_completed_display_actionable": False,
            "scalp_last_completed_is_display_memory_only": True,
            "scalp_entry_guidance_is_display_only": True,
            "scalp_entry_price_filter_applied": False,
            "scalp_last_completed_opportunity_index": 2,
            "scalp_last_completed_side": "DOWN",
            "scalp_hold_completed_while_scanning": True,
        }

    def test_safe_v6_display_envelope_is_accepted(self):
        d = m.build_shadow_status(self.main_state(), self.safe_v6())
        self.assertTrue(d["display_v6_safe"])
        self.assertTrue(d["safety_envelope"])
        self.assertTrue(d["all_safety_checks_pass"])
        self.assertFalse(d["completed_display_actionable"])
        self.assertTrue(d["entry_guidance_display_only"])
        self.assertFalse(d["entry_price_filter_applied"])
        self.assertEqual(d["last_completed_opportunity_index"], 2)
        self.assertEqual(d["last_completed_side"], "DOWN")

    def test_display_memory_cannot_be_actionable(self):
        x = self.safe_v6()
        x["scalp_completed_display_actionable"] = True
        d = m.build_shadow_status(self.main_state(), x)
        self.assertFalse(d["display_v6_safe"])
        self.assertFalse(d["safety_envelope"])
        self.assertFalse(d["all_safety_checks_pass"])

    def test_entry_guidance_cannot_become_hidden_filter(self):
        x = self.safe_v6()
        x["scalp_entry_price_filter_applied"] = True
        d = m.build_shadow_status(self.main_state(), x)
        self.assertFalse(d["display_v6_safe"])
        self.assertFalse(d["all_safety_checks_pass"])

    def test_lifecycle_safety_still_required(self):
        x = self.safe_v6()
        x["scalp_armed_no_exit_reset_allowed"] = True
        d = m.build_shadow_status(self.main_state(), x)
        self.assertFalse(d["display_v6_safe"])
        self.assertFalse(d["all_safety_checks_pass"])


if __name__ == "__main__":
    unittest.main()
