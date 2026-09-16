#!/usr/bin/env python3
import unittest

import btc15_mobile_dashboard_view_model_v3 as v3
import btc15_mobile_dashboard_view_model_v4 as v4


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


class MobileDashboardViewModelV4Tests(unittest.TestCase):
    def test_same_contract_exit_memory_persists_while_scanning_next(self):
        prev = v3.build_mobile_dashboard_view_model(
            combined("C1", 250), ui("C1", lifecycle="EXIT", opp=1, completed=1, tier="GOOD_36_50")
        )
        out = v4.build_mobile_dashboard_view_model(
            combined("C1", 240), ui("C1", lifecycle="PASS", completed=1, scanning=True), previous_model=prev
        )
        hist = out["scalp_history_slot"]
        self.assertTrue(hist["visible"])
        self.assertEqual(hist["headline"], "#1 COMPLETE · PROTECTED EXIT")
        self.assertIn("scanning for #2", hist["detail"].lower())
        self.assertFalse(hist["actionable"])
        self.assertTrue(out["presentation_integrity"]["ok"])

    def test_same_contract_exit_memory_persists_when_next_opportunity_is_active(self):
        prev = v3.build_mobile_dashboard_view_model(
            combined("C1", 250), ui("C1", lifecycle="EXIT", opp=1, completed=1, tier="GOOD_36_50")
        )
        out = v4.build_mobile_dashboard_view_model(
            combined("C1", 220), ui("C1", lifecycle="ACTIVE", opp=2, completed=1, tier="IDEAL_25_35"), previous_model=prev
        )
        self.assertEqual(out["scalp_history_slot"]["headline"], "#1 COMPLETE · PROTECTED EXIT")
        self.assertEqual(out["cards"]["SCALP_OPPORTUNITY"]["action"], "UP #2 · ENTRY AVAILABLE")
        self.assertEqual(out["cards"]["SCALP_OPPORTUNITY"]["underlying_lifecycle_state"], "ACTIVE")

    def test_unprotected_end_uses_plain_language_memory(self):
        prev = v3.build_mobile_dashboard_view_model(
            combined("C1", 400), ui("C1", lifecycle="ACTIVE", opp=1, completed=0, tier="GOOD_36_50")
        )
        out = v4.build_mobile_dashboard_view_model(
            combined("C1", 380), ui("C1", lifecycle="PASS", completed=1, scanning=True), previous_model=prev
        )
        self.assertEqual(out["scalp_history_slot"]["headline"], "#1 ENDED · NO PROTECTED EXIT")
        self.assertNotIn("ENDED_UNARMED", out["scalp_history_slot"]["headline"])

    def test_tracking_only_memory_never_assumes_position(self):
        prev = v3.build_mobile_dashboard_view_model(
            combined("C1", 300), ui("C1", lifecycle="EXIT", opp=1, completed=1, tier="CAUTION_ABOVE_50")
        )
        out = v4.build_mobile_dashboard_view_model(
            combined("C1", 280), ui("C1", lifecycle="PASS", completed=1, scanning=True), previous_model=prev
        )
        hist = out["scalp_history_slot"]
        self.assertEqual(hist["headline"], "#1 ENDED · TRACKING ONLY")
        self.assertFalse(hist["manual_position_assumed"])
        self.assertIn("no manual position assumed", hist["detail"].lower())

    def test_protect_without_exit_handoff_is_blocked_not_memorialized(self):
        prev = v3.build_mobile_dashboard_view_model(
            combined("C1", 300), ui("C1", lifecycle="PROTECT", opp=1, completed=0, tier="GOOD_36_50")
        )
        out = v4.build_mobile_dashboard_view_model(
            combined("C1", 280), ui("C1", lifecycle="ACTIVE", opp=2, completed=1, tier="GOOD_36_50"), previous_model=prev
        )
        self.assertFalse(out["presentation_integrity"]["ok"])
        self.assertTrue(out["presentation_integrity"]["armed_no_exit_handoff_blocked"])
        self.assertEqual(out["presentation_integrity"]["blocked_reason"], "ARMED_NO_EXIT_HANDOFF_BLOCKED")
        self.assertFalse(out["scalp_history_slot"]["visible"])
        self.assertEqual(out["cards"]["SCALP_OPPORTUNITY"]["action"], "UP #2 · ENTRY AVAILABLE")

    def test_rollover_history_from_v3_takes_precedence(self):
        prev = v3.build_mobile_dashboard_view_model(
            combined("C1", 1), ui("C1", lifecycle="EXIT", opp=2, completed=2, tier="GOOD_36_50")
        )
        out = v4.build_mobile_dashboard_view_model(combined("C2", 899), ui("C2"), previous_model=prev)
        self.assertTrue(out["rollover"]["rollover_detected"])
        self.assertEqual(out["scalp_history_slot"]["headline"], "#2 COMPLETE · PROTECTED EXIT")
        self.assertFalse(out["scalp_memory_guard"]["same_contract"])

    def test_current_core_cards_match_v3_exactly(self):
        prev = v3.build_mobile_dashboard_view_model(
            combined("C1", 200), ui("C1", lifecycle="EXIT", opp=1, completed=1, tier="GOOD_36_50")
        )
        c = combined("C1", 180)
        u = ui("C1", lifecycle="ACTIVE", opp=2, completed=1, tier="IDEAL_25_35")
        expected = v3.build_mobile_dashboard_view_model(c, u, previous_model=prev)
        out = v4.build_mobile_dashboard_view_model(c, u, previous_model=prev)
        self.assertEqual(out["cards"], expected["cards"])
        self.assertEqual(out["card_order"], expected["card_order"])
        self.assertEqual(out["cards"]["CONTRACT_TIME_LEFT"]["visible_timer_count"], 1)

    def test_safety_is_explicit(self):
        out = v4.build_mobile_dashboard_view_model(combined("C1"), ui("C1"))
        self.assertFalse(out["safety"]["scalp_memory_actionable"])
        self.assertFalse(out["safety"]["scalp_memory_changes_current_signals"])
        self.assertFalse(out["presentation_integrity"]["orders"])
        self.assertFalse(out["safety"]["orders"])
        self.assertIsNone(out["safety"]["order_action"])


if __name__ == "__main__":
    unittest.main()
