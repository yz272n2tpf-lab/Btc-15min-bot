#!/usr/bin/env python3
import unittest

import btc15_mobile_dashboard_view_model_v1 as v1
import btc15_mobile_dashboard_view_model_v2 as v2


def combined(seconds_left):
    return {
        "contract": "KXBTC15M-T",
        "canonical_seconds_left": seconds_left,
        "up_ask": .44,
        "down_ask": .56,
        "early": {"state": "PASS", "side": None, "ask": None, "fair": None, "edge": None},
        "final": {"state": "WATCH", "side": None, "fair": None},
    }


def ui():
    return {
        "contract": "KXBTC15M-T",
        "display_state": "WAIT",
        "lifecycle_state": "PASS",
        "side": None,
        "opportunity_index": None,
        "serial_opportunities_completed": 0,
        "scanning_for_next": False,
        "entry_guidance": {"tier": "UNAVAILABLE"},
        "entry_ask_c": None,
        "current_bid_c": None,
        "exec_gain_c": None,
        "peak_exec_gain_c": None,
        "giveback_from_peak_c": None,
        "source": {
            "app_ready": True,
            "source_fresh": True,
            "integration_ready": True,
            "block_reason": None,
        },
    }


class MobileDashboardViewModelV2Tests(unittest.TestCase):
    def test_v1_card_order_is_preserved(self):
        out = v2.build_mobile_dashboard_view_model(combined(600), ui())
        self.assertEqual(out["card_order"], list(v1.CARD_ORDER))
        self.assertEqual(out["version"], v2.VERSION)

    def test_normal_timer_context(self):
        timer = v2.build_mobile_dashboard_view_model(combined(301), ui())["cards"]["CONTRACT_TIME_LEFT"]
        self.assertEqual(timer["primary"], "5:01")
        self.assertEqual(timer["guardrail_band"], "NORMAL")
        self.assertEqual(timer["status_label"], "CONTRACT ACTIVE")
        self.assertEqual(timer["tone"], "neutral")

    def test_five_minute_caution(self):
        timer = v2.build_mobile_dashboard_view_model(combined(300), ui())["cards"]["CONTRACT_TIME_LEFT"]
        self.assertEqual(timer["primary"], "5:00")
        self.assertEqual(timer["guardrail_band"], "CAUTION_5M")
        self.assertEqual(timer["status_label"], "5M CAUTION")
        self.assertEqual(timer["tone"], "caution")

    def test_three_minute_guardrail(self):
        timer = v2.build_mobile_dashboard_view_model(combined(180), ui())["cards"]["CONTRACT_TIME_LEFT"]
        self.assertEqual(timer["primary"], "3:00")
        self.assertEqual(timer["guardrail_band"], "GUARD_3M")
        self.assertEqual(timer["status_label"], "3M GUARD RAIL")

    def test_rollover_context(self):
        timer = v2.build_mobile_dashboard_view_model(combined(0), ui())["cards"]["CONTRACT_TIME_LEFT"]
        self.assertEqual(timer["primary"], "0:00")
        self.assertEqual(timer["guardrail_band"], "ROLLOVER")
        self.assertEqual(timer["status_label"], "NEXT CONTRACT SYNCING")

    def test_guardrail_never_changes_signal_cards(self):
        base = v1.build_mobile_dashboard_view_model(combined(180), ui())
        out = v2.build_mobile_dashboard_view_model(combined(180), ui())
        for card_id in ("FINAL_OUTCOME", "EARLY_OPPORTUNITY", "SCALP_OPPORTUNITY", "FLIP_RISK"):
            self.assertEqual(out["cards"][card_id], base["cards"][card_id])

    def test_guardrail_safety_is_explicit(self):
        out = v2.build_mobile_dashboard_view_model(combined(120), ui())
        timer = out["cards"]["CONTRACT_TIME_LEFT"]
        self.assertTrue(timer["presentation_only"])
        self.assertFalse(timer["signal_filtering"])
        self.assertFalse(timer["signal_suppression"])
        self.assertFalse(timer["changes_entry_rule"])
        self.assertFalse(timer["changes_exit_rule"])
        self.assertFalse(out["safety"]["time_guardrail_signal_filtering"])
        self.assertFalse(out["safety"]["time_guardrail_signal_suppression"])
        self.assertFalse(out["safety"]["orders"])
        self.assertIsNone(out["safety"]["order_action"])


if __name__ == "__main__":
    unittest.main()
