#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

import BTC15_FINAL_FORWARD_SCORECARD_V4 as m


def state(contract, *, seconds_left, ready=False, side="UP", confidence=0.92, up_ask=0.94, down_ask=0.07):
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


class FinalForwardScorecardV4Tests(unittest.TestCase):
    def setUp(self):
        m.reset_state_for_tests()

    def test_contract_first_seen_30s_late_still_valid_for_final_coverage(self):
        now = datetime(2026, 9, 15, 20, 0, 30, tzinfo=timezone.utc)
        m.observer_cycle(state("A", seconds_left=870), now)
        self.assertEqual(m.STATE["observed_contracts"], ["A"])
        self.assertEqual(m.STATE["coverage_excluded_late"], {})
        self.assertEqual(m.STATE["first_seen_seconds_left"]["A"], 870)

    def test_contract_first_seen_after_final_window_opens_is_excluded(self):
        now = datetime(2026, 9, 15, 20, 7, 10, tzinfo=timezone.utc)
        m.observer_cycle(state("A", seconds_left=470), now)
        self.assertEqual(m.STATE["observed_contracts"], [])
        self.assertIn("A", m.STATE["coverage_excluded_late"])

    def test_excluded_contract_cannot_later_enter_denominator(self):
        m.observer_cycle(
            state("A", seconds_left=470),
            datetime(2026, 9, 15, 20, 7, 10, tzinfo=timezone.utc),
        )
        m.observer_cycle(
            state("A", seconds_left=460),
            datetime(2026, 9, 15, 20, 7, 20, tzinfo=timezone.utc),
        )
        self.assertEqual(m.STATE["observed_contracts"], [])
        self.assertEqual(len(m.STATE["coverage_excluded_late"]), 1)

    def test_lock_counts_only_in_coverage_eligible_contract(self):
        m.observer_cycle(
            state("A", seconds_left=870),
            datetime(2026, 9, 15, 20, 0, 30, tzinfo=timezone.utc),
        )
        m.observer_cycle(
            state("A", seconds_left=420, ready=True, up_ask=0.94),
            datetime(2026, 9, 15, 20, 8, 0, tzinfo=timezone.utc),
        )
        self.assertIn("A", m.STATE["lock_records"])
        self.assertEqual(m.STATE["lock_records"]["A"]["preferred_ask"], 0.94)

    def test_late_contract_lock_is_not_scored(self):
        m.observer_cycle(
            state("A", seconds_left=470, ready=True),
            datetime(2026, 9, 15, 20, 7, 10, tzinfo=timezone.utc),
        )
        self.assertNotIn("A", m.STATE["lock_records"])

    def test_summary_states_true_denominator_semantics(self):
        m.observer_cycle(
            state("A", seconds_left=870),
            datetime(2026, 9, 15, 20, 0, 30, tzinfo=timezone.utc),
        )
        s = m.summarize_live_snapshot(m.STATE)
        self.assertEqual(s["coverage_universe_semantics"], "FIRST_SEEN_BEFORE_FINAL_ELIGIBILITY_WINDOW")
        self.assertEqual(s["final_eligibility_open_seconds_left"], 480.0)
        self.assertEqual(s["eligibility_complete_contracts"], 1)
        self.assertFalse(s["full_contract_from_second_zero_required"])
        self.assertFalse(s["full_contract_from_second_zero_claimed"])
        self.assertFalse(s["protected_final_thresholds_changed"])
        self.assertFalse(s["production_behavior_changed"])
        self.assertFalse(s["orders"])
        self.assertTrue(s["manual_execution_only"])


if __name__ == "__main__":
    unittest.main()
