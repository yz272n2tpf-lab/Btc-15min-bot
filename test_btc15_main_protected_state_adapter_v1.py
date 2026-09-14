#!/usr/bin/env python3
import unittest

from btc15_main_protected_state_adapter_v1 import (
    canonical_seconds_left,
    early_state_from_main,
    final_state_from_main,
    protected_main_summary,
)

NESTED = {
    "contract": "KXBTC15M-T",
    "timer": {"seconds_left": 287.5, "minutes_left": 4.79},
    "market": {
        "target": 78000.0,
        "up_bid": .62, "up_ask": .63,
        "down_bid": .37, "down_ask": .38,
    },
    "early": {
        "ready": True, "side": "UP", "ask": .34,
        "fair": .79, "edge": .45, "status": "QUALIFIED",
    },
    "final": {
        "ready": True, "side": "UP", "confidence": .94,
        "recorded_final_call": False,
        "recorded_side": None,
        "recorded_confidence": None,
    },
}


class MainProtectedStateAdapterV1Tests(unittest.TestCase):
    def test_canonical_timer_comes_from_nested_timer(self):
        self.assertAlmostEqual(canonical_seconds_left(NESTED), 287.5)

    def test_nested_early_ready_is_qualified_without_recomputing_gates(self):
        x = early_state_from_main(NESTED)
        self.assertEqual(x.state, "QUALIFIED")
        self.assertEqual(x.side, "UP")
        self.assertAlmostEqual(x.ask, .34)
        self.assertAlmostEqual(x.fair, .79)
        self.assertAlmostEqual(x.seconds_left, 287.5)

    def test_nested_early_not_ready_fails_closed(self):
        d = dict(NESTED, early=dict(NESTED["early"], ready=False))
        self.assertEqual(early_state_from_main(d).state, "PASS")

    def test_nested_live_final_ready_is_lock(self):
        x = final_state_from_main(NESTED)
        self.assertEqual(x.state, "LOCK")
        self.assertEqual(x.side, "UP")
        self.assertAlmostEqual(x.fair, .94)
        self.assertAlmostEqual(x.seconds_left, 287.5)

    def test_recorded_final_call_persists_when_live_gate_drops(self):
        f = dict(
            NESTED["final"],
            ready=False,
            side="DOWN",
            confidence=.55,
            recorded_final_call=True,
            recorded_side="UP",
            recorded_confidence=.94,
        )
        x = final_state_from_main(dict(NESTED, final=f))
        self.assertEqual(x.state, "LOCK")
        self.assertEqual(x.side, "UP")
        self.assertAlmostEqual(x.fair, .94)

    def test_recorded_flag_without_complete_record_fails_closed(self):
        f = dict(
            NESTED["final"],
            ready=False,
            recorded_final_call=True,
            recorded_side=None,
            recorded_confidence=None,
        )
        self.assertEqual(final_state_from_main(dict(NESTED, final=f)).state, "WATCH")

    def test_summary_maps_nested_market_quotes(self):
        x = protected_main_summary(NESTED)
        self.assertAlmostEqual(x["kalshi_target"], 78000.0)
        self.assertAlmostEqual(x["up_ask"], .63)
        self.assertAlmostEqual(x["down_bid"], .37)

    def test_legacy_flat_compatibility(self):
        flat = {
            "contract":"X", "time_left_min":5.0,
            "fair_preferred_side":"DOWN", "preferred_kalshi_ask":.34,
            "fair_preferred":.80, "fair_edge_vs_ask":.46,
            "entry_tournament_ready":True, "opportunity_status":"OPPORTUNITY",
            "final_status":"FINAL CALL", "final_side":"DOWN",
            "final_confidence":.95, "final_call_source":"TOURNAMENT WINNER",
        }
        self.assertEqual(early_state_from_main(flat).state, "QUALIFIED")
        self.assertEqual(final_state_from_main(flat).state, "LOCK")
        self.assertAlmostEqual(canonical_seconds_left(flat), 300.0)


if __name__ == "__main__":
    unittest.main()
