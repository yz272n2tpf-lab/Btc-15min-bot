#!/usr/bin/env python3
import unittest
from datetime import datetime, timedelta, timezone

import BTC15_FINAL_FORWARD_SCORECARD_V3 as m


def state(contract, *, ready=False, side="UP", confidence=0.92, seconds_left=600, up_ask=0.94, down_ask=0.07):
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


class FinalForwardScorecardV3Tests(unittest.TestCase):
    def setUp(self):
        m.reset_runtime_for_tests()

    def test_watchdog_healthy_when_worker_fresh(self):
        now = datetime(2026, 9, 15, 19, 40, tzinfo=timezone.utc)
        with m.RUNTIME_LOCK:
            m.RUNTIME["observer_worker_alive"] = True
            m.RUNTIME["observer_last_iteration_utc"] = m._iso(now)
        h = m.runtime_health(now)
        self.assertTrue(h["healthy"])
        self.assertLessEqual(h["observer_age_sec"], 0.001)

    def test_watchdog_fails_closed_when_worker_stale(self):
        now = datetime(2026, 9, 15, 19, 40, tzinfo=timezone.utc)
        with m.RUNTIME_LOCK:
            m.RUNTIME["observer_worker_alive"] = True
            m.RUNTIME["observer_last_iteration_utc"] = m._iso(now - timedelta(seconds=m.OBSERVER_STALE_SEC + 1))
        h = m.runtime_health(now)
        self.assertFalse(h["healthy"])
        self.assertGreater(h["observer_age_sec"], m.OBSERVER_STALE_SEC)

    def test_watchdog_fails_closed_when_worker_dead(self):
        now = datetime(2026, 9, 15, 19, 40, tzinfo=timezone.utc)
        with m.RUNTIME_LOCK:
            m.RUNTIME["observer_worker_alive"] = False
            m.RUNTIME["observer_last_iteration_utc"] = m._iso(now)
        self.assertFalse(m.runtime_health(now)["healthy"])

    def test_v2_final_lock_scoring_is_preserved(self):
        m.v2.observer_cycle(state("A"), datetime(2026, 9, 15, 19, 40, tzinfo=timezone.utc))
        m.v2.observer_cycle(
            state("B", ready=True, seconds_left=420, up_ask=0.94),
            datetime(2026, 9, 15, 19, 45, 1, tzinfo=timezone.utc),
        )
        rec = m.STATE["lock_records"]["B"]
        self.assertEqual(rec["side"], "UP")
        self.assertEqual(rec["preferred_ask"], 0.94)
        self.assertFalse(rec["ask_at_or_below_50c"])
        summary = m.v2.summarize_live_snapshot(m.STATE)
        self.assertEqual(summary["lock_calls"], 1)
        self.assertFalse(summary["price_filter_applied"])
        self.assertFalse(summary["protected_final_thresholds_changed"])
        self.assertFalse(summary["orders"])
        self.assertTrue(summary["manual_execution_only"])

    def test_watchdog_metadata_cannot_create_or_remove_lock(self):
        m.v2.observer_cycle(state("A"), datetime(2026, 9, 15, 19, 40, tzinfo=timezone.utc))
        m.v2.observer_cycle(
            state("B", ready=True, seconds_left=300, side="DOWN", up_ask=0.08, down_ask=0.93),
            datetime(2026, 9, 15, 19, 45, 1, tzinfo=timezone.utc),
        )
        before = dict(m.STATE["lock_records"])
        with m.RUNTIME_LOCK:
            m.RUNTIME["observer_restarts"] = 3
            m.RUNTIME["observer_worker_alive"] = False
            m.RUNTIME["observer_last_iteration_utc"] = m._iso(datetime(2026, 9, 15, 19, 46, tzinfo=timezone.utc))
        _ = m.runtime_health(datetime(2026, 9, 15, 19, 46, tzinfo=timezone.utc))
        self.assertEqual(before, m.STATE["lock_records"])


if __name__ == "__main__":
    unittest.main()
