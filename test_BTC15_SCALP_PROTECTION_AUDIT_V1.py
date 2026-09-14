#!/usr/bin/env python3
from __future__ import annotations

import os
import unittest

os.environ.setdefault("SCALP_BLUEPRINT_CUTOFF_UTC", "2026-09-14T21:08:00Z")

import BTC15_SCALP_PROTECTION_AUDIT_V1 as m


def c(cid, t, contract="C1", ask="0.30", side="UP"):
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


class ProtectionAuditTests(unittest.TestCase):
    def test_first_observed_four_cent_giveback_exits(self):
        rows = [
            c("a", "2026-09-14T21:10:00Z"),
            p("a", "2026-09-14T21:10:05Z", 5, .05),
            p("a", "2026-09-14T21:10:10Z", 10, .12),
            p("a", "2026-09-14T21:10:15Z", 15, .17),
            p("a", "2026-09-14T21:10:20Z", 20, .15),
            p("a", "2026-09-14T21:10:25Z", 25, .13),
            result("a"),
        ]
        s = m.audit(rows)
        self.assertEqual(s["protected_exit_records"], 1)
        r = s["records"][0]
        self.assertTrue(r["armed_plus5"])
        self.assertAlmostEqual(r["peak_at_exit"], .17)
        self.assertAlmostEqual(r["giveback_at_exit"], .04)
        self.assertAlmostEqual(r["exit_gain"], .13)
        self.assertTrue(r["first_observed_4c_crossing"])
        self.assertTrue(r["positive_exit"])

    def test_high_price_does_not_change_protection(self):
        rows = [
            c("hi", "2026-09-14T21:11:00Z", ask="0.88"),
            p("hi", "2026-09-14T21:11:05Z", 5, .06),
            p("hi", "2026-09-14T21:11:10Z", 10, .11),
            p("hi", "2026-09-14T21:11:15Z", 15, .07),
            result("hi"),
        ]
        s = m.audit(rows)
        self.assertEqual(s["selected_serial_records"], 1)
        self.assertEqual(s["protected_exit_records"], 1)
        self.assertAlmostEqual(s["records"][0]["entry_ask"], .88)
        self.assertFalse(s["rule_changed"])

    def test_failed_prearm_has_no_invented_exit(self):
        rows = [
            c("bad", "2026-09-14T21:12:00Z"),
            p("bad", "2026-09-14T21:12:05Z", 5, .02),
            p("bad", "2026-09-14T21:12:10Z", 10, -.03),
            p("bad", "2026-09-14T21:12:20Z", 20, -.12),
            result("bad"),
        ]
        s = m.audit(rows)
        self.assertEqual(s["armed_records"], 0)
        self.assertEqual(s["protected_exit_records"], 0)
        self.assertFalse(s["records"][0]["protected_exit_observed"])
        self.assertFalse(s["freeze_allowed"])
        self.assertFalse(s["orders"])

    def test_reset_after_exit_keeps_auditing_next_scalp(self):
        rows = [
            c("a", "2026-09-14T21:10:00Z"),
            p("a", "2026-09-14T21:10:05Z", 5, .06),
            p("a", "2026-09-14T21:10:10Z", 10, .02),
            result("a"),
            c("b", "2026-09-14T21:11:00Z", side="DOWN"),
            p("b", "2026-09-14T21:11:05Z", 5, .08),
            p("b", "2026-09-14T21:11:10Z", 10, .03),
            result("b"),
        ]
        s = m.audit(rows)
        self.assertEqual(s["selected_serial_records"], 2)
        self.assertEqual(s["protected_exit_records"], 2)
        self.assertEqual([r["candidate_id"] for r in s["records"]], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
