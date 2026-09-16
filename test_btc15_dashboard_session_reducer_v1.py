#!/usr/bin/env python3
import copy
import unittest

import btc15_dashboard_session_reducer_v1 as r


def model(contract="C1", *, lifecycle="PASS", action=None, primary=None,
          opp=None, completed=0, scanning=False, timer="10:00",
          final_action="FINAL CALL NOT READY", early_action="EARLY WATCH",
          integrity_ok=True, integrity_reason=None, context_state="NONE"):
    if action is None:
        action = {
            "PASS": "WATCHING FOR SCALP",
            "ACTIVE": f"UP #{opp or 1} · ENTRY AVAILABLE",
            "PROTECT": "PROTECT PROFITS",
            "EXIT": "EXIT NOW · PROTECT PROFITS",
        }[lifecycle]
    if primary is None:
        primary = {
            "PASS": "WAITING FOR A QUALIFIED MOVE",
            "ACTIVE": "HOLD · MOVE STILL BUILDING",
            "PROTECT": "MOVE REACHED PROTECTION LEVEL",
            "EXIT": "VALIDATED GIVEBACK EXIT",
        }[lifecycle]
    return {
        "contract": contract,
        "card_order": ["FINAL_OUTCOME", "EARLY_OPPORTUNITY", "CONTRACT_TIME_LEFT", "SCALP_OPPORTUNITY", "FLIP_RISK"],
        "cards": {
            "FINAL_OUTCOME": {"id": "FINAL_OUTCOME", "action": final_action},
            "EARLY_OPPORTUNITY": {"id": "EARLY_OPPORTUNITY", "action": early_action},
            "CONTRACT_TIME_LEFT": {"id": "CONTRACT_TIME_LEFT", "primary": timer, "visible_timer_count": 1},
            "SCALP_OPPORTUNITY": {
                "id": "SCALP_OPPORTUNITY",
                "action": action,
                "primary": primary,
                "underlying_lifecycle_state": lifecycle,
                "opportunity_index": opp,
                "serial_opportunities_completed": completed,
                "scanning_for_next": scanning,
            },
            "FLIP_RISK": {"id": "FLIP_RISK", "primary": "NOT CALIBRATED", "numeric_visible": False},
        },
        "scalp_history_slot": {"visible": False, "historical_only": True, "actionable": False},
        "manual_entry_context": {"state": context_state},
        "scalp_memory_guard": {"blocked_reason": None},
        "presentation_integrity": {
            "ok": integrity_ok,
            "blocked_reason": integrity_reason,
            "orders": False,
        },
        "safety": {"orders": False, "order_action": None},
    }


def scalp(m):
    return m["cards"]["SCALP_OPPORTUNITY"]


