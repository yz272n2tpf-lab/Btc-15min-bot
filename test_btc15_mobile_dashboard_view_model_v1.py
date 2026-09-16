#!/usr/bin/env python3
import unittest

import btc15_mobile_dashboard_view_model_v1 as vm


def combined(*, final_state="WATCH", final_side=None, final_fair=None,
             early_state="PASS", early_side=None, early_ask=None,
             early_fair=None, early_edge=None, up_ask=.62, down_ask=.38,
             seconds_left=512.0):
    return {
        "contract": "KXBTC15M-T",
        "canonical_seconds_left": seconds_left,
        "up_ask": up_ask,
        "down_ask": down_ask,
        "early": {
            "state": early_state,
            "side": early_side,
            "ask": early_ask,
            "fair": early_fair,
            "edge": early_edge,
        },
        "final": {
            "state": final_state,
            "side": final_side,
            "fair": final_fair,
        },
    }


def ui(*, lifecycle="PASS", side=None, tier="UNAVAILABLE", ask_c=None,
       bid_c=None, gain_c=None, peak_c=None, giveback_c=None, opp=None,
       completed=0, scanning=False, app_ready=True, block=None):
    return {
        "contract": "KXBTC15M-T",
        "display_state": "WAIT" if lifecycle == "PASS" else lifecycle,
        "lifecycle_state": lifecycle,
        "side": side,
        "opportunity_index": opp,
        "serial_opportunities_completed": completed,
        "scanning_for_next": scanning,
        "entry_guidance": {"tier": tier},
        "entry_ask_c": ask_c,
        "current_bid_c": bid_c,
        "exec_gain_c": gain_c,
        "peak_exec_gain_c": peak_c,
        "giveback_from_peak_c": giveback_c,
        "source": {
            "app_ready": app_ready,
            "source_fresh": app_ready,
            "integration_ready": app_ready,
            "block_reason": block,
        },
    }


