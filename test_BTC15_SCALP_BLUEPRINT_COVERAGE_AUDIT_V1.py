#!/usr/bin/env python3
from __future__ import annotations

import os
import unittest

os.environ.setdefault("SCALP_BLUEPRINT_CUTOFF_UTC", "2026-09-14T21:08:00Z")

import BTC15_SCALP_BLUEPRINT_COVERAGE_AUDIT_V1 as m


def c(cid, t, ask="0.30", side="UP", contract="C1"):
    return {
        "record_type":"CANDIDATE", "contract":contract, "candidate_id":cid,
        "timestamp_utc":t, "side":side, "seconds_left":"600",
        "btc30":"20", "entry_ask":ask,
    }


def p(cid, t, elapsed, gain):
    return {
        "record_type":"PATH", "candidate_id":cid, "timestamp_utc":t,
        "elapsed_sec":str(elapsed), "exec_gain":str(gain),
    }


def result(cid, t="2026-09-14T21:14:00Z", contract="C1"):
    return {
        "record_type":"RESULT", "contract":contract, "candidate_id":cid,
        "timestamp_utc":t,
    }


class CoverageAuditTests(unittest.TestCase):
    def test_classifies_overlap_and_failed_prearm_block(self):
        rows = [
            c("a", "2026-09-14T21:10:00Z"),
            p("a", "2026-09-14T21:10:05Z", 5, .06),
            p("a", "2026-09-14T21:10:30Z", 30, .01),
            result("a"),
            c("b", "2026-09-14T21:10:20Z", side="DOWN"),
            p("b", "2026-09-14T21:10:25Z", 5, .15),
            result("b"),
            c("c", "2026-09-14T21:10:40Z"),
            p("c", "2026-09-14T21:10:50Z", 10, .02),
            p("c", "2026-09-14T21:11:00Z", 20, -.12),
            result("c"),
            c("d", "2026-09-14T21:11:20Z", side="DOWN"),
            p("d", "2026-09-14T21:11:25Z", 5, .20),
            result("d"),
        ]
        s = m.audit(rows)
        by_id = {r["candidate_id"]: r for r in s["records"]}
        self.assertEqual(by_id["a"]["classification"], "SELECTED_SERIAL_SCALP")
        self.assertEqual(by_id["b"]["classification"], "OVERLAP_WHILE_PRIOR_SCALP_ACTIVE")
        self.assertEqual(by_id["c"]["classification"], "SELECTED_SERIAL_SCALP")
        self.assertEqual(by_id["d"]["classification"], "BLOCKED_BY_FAILED_PREARM_NO_EXIT")
        self.assertEqual(s["post_exit_missed_qualified"], 0)
        self.assertEqual(s["max_serial_index"], 2)
        self.assertEqual(s["failed_prearm_blocked_candidates"], 1)

    def test_high_price_never_suppresses(self):
        rows = [
            c("hi", "2026-09-14T21:12:00Z", ask="0.88"),
            p("hi", "2026-09-14T21:12:05Z", 5, .12),
            p("hi", "2026-09-14T21:12:20Z", 20, .07),
            result("hi"),
        ]
        s = m.audit(rows)
        self.assertEqual(s["selected_serial_scalps"], 1)
        self.assertEqual(s["records"][0]["price_band"], "80c+")
        self.assertTrue(s["records"][0]["price_is_telemetry_only"])

    def test_true_post_exit_miss_fails_coverage_gate(self):
        summary = {
            "post_exit_missed_qualified": 1,
            "max_serial_index": 4,
            "failed_prearm_blocked_candidates": 0,
        }
        g = m.gate(summary)
        self.assertFalse(g["coverage_logic_pass"])
        self.assertFalse(g["freeze_allowed"])
        self.assertFalse(g["orders"])


if __name__ == "__main__":
    unittest.main()
