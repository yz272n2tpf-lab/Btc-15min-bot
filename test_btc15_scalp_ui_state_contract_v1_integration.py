#!/usr/bin/env python3
import unittest

from btc15_cross_service_payload_v4 import compose_cross_service_payload
from btc15_scalp_ui_state_contract_v1 import build_scalp_ui_state

MAIN = {
    "contract": "KXBTC15M-T",
    "timer": {"seconds_left": 300.0, "minutes_left": 5.0},
    "market": {
        "target": 78000.0,
        "up_bid": .62, "up_ask": .63,
        "down_bid": .37, "down_ask": .38,
    },
    "early": {
        "ready": True, "side": "UP", "ask": .34, "bid": .33,
        "fair": .79, "edge": .45, "status": "QUALIFIED", "source": "PROTECTED",
    },
    "final": {
        "ready": True, "side": "UP", "confidence": .94, "source": "PROTECTED",
        "recorded_final_call": False, "recorded_side": None, "recorded_confidence": None,
    },
}


def scalp(**kw):
    d = {
        "version": "GENERALIZED_SCALP_INTEGRATION_V5",
        "contract": "KXBTC15M-T",
        "state": "ACTIVE", "side": "DOWN",
        "entry_price": .40, "current_bid": .43,
        "exec_gain": .03, "peak_exec_gain": .03,
        "entry_seconds_left": 420.0, "contract_seconds_left": 298.5,
        "management_message": "SCALP ACTIVE · BUILDING",
        "armed": False, "pullback_detected": False, "exit_triggered": False,
        "opportunity_index": 2, "serial_opportunities_completed": 1,
        "scanning_for_next": False,
        "source_fresh": True, "source_event_age_sec": 1.0,
        "integration_ready": True,
        "manual_execution_only": True,
        "order_action": None,
        "orders": False,
        "numeric_flip_risk_validated": False,
    }
    d.update(kw)
    return d


class ScalpUIStateV5IntegrationTests(unittest.TestCase):
    def test_actual_cross_service_payload_maps_into_ui_contract(self):
        raw = scalp()
        combined = compose_cross_service_payload(MAIN, raw).to_dict()
        ui = build_scalp_ui_state(combined, raw)
        self.assertEqual(ui.contract, "KXBTC15M-T")
        self.assertEqual(ui.display_state, "ACTIVE")
        self.assertEqual(ui.lifecycle_state, "ACTIVE")
        self.assertEqual(ui.side, "DOWN")
        self.assertEqual(ui.entry_guidance["tier"], "GOOD_36_50")
        self.assertEqual(ui.opportunity_index, 2)
        self.assertEqual(ui.serial_opportunities_completed, 1)
        self.assertEqual(ui.horizon_context["early"]["state"], "QUALIFIED")
        self.assertEqual(ui.horizon_context["final"]["state"], "LOCK")
        self.assertIn("COUNTERTREND_SCALP", ui.horizon_context["context_labels"])
        self.assertIsNone(ui.horizon_context["blended_accuracy"])

    def test_stale_cross_service_payload_fails_ui_closed(self):
        raw = scalp(
            source_fresh=False,
            integration_ready=False,
            source_event_age_sec=31.0,
            integration_block_reason="SCALP SOURCE STALE",
        )
        combined = compose_cross_service_payload(MAIN, raw).to_dict()
        ui = build_scalp_ui_state(combined, raw)
        self.assertEqual(combined["scalp"]["state"], "PASS")
        self.assertEqual(ui.display_state, "WAIT")
        self.assertFalse(ui.source["app_ready"])
        self.assertTrue(ui.source["fail_closed"])

    def test_contract_mismatch_fails_ui_closed_without_touching_final(self):
        raw = scalp(contract="OTHER")
        combined = compose_cross_service_payload(MAIN, raw).to_dict()
        ui = build_scalp_ui_state(combined, raw)
        self.assertEqual(ui.display_state, "WAIT")
        self.assertEqual(ui.source["block_reason"], "CONTRACT_MISMATCH")
        self.assertEqual(ui.horizon_context["final"]["state"], "LOCK")

    def test_protect_context_never_turns_on_uncertified_watch_warning(self):
        raw = scalp(
            state="PROTECT",
            entry_price=.34,
            current_bid=.41,
            peak_exec_gain=.10,
            exec_gain=.07,
            management_message="PROTECT PROFITS · PULLBACK DETECTED",
            armed=True,
            pullback_detected=True,
            opportunity_index=3,
        )
        combined = compose_cross_service_payload(MAIN, raw).to_dict()
        ui = build_scalp_ui_state(combined, raw)
        self.assertEqual(ui.display_state, "PROTECT")
        self.assertTrue(ui.protection_armed)
        self.assertTrue(ui.pullback_context)
        self.assertFalse(ui.watch_warning["visible"])
        self.assertFalse(ui.watch_warning["certified"])
        self.assertFalse(ui.numeric_flip_risk["visible"])

    def test_signal_only_invariants_survive_full_composition(self):
        raw = scalp()
        combined = compose_cross_service_payload(MAIN, raw).to_dict()
        ui = build_scalp_ui_state(combined, raw)
        self.assertTrue(ui.manual_execution_only)
        self.assertFalse(ui.orders)
        self.assertIsNone(ui.order_action)
        self.assertFalse(ui.numeric_flip_risk["visible"])


if __name__ == "__main__":
    unittest.main()
