#!/usr/bin/env python3
import unittest

import BTC15_SCALP_10C_ACCOUNTING_AUDIT_V2 as a


class TenCentAccountingTests(unittest.TestCase):
    C = "KXBTC15M-26SEP150030-30"

    def cand(self, ts, cid, ask="0.31", side="UP"):
        return {"record_type":"CANDIDATE","timestamp_utc":ts,"candidate_id":cid,
                "contract":self.C,"entry_ask":ask,"side":side,"seconds_left":"600","btc30":"20"}

    def path(self, ts, cid, gain, elapsed):
        return {"record_type":"PATH","timestamp_utc":ts,"candidate_id":cid,
                "contract":self.C,"exec_gain":str(gain),"elapsed_sec":str(elapsed)}

    def result(self, ts, cid):
        return {"record_type":"RESULT","timestamp_utc":ts,"candidate_id":cid,"contract":self.C}

    def test_selected_overlap_and_failed_prearm_are_separate(self):
        rows = [
            self.cand("2026-09-15T01:00:00Z","a"),
            self.cand("2026-09-15T01:00:10Z","b", ask="0.84", side="DOWN"),
            self.path("2026-09-15T01:00:10Z","a",.12,10),
            self.path("2026-09-15T01:00:20Z","a",.07,20),
            self.path("2026-09-15T01:00:20Z","b",.11,10),
            self.result("2026-09-15T01:00:25Z","a"),
            self.result("2026-09-15T01:00:26Z","b"),
            self.cand("2026-09-15T01:00:30Z","c"),
            self.path("2026-09-15T01:00:40Z","c",.02,10),
            self.result("2026-09-15T01:00:45Z","c"),
            self.cand("2026-09-15T01:00:50Z","d", ask="0.07", side="DOWN"),
            self.path("2026-09-15T01:01:00Z","d",.15,10),
            self.result("2026-09-15T01:01:05Z","d"),
        ]
        out = a.audit(rows)
        self.assertTrue(out["accounting_identity_ok"])
        self.assertEqual(out["selected_plus10_n"], 1)
        self.assertEqual(out["overlap_plus10_n"], 1)
        self.assertEqual(out["blocked_failed_prearm_plus10_n"], 1)
        self.assertEqual(out["true_post_exit_missed_plus10_n"], 0)
        self.assertFalse(out["entry_price_filter_applied"])
        self.assertFalse(out["orders"])

    def test_high_price_plus10_is_still_accounted(self):
        rows = [
            self.cand("2026-09-15T01:10:00Z","a", ask="0.91"),
            self.path("2026-09-15T01:10:10Z","a",.13,10),
            self.path("2026-09-15T01:10:20Z","a",.08,20),
            self.result("2026-09-15T01:10:25Z","a"),
        ]
        out = a.audit(rows)
        self.assertEqual(out["completed_frozen_qualified_plus10_n"], 1)
        self.assertEqual(out["selected_plus10_n"], 1)
        self.assertAlmostEqual(out["records"][0]["entry_ask"], .91)
        self.assertTrue(out["price_is_telemetry_only"])

    def test_true_post_exit_miss_is_explicit_failure(self):
        rows = [
            self.cand("2026-09-15T01:20:00Z","a"),
            self.path("2026-09-15T01:20:10Z","a",.11,10),
            self.path("2026-09-15T01:20:20Z","a",.06,20),
            self.result("2026-09-15T01:20:25Z","a"),
            # First post-exit candidate remains incomplete, so a later completed
            # +10 candidate must not disappear from the accounting.
            self.cand("2026-09-15T01:20:30Z","incomplete"),
            self.path("2026-09-15T01:20:35Z","incomplete",.01,5),
            self.cand("2026-09-15T01:20:40Z","later"),
            self.path("2026-09-15T01:20:50Z","later",.14,10),
            self.result("2026-09-15T01:20:55Z","later"),
        ]
        out = a.audit(rows)
        self.assertEqual(out["true_post_exit_missed_plus10_n"], 1)
        self.assertTrue(out["accounting_identity_ok"])
        gate = a.gate(out)
        self.assertFalse(gate["normal_reset_plus10_coverage_pass"])
        self.assertFalse(gate["freeze_allowed"])


if __name__ == "__main__":
    unittest.main()