class DashboardSessionReducerV1Tests(unittest.TestCase):
    def test_initial_frame_is_accepted(self):
        cur = model(lifecycle="ACTIVE", opp=1)
        out = r.reduce_dashboard_session(None, cur)
        self.assertEqual(scalp(out), scalp(cur))
        self.assertFalse(out["session_reducer"]["scalp_frame_quarantined"])
        self.assertTrue(out["session_reducer"]["current_timer_authoritative"])

    def test_normal_active_to_protect_is_accepted(self):
        prev = model(lifecycle="ACTIVE", opp=1, timer="8:10")
        cur = model(lifecycle="PROTECT", opp=1, timer="8:09")
        out = r.reduce_dashboard_session(prev, cur)
        self.assertEqual(scalp(out)["underlying_lifecycle_state"], "PROTECT")
        self.assertEqual(out["cards"]["CONTRACT_TIME_LEFT"]["primary"], "8:09")
        self.assertFalse(out["session_reducer"]["scalp_frame_quarantined"])

    def test_same_opportunity_protect_to_active_regression_quarantines_only_scalp(self):
        prev = model(
            lifecycle="PROTECT", opp=1, timer="7:10",
            final_action="FINAL OLD", early_action="EARLY OLD", context_state="ACCEPTABLE_ENTRY_PATH",
        )
        cur = model(
            lifecycle="ACTIVE", opp=1, timer="7:09",
            final_action="FINAL NEW", early_action="EARLY NEW", context_state="UNKNOWN",
        )
        out = r.reduce_dashboard_session(prev, cur)
        self.assertTrue(out["session_reducer"]["scalp_frame_quarantined"])
        self.assertEqual(out["session_reducer"]["quarantine_reason"], "SAME_OPPORTUNITY_STATE_REGRESSION")
        self.assertEqual(scalp(out), scalp(prev))
        self.assertEqual(out["manual_entry_context"], prev["manual_entry_context"])
        self.assertEqual(out["cards"]["FINAL_OUTCOME"], cur["cards"]["FINAL_OUTCOME"])
        self.assertEqual(out["cards"]["EARLY_OPPORTUNITY"], cur["cards"]["EARLY_OPPORTUNITY"])
        self.assertEqual(out["cards"]["CONTRACT_TIME_LEFT"], cur["cards"]["CONTRACT_TIME_LEFT"])
        self.assertEqual(out["cards"]["FLIP_RISK"], cur["cards"]["FLIP_RISK"])

    def test_opportunity_index_regression_quarantines_scalp(self):
        prev = model(lifecycle="ACTIVE", opp=3, completed=2, timer="5:10")
        cur = model(lifecycle="ACTIVE", opp=2, completed=2, timer="5:09")
        out = r.reduce_dashboard_session(prev, cur)
        self.assertTrue(out["session_reducer"]["scalp_frame_quarantined"])
        self.assertEqual(out["session_reducer"]["quarantine_reason"], "OPPORTUNITY_INDEX_REGRESSION")
        self.assertEqual(scalp(out)["opportunity_index"], 3)
        self.assertEqual(out["cards"]["CONTRACT_TIME_LEFT"]["primary"], "5:09")

    def test_completed_count_regression_quarantines_scalp(self):
        prev = model(lifecycle="PASS", opp=None, completed=3, scanning=True, timer="4:50")
        cur = model(lifecycle="PASS", opp=None, completed=2, scanning=True, timer="4:49")
        out = r.reduce_dashboard_session(prev, cur)
        self.assertTrue(out["session_reducer"]["scalp_frame_quarantined"])
        self.assertEqual(out["session_reducer"]["quarantine_reason"], "SERIAL_COMPLETED_COUNT_REGRESSION")
        self.assertEqual(scalp(out)["serial_opportunities_completed"], 3)

    def test_later_opportunity_after_exit_is_accepted(self):
        prev = model(lifecycle="EXIT", opp=1, completed=1, timer="6:20")
        cur = model(lifecycle="ACTIVE", opp=2, completed=1, timer="6:19")
        out = r.reduce_dashboard_session(prev, cur)
        self.assertFalse(out["session_reducer"]["scalp_frame_quarantined"])
        self.assertEqual(scalp(out)["opportunity_index"], 2)
        self.assertEqual(scalp(out)["underlying_lifecycle_state"], "ACTIVE")

    def test_scanning_wait_after_exit_is_accepted(self):
        prev = model(lifecycle="EXIT", opp=2, completed=2)
        cur = model(lifecycle="PASS", opp=None, completed=2, scanning=True)
        out = r.reduce_dashboard_session(prev, cur)
        self.assertFalse(out["session_reducer"]["scalp_frame_quarantined"])
        self.assertTrue(scalp(out)["scanning_for_next"])

    def test_current_presentation_integrity_block_quarantines_scalp(self):
        prev = model(lifecycle="PROTECT", opp=1, completed=0, timer="6:00")
        cur = model(
            lifecycle="ACTIVE", opp=2, completed=1, timer="5:59",
            integrity_ok=False, integrity_reason="ARMED_NO_EXIT_HANDOFF_BLOCKED",
        )
        out = r.reduce_dashboard_session(prev, cur)
        self.assertTrue(out["session_reducer"]["scalp_frame_quarantined"])
        self.assertEqual(out["session_reducer"]["quarantine_reason"], "ARMED_NO_EXIT_HANDOFF_BLOCKED")
        self.assertEqual(scalp(out), scalp(prev))
        self.assertEqual(out["cards"]["CONTRACT_TIME_LEFT"]["primary"], "5:59")

    def test_source_fail_closed_wait_beats_smoothness(self):
        prev = model(lifecycle="PROTECT", opp=1, timer="5:10")
        cur = model(
            lifecycle="PASS", opp=None, completed=0, timer="5:09",
            action="WAIT · SCALP DATA NOT FRESH",
            primary="NO ACTION · SOURCE NOT READY",
        )
        out = r.reduce_dashboard_session(prev, cur)
        self.assertTrue(out["session_reducer"]["source_fail_closed_accepted"])
        self.assertFalse(out["session_reducer"]["scalp_frame_quarantined"])
        self.assertEqual(scalp(out)["action"], "WAIT · SCALP DATA NOT FRESH")
        self.assertEqual(scalp(out)["underlying_lifecycle_state"], "PASS")
        self.assertEqual(out["cards"]["CONTRACT_TIME_LEFT"]["primary"], "5:09")

    def test_recovery_from_fail_closed_accepts_healthy_current_state(self):
        prev = model(
            lifecycle="PASS", opp=None, timer="5:09",
            action="WAIT · SCALP DATA NOT FRESH",
            primary="NO ACTION · SOURCE NOT READY",
        )
        cur = model(lifecycle="ACTIVE", opp=1, timer="5:08")
        out = r.reduce_dashboard_session(prev, cur)
        self.assertFalse(out["session_reducer"]["scalp_frame_quarantined"])
        self.assertEqual(scalp(out)["underlying_lifecycle_state"], "ACTIVE")

    def test_contract_rollover_always_accepts_new_contract(self):
        prev = model("C1", lifecycle="EXIT", opp=4, completed=4, timer="0:00")
        cur = model("C2", lifecycle="PASS", opp=None, completed=0, timer="14:59")
        out = r.reduce_dashboard_session(prev, cur)
        self.assertTrue(out["session_reducer"]["contract_rollover"])
        self.assertFalse(out["session_reducer"]["scalp_frame_quarantined"])
        self.assertEqual(out["contract"], "C2")
        self.assertEqual(out["cards"]["CONTRACT_TIME_LEFT"]["primary"], "14:59")
        self.assertEqual(scalp(out)["serial_opportunities_completed"], 0)

    def test_reducer_does_not_mutate_inputs(self):
        prev = model(lifecycle="PROTECT", opp=1)
        cur = model(lifecycle="ACTIVE", opp=1)
        prev_before = copy.deepcopy(prev)
        cur_before = copy.deepcopy(cur)
        r.reduce_dashboard_session(prev, cur)
        self.assertEqual(prev, prev_before)
        self.assertEqual(cur, cur_before)

    def test_safety_metadata_is_explicit(self):
        out = r.reduce_dashboard_session(None, model())
        meta = out["session_reducer"]
        self.assertFalse(meta["signal_filtering"])
        self.assertFalse(meta["signal_suppression"])
        self.assertFalse(meta["orders"])
        self.assertTrue(meta["current_non_scalp_cards_authoritative"])
        self.assertTrue(meta["current_timer_authoritative"])


if __name__ == "__main__":
    unittest.main()
