#!/usr/bin/env python3
import copy
import unittest

import btc15_dashboard_session_payload_gate_v1 as gate
import btc15_dashboard_session_shadow_v1 as shadow


def combined(seconds=600.0, *, final_state="WATCH", final_side=None, final_fair=None):
    return {
        "contract": "C1",
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


def direct():
    return {
        "contract": "C1",
        "state": "ACTIVE",
        "side": "UP",
        "entry_price": .31,
        "current_bid": .34,
        "exec_gain": .03,
        "peak_exec_gain": .03,
        "armed": False,
        "pullback_detected": False,
        "exit_triggered": False,
        "opportunity_index": 1,
        "serial_opportunities_completed": 0,
        "scanning_for_next": False,
        "source_fresh": True,
        "integration_ready": True,
        "manual_execution_only": True,
        "orders": False,
        "order_action": None,
    }


class DashboardSessionPayloadGateV1Tests(unittest.TestCase):
    def setUp(self):
        shadow.SESSION.reset()

    def test_healthy_session_payload_is_accepted(self):
        raw = shadow.build_ready_state(combined(), direct())
        out = gate.gate_session_payload(raw)
        self.assertTrue(out["gate"]["accepted"])
        self.assertFalse(out["gate"]["fail_closed"])
        self.assertEqual(out["gate"]["reason"], "SAFE_SESSION_PAYLOAD")
        self.assertEqual(out["dashboard"]["cards"]["CONTRACT_TIME_LEFT"]["visible_timer_count"], 1)
        self.assertFalse(out["orders"])

    def test_safe_upstream_fail_closed_payload_is_accepted_as_fail_closed(self):
        raw = shadow.fail_closed_combined(RuntimeError("combined unavailable"))
        out = gate.gate_session_payload(raw)
        self.assertTrue(out["gate"]["accepted"])
        self.assertTrue(out["gate"]["fail_closed"])
        self.assertEqual(out["gate"]["reason"], "SAFE_FAIL_CLOSED_PAYLOAD")
        self.assertTrue(out["dashboard"]["cards"]["SCALP_OPPORTUNITY"]["action"].startswith("WAIT ·"))

    def test_order_capability_violation_forces_fresh_wait_payload(self):
        raw = shadow.build_ready_state(combined(), direct())
        raw["orders"] = True
        out = gate.gate_session_payload(raw)
        self.assertFalse(out["gate"]["accepted"])
        self.assertTrue(out["gate"]["fail_closed"])
        self.assertEqual(out["gate"]["reason"], "ORDER_CAPABILITY_PRESENT")
        self.assertTrue(out["dashboard"]["cards"]["SCALP_OPPORTUNITY"]["action"].startswith("WAIT ·"))
        self.assertFalse(out["orders"])

    def test_numeric_flip_leak_forces_wait(self):
        raw = shadow.build_ready_state(combined(), direct())
        raw["dashboard"]["cards"]["FLIP_RISK"]["numeric_visible"] = True
        raw["dashboard"]["cards"]["FLIP_RISK"]["numeric_value"] = 12.0
        out = gate.gate_session_payload(raw)
        self.assertFalse(out["gate"]["accepted"])
        self.assertEqual(out["gate"]["reason"], "FLIP_RISK_NUMERIC_LEAK")
        self.assertIsNone(out["dashboard"]["cards"]["FLIP_RISK"]["numeric_value"])
        self.assertFalse(out["dashboard"]["cards"]["FLIP_RISK"]["numeric_visible"])

    def test_uncertified_watch_threshold_visibility_forces_wait(self):
        raw = shadow.build_ready_state(combined(), direct())
        raw["watch_warning_thresholds_visible"] = True
        out = gate.gate_session_payload(raw)
        self.assertFalse(out["gate"]["accepted"])
        self.assertEqual(out["gate"]["reason"], "UNCERTIFIED_WATCH_THRESHOLD_VISIBLE")

    def test_multiple_timer_marker_forces_wait(self):
        raw = shadow.build_ready_state(combined(), direct())
        raw["dashboard"]["cards"]["CONTRACT_TIME_LEFT"]["visible_timer_count"] = 2
        out = gate.gate_session_payload(raw)
        self.assertFalse(out["gate"]["accepted"])
        self.assertEqual(out["gate"]["reason"], "CANONICAL_TIMER_COUNT_DRIFT")
        self.assertEqual(out["dashboard"]["cards"]["CONTRACT_TIME_LEFT"]["visible_timer_count"], 1)

    def test_card_set_drift_forces_wait(self):
        raw = shadow.build_ready_state(combined(), direct())
        raw["dashboard"]["cards"].pop("EARLY_OPPORTUNITY")
        out = gate.gate_session_payload(raw)
        self.assertFalse(out["gate"]["accepted"])
        self.assertEqual(out["gate"]["reason"], "CARD_SET_DRIFT")
        self.assertEqual(set(out["dashboard"]["cards"]), gate.REQUIRED_CARDS)

    def test_outer_fail_closed_cannot_leak_actionable_final(self):
        raw = shadow.fail_closed_combined(RuntimeError("combined unavailable"))
        raw["dashboard"]["cards"]["FINAL_OUTCOME"]["action"] = "LOCK · UP"
        out = gate.gate_session_payload(raw)
        self.assertFalse(out["gate"]["accepted"])
        self.assertEqual(out["gate"]["reason"], "OUTER_FAIL_CLOSED_ACTION_LEAK")
        self.assertTrue(out["dashboard"]["cards"]["FINAL_OUTCOME"]["action"].startswith("WAIT ·"))

    def test_gate_never_mutates_input(self):
        raw = shadow.build_ready_state(combined(), direct())
        before = copy.deepcopy(raw)
        gate.gate_session_payload(raw)
        self.assertEqual(raw, before)

    def test_signal_only_safety_is_fixed(self):
        raw = shadow.build_ready_state(combined(), direct())
        out = gate.gate_session_payload(raw)
        self.assertTrue(out["manual_execution_only"])
        self.assertFalse(out["orders"])
        self.assertIsNone(out["order_action"])
        self.assertFalse(out["gate"]["orders"])
        self.assertFalse(out["gate"]["signal_filtering"])
        self.assertFalse(out["gate"]["signal_suppression"])


if __name__ == "__main__":
    unittest.main()
