#!/usr/bin/env python3
import unittest

import btc15_scalp_unarmed_live_tape_validator_v1 as v


class LiveTapeValidatorTests(unittest.TestCase):
    CONTRACT = "KXBTC15M-26SEP150000-00"

    def c(self, ts, cid, ask="0.31", side="UP"):
        return {
            "record_type": "CANDIDATE", "timestamp_utc": ts,
            "candidate_id": cid, "contract": self.CONTRACT,
            "entry_ask": ask, "side": side, "seconds_left": "600", "btc30": "20",
        }

    def p(self, ts, cid, gain, elapsed):
        return {
            "record_type": "PATH", "timestamp_utc": ts,
            "candidate_id": cid, "contract": self.CONTRACT,
            "exec_gain": str(gain), "elapsed_sec": str(elapsed),
        }

    def r(self, ts, cid):
        return {
            "record_type": "RESULT", "timestamp_utc": ts,
            "candidate_id": cid, "contract": self.CONTRACT,
        }

    def test_unarmed_result_recovers_later_completed_scalp(self):
        rows = [
            self.c("2026-09-15T00:00:00Z", "a"),
            self.p("2026-09-15T00:00:20Z", "a", 0.02, 20),
            self.r("2026-09-15T00:01:00Z", "a"),
            self.c("2026-09-15T00:01:10Z", "b", ask="0.86", side="DOWN"),
            self.p("2026-09-15T00:01:20Z", "b", 0.11, 10),
            self.p("2026-09-15T00:01:30Z", "b", 0.06, 20),
            self.r("2026-09-15T00:02:00Z", "b"),
        ]
        out = v.summarize(rows, "abc")
        self.assertEqual(out["baseline_completed_serial_opportunities"], 1)
        self.assertEqual(out["projected_completed_serial_opportunities"], 2)
        self.assertEqual(out["projected_additional_serial_opportunities"], 1)
        self.assertEqual(out["ended_unarmed_n"], 1)
        self.assertEqual(out["post_unarmed_later_completed_n"], 1)
        self.assertEqual(out["post_unarmed_later_plus10_n"], 1)
        self.assertFalse(out["entry_price_filter_applied"])
        self.assertFalse(out["orders"])

    def test_existing_protected_exit_needs_no_lifecycle_recovery(self):
        rows = [
            self.c("2026-09-15T00:00:00Z", "a"),
            self.p("2026-09-15T00:00:10Z", "a", 0.06, 10),
            self.p("2026-09-15T00:00:20Z", "a", 0.01, 20),
            self.r("2026-09-15T00:00:30Z", "a"),
            self.c("2026-09-15T00:00:40Z", "b", side="DOWN"),
            self.p("2026-09-15T00:00:50Z", "b", 0.12, 10),
            self.p("2026-09-15T00:01:00Z", "b", 0.07, 20),
            self.r("2026-09-15T00:01:10Z", "b"),
        ]
        out = v.summarize(rows)
        self.assertEqual(out["baseline_completed_serial_opportunities"], 2)
        self.assertEqual(out["projected_completed_serial_opportunities"], 2)
        self.assertEqual(out["projected_additional_serial_opportunities"], 0)
        self.assertEqual(out["ended_unarmed_n"], 0)
        self.assertFalse(out["protected_thresholds_changed"])

    def test_incomplete_current_candidate_is_not_skipped(self):
        rows = [
            self.c("2026-09-15T00:00:00Z", "a"),
            self.p("2026-09-15T00:00:20Z", "a", -0.12, 20),
            self.c("2026-09-15T00:00:30Z", "b"),
            self.p("2026-09-15T00:00:40Z", "b", 0.20, 10),
            self.r("2026-09-15T00:01:00Z", "b"),
        ]
        out = v.summarize(rows)
        self.assertEqual(out["baseline_completed_serial_opportunities"], 0)
        self.assertEqual(out["projected_completed_serial_opportunities"], 0)
        self.assertEqual(out["projected_additional_serial_opportunities"], 0)
        self.assertEqual(out["ended_unarmed_n"], 0)
        self.assertFalse(out["ended_unarmed_is_actionable_exit"])


if __name__ == "__main__":
    unittest.main()
