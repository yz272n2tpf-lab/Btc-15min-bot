#!/usr/bin/env python3
import copy
import unittest
from unittest.mock import patch

import btc15_dashboard_session_shadow_v1 as shadow


def combined(contract="C1", seconds=600.0, *, final_state="WATCH", final_side=None, final_fair=None):
    return {
        "contract": contract,
        "canonical_seconds_left": seconds,
        "up_bid": .44,
        "up_ask": .45,
        "down_bid": .55,
        "down_ask": .56,
        "early": {"state": "PASS", "side": None, "ask": None, "fair": None, "edge": None},
        "final": {"state": final_state, "side": final_side, "fair": final_fair},
        "headline": "TEST",
        "context_labels": [],
        "scalp_contract_aligned": True,
        "scalp_source_fresh": True,
        "scalp_integration_ready": True,
        "scalp_source_age_sec": 1.0,
        "scalp_timer_delta_sec": 1.0,
        "scalp_block_reason": None,
        "scalp_opportunity_index": 1,
        "scalp_serial_opportunities_completed": 0,
        "scalp_scanning_for_next": False,
        "scalp_management_message": "SCALP ACTIVE · BUILDING",
        "scalp": {
            "state": "ACTIVE",
            "side": "UP",
            "entry_ask": .31,
            "current_bid": .34,
            "exec_gain": .03,
            "peak_exec_gain": .03,
            "seconds_left": seconds - 1,
        },
    }


def direct(contract="C1", *, state="ACTIVE", entry=.31, bid=.34, opp=1, completed=0):
    return {
        "contract": contract,
        "state": state,
        "side": "UP" if state != "PASS" else None,
        "entry_price": entry,
        "current_bid": bid,
        "exec_gain": None if entry is None or bid is None else bid - entry,
        "peak_exec_gain": None if entry is None or bid is None else bid - entry,
        "armed": state in {"PROTECT", "EXIT"},
        "pullback_detected": state in {"PROTECT", "EXIT"},
        "exit_triggered": state == "EXIT",
        "opportunity_index": opp,
        "serial_opportunities_completed": completed,
        "scanning_for_next": False,
        "source_fresh": True,
        "integration_ready": True,
        "manual_execution_only": True,
        "orders": False,
        "order_action": None,
    }


