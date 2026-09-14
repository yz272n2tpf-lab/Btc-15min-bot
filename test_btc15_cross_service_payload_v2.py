#!/usr/bin/env python3
import unittest

from btc15_cross_service_payload_v2 import compose_cross_service_payload


SNAP = {
    "contract": "KXBTC15M-TEST",
    "time_left_min": 5.0,
    "kalshi_target": 78000.0,
    "up_bid": .61,
    "up_ask": .62,
    "down_bid": .38,
    "down_ask": .39,
    "fair_preferred_side": "UP",
    "fair_preferred": .79,
    "preferred_kalshi_ask": .34,
    "fair_edge_vs_ask": .45,
    "entry_tournament_ready": True,
    "opportunity_status": "OPPORTUNITY",
    "final_status": "FINAL CALL",
    "final_side": "UP",
    "final_confidence": .94,
    "final_call_source": "TOURNAMENT WINNER",
}


def scalp(state="ACTIVE", contract="KXBTC15M-TEST", side="DOWN", left=299.0, message=None):
    out = {
        "contract": contract,
        "state": state,
        "side": side,
        "entry_price": .40,
        "current_bid": .46,
        "peak_exec_gain": .08,
        "exec_gain": .06,
        "entry_seconds_left": 500,
        "contract_seconds_left": left,
        "management_message": message,
        "manual_execution_only": True,
        "order_action": None,
    }
    return out


class CrossServicePayloadTests(unittest.TestCase):
    def test_aligned_contract_composes_all_three_paths(self):
        x = compose_cross_service_payload(SNAP, scalp()).to_dict()
        self.assertEqual(x["contract"], "KXBTC15M-TEST")
        self.assertEqual(x["actionable_paths"], ("EARLY", "FINAL", "SCALP"))
        self.assertTrue(x["union_actionable"])
        self.assertTrue(x["scalp_contract_aligned"])
        self.assertIn("COUNTERTREND_SCALP", x["context_labels"])
        self.assertIn("MIXED_HORIZONS", x["context_labels"])

    def test_canonical_timer_always_comes_from_protected_main_snapshot(self):
        x = compose_cross_service_payload(SNAP, scalp(left=297.5)).to_dict()
        self.assertAlmostEqual(x["canonical_seconds_left"], 300.0)
        self.assertAlmostEqual(x["scalp_timer_delta_sec"], 2.5)

    def test_contract_mismatch_fails_scalp_closed(self):
        x = compose_cross_service_payload(SNAP, scalp(contract="OLD")).to_dict()
        self.assertFalse(x["scalp_contract_aligned"])
        self.assertEqual(x["scalp"]["state"], "PASS")
        self.assertEqual(x["scalp_management_message"], "SCALP WAIT · CONTRACT SYNC")
        self.assertEqual(x["actionable_paths"], ("EARLY", "FINAL"))

    def test_exit_has_display_priority_but_final_remains_visible(self):
        s = scalp(state="EXIT", message="EXIT / PROTECT PROFITS NOW")
        x = compose_cross_service_payload(SNAP, s).to_dict()
        self.assertEqual(x["headline"], "SCALP_EXIT")
        self.assertEqual(x["final"]["state"], "LOCK")
        self.assertIn("FINAL", x["actionable_paths"])
        self.assertIn("SCALP", x["actionable_paths"])

    def test_protect_message_survives_bridge_unchanged(self):
        msg = "PROTECT PROFITS · PULLBACK DETECTED"
        x = compose_cross_service_payload(SNAP, scalp(state="PROTECT", message=msg)).to_dict()
        self.assertEqual(x["headline"], "SCALP_PROTECT")
        self.assertEqual(x["scalp_management_message"], msg)

    def test_watch_final_stays_non_actionable_if_early_and_scalp_pass(self):
        row = dict(
            SNAP,
            entry_tournament_ready=False,
            opportunity_status="WATCH",
            final_status="WATCH",
            final_call_source="NONE",
        )
        s = scalp(state="PASS", side=None)
        x = compose_cross_service_payload(row, s).to_dict()
        self.assertEqual(x["actionable_paths"], ())
        self.assertFalse(x["union_actionable"])

    def test_malformed_actionable_scalp_without_side_fails_closed(self):
        s = scalp(state="ACTIVE", side=None)
        x = compose_cross_service_payload(SNAP, s).to_dict()
        self.assertEqual(x["scalp"]["state"], "PASS")
        self.assertEqual(x["actionable_paths"], ("EARLY", "FINAL"))

    def test_no_order_or_numeric_flip_risk_output(self):
        x = compose_cross_service_payload(SNAP, scalp()).to_dict()
        self.assertTrue(x["manual_execution_only"])
        self.assertFalse(x["numeric_flip_risk_validated"])
        self.assertIsNone(x["order_action"])
        self.assertNotIn("flip_risk_percent", x)


if __name__ == "__main__":
    unittest.main()