class MobileDashboardViewModelV1Tests(unittest.TestCase):
    def test_fixed_card_order_and_single_timer(self):
        out = vm.build_mobile_dashboard_view_model(combined(), ui())
        self.assertEqual(out["card_order"], list(vm.CARD_ORDER))
        self.assertTrue(out["layout"]["single_canonical_timer"])
        self.assertEqual(out["cards"]["CONTRACT_TIME_LEFT"]["visible_timer_count"], 1)
        self.assertEqual(out["cards"]["CONTRACT_TIME_LEFT"]["primary"], "8:32")

    def test_final_lock_with_expensive_entry_separates_outcome_from_entry(self):
        out = vm.build_final_card(
            combined(final_state="LOCK", final_side="UP", final_fair=.94, up_ask=.82)
        )
        self.assertEqual(out["action"], "LOCK · UP")
        self.assertEqual(out["primary"], "UP 94%")
        self.assertEqual(out["subline"], "OUTCOME LOCK · ENTRY EXPENSIVE")
        self.assertEqual(out["fixed_row_count"], 4)
        self.assertEqual(len(out["rows"]), 4)

    def test_early_good_entry(self):
        out = vm.build_early_card(
            combined(
                early_state="QUALIFIED", early_side="DOWN",
                early_ask=.44, early_fair=.78, early_edge=.34,
            )
        )
        self.assertEqual(out["action"], "EARLY DOWN OPPORTUNITY")
        self.assertEqual(out["primary"], "GOOD ENTRY")
        self.assertEqual(out["fixed_row_count"], 4)

    def test_expensive_active_scalp_is_tracking_only(self):
        out = vm.build_scalp_card(
            ui(
                lifecycle="ACTIVE", side="UP", tier="CAUTION_ABOVE_50",
                ask_c=58, bid_c=61, gain_c=3, peak_c=3, giveback_c=0,
                opp=1,
            )
        )
        self.assertTrue(out["tracking_only"])
        self.assertFalse(out["manual_entry_path_available"])
        self.assertEqual(out["action"], "UP #1 · TRACKING ONLY")
        self.assertEqual(out["primary"], "MOVE VALID · NO ENTRY · DON'T CHASE")
        self.assertEqual(out["rows"][-1]["value"], "MODEL TRACKING ONLY · NO POSITION ASSUMED")
        self.assertNotIn("PROTECT PROFITS", out["action"])

    def test_expensive_internal_exit_never_tells_user_to_exit(self):
        out = vm.build_scalp_card(
            ui(
                lifecycle="EXIT", side="DOWN", tier="CAUTION_ABOVE_50",
                ask_c=71, bid_c=77, gain_c=6, peak_c=11, giveback_c=5,
                opp=2, completed=1,
            )
        )
        self.assertEqual(out["underlying_lifecycle_state"], "EXIT")
        self.assertTrue(out["tracking_only"])
        self.assertEqual(out["action"], "DOWN #2 · TRACKING ONLY")
        self.assertNotIn("EXIT NOW", out["action"])
        self.assertEqual(out["rows"][-1]["value"], "MODEL TRACKING ONLY · NO POSITION ASSUMED")

    def test_acceptable_protect_and_exit_are_user_facing(self):
        protect = vm.build_scalp_card(
            ui(
                lifecycle="PROTECT", side="UP", tier="GOOD_36_50",
                ask_c=44, bid_c=52, gain_c=8, peak_c=10, giveback_c=2,
                opp=1,
            )
        )
        self.assertEqual(protect["action"], "PROTECT PROFITS")
        self.assertFalse(protect["tracking_only"])

        exit_card = vm.build_scalp_card(
            ui(
                lifecycle="EXIT", side="UP", tier="IDEAL_25_35",
                ask_c=31, bid_c=38, gain_c=7, peak_c=12, giveback_c=5,
                opp=1,
            )
        )
        self.assertEqual(exit_card["action"], "EXIT NOW · PROTECT PROFITS")
        self.assertFalse(exit_card["tracking_only"])

    def test_stale_source_uses_plain_language_wait(self):
        out = vm.build_scalp_card(
            ui(
                lifecycle="ACTIVE", side="UP", tier="IDEAL_25_35",
                ask_c=31, opp=1, app_ready=False, block="SCALP_SOURCE_STALE",
            )
        )
        self.assertEqual(out["action"], "WAIT · SCALP DATA NOT FRESH")
        self.assertEqual(out["primary"], "NO ACTION · SOURCE NOT READY")

    def test_scanning_for_next_keeps_serial_memory(self):
        out = vm.build_scalp_card(
            ui(lifecycle="PASS", completed=2, scanning=True, app_ready=True)
        )
        self.assertEqual(out["action"], "WATCHING FOR SCALP")
        self.assertEqual(out["primary"], "SCANNING FOR #3")
        self.assertEqual(out["serial_opportunities_completed"], 2)

    def test_scalp_rows_are_fixed_size(self):
        for state, tier in [
            ("PASS", "UNAVAILABLE"),
            ("ACTIVE", "GOOD_36_50"),
            ("PROTECT", "GOOD_36_50"),
            ("EXIT", "IDEAL_25_35"),
        ]:
            with self.subTest(state=state):
                out = vm.build_scalp_card(ui(lifecycle=state, side="UP", tier=tier, ask_c=40, opp=1))
                self.assertEqual(out["fixed_row_count"], 6)
                self.assertEqual(len(out["rows"]), 6)

    def test_flip_risk_has_no_numeric_value(self):
        out = vm.build_flip_risk_card(ui())
        self.assertEqual(out["primary"], "NOT CALIBRATED")
        self.assertIsNone(out["numeric_value"])
        self.assertFalse(out["numeric_visible"])

    def test_safety_contract(self):
        out = vm.build_mobile_dashboard_view_model(combined(), ui())
        self.assertTrue(out["safety"]["manual_execution_only"])
        self.assertFalse(out["safety"]["orders"])
        self.assertIsNone(out["safety"]["order_action"])
        self.assertFalse(out["safety"]["numeric_flip_risk_visible"])
        self.assertFalse(out["safety"]["watch_warning_thresholds_visible"])
        self.assertIsNone(out["safety"]["blended_accuracy"])


if __name__ == "__main__":
    unittest.main()
