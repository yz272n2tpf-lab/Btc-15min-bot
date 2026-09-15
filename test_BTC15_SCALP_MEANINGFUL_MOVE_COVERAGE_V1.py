#!/usr/bin/env python3
import unittest

import BTC15_SCALP_MEANINGFUL_MOVE_COVERAGE_V1 as m


class MeaningfulMoveCoverageTests(unittest.TestCase):
    CONTRACT = "KXBTC15M-26SEP150000-00"

    def c(self, ts, cid, ask="0.31", side="UP", left="600"):
        return {
            "record_type": "CANDIDATE", "timestamp_utc": ts,
            "candidate_id": cid, "contract": self.CONTRACT,
            "entry_ask": ask, "side": side, "seconds_left": left, "btc30": "20",
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

    def test_failed_prearm_can_hide_later_ten_cent_move(self):
        rows = [
            self.c("2026-09-15T00:00:00Z", "a"),
            self.p("2026-09-15T00:00:20Z", "a", 0.02, 20),
            self.r("2026-09-15T00:01:00Z", "a"),
            self.c("2026-09-15T00:01:10Z", "b", ask="0.86", side="DOWN"),
            self.p("2026-09-15T00:01:20Z", "b", 0.12, 10),
            self.p("2026-09-15T00:01:30Z", "b", 0.07, 20),
            self.r("2026-09-15T00:02:00Z", "b"),
        ]
        out = m.audit(rows)
        self.assertEqual(out["completed_meaningful_10c_candidates"], 1)
        self.assertEqual(out["blocked_prearm_meaningful_10c"], 1)
        self.assertEqual(out["baseline_serial_captured_meaningful_10c"], 0)
        self.assertEqual(out["projected_unarmed_lifecycle_captured_meaningful_10c"], 1)
        self.assertEqual(out["projected_additional_10c_captured"], 1)
        self.assertFalse(out["entry_price_filter_applied"])
        self.assertFalse(out["orders"])

    def test_overlap_ten_cent_move_is_reported_not_true_miss(self):
        rows = [
            self.c("2026-09-15T00:00:00Z", "a"),
            self.p("2026-09-15T00:00:10Z", "a", 0.06, 10),
            self.c("2026-09-15T00:00:15Z", "b", side="DOWN"),
            self.p("2026-09-15T00:00:20Z", "b", 0.15, 5),
            self.r("2026-09-15T00:00:25Z", "b"),
            self.p("2026-09-15T00:00:30Z", "a", 0.01, 30),
            self.r("2026-09-15T00:00:40Z", "a"),
        ]
        out = m.audit(rows)
        self.assertEqual(out["overlap_meaningful_10c"], 1)
        self.assertEqual(out["true_post_exit_missed_meaningful_10c"], 0)
        self.assertEqual(out["serial_addressable_meaningful_10c"], 0)

    def test_high_price_winner_is_counted_without_price_suppression(self):
        rows = [
            self.c("2026-09-15T00:00:00Z", "a", ask="0.91"),
            self.p("2026-09-15T00:00:10Z", "a", 0.13, 10),
            self.p("2026-09-15T00:00:20Z", "a", 0.08, 20),
            self.r("2026-09-15T00:00:30Z", "a"),
        ]
        out = m.audit(rows)
        self.assertEqual(out["selected_meaningful_10c"], 1)
        self.assertAlmostEqual(out["selected_10c_precision"], 1.0)
        self.assertTrue(out["price_is_telemetry_only"])
        self.assertFalse(out["entry_price_filter_applied"])


if __name__ == "__main__":
    unittest.main()
