#!/usr/bin/env python3
import copy
import unittest

import btc15_mobile_dashboard_view_model_v2 as v2
import btc15_mobile_dashboard_view_model_v3 as v3


def combined(contract, seconds=600):
    return {
        "contract": contract,
        "canonical_seconds_left": seconds,
        "up_ask": .44,
        "down_ask": .56,
        "early": {"state": "PASS", "side": None, "ask": None, "fair": None, "edge": None},
        "final": {"state": "WATCH", "side": None, "fair": None},
    }


def ui(contract, *, lifecycle="PASS", opp=None, completed=0, tier="UNAVAILABLE", scanning=False):
    ask_c = {"IDEAL_25_35": 31.0, "GOOD_36_50": 44.0, "CAUTION_ABOVE_50": 68.0}.get(tier)
    return {
        "contract": contract,
        "display_state": "WAIT" if lifecycle == "PASS" else lifecycle,
        "lifecycle_state": lifecycle,
        "side": None if lifecycle == "PASS" else "UP",
        "opportunity_index": opp,
        "serial_opportunities_completed": completed,
        "scanning_for_next": scanning,
        "entry_guidance": {"tier": tier},
        "entry_ask_c": ask_c,
        "current_bid_c": None if ask_c is None else ask_c + 5,
        "exec_gain_c": None if lifecycle == "PASS" else 5.0,
        "peak_exec_gain_c": None if lifecycle == "PASS" else 9.0,
        "giveback_from_peak_c": None if lifecycle == "PASS" else 4.0,
        "source": {
            "app_ready": True,
            "source_fresh": True,
            "integration_ready": True,
            "block_reason": None,
        },
    }


class MobileDashboardViewModelV3Tests(unittest.TestCase):
    def test_no_previous_model_reserves_empty_history_slot(self):
        out = v3.build_mobile_dashboard_view_model(combined("C1"), ui("C1"))
        self.assertEqual(out["version"], v3.VERSION)
        self.assertFalse(out["scalp_history_slot"]["visible"])
        self.assertTrue(out["scalp_history_slot"]["reserved"])
        self.assertFalse(out["scalp_history_slot"]["actionable"])
        self.assertEqual(out["card_order"], list(v3.CARD_ORDER))

    def test_same_contract_core_model_equals_v2(self):
        prev = v2.build_mobile_dashboard_view_model(combined("C1"), ui("C1", lifecycle="ACTIVE", opp=1, tier="GOOD_36_50"))
        base = v2.build_mobile_dashboard_view_model(combined("C1", 299), ui("C1", lifecycle="PROTECT", opp=1, tier="GOOD_36_50"))
        out = v3.build_mobile_dashboard_view_model(
            combined("C1", 299),
            ui("C1", lifecycle="PROTECT", opp=1, tier="GOOD_36_50"),
            previous_model=prev,
        )
        self.assertEqual(out["cards"], base["cards"])
        self.assertFalse(out["rollover"]["rollover_detected"])
        self.assertFalse(out["scalp_history_slot"]["visible"])

    def test_rollover_from_protected_exit_shows_muted_history(self):
        prev = v2.build_mobile_dashboard_view_model(
            combined("C1", 1),
            ui("C1", lifecycle="EXIT", opp=2, completed=2, tier="GOOD_36_50"),
        )
        out = v3.build_mobile_dashboard_view_model(
            combined("C2", 899), ui("C2"), previous_model=prev
        )
        hist = out["scalp_history_slot"]
        self.assertTrue(out["rollover"]["rollover_detected"])
        self.assertTrue(hist["visible"])
        self.assertEqual(hist["headline"], "#2 COMPLETE · PROTECTED EXIT")
        self.assertTrue(hist["historical_only"])
        self.assertFalse(hist["actionable"])
        self.assertEqual(hist["tone"], "muted")
        self.assertFalse(hist["orders"])
        self.assertIsNone(hist["order_action"])

    def test_rollover_tracking_only_never_becomes_position(self):
        prev = v2.build_mobile_dashboard_view_model(
            combined("C1", 1),
            ui("C1", lifecycle="EXIT", opp=1, completed=1, tier="CAUTION_ABOVE_50"),
        )
        out = v3.build_mobile_dashboard_view_model(combined("C2", 899), ui("C2"), previous_model=prev)
        hist = out["scalp_history_slot"]
        self.assertTrue(hist["visible"])
        self.assertEqual(hist["headline"], "#1 ENDED · TRACKING ONLY")
        self.assertFalse(hist["manual_position_assumed"])
        self.assertIn("no manual position assumed", hist["detail"].lower())

    def test_new_contract_cards_are_never_modified_by_history(self):
        prev = v2.build_mobile_dashboard_view_model(
            combined("C1", 0), ui("C1", lifecycle="PROTECT", opp=3, completed=2, tier="GOOD_36_50")
        )
        new_combined = combined("C2", 180)
        new_ui = ui("C2", lifecycle="ACTIVE", opp=1, tier="IDEAL_25_35")
        expected = v2.build_mobile_dashboard_view_model(new_combined, new_ui)
        out = v3.build_mobile_dashboard_view_model(new_combined, new_ui, previous_model=prev)
        self.assertEqual(out["cards"], expected["cards"])
        self.assertEqual(out["card_order"], expected["card_order"])
        self.assertEqual(out["cards"]["SCALP_OPPORTUNITY"]["action"], "UP #1 · ENTRY AVAILABLE")

    def test_history_slot_does_not_change_core_card_order_or_timer_count(self):
        prev = v2.build_mobile_dashboard_view_model(
            combined("C1", 0), ui("C1", lifecycle="EXIT", opp=1, completed=1, tier="GOOD_36_50")
        )
        out = v3.build_mobile_dashboard_view_model(combined("C2", 300), ui("C2"), previous_model=prev)
        self.assertEqual(out["card_order"], list(v3.CARD_ORDER))
        self.assertTrue(out["layout"]["scalp_history_slot_reserved"])
        self.assertFalse(out["layout"]["scalp_history_slot_changes_core_card_order"])
        self.assertEqual(out["cards"]["CONTRACT_TIME_LEFT"]["visible_timer_count"], 1)

    def test_safety_flags_are_explicit(self):
        out = v3.build_mobile_dashboard_view_model(combined("C1"), ui("C1"))
        self.assertFalse(out["safety"]["historical_scalp_actionable"])
        self.assertFalse(out["safety"]["historical_scalp_can_change_current_signals"])
        self.assertFalse(out["safety"]["orders"])
        self.assertIsNone(out["safety"]["order_action"])
        self.assertFalse(out["safety"]["numeric_flip_risk_visible"])


if __name__ == "__main__":
    unittest.main()
