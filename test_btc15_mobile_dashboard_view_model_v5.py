#!/usr/bin/env python3
import unittest

import btc15_mobile_dashboard_view_model_v5 as v5


def combined(contract="C1", seconds=600):
    return {
        "contract": contract,
        "canonical_seconds_left": seconds,
        "up_ask": .44,
        "down_ask": .56,
        "early": {"state": "PASS", "side": None, "ask": None, "fair": None, "edge": None},
        "final": {"state": "WATCH", "side": None, "fair": None},
    }


def ui(contract="C1", *, lifecycle="ACTIVE", opp=1, completed=0, tier="GOOD_36_50", scanning=False, entry_c=None):
    if entry_c is None:
        entry_c = {"IDEAL_25_35": 31.0, "GOOD_36_50": 44.0, "CAUTION_ABOVE_50": 68.0, "UNAVAILABLE": None}.get(tier)
    return {
        "contract": contract,
        "display_state": "WAIT" if lifecycle == "PASS" else lifecycle,
        "lifecycle_state": lifecycle,
        "side": None if lifecycle == "PASS" else "UP",
        "opportunity_index": opp,
        "serial_opportunities_completed": completed,
        "scanning_for_next": scanning,
        "entry_guidance": {"tier": tier},
        "entry_ask_c": entry_c,
        "current_bid_c": None if entry_c is None else entry_c + 5.0,
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


def row_value(card, label):
    return next(r["value"] for r in card["rows"] if r["label"] == label)


class MobileDashboardViewModelV5Tests(unittest.TestCase):
    def test_initial_good_entry_sets_acceptable_context(self):
        out = v5.build_mobile_dashboard_view_model(combined(), ui(tier="GOOD_36_50"))
        self.assertEqual(out["manual_entry_context"]["state"], "ACCEPTABLE_ENTRY_PATH")
        self.assertEqual(out["manual_entry_context"]["origin_entry_price_text"], "44¢")
        self.assertFalse(out["manual_entry_context"]["manual_position_confirmed"])
        self.assertEqual(out["cards"]["SCALP_OPPORTUNITY"]["action"], "UP #1 · ENTRY AVAILABLE")

    def test_initial_above50_sets_tracking_context(self):
        out = v5.build_mobile_dashboard_view_model(combined(), ui(tier="CAUTION_ABOVE_50"))
        self.assertEqual(out["manual_entry_context"]["state"], "TRACKING_ONLY_NO_POSITION")
        scalp = out["cards"]["SCALP_OPPORTUNITY"]
        self.assertTrue(scalp["tracking_only"])
        self.assertFalse(scalp["manual_entry_path_available"])
        self.assertIn("TRACKING ONLY", scalp["action"])
        self.assertIn("DON'T CHASE", scalp["primary"])

    def test_tracking_context_cannot_flip_to_position_bearing_wording(self):
        prev = v5.build_mobile_dashboard_view_model(combined(), ui(tier="CAUTION_ABOVE_50"))
        out = v5.build_mobile_dashboard_view_model(
            combined(seconds=500),
            ui(lifecycle="PROTECT", tier="GOOD_36_50", entry_c=44.0),
            previous_model=prev,
        )
        self.assertEqual(out["manual_entry_context"]["state"], "TRACKING_ONLY_NO_POSITION")
        scalp = out["cards"]["SCALP_OPPORTUNITY"]
        self.assertTrue(scalp["tracking_only"])
        self.assertFalse(scalp["manual_entry_path_available"])
        self.assertIn("TRACKING ONLY", scalp["action"])
        self.assertNotIn("PROTECT PROFITS", scalp["action"])
        self.assertEqual(row_value(scalp, "Profit Protection"), "MODEL TRACKING ONLY · NO POSITION ASSUMED")
        self.assertEqual(scalp["underlying_lifecycle_state"], "PROTECT")

    def test_acceptable_context_survives_missing_entry_telemetry_at_protect(self):
        prev = v5.build_mobile_dashboard_view_model(combined(), ui(tier="IDEAL_25_35", entry_c=31.0))
        out = v5.build_mobile_dashboard_view_model(
            combined(seconds=480),
            ui(lifecycle="PROTECT", tier="UNAVAILABLE", entry_c=None),
            previous_model=prev,
        )
        self.assertEqual(out["manual_entry_context"]["state"], "ACCEPTABLE_ENTRY_PATH")
        scalp = out["cards"]["SCALP_OPPORTUNITY"]
        self.assertEqual(scalp["action"], "PROTECT PROFITS")
        self.assertEqual(scalp["primary"], "MOVE REACHED PROTECTION LEVEL")
        self.assertFalse(scalp["tracking_only"])
        self.assertTrue(scalp["manual_entry_path_available"])
        self.assertEqual(row_value(scalp, "Entry Price"), "31¢")
        self.assertEqual(row_value(scalp, "Profit Protection"), "WATCH FOR GIVEBACK")
        self.assertEqual(scalp["underlying_lifecycle_state"], "PROTECT")

    def test_acceptable_context_survives_missing_entry_telemetry_at_exit(self):
        prev = v5.build_mobile_dashboard_view_model(combined(), ui(tier="GOOD_36_50", entry_c=44.0))
        out = v5.build_mobile_dashboard_view_model(
            combined(seconds=450),
            ui(lifecycle="EXIT", tier="UNAVAILABLE", entry_c=None),
            previous_model=prev,
        )
        scalp = out["cards"]["SCALP_OPPORTUNITY"]
        self.assertEqual(scalp["action"], "EXIT NOW · PROTECT PROFITS")
        self.assertEqual(scalp["primary"], "VALIDATED GIVEBACK EXIT")
        self.assertEqual(row_value(scalp, "Entry Price"), "44¢")
        self.assertEqual(row_value(scalp, "Profit Protection"), "PROTECTED EXIT")
        self.assertEqual(scalp["underlying_lifecycle_state"], "EXIT")

    def test_new_opportunity_resets_tracking_context(self):
        prev = v5.build_mobile_dashboard_view_model(combined(), ui(opp=1, tier="CAUTION_ABOVE_50"))
        out = v5.build_mobile_dashboard_view_model(
            combined(seconds=400),
            ui(opp=2, completed=1, tier="IDEAL_25_35", entry_c=31.0),
            previous_model=prev,
        )
        self.assertEqual(out["manual_entry_context"]["state"], "ACCEPTABLE_ENTRY_PATH")
        self.assertEqual(out["manual_entry_context"]["opportunity_index"], 2)
        self.assertEqual(out["cards"]["SCALP_OPPORTUNITY"]["action"], "UP #2 · ENTRY AVAILABLE")

    def test_contract_rollover_resets_context(self):
        prev = v5.build_mobile_dashboard_view_model(combined("C1"), ui("C1", tier="CAUTION_ABOVE_50"))
        out = v5.build_mobile_dashboard_view_model(
            combined("C2", 899),
            ui("C2", opp=1, tier="IDEAL_25_35", entry_c=31.0),
            previous_model=prev,
        )
        self.assertTrue(out["rollover"]["rollover_detected"])
        self.assertEqual(out["manual_entry_context"]["contract"], "C2")
        self.assertEqual(out["manual_entry_context"]["state"], "ACCEPTABLE_ENTRY_PATH")

    def test_scanning_state_has_no_active_entry_context(self):
        prev = v5.build_mobile_dashboard_view_model(combined(), ui(lifecycle="EXIT", opp=1, completed=1, tier="GOOD_36_50"))
        out = v5.build_mobile_dashboard_view_model(
            combined(seconds=300),
            ui(lifecycle="PASS", opp=None, completed=1, tier="UNAVAILABLE", scanning=True),
            previous_model=prev,
        )
        self.assertEqual(out["manual_entry_context"]["state"], "NONE")
        self.assertEqual(out["cards"]["SCALP_OPPORTUNITY"]["primary"], "SCANNING FOR #2")
        self.assertTrue(out["scalp_history_slot"]["visible"])

    def test_other_cards_are_not_changed_by_entry_context_layer(self):
        prev = v5.build_mobile_dashboard_view_model(combined(), ui(tier="GOOD_36_50"))
        out = v5.build_mobile_dashboard_view_model(
            combined(seconds=300),
            ui(lifecycle="PROTECT", tier="UNAVAILABLE", entry_c=None),
            previous_model=prev,
        )
        for card_id in ("FINAL_OUTCOME", "EARLY_OPPORTUNITY", "CONTRACT_TIME_LEFT", "FLIP_RISK"):
            self.assertIn(card_id, out["cards"])
        self.assertEqual(out["cards"]["CONTRACT_TIME_LEFT"]["visible_timer_count"], 1)
        self.assertFalse(out["cards"]["FLIP_RISK"]["numeric_visible"])

    def test_safety_never_claims_confirmed_position(self):
        out = v5.build_mobile_dashboard_view_model(combined(), ui(tier="GOOD_36_50"))
        self.assertFalse(out["safety"]["manual_position_confirmed"])
        self.assertFalse(out["safety"]["manual_entry_context_signal_filtering"])
        self.assertFalse(out["safety"]["manual_entry_context_signal_suppression"])
        self.assertFalse(out["safety"]["manual_entry_context_changes_underlying_lifecycle"])
        self.assertFalse(out["safety"]["orders"])
        self.assertIsNone(out["safety"]["order_action"])


if __name__ == "__main__":
    unittest.main()
