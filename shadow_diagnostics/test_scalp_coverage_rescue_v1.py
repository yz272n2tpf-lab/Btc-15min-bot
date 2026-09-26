#!/usr/bin/env python3
import unittest

import scalp_coverage_rescue_v1 as r


def candidate(**kw):
    base = {
        "record_type":"CANDIDATE", "contract":"C1", "candidate_id":"x1",
        "timestamp_utc":"2026-09-16T05:00:00Z", "side":"UP",
        "seconds_left":"600", "entry_ask":"0.40", "btc30":"12",
        "btc5":"18", "btc15":"20", "brti5":"17", "brti15":"19",
        "btc5_norm":"0.70", "btc15_norm":"0.85", "ask5":"0", "ask15":"0.01",
        "confirm_count":"2", "structure_ok":"1", "btc_against_side":"0",
        "brti_against_side":"0", "dual_reversal_evidence":"0",
        "brti_status":"PRIMARY_OK", "entry_spread":"0.01",
        "max_possible_upside_c":"60", "accel":"10", "recent_btc_range60":"40",
        "brti_latency_ms":"300",
    }
    base.update(kw)
    return base


class CoverageRescueV1Tests(unittest.TestCase):
    def test_frozen_rescue_accepts_intended_weak_btc30_candidate(self):
        self.assertTrue(r.rescue_qualified(candidate()))

    def test_rescue_never_duplicates_baseline(self):
        self.assertFalse(r.rescue_qualified(candidate(btc30="15")))
        self.assertFalse(r.rescue_qualified(candidate(btc30="20")))

    def test_rescue_rejects_expensive_or_weak_short_momentum(self):
        self.assertFalse(r.rescue_qualified(candidate(entry_ask="0.51")))
        self.assertFalse(r.rescue_qualified(candidate(btc5_norm="0.59")))

    def test_rescue_rejects_late_reversal_or_bad_brti(self):
        self.assertFalse(r.rescue_qualified(candidate(seconds_left="119")))
        self.assertFalse(r.rescue_qualified(candidate(dual_reversal_evidence="1")))
        self.assertFalse(r.rescue_qualified(candidate(brti_status="FALLBACK")))

    def test_path_can_reconcile_missing_result_for_scoring_only(self):
        c = candidate()
        path = [
            {"record_type":"PATH","candidate_id":"x1","contract":"C1","timestamp_utc":"2026-09-16T05:00:10Z","elapsed_sec":"10","exec_gain":"0.03"},
            {"record_type":"PATH","candidate_id":"x1","contract":"C1","timestamp_utc":"2026-09-16T05:00:20Z","elapsed_sec":"20","exec_gain":"0.11"},
            {"record_type":"PATH","candidate_id":"x1","contract":"C1","timestamp_utc":"2026-09-16T05:00:30Z","elapsed_sec":"30","exec_gain":"0.06"},
        ]
        out = r.outcome_record(c, path, has_result=False)
        self.assertTrue(out["scoreable"])
        self.assertEqual(out["score_source"], "PATH_RECONCILED")
        self.assertEqual(out["plus10"], 1)

    def test_future_labels_are_not_part_of_trigger_contract(self):
        frozen = r.frozen_rule()
        self.assertTrue(frozen["baseline_unchanged"])
        self.assertFalse(frozen["orders"])
        # Adding hindsight fields must not change trigger result.
        a = candidate()
        b = dict(a, exec_gain="-0.99", result="LOSS", future_bid="0")
        self.assertEqual(r.rescue_qualified(a), r.rescue_qualified(b))


if __name__ == "__main__":
    unittest.main()
