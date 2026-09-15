#!/usr/bin/env python3
from __future__ import annotations

import os
import unittest

os.environ.setdefault("SCALP_BLUEPRINT_CUTOFF_UTC", "2026-09-14T21:08:00Z")

import BTC15_SCALP_FAILED_PREARM_RESET_TOURNAMENT_V1 as m


def c(cid, t, contract="C1", side="UP", ask="0.30"):
    return {
        "record_type": "CANDIDATE", "contract": contract, "candidate_id": cid,
        "timestamp_utc": t, "side": side, "seconds_left": "600",
        "btc30": "20", "entry_ask": ask,
    }


def p(cid, t, elapsed, gain):
    return {
        "record_type": "PATH", "candidate_id": cid, "timestamp_utc": t,
        "elapsed_sec": str(elapsed), "exec_gain": str(gain),
    }


def result(cid, contract="C1", t="2026-09-14T21:14:00Z"):
    return {
        "record_type": "RESULT", "contract": contract, "candidate_id": cid,
        "timestamp_utc": t,
    }


class FailedPrearmResetTournamentTests(unittest.TestCase):
    def test_failed_primary_release_exposes_later_plus10_candidate(self):
        rows = [
            c("a", "2026-09-14T21:10:00Z"),
            p("a", "2026-09-14T21:10:10Z", 10, -.03),
            p("a", "2026-09-14T21:10:20Z", 20, -.06),
            p("a", "2026-09-14T21:10:30Z", 30, -.08),
            result("a"),
            c("b", "2026-09-14T21:10:35Z", side="DOWN"),
            p("b", "2026-09-14T21:10:40Z", 5, .06),
            p("b", "2026-09-14T21:10:45Z", 10, .12),
            result("b"),
        ]
        s = m.audit(rows)
        cell = s["grid"]["-5c_after_20s"]
        self.assertEqual(s["failed_prearm_primary_n"], 1)
        self.assertEqual(cell["triggered_before_arm_n"], 1)
        self.assertEqual(cell["later_candidate_available_n"], 1)
        self.assertEqual(cell["later_candidate_completed_n"], 1)
        self.assertEqual(cell["later_candidate_plus10_n"], 1)
        self.assertEqual(cell["false_abort_recovery_rate"], 0.0)
        self.assertFalse(s["rule_selected"])
        self.assertFalse(s["auto_promote_allowed"])

    def test_slow_winner_counts_as_false_abort_if_rule_triggers_first(self):
        rows = [
            c("a", "2026-09-14T21:10:00Z"),
            p("a", "2026-09-14T21:10:10Z", 10, -.03),
            p("a", "2026-09-14T21:10:20Z", 20, -.06),
            p("a", "2026-09-14T21:10:40Z", 40, .02),
            p("a", "2026-09-14T21:11:00Z", 60, .06),
            result("a"),
        ]
        s = m.audit(rows)
        cell = s["grid"]["-5c_after_20s"]
        self.assertEqual(s["failed_prearm_primary_n"], 0)
        self.assertEqual(cell["triggered_before_arm_n"], 1)
        self.assertEqual(cell["original_later_recovers_plus5_n"], 1)
        self.assertEqual(cell["false_abort_recovery_rate"], 1.0)

    def test_rule_does_not_trigger_after_plus5_already_armed(self):
        rows = [
            c("a", "2026-09-14T21:10:00Z"),
            p("a", "2026-09-14T21:10:05Z", 5, .06),
            p("a", "2026-09-14T21:10:20Z", 20, -.08),
            result("a"),
        ]
        s = m.audit(rows)
        cell = s["grid"]["-5c_after_20s"]
        self.assertEqual(cell["triggered_before_arm_n"], 0)

    def test_no_price_filter_or_order_capability_is_added(self):
        rows = [
            c("a", "2026-09-14T21:10:00Z", ask="0.88"),
            p("a", "2026-09-14T21:10:20Z", 20, -.06),
            result("a"),
        ]
        s = m.audit(rows)
        self.assertFalse(s["orders"])
        self.assertTrue(s["manual_execution_only"])
        self.assertFalse(s["rule_selected"])
        self.assertFalse(s["auto_promote_allowed"])


if __name__ == "__main__":
    unittest.main()
