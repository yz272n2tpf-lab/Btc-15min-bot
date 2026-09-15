import unittest
from datetime import datetime, timedelta, timezone

import BTC15_EARLY_FINAL_HANDOFF_FORWARD_V1 as m


def row(contract, left, *, early=None, final=None, up_ask=0.40, down_ask=0.60):
    return {
        "contract": contract,
        "timer": {"seconds_left": left},
        "market": {
            "target": 100000.0,
            "up_bid": max(0.0, up_ask - 0.01),
            "up_ask": up_ask,
            "down_bid": max(0.0, down_ask - 0.01),
            "down_ask": down_ask,
        },
        "early": early or {"ready": False},
        "final": final or {"ready": False, "recorded_final_call": False},
    }


def early(side="UP", ask=0.33, fair=0.80, edge=0.12):
    return {"ready": True, "side": side, "ask": ask, "fair": fair, "edge": edge}


def final(side="UP", confidence=0.92):
    return {
        "ready": True,
        "recorded_final_call": False,
        "side": side,
        "confidence": confidence,
    }


class HandoffForwardV1Tests(unittest.TestCase):
    def setUp(self):
        m.reset_state_for_tests()
        self.t0 = datetime(2026, 9, 15, 21, 0, tzinfo=timezone.utc)

    def arm_b(self, left=885.0):
        m.observer_cycle(row("A", 300.0), self.t0)
        m.observer_cycle(row("B", left), self.t0 + timedelta(seconds=1))

    def test_startup_contract_is_excluded_and_first_rollover_arms(self):
        m.observer_cycle(row("A", 850.0, early=early()), self.t0)
        self.assertEqual(m.STATE["startup_contract"], "A")
        self.assertFalse(m.STATE["live_scoring_armed"])
        self.assertEqual(m.STATE["eligible_contracts"], [])
        self.assertEqual(m.STATE["early_records"], {})

        m.observer_cycle(row("B", 885.0), self.t0 + timedelta(seconds=1))
        self.assertTrue(m.STATE["live_scoring_armed"])
        self.assertEqual(m.STATE["eligible_contracts"], ["B"])

    def test_contract_first_seen_before_10m_is_eligible(self):
        self.arm_b(600.0)
        self.assertIn("B", m.STATE["eligible_contracts"])
        self.assertNotIn("B", m.STATE["coverage_excluded_late"])

    def test_contract_first_seen_after_10m_is_excluded_fail_closed(self):
        self.arm_b(599.9)
        self.assertNotIn("B", m.STATE["eligible_contracts"])
        self.assertEqual(m.STATE["coverage_excluded_late"]["B"], 599.9)
        m.observer_cycle(row("B", 500.0, early=early()), self.t0 + timedelta(seconds=2))
        self.assertNotIn("B", m.STATE["early_records"])

    def test_first_protected_early_and_final_are_captured_once(self):
        self.arm_b()
        m.observer_cycle(
            row("B", 550.0, early=early("UP", 0.33, 0.81, 0.13), up_ask=0.33, down_ask=0.68),
            self.t0 + timedelta(seconds=2),
        )
        m.observer_cycle(
            row("B", 280.0, early=early("DOWN", 0.25, 0.90, 0.20), final=final("UP", 0.93), up_ask=0.92, down_ask=0.09),
            self.t0 + timedelta(seconds=3),
        )
        self.assertEqual(m.STATE["early_records"]["B"]["side"], "UP")
        self.assertAlmostEqual(m.STATE["early_records"]["B"]["ask"], 0.33)
        self.assertEqual(m.STATE["final_records"]["B"]["side"], "UP")
        self.assertAlmostEqual(m.STATE["final_records"]["B"]["ask"], 0.92)

        m.observer_cycle(
            row("B", 200.0, early=early("DOWN", 0.20, 0.95, 0.30), final=final("DOWN", 0.99), up_ask=0.02, down_ask=0.99),
            self.t0 + timedelta(seconds=4),
        )
        self.assertEqual(m.STATE["early_records"]["B"]["side"], "UP")
        self.assertEqual(m.STATE["final_records"]["B"]["side"], "UP")

    def test_final_uses_locked_side_ask(self):
        self.arm_b()
        m.observer_cycle(
            row("B", 250.0, final=final("DOWN", 0.94), up_ask=0.07, down_ask=0.94),
            self.t0 + timedelta(seconds=2),
        )
        self.assertAlmostEqual(m.STATE["final_records"]["B"]["ask"], 0.94)

    def test_summary_measures_same_side_handoff_and_price_change(self):
        self.arm_b()
        m.observer_cycle(
            row("B", 540.0, early=early("UP", 0.30, 0.80, 0.12), up_ask=0.30, down_ask=0.71),
            self.t0 + timedelta(seconds=2),
        )
        m.observer_cycle(
            row("B", 240.0, final=final("UP", 0.95), up_ask=0.90, down_ask=0.11),
            self.t0 + timedelta(seconds=3),
        )
        s = m.summarize_state()
        self.assertEqual(s["handoffs"], 1)
        self.assertEqual(s["handoff_side_agreement_rate"], 1.0)
        self.assertAlmostEqual(s["avg_early_to_final_gap_minutes"], 5.0)
        self.assertAlmostEqual(s["avg_same_side_ask_change_early_to_final"], 0.60)
        self.assertEqual(s["early_ideal_25_35c_n"], 1)
        self.assertEqual(s["early_le_50c_n"], 1)
        self.assertEqual(s["final_le_50c_n"], 0)

    def test_side_flip_is_measured_not_rewritten(self):
        self.arm_b()
        m.observer_cycle(
            row("B", 500.0, early=early("UP", 0.35, 0.79, 0.11), up_ask=0.35, down_ask=0.66),
            self.t0 + timedelta(seconds=2),
        )
        m.observer_cycle(
            row("B", 220.0, final=final("DOWN", 0.92), up_ask=0.09, down_ask=0.92),
            self.t0 + timedelta(seconds=3),
        )
        s = m.summarize_state()
        self.assertEqual(s["handoffs"], 1)
        self.assertEqual(s["handoff_side_agreement_rate"], 0.0)
        self.assertIsNone(s["avg_same_side_ask_change_early_to_final"])
        self.assertEqual(m.STATE["early_records"]["B"]["side"], "UP")
        self.assertEqual(m.STATE["final_records"]["B"]["side"], "DOWN")

    def test_settlement_metrics_keep_final_accuracy_separate_from_early_context(self):
        self.arm_b()
        m.observer_cycle(
            row("B", 520.0, early=early("UP", 0.34, 0.80, 0.12), up_ask=0.34, down_ask=0.67),
            self.t0 + timedelta(seconds=2),
        )
        m.observer_cycle(
            row("B", 210.0, final=final("DOWN", 0.93), up_ask=0.08, down_ask=0.93),
            self.t0 + timedelta(seconds=3),
        )
        m.STATE["settlements"]["B"] = "DOWN"
        s = m.summarize_state()
        self.assertEqual(s["final_accuracy"], 1.0)
        self.assertEqual(s["early_same_side_as_settlement_rate_secondary"], 0.0)
        self.assertEqual(s["settled_final_locks"], 1)
        self.assertEqual(s["settled_early_calls"], 1)

    def test_review_gate_is_measurement_only_and_requires_all_three_counts(self):
        m.STATE["eligible_contracts"] = [f"C{i}" for i in range(30)]
        for i in range(12):
            c = f"C{i}"
            m.STATE["final_records"][c] = {
                "contract": c, "side": "UP", "ask": 0.90, "fair": 0.95,
                "minutes_left": 4.0, "ask_at_or_below_50c": False,
            }
            m.STATE["settlements"][c] = "UP"
        for i in range(10):
            c = f"C{i}"
            m.STATE["early_records"][c] = {
                "contract": c, "side": "UP", "ask": 0.33, "fair": 0.80,
                "edge": 0.12, "minutes_left": 8.0,
                "ask_in_25_35c": True, "ask_at_or_below_50c": True,
            }
        s = m.summarize_state()
        self.assertTrue(s["sample_ready"])
        self.assertEqual(s["status"], "HANDOFF_REVIEW_SAMPLE_READY")
        self.assertFalse(s["protected_early_thresholds_changed"])
        self.assertFalse(s["protected_final_thresholds_changed"])
        self.assertFalse(s["auto_promotion"])
        self.assertFalse(s["orders"])

    def test_watchdog_health_turns_red_when_stale(self):
        now = self.t0
        m.RUNTIME["observer_worker_alive"] = True
        m.RUNTIME["observer_last_iteration_utc"] = m._iso(now)
        self.assertTrue(m.runtime_health(now)["healthy"])
        self.assertFalse(m.runtime_health(now + timedelta(seconds=31))["healthy"])


if __name__ == "__main__":
    unittest.main()
