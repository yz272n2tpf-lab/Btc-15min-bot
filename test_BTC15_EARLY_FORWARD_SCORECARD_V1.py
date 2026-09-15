#!/usr/bin/env python3
import unittest
from datetime import datetime, timedelta, timezone

import BTC15_EARLY_FORWARD_SCORECARD_V1 as m


def state(contract, *, seconds_left=900, ready=False, side="UP", ask=0.34, fair=0.80, edge=0.10):
    return {
        "contract": contract,
        "timer": {"seconds_left": seconds_left},
        "market": {
            "target": 100000.0,
            "up_bid": max(0.0, ask - 0.01) if side == "UP" else 0.60,
            "up_ask": ask if side == "UP" else 0.61,
            "down_bid": max(0.0, ask - 0.01) if side == "DOWN" else 0.38,
            "down_ask": ask if side == "DOWN" else 0.39,
        },
        "early": {
            "ready": ready,
            "side": side,
            "ask": ask,
            "fair": fair,
            "edge": edge,
        },
        "final": {"ready": False},
    }


class EarlyForwardScorecardV1Tests(unittest.TestCase):
    def setUp(self):
        m.reset_state_for_tests()

    def test_startup_contract_is_excluded_even_if_early_ready(self):
        t = datetime(2026, 9, 15, 20, 7, tzinfo=timezone.utc)
        m.observer_cycle(state("A", seconds_left=480, ready=True), t)
        self.assertEqual(m.STATE["startup_contract"], "A")
        self.assertFalse(m.STATE["live_scoring_armed"])
        self.assertEqual(m.STATE["eligible_contracts"], [])
        self.assertEqual(m.STATE["call_records"], {})

    def test_first_post_start_rollover_arms_and_counts_when_seen_before_10m(self):
        t = datetime(2026, 9, 15, 20, 7, tzinfo=timezone.utc)
        m.observer_cycle(state("A", seconds_left=480), t)
        m.observer_cycle(
            state("B", seconds_left=870, ready=True, side="UP", ask=0.31, fair=0.81, edge=0.12),
            t + timedelta(minutes=8),
        )
        self.assertTrue(m.STATE["live_scoring_armed"])
        self.assertEqual(m.STATE["eligible_contracts"], ["B"])
        self.assertIn("B", m.STATE["call_records"])
        rec = m.STATE["call_records"]["B"]
        self.assertTrue(rec["ask_in_25_35c"])
        self.assertTrue(rec["ask_at_or_below_50c"])

    def test_contract_first_seen_inside_early_window_is_excluded(self):
        t = datetime(2026, 9, 15, 20, 7, tzinfo=timezone.utc)
        m.observer_cycle(state("A", seconds_left=480), t)
        m.observer_cycle(state("B", seconds_left=590, ready=True), t + timedelta(minutes=8))
        self.assertNotIn("B", m.STATE["eligible_contracts"])
        self.assertIn("B", m.STATE["coverage_excluded_late"])
        self.assertNotIn("B", m.STATE["call_records"])

    def test_first_early_opportunity_is_not_overwritten(self):
        t = datetime(2026, 9, 15, 20, 7, tzinfo=timezone.utc)
        m.observer_cycle(state("A", seconds_left=480), t)
        m.observer_cycle(state("B", seconds_left=870, ready=True, side="UP", ask=0.34), t + timedelta(minutes=8))
        m.observer_cycle(state("B", seconds_left=500, ready=True, side="DOWN", ask=0.29), t + timedelta(minutes=14))
        rec = m.STATE["call_records"]["B"]
        self.assertEqual(rec["side"], "UP")
        self.assertAlmostEqual(rec["ask"], 0.34)

    def test_pass_does_not_count_as_early_call(self):
        t = datetime(2026, 9, 15, 20, 7, tzinfo=timezone.utc)
        m.observer_cycle(state("A", seconds_left=480), t)
        m.observer_cycle(state("B", seconds_left=870, ready=False), t + timedelta(minutes=8))
        self.assertEqual(m.STATE["eligible_contracts"], ["B"])
        self.assertEqual(m.STATE["call_records"], {})
        s = m.summarize_state()
        self.assertEqual(s["early_calls"], 0)
        self.assertEqual(s["early_only_coverage"], 0.0)

    def test_settlement_direction_is_secondary_and_price_metrics_are_separate(self):
        t = datetime(2026, 9, 15, 20, 7, tzinfo=timezone.utc)
        m.observer_cycle(state("A", seconds_left=480), t)
        m.observer_cycle(state("B", seconds_left=870, ready=True, side="UP", ask=0.31), t + timedelta(minutes=8))
        with m.LOCK:
            m.STATE["settlements"]["B"] = "DOWN"
        s = m.summarize_state()
        self.assertEqual(s["settled_early_calls"], 1)
        self.assertEqual(s["settlement_same_side_rate_secondary"], 0.0)
        self.assertEqual(s["ask_25_35c_n"], 1)
        self.assertEqual(s["ask_le_50c_n"], 1)
        self.assertTrue(s["settlement_accuracy_is_secondary_not_final_authority"])
        self.assertFalse(s["protected_early_thresholds_changed"])
        self.assertFalse(s["production_behavior_changed"])
        self.assertFalse(s["orders"])
        self.assertTrue(s["manual_execution_only"])

    def test_watchdog_health_is_independent_of_signal_state(self):
        now = datetime(2026, 9, 15, 20, 0, tzinfo=timezone.utc)
        with m.RUNTIME_LOCK:
            m.RUNTIME["observer_worker_alive"] = True
            m.RUNTIME["observer_last_iteration_utc"] = m._iso(now)
        self.assertTrue(m.runtime_health(now)["healthy"])
        later = now + timedelta(seconds=m.OBSERVER_STALE_SEC + 1)
        self.assertFalse(m.runtime_health(later)["healthy"])
        s = m.summarize_state()
        self.assertFalse(s["protected_early_thresholds_changed"])
        self.assertFalse(s["orders"])


if __name__ == "__main__":
    unittest.main()
