#!/usr/bin/env python3
import unittest

from btc15_cross_service_payload_v3 import compose_cross_service_payload

BASE = {
    "contract": "KXBTC15M-T",
    "time_left_min": 5.0,
    "kalshi_target": 78000.0,
    "up_bid": .62,
    "up_ask": .63,
    "down_bid": .37,
    "down_ask": .38,
    "fair_preferred_side": "UP",
    "fair_preferred": .94,
    "preferred_kalshi_ask": .34,
    "fair_edge_vs_ask": .60,
    "entry_tournament_ready": True,
    "opportunity_status": "OPPORTUNITY",
    "final_status": "FINAL CALL",
    "final_side": "UP",
    "final_confidence": .94,
    "final_call_source": "TOURNAMENT WINNER",
}


def scalp(**kw):
    d = {
        "version": "GENERALIZED_SCALP_INTEGRATION_V4",
        "contract": "KXBTC15M-T",
        "state": "ACTIVE",
        "side": "DOWN",
        "entry_price": .40,
        "current_bid": .43,
        "exec_gain": .03,
        "peak_exec_gain": .03,
        "entry_seconds_left": 420,
        "contract_seconds_left": 299,
        "management_message": "SCALP ACTIVE · BUILDING",
        "source_fresh": True,
        "source_event_age_sec": 1.2,
        "integration_ready": True,
        "manual_execution_only": True,
        "order_action": None,
    }
    d.update(kw)
    return d


class CrossServicePayloadV3Tests(unittest.TestCase):
    def test_fresh_active_scalp_composes_and_keeps_conflict_visible(self):
        x = compose_cross_service_payload(BASE, scalp()).to_dict()
        self.assertEqual(x["scalp"]["state"], "ACTIVE")
        self.assertIn("SCALP", x["actionable_paths"])
        self.assertIn("COUNTERTREND_SCALP", x["context_labels"])
        self.assertTrue(x["scalp_source_fresh"])
        self.assertTrue(x["scalp_contract_aligned"])

    def test_stale_active_scalp_fails_closed(self):
        x = compose_cross_service_payload(
            BASE,
            scalp(source_fresh=False, integration_ready=False,
                  source_event_age_sec=31.0,
                  integration_block_reason="SCALP SOURCE STALE"),
        ).to_dict()
        self.assertEqual(x["scalp"]["state"], "PASS")
        self.assertNotIn("SCALP", x["actionable_paths"])
        self.assertEqual(x["scalp_management_message"], "SCALP WAIT · STALE SOURCE")
        self.assertFalse(x["scalp_source_fresh"])
        # Protected EARLY and FINAL still pass through untouched.
        self.assertEqual(x["early"]["state"], "QUALIFIED")
        self.assertEqual(x["early"]["side"], "UP")
        self.assertEqual(x["final"]["state"], "LOCK")
        self.assertEqual(x["final"]["side"], "UP")

    def test_contract_mismatch_fails_closed(self):
        x = compose_cross_service_payload(BASE, scalp(contract="OTHER")).to_dict()
        self.assertEqual(x["scalp"]["state"], "PASS")
        self.assertFalse(x["scalp_contract_aligned"])
        self.assertEqual(x["scalp_management_message"], "SCALP WAIT · CONTRACT SYNC")
        self.assertEqual(x["scalp_block_reason"], "CONTRACT_MISMATCH")

    def test_fresh_exit_is_preserved(self):
        x = compose_cross_service_payload(
            BASE,
            scalp(state="EXIT", exec_gain=.17, peak_exec_gain=.21,
                  management_message="EXIT / PROTECT PROFITS NOW"),
        ).to_dict()
        self.assertEqual(x["scalp"]["state"], "EXIT")
        self.assertEqual(x["headline"], "SCALP_EXIT")
        self.assertEqual(x["scalp_management_message"], "EXIT / PROTECT PROFITS NOW")

    def test_canonical_clock_never_comes_from_scalp(self):
        x = compose_cross_service_payload(BASE, scalp(contract_seconds_left=111)).to_dict()
        self.assertAlmostEqual(x["canonical_seconds_left"], 300.0)
        self.assertAlmostEqual(x["scalp_timer_delta_sec"], 189.0)

    def test_no_orders_or_numeric_flip_risk(self):
        x = compose_cross_service_payload(BASE, scalp()).to_dict()
        self.assertTrue(x["manual_execution_only"])
        self.assertIsNone(x["order_action"])
        self.assertFalse(x["numeric_flip_risk_validated"])
        self.assertNotIn("flip_risk_percent", x)


if __name__ == "__main__":
    unittest.main()