class DashboardSessionShadowV1Tests(unittest.TestCase):
    def setUp(self):
        shadow.SESSION.reset()
        with shadow.LOCK:
            shadow.STATE.clear()
            shadow.STATE.update({"ok": False, "version": shadow.VERSION, "status": "TEST_RESET", "orders": False})

    def test_both_sources_healthy_builds_stabilized_dashboard(self):
        out = shadow.build_ready_state(combined(), direct())
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "READY")
        self.assertEqual(out["source"]["transport"], "GET_ONLY")
        self.assertEqual(out["source"]["combined_status"], "HEALTHY")
        self.assertEqual(out["source"]["scalp_status"], "HEALTHY")
        self.assertIn("ENTRY AVAILABLE", out["dashboard"]["cards"]["SCALP_OPPORTUNITY"]["action"])
        self.assertFalse(out["orders"])
        self.assertFalse(out["numeric_flip_risk_visible"])
        self.assertFalse(out["watch_warning_thresholds_visible"])

    def test_direct_scalp_failure_keeps_current_final_and_timer_but_fails_scalp_closed(self):
        c = combined(seconds=500.0, final_state="LOCK", final_side="UP", final_fair=.94)
        out = shadow.build_ready_state(c, None, direct_error=RuntimeError("scalp down"))
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "READY_SCALP_FAIL_CLOSED")
        self.assertEqual(out["source"]["scalp_status"], "FAIL_CLOSED")
        dashboard = out["dashboard"]
        self.assertEqual(dashboard["cards"]["FINAL_OUTCOME"]["action"], "LOCK · UP")
        self.assertEqual(dashboard["cards"]["CONTRACT_TIME_LEFT"]["primary"], "8:20")
        self.assertTrue(dashboard["cards"]["SCALP_OPPORTUNITY"]["action"].startswith("WAIT ·"))
        self.assertEqual(dashboard["cards"]["SCALP_OPPORTUNITY"]["primary"], "NO ACTION · SOURCE NOT READY")
        self.assertTrue(dashboard["presentation_session"]["current_fail_closed"])

    def test_combined_failure_never_replays_old_actionable_dashboard(self):
        healthy = shadow.build_ready_state(combined(), direct())
        self.assertIn("ENTRY AVAILABLE", healthy["dashboard"]["cards"]["SCALP_OPPORTUNITY"]["action"])
        failed = shadow.fail_closed_combined(RuntimeError("combined down"))
        self.assertFalse(failed["ok"])
        self.assertEqual(failed["status"], "FAIL_CLOSED_COMBINED_SOURCE_UNAVAILABLE")
        for card_id in ("FINAL_OUTCOME", "EARLY_OPPORTUNITY", "SCALP_OPPORTUNITY"):
            self.assertTrue(failed["dashboard"]["cards"][card_id]["action"].startswith("WAIT ·"))
        self.assertEqual(failed["dashboard"]["cards"]["CONTRACT_TIME_LEFT"]["primary"], "—:—")
        self.assertFalse(failed["orders"])

    def test_refresh_combined_failure_does_not_mutate_session_history(self):
        shadow.build_ready_state(combined(), direct())
        before = shadow.SESSION.snapshot()
        with patch.object(shadow, "fetch_combined_state", side_effect=RuntimeError("no combined")):
            out = shadow.refresh_once()
        after = shadow.SESSION.snapshot()
        self.assertFalse(out["ok"])
        self.assertEqual(before["processed_frames"], after["processed_frames"])
        self.assertEqual(before["accepted"], after["accepted"])
        self.assertEqual(before["last_healthy"], after["last_healthy"])

    def test_refresh_direct_failure_uses_current_combined_in_session(self):
        shadow.build_ready_state(combined(seconds=600), direct())
        current = combined(seconds=540, final_state="LOCK", final_side="UP", final_fair=.94)
        with patch.object(shadow, "fetch_combined_state", return_value=current), patch.object(
            shadow, "fetch_direct_scalp_state", side_effect=RuntimeError("scalp unavailable")
        ):
            out = shadow.refresh_once()
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "READY_SCALP_FAIL_CLOSED")
        self.assertEqual(out["dashboard"]["cards"]["CONTRACT_TIME_LEFT"]["primary"], "9:00")
        self.assertEqual(out["dashboard"]["cards"]["FINAL_OUTCOME"]["action"], "LOCK · UP")
        self.assertTrue(out["dashboard"]["cards"]["SCALP_OPPORTUNITY"]["action"].startswith("WAIT ·"))

    def test_fetch_functions_are_get_only(self):
        seen = []

        def fake_get(url):
            seen.append(url)
            return {"url": url}

        with patch.object(shadow, "_get_json", side_effect=fake_get):
            a = shadow.fetch_combined_state()
            b = shadow.fetch_direct_scalp_state()
        self.assertEqual(seen, [shadow.COMBINED_URL, shadow.SCALP_URL])
        self.assertEqual(a["url"], shadow.COMBINED_URL)
        self.assertEqual(b["url"], shadow.SCALP_URL)

    def test_http_handler_has_no_post_or_order_action(self):
        self.assertFalse(hasattr(shadow.Handler, "do_POST"))
        out = shadow.build_ready_state(combined(), direct())
        self.assertFalse(out["orders"])
        self.assertIsNone(out["order_action"])
        self.assertFalse(out["production_logic_changed"])
        self.assertFalse(out["signal_thresholds_changed"])


if __name__ == "__main__":
    unittest.main()
