#!/usr/bin/env python3
import unittest
from datetime import datetime, timedelta, timezone

import BTC15_EARLY_EXCURSION_FORWARD_V1 as m

BASE = datetime(2026, 9, 15, 23, 0, 0, tzinfo=timezone.utc)


def row(contract, left, *, early_ready=False, early_side="UP", early_ask=.34,
        early_fair=.80, early_edge=.12, up_bid=.33, up_ask=.34,
        down_bid=.65, down_ask=.66, final_ready=False, final_side="UP",
        final_conf=.92):
    return {
        "contract": contract,
        "timer": {"seconds_left": left},
        "market": {
            "up_bid": up_bid, "up_ask": up_ask,
            "down_bid": down_bid, "down_ask": down_ask,
        },
        "early": {
            "ready": early_ready, "side": early_side, "ask": early_ask,
            "fair": early_fair, "edge": early_edge,
        },
        "final": {
            "ready": final_ready, "side": final_side, "confidence": final_conf,
            "recorded_final_call": False,
        },
    }


class TestEarlyExcursionForwardV1(unittest.TestCase):
    def setUp(self):
        m.reset_state_for_tests()

    def arm_b(self, left=885):
        m.observer_cycle(row("A", 400), BASE)
        m.observer_cycle(row("B", left), BASE + timedelta(seconds=5))

    def test_startup_excluded_and_first_rollover_eligible(self):
        m.observer_cycle(row("A", 880), BASE)
        self.assertFalse(m.STATE["armed"])
        self.assertEqual(m.STATE["eligible_contracts"], [])
        m.observer_cycle(row("B", 885), BASE + timedelta(seconds=5))
        self.assertTrue(m.STATE["armed"])
        self.assertEqual(m.STATE["eligible_contracts"], ["B"])
        self.assertEqual(m.STATE["startup_contract"], "A")

    def test_late_discovered_rollover_excluded(self):
        m.observer_cycle(row("A", 400), BASE)
        m.observer_cycle(row("B", 599.9), BASE + timedelta(seconds=5))
        self.assertNotIn("B", m.STATE["eligible_contracts"])
        self.assertIn("B", m.STATE["excluded_late"])

    def test_protected_early_only_no_requalification(self):
        self.arm_b()
        # Attractive-looking values do not matter unless protected ready=True.
        m.observer_cycle(row("B", 540, early_ready=False, early_ask=.30,
                             early_fair=.90, early_edge=.30), BASE + timedelta(seconds=20))
        self.assertNotIn("B", m.STATE["early_calls"])

    def test_first_early_captured_and_not_overwritten(self):
        self.arm_b()
        t1 = BASE + timedelta(seconds=20)
        m.observer_cycle(row("B", 540, early_ready=True, early_ask=.34, up_bid=.33), t1)
        self.assertEqual(m.STATE["early_calls"]["B"]["entry_ask"], .34)
        m.observer_cycle(row("B", 520, early_ready=True, early_ask=.28, up_bid=.40), t1 + timedelta(seconds=20))
        self.assertEqual(m.STATE["early_calls"]["B"]["entry_ask"], .34)

    def test_bid_based_mfe_targets_and_elapsed(self):
        self.arm_b()
        t0 = BASE + timedelta(seconds=20)
        m.observer_cycle(row("B", 540, early_ready=True, early_ask=.34, up_bid=.33), t0)
        m.observer_cycle(row("B", 510, up_bid=.40), t0 + timedelta(seconds=30))
        x = m.STATE["excursions"]["B"]
        self.assertAlmostEqual(x["peak_delta"], .06)
        self.assertIsNotNone(x["targets"]["+5c"])
        self.assertEqual(x["targets"]["+5c"]["elapsed_seconds"], 30.0)
        self.assertIsNone(x["targets"]["+10c"])
        m.observer_cycle(row("B", 480, up_bid=.46), t0 + timedelta(seconds=60))
        x = m.STATE["excursions"]["B"]
        self.assertAlmostEqual(x["peak_delta"], .12)
        self.assertIsNotNone(x["targets"]["+10c"])
        self.assertIsNone(x["targets"]["+15c"])

    def test_mae_includes_spread_and_later_adverse_move(self):
        self.arm_b()
        t0 = BASE + timedelta(seconds=20)
        m.observer_cycle(row("B", 540, early_ready=True, early_ask=.34, up_bid=.32), t0)
        m.observer_cycle(row("B", 520, up_bid=.27), t0 + timedelta(seconds=20))
        x = m.STATE["excursions"]["B"]
        self.assertAlmostEqual(x["trough_delta"], -.07)
        self.assertAlmostEqual(x["trough_bid"], .27)

    def test_final_confirmation_and_flip_are_descriptive(self):
        self.arm_b()
        t0 = BASE + timedelta(seconds=20)
        m.observer_cycle(row("B", 540, early_ready=True, early_side="UP", early_ask=.34, up_bid=.33), t0)
        m.observer_cycle(row("B", 280, up_bid=.60, final_ready=True, final_side="DOWN",
                             final_conf=.93, down_ask=.91), t0 + timedelta(seconds=260))
        x = m.STATE["excursions"]["B"]
        self.assertEqual(x["final_side"], "DOWN")
        self.assertFalse(x["final_agrees"])
        self.assertAlmostEqual(x["final_ask"], .91)
        # EARLY itself was not rewritten.
        self.assertEqual(m.STATE["early_calls"]["B"]["side"], "UP")

    def test_rollover_finalizes_and_summary_scores_targets(self):
        self.arm_b()
        t0 = BASE + timedelta(seconds=20)
        m.observer_cycle(row("B", 540, early_ready=True, early_ask=.30, up_bid=.29), t0)
        m.observer_cycle(row("B", 500, up_bid=.42), t0 + timedelta(seconds=40))
        m.observer_cycle(row("C", 885), t0 + timedelta(seconds=100))
        self.assertIn("B", m.STATE["completed_excursions"])
        self.assertTrue(m.STATE["completed_excursions"]["B"]["completed"])
        self.assertIn("B", m.STATE["pending_settlement"])
        s = m.summarize_state()
        self.assertEqual(s["completed_early_excursions"], 1)
        self.assertEqual(s["ideal_25_35c_n"], 1)
        self.assertEqual(s["hit_5c_n"], 1)
        self.assertEqual(s["hit_10c_n"], 1)
        self.assertAlmostEqual(s["avg_mfe"], .12)

    def test_summary_secondary_settlement_metric(self):
        self.arm_b()
        t0 = BASE + timedelta(seconds=20)
        m.observer_cycle(row("B", 540, early_ready=True, early_side="DOWN",
                             early_ask=.40, down_bid=.39), t0)
        m.observer_cycle(row("C", 885), t0 + timedelta(seconds=100))
        m.STATE["settlements"]["B"] = "UP"
        s = m.summarize_state()
        self.assertEqual(s["settled_early_n"], 1)
        self.assertEqual(s["settlement_same_side_rate_secondary"], 0.0)
        self.assertFalse(s["early_thresholds_changed"])
        self.assertFalse(s["orders"])

    def test_watchdog_can_fail_red_without_signal_change(self):
        self.arm_b()
        m.observer_cycle(row("B", 540, early_ready=True, early_ask=.34), BASE + timedelta(seconds=20))
        before = dict(m.STATE["early_calls"]["B"])
        with m.RUNTIME_LOCK:
            m.RUNTIME["worker_alive"] = True
            m.RUNTIME["last_iteration_utc"] = m._iso(BASE)
        h = m.runtime_health(BASE + timedelta(seconds=31))
        self.assertFalse(h["healthy"])
        self.assertEqual(before, m.STATE["early_calls"]["B"])


if __name__ == "__main__":
    unittest.main()
