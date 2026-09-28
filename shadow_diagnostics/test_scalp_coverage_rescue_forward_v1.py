#!/usr/bin/env python3
import unittest

import scalp_coverage_rescue_forward_v1 as f


class CoverageRescueForwardV1Tests(unittest.TestCase):
    def test_cutoff_is_required(self):
        out = f.analyze_rows([], cutoff_text="")
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], "FAIL_CLOSED_MISSING_OR_INVALID_CUTOFF")
        self.assertFalse(out["orders"])

    def test_future_universe_excludes_contract_first_seen_before_cutoff(self):
        rows = [
            {"contract":"OLD","record_type":"SNAPSHOT","timestamp_utc":"2026-09-16T05:00:00Z","seconds_left":"850"},
            {"contract":"OLD","record_type":"SNAPSHOT","timestamp_utc":"2026-09-16T05:14:00Z","seconds_left":"50"},
            {"contract":"NEW","record_type":"SNAPSHOT","timestamp_utc":"2026-09-16T05:30:00Z","seconds_left":"850"},
            {"contract":"NEW","record_type":"SNAPSHOT","timestamp_utc":"2026-09-16T05:44:00Z","seconds_left":"50"},
        ]
        cutoff = f.parse_cutoff("2026-09-16T05:20:00Z")
        universe, _ = f.future_universe(rows, cutoff)
        self.assertEqual(set(universe), {"NEW"})

    def test_rescue_is_suppressed_if_baseline_already_fired(self):
        rescue_rows = [{"contract":"C","timestamp":f.parse_cutoff("2026-09-16T05:02:00Z")}]
        baseline_rows = [{"contract":"C","timestamp":f.parse_cutoff("2026-09-16T05:01:00Z")}]
        self.assertEqual(f.without_prior_baseline(rescue_rows, baseline_rows), [])

    def test_rescue_can_fire_before_a_later_baseline(self):
        rescue_rows = [{"contract":"C","timestamp":f.parse_cutoff("2026-09-16T05:01:00Z")}]
        baseline_rows = [{"contract":"C","timestamp":f.parse_cutoff("2026-09-16T05:02:00Z")}]
        self.assertEqual(len(f.without_prior_baseline(rescue_rows, baseline_rows)), 1)

    def test_compact_never_claims_auto_promotion(self):
        out = f.compact({"status":"COLLECTING_FUTURE_RESCUE_V1"})
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])
        self.assertTrue(out["frozen_rule"]["baseline_unchanged"])


if __name__ == "__main__":
    unittest.main()
