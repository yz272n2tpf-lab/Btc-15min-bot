#!/usr/bin/env python3
import unittest

import BTC15_SCALP_15S_PARITY_FORWARD_V1 as m


class ParityForwardTests(unittest.TestCase):
    CONTRACT = "KXBTC15M-TEST"

    def c(self, cid, ts, *, b15=20, r15=20, side="UP", left=600, b30=20):
        return {
            "record_type": "CANDIDATE",
            "candidate_id": cid,
            "contract": self.CONTRACT,
            "timestamp_utc": ts,
            "side": side,
            "seconds_left": str(left),
            "btc30": str(b30),
            "btc15": str(b15),
            "brti15": str(r15),
            "entry_ask": "0.30",
        }

    def p(self, cid, ts, elapsed, gain):
        return {
            "record_type": "PATH",
            "candidate_id": cid,
            "contract": self.CONTRACT,
            "timestamp_utc": ts,
            "elapsed_sec": str(elapsed),
            "exec_gain": str(gain),
        }

    def r(self, cid, ts):
        return {
            "record_type": "RESULT",
            "candidate_id": cid,
            "contract": self.CONTRACT,
            "timestamp_utc": ts,
        }

    def test_parity_is_literal_cross_source_ratio(self):
        self.assertTrue(m.parity_pass(self.c("a", "2026-09-15T04:52:00Z", b15=20, r15=20)))
        self.assertTrue(m.parity_pass(self.c("a", "2026-09-15T04:52:00Z", b15=20, r15=22)))
        self.assertFalse(m.parity_pass(self.c("a", "2026-09-15T04:52:00Z", b15=20, r15=19.9)))
        self.assertAlmostEqual(m.parity_ratio(self.c("a", "2026-09-15T04:52:00Z", b15=20, r15=22)), 1.1)

    def test_fresh_cutoff_excludes_old_candidates(self):
        rows = [
            self.c("old", "2026-09-15T04:50:59Z"),
            self.c("new", "2026-09-15T04:51:00Z"),
        ]
        ids = [x["candidate_id"] for x in m.fresh_candidates(rows)]
        self.assertEqual(ids, ["new"])

    def test_hypothesis_skips_failed_parity_and_can_take_later_candidate(self):
        rows = [
            self.c("a", "2026-09-15T04:52:00Z", b15=20, r15=15),
            self.p("a", "2026-09-15T04:52:10Z", 10, .02),
            self.r("a", "2026-09-15T04:52:30Z"),
            self.c("b", "2026-09-15T04:52:40Z", b15=20, r15=22, side="DOWN"),
            self.p("b", "2026-09-15T04:52:50Z", 10, .12),
            self.p("b", "2026-09-15T04:53:00Z", 20, .06),
            self.r("b", "2026-09-15T04:53:10Z"),
        ]
        baseline = m.build_serial(rows)
        parity = m.build_serial(rows, m.parity_pass)
        self.assertEqual([x["candidate_id"] for x in baseline], ["a", "b"])
        self.assertEqual([x["candidate_id"] for x in parity], ["b"])
        self.assertTrue(parity[0]["plus10"])
        self.assertEqual(parity[0]["opportunity_index"], 1)

    def test_accepted_armed_no_exit_still_blocks_later_candidate(self):
        rows = [
            self.c("a", "2026-09-15T04:52:00Z", b15=20, r15=22),
            self.p("a", "2026-09-15T04:52:10Z", 10, .06),
            self.p("a", "2026-09-15T04:52:20Z", 20, .08),
            self.r("a", "2026-09-15T04:52:30Z"),
            self.c("b", "2026-09-15T04:52:40Z", b15=20, r15=24),
            self.p("b", "2026-09-15T04:52:50Z", 10, .20),
            self.r("b", "2026-09-15T04:53:00Z"),
        ]
        parity = m.build_serial(rows, m.parity_pass)
        self.assertEqual([x["candidate_id"] for x in parity], ["a"])
        self.assertEqual(parity[0]["terminal_kind"], "ARMED_NO_VALIDATED_EXIT")

    def test_safety_and_acceptance_are_manual_review_only(self):
        s = m.summarize([])
        self.assertEqual(s["status"], "COLLECTING_FRESH_FORWARD")
        self.assertFalse(s["acceptance_pass"])
        self.assertFalse(s["orders"])
        self.assertTrue(s["manual_execution_only"])
        self.assertFalse(s["entry_price_filter_applied"])
        self.assertFalse(s["new_fixed_time_window_applied"])
        self.assertFalse(s["protected_thresholds_changed"])
        self.assertFalse(s["stop_loss_rule_selected"])
        self.assertFalse(s["auto_promote_allowed"])
        self.assertFalse(s["actionable_now"])
        self.assertFalse(s["production_behavior_changed"])


if __name__ == "__main__":
    unittest.main()
