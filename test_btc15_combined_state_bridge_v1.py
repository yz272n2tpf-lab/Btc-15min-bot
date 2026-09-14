#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

from btc15_combined_state_bridge_v1 import build_combined_state, unwrap_main_state

NOW = datetime(2026, 9, 14, 15, 0, 0, tzinfo=timezone.utc)

MAIN = {
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


def ts(seconds_ago):
    return datetime.fromtimestamp(NOW.timestamp() - seconds_ago, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def rows(seconds_ago=2):
    return [
        {"record_type":"SNAPSHOT","contract":"KXBTC15M-T","seconds_left":299,"timestamp_utc":ts(seconds_ago)},
        {"record_type":"CANDIDATE","candidate_id":"C1","contract":"KXBTC15M-T","side":"DOWN","seconds_left":420,"entry_ask":.40,"btc30":22.0,"timestamp_utc":ts(seconds_ago)},
        {"record_type":"PATH","candidate_id":"C1","exec_gain":.06,"peak_exec_gain":.06,"elapsed_sec":5,"timestamp_utc":ts(seconds_ago)},
    ]


class CombinedStateBridgeV1Tests(unittest.TestCase):
    def test_direct_main_state(self):
        self.assertIs(unwrap_main_state(MAIN), MAIN)

    def test_known_envelopes(self):
        self.assertEqual(unwrap_main_state({"state": MAIN})["contract"], "KXBTC15M-T")
        self.assertEqual(unwrap_main_state({"data": MAIN})["contract"], "KXBTC15M-T")

    def test_unknown_envelope_fails_closed(self):
        with self.assertRaises(ValueError):
            unwrap_main_state({"payload": MAIN})

    def test_fresh_combined_state_preserves_all_modules(self):
        x = build_combined_state(MAIN, rows(), now=NOW)
        self.assertEqual(x["version"], "BTC15_COMBINED_STATE_BRIDGE_V1")
        self.assertEqual(x["early"]["state"], "QUALIFIED")
        self.assertEqual(x["final"]["state"], "LOCK")
        self.assertEqual(x["scalp"]["state"], "PROTECT")
        self.assertTrue(x["scalp_contract_aligned"])
        self.assertTrue(x["scalp_source_fresh"])
        self.assertIn("SCALP", x["actionable_paths"])
        self.assertIn("COUNTERTREND_SCALP", x["context_labels"])

    def test_stale_scalp_cannot_become_actionable(self):
        x = build_combined_state(MAIN, rows(seconds_ago=30), now=NOW)
        self.assertEqual(x["early"]["state"], "QUALIFIED")
        self.assertEqual(x["final"]["state"], "LOCK")
        self.assertEqual(x["scalp"]["state"], "PASS")
        self.assertFalse(x["scalp_source_fresh"])
        self.assertEqual(x["scalp_management_message"], "SCALP WAIT · STALE SOURCE")

    def test_signal_only_envelope(self):
        x = build_combined_state(MAIN, rows(), now=NOW)
        self.assertTrue(x["manual_execution_only"])
        self.assertIsNone(x["order_action"])
        self.assertFalse(x["numeric_flip_risk_validated"])
        self.assertFalse(x["orders"])
        self.assertNotIn("flip_risk_percent", x)


if __name__ == "__main__":
    unittest.main()
