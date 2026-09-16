import unittest

import btc15_scalp_ui_state_contract_v1 as ui


def combined(*, state="PASS", ask=None, bid=None, peak=None, gain=None,
             aligned=True, fresh=True, ready=True, opp=1, completed=0,
             scan_next=False, block=None):
    return {
        "contract": "KXBTC15M-TEST",
        "canonical_seconds_left": 601.5,
        "headline": "SCALP_ACTIVE" if state == "ACTIVE" else state,
        "early": {"state": "PASS", "side": None},
        "final": {"state": "WATCH", "side": None},
        "context_labels": [],
        "scalp": {
            "state": state,
            "side": "UP" if state != "PASS" else None,
            "entry_ask": ask,
            "current_bid": bid,
            "peak_exec_gain": peak,
            "exec_gain": gain,
            "seconds_left": 600.0,
        },
        "scalp_contract_aligned": aligned,
        "scalp_source_fresh": fresh,
        "scalp_integration_ready": ready,
        "scalp_source_age_sec": 2.0,
        "scalp_timer_delta_sec": 1.5,
        "scalp_block_reason": block,
        "scalp_management_message": None,
        "scalp_opportunity_index": opp,
        "scalp_serial_opportunities_completed": completed,
        "scalp_scanning_for_next": scan_next,
        "manual_execution_only": True,
        "numeric_flip_risk_validated": False,
        "orders": False,
        "order_action": None,
    }


class ScalpUIStateContractTests(unittest.TestCase):
    def test_entry_bands_are_presentation_only(self):
        self.assertEqual(ui.entry_guidance(.31)["tier"], "IDEAL_25_35")
        self.assertEqual(ui.entry_guidance(.44)["tier"], "GOOD_36_50")
        self.assertEqual(ui.entry_guidance(.58)["tier"], "CAUTION_ABOVE_50")
        self.assertEqual(ui.entry_guidance(.20)["tier"], "BELOW_IDEAL_BAND")
        self.assertTrue(ui.entry_guidance(.31)["presentation_only"])

    def test_high_price_does_not_suppress_active_lifecycle(self):
        out = ui.build_scalp_ui_state(combined(state="ACTIVE", ask=.58, bid=.60))
        self.assertEqual(out.lifecycle_state, "ACTIVE")
        self.assertEqual(out.display_state, "ACTIVE")
        self.assertEqual(out.entry_guidance["tier"], "CAUTION_ABOVE_50")
        self.assertFalse(out.entry_guidance["within_target_le50"])

    def test_ideal_entry_and_serial_context(self):
        out = ui.build_scalp_ui_state(combined(state="ACTIVE", ask=.31, bid=.33, opp=3, completed=2))
        self.assertEqual(out.entry_ask_c, 31.0)
        self.assertEqual(out.current_bid_c, 33.0)
        self.assertEqual(out.entry_guidance["tier"], "IDEAL_25_35")
        self.assertEqual(out.opportunity_index, 3)
        self.assertEqual(out.serial_opportunities_completed, 2)

    def test_protect_and_pullback_context_without_uncertified_watch(self):
        direct = {
            "state": "PROTECT",
            "armed": True,
            "pullback_detected": True,
            "exit_triggered": False,
            "opportunity_index": 2,
            "serial_opportunities_completed": 1,
        }
        out = ui.build_scalp_ui_state(
            combined(state="PROTECT", ask=.42, bid=.49, peak=.10, gain=.07, opp=2, completed=1),
            direct,
        )
        self.assertEqual(out.display_state, "PROTECT")
        self.assertTrue(out.protection_armed)
        self.assertTrue(out.pullback_context)
        self.assertEqual(out.giveback_from_peak_c, 3.0)
        self.assertFalse(out.watch_warning["visible"])
        self.assertFalse(out.watch_warning["certified"])
        self.assertFalse(out.watch_warning["research_thresholds_exposed"])

    def test_frozen_exit_can_surface(self):
        direct = {"state": "EXIT", "armed": True, "exit_triggered": True}
        out = ui.build_scalp_ui_state(
            combined(state="EXIT", ask=.40, bid=.46, peak=.11, gain=.06), direct
        )
        self.assertEqual(out.display_state, "EXIT")
        self.assertTrue(out.frozen_exit_triggered)
        self.assertTrue(out.watch_warning["frozen_exit_remains_visible"])
        self.assertFalse(out.watch_warning["visible"])

    def test_stale_or_misaligned_source_fails_closed_to_wait(self):
        out = ui.build_scalp_ui_state(
            combined(state="ACTIVE", ask=.35, bid=.38, aligned=False, fresh=True, ready=False, block="CONTRACT_MISMATCH")
        )
        self.assertEqual(out.lifecycle_state, "ACTIVE")
        self.assertEqual(out.display_state, "WAIT")
        self.assertTrue(out.source["fail_closed"])
        self.assertFalse(out.source["app_ready"])
        self.assertEqual(out.source["block_reason"], "CONTRACT_MISMATCH")

    def test_numeric_flip_risk_never_leaks(self):
        raw = combined(state="ACTIVE", ask=.33, bid=.35)
        raw["numeric_flip_risk_validated"] = True
        raw["flip_risk"] = 0.07
        out = ui.build_scalp_ui_state(raw)
        self.assertFalse(out.numeric_flip_risk["visible"])
        self.assertIsNone(out.numeric_flip_risk["value"])
        self.assertFalse(out.numeric_flip_risk["certified"])

    def test_horizons_stay_separate_no_blended_accuracy(self):
        raw = combined(state="ACTIVE", ask=.34, bid=.36)
        raw["early"] = {"state": "QUALIFIED", "side": "UP"}
        raw["final"] = {"state": "LOCK", "side": "DOWN"}
        raw["context_labels"] = ["MIXED_HORIZONS"]
        out = ui.build_scalp_ui_state(raw)
        self.assertEqual(out.horizon_context["early"]["state"], "QUALIFIED")
        self.assertEqual(out.horizon_context["final"]["state"], "LOCK")
        self.assertTrue(out.horizon_context["horizons_remain_separate"])
        self.assertIsNone(out.horizon_context["blended_accuracy"])

    def test_safety_fields_are_fixed(self):
        out = ui.build_scalp_ui_state(combined(state="PASS"))
        self.assertTrue(out.manual_execution_only)
        self.assertFalse(out.orders)
        self.assertIsNone(out.order_action)


if __name__ == "__main__":
    unittest.main()
