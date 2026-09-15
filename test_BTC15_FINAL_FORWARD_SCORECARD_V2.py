#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

import BTC15_FINAL_FORWARD_SCORECARD_V2 as m


def state(contract, *, ready=False, side="UP", confidence=0.92, seconds_left=600, up_ask=0.40, down_ask=0.61):
    return {
        "contract": contract,
        "timer": {"seconds_left": seconds_left},
        "market": {
            "target": 100000.0,
            "up_bid": max(0.0, up_ask - 0.01),
            "up_ask": up_ask,
            "down_bid": max(0.0, down_ask - 0.01),
            "down_ask": down_ask,
        },
        "final": {
            "ready": ready,
            "side": side,
            "confidence": confidence,
            "recorded_final_call": False,
        },
    }


class FinalForwardScorecardV2Tests(unittest.TestCase):
    def setUp(self):
        m.reset_live_state_for_tests()

    def test_starting_mid_contract_after_cutoff_is_excluded(self):
        now = datetime(2026, 9, 15, 16, 50, tzinfo=timezone.utc)
        m.observer_cycle(state("A", ready=True, up_ask=0.94), now)
        self.assertEqual(m.STATE["startup_contract"], "A")
        self.assertFalse(m.STATE["live_scoring_armed"])
        self.assertEqual(m.STATE["observed_contracts"], [])
        self.assertEqual(m.STATE["lock_records"], {})

    def test_first_rollover_after_cutoff_arms_and_counts_full_contract(self):
        m.observer_cycle(state("A"), datetime(2026, 9, 15, 16, 50, tzinfo=timezone.utc))
        m.observer_cycle(
            state("B", ready=True, seconds_left=895, up_ask=0.45),
            datetime(2026, 9, 15, 17, 0, 5, tzinfo=timezone.utc),
        )
        self.assertTrue(m.STATE["live_scoring_armed"])
        self.assertEqual(m.STATE["first_full_contract"], "B")
        self.assertEqual(m.STATE["observed_contracts"], ["B"])
        self.assertIn("B", m.STATE["lock_records"])
        self.assertNotIn("A", m.STATE["lock_records"])

    def test_start_before_cutoff_arms_on_post_cutoff_rollover(self):
        m.observer_cycle(state("A"), datetime(2026, 9, 15, 16, 40, tzinfo=timezone.utc))
        m.observer_cycle(state("A"), datetime(2026, 9, 15, 16, 44, 59, tzinfo=timezone.utc))
        self.assertFalse(m.STATE["live_scoring_armed"])
        m.observer_cycle(
            state("B", ready=False, seconds_left=899),
            datetime(2026, 9, 15, 16, 45, 1, tzinfo=timezone.utc),
        )
        self.assertTrue(m.STATE["live_scoring_armed"])
        self.assertEqual(m.STATE["first_full_contract"], "B")
        self.assertEqual(m.STATE["observed_contracts"], ["B"])

    def test_same_contract_is_not_double_counted(self):
        m.observer_cycle(state("A"), datetime(2026, 9, 15, 16, 50, tzinfo=timezone.utc))
        m.observer_cycle(state("B"), datetime(2026, 9, 15, 17, 0, 1, tzinfo=timezone.utc))
        m.observer_cycle(state("B"), datetime(2026, 9, 15, 17, 1, 0, tzinfo=timezone.utc))
        self.assertEqual(m.STATE["observed_contracts"], ["B"])

    def test_lock_price_is_evaluation_only(self):
        m.observer_cycle(state("A"), datetime(2026, 9, 15, 16, 50, tzinfo=timezone.utc))
        m.observer_cycle(
            state("B", ready=True, seconds_left=899, up_ask=0.94),
            datetime(2026, 9, 15, 17, 0, 1, tzinfo=timezone.utc),
        )
        rec = m.STATE["lock_records"]["B"]
        self.assertEqual(rec["price_band"], ">85C")
        self.assertFalse(rec["ask_at_or_below_50c"])
        summary = m.summarize_live_snapshot(m.STATE)
        self.assertFalse(summary["price_filter_applied"])
        self.assertFalse(summary["production_behavior_changed"])
        self.assertFalse(summary["numeric_flip_risk_validated"])
        self.assertFalse(summary["orders"])
        self.assertTrue(summary["manual_execution_only"])
        self.assertFalse(summary["partial_start_contract_counted"])


if __name__ == "__main__":
    unittest.main()
