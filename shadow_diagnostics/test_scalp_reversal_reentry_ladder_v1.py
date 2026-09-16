#!/usr/bin/env python3
import unittest
from datetime import datetime, timedelta, timezone

import scalp_reversal_reentry_ladder_v1 as m

BASE = datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc)


def iso(sec):
    return (BASE + timedelta(seconds=sec)).isoformat()


def candidate(cid, contract, side, sec, ask=.40, left=780, btc30=25):
    return {
        "record_type":"CANDIDATE", "candidate_id":cid, "contract":contract,
        "side":side, "timestamp_utc":iso(sec), "entry_ask":ask,
        "seconds_left":left, "btc30":btc30,
    }


def path(cid, absolute_sec, candidate_sec, gain):
    return {
        "record_type":"PATH", "candidate_id":cid,
        "timestamp_utc":iso(absolute_sec),
        "elapsed_sec":absolute_sec-candidate_sec,
        "exec_gain":gain,
    }


def result(cid):
    return {"record_type":"RESULT", "candidate_id":cid}


def protected_path(cid, candidate_sec, exit_after=30):
    # +5 arm, then 4c giveback from +10 peak => protected exit at +5.
    return [
        path(cid, candidate_sec+10, candidate_sec, .05),
        path(cid, candidate_sec+20, candidate_sec, .10),
        path(cid, candidate_sec+exit_after, candidate_sec, .05),
    ]


class ReversalReentryLadderTests(unittest.TestCase):
    def test_same_side_after_real_exit_is_reentry(self):
        rows = [
            candidate("a","C1","UP",0), result("a"), *protected_path("a",0),
            candidate("b","C1","UP",40), result("b"), *protected_path("b",40),
        ]
        recs, meta = m.build_serial(m.prepare(rows))
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0]["lane"], "FIRST")
        self.assertEqual(recs[1]["lane"], "REENTRY_CONTINUATION")
        self.assertEqual(recs[1]["opportunity_index"], 2)
        self.assertIn("C1", meta["serial_eligible_contracts"])

    def test_opposite_side_after_real_exit_is_reversal(self):
        rows = [
            candidate("a","C1","UP",0), result("a"), *protected_path("a",0),
            candidate("b","C1","DOWN",40), result("b"), *protected_path("b",40),
        ]
        recs, _ = m.build_serial(m.prepare(rows))
        self.assertEqual(recs[1]["lane"], "REVERSAL_RECROSS")
        self.assertEqual(recs[1]["prior_side"], "UP")

    def test_candidate_before_prior_exit_is_not_serial_opportunity(self):
        rows = [
            candidate("a","C1","UP",0), result("a"), *protected_path("a",0,30),
            candidate("too_early","C1","DOWN",25), result("too_early"), *protected_path("too_early",25),
            candidate("b","C1","DOWN",40), result("b"), *protected_path("b",40),
        ]
        recs, _ = m.build_serial(m.prepare(rows))
        ids = [r["candidate_id"] for r in recs]
        self.assertEqual(ids, ["a","b"])
        self.assertEqual(recs[1]["lane"], "REVERSAL_RECROSS")

    def test_no_protected_exit_means_no_serial_lane(self):
        rows = [
            candidate("a","C1","UP",0), result("a"),
            path("a",10,0,.03), path("a",20,0,.02), path("a",30,0,.01),
            candidate("b","C1","DOWN",40), result("b"), *protected_path("b",40),
        ]
        recs, meta = m.build_serial(m.prepare(rows))
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["lane"], "FIRST")
        self.assertEqual(meta["serial_eligible_contracts"], [])
        self.assertEqual(meta["contracts_blocked_without_prior_protected_exit"], 1)

    def test_unresolved_serial_candidate_fails_closed_and_stops_chain(self):
        rows = [
            candidate("a","C1","UP",0), result("a"), *protected_path("a",0),
            candidate("b","C1","DOWN",40),  # no RESULT/PATH
            candidate("c","C1","UP",80), result("c"), *protected_path("c",80),
        ]
        recs, meta = m.build_serial(m.prepare(rows))
        self.assertEqual([r["candidate_id"] for r in recs], ["a"])
        self.assertEqual(meta["unresolved_serial_candidates"], 1)
        self.assertIn("C1", meta["serial_eligible_contracts"])

    def test_index_three_can_switch_back_to_reentry_or_reversal(self):
        rows = [
            candidate("a","C1","UP",0), result("a"), *protected_path("a",0),
            candidate("b","C1","DOWN",40), result("b"), *protected_path("b",40),
            candidate("c","C1","DOWN",80), result("c"), *protected_path("c",80),
        ]
        recs, _ = m.build_serial(m.prepare(rows))
        self.assertEqual(recs[1]["lane"], "REVERSAL_RECROSS")
        self.assertEqual(recs[2]["lane"], "REENTRY_CONTINUATION")
        self.assertEqual(recs[2]["opportunity_index"], 3)

    def test_summary_scope_is_serial_eligible_not_all_contracts(self):
        rows = [
            candidate("a","C1","UP",0), result("a"), *protected_path("a",0),
            candidate("b","C1","DOWN",40), result("b"), *protected_path("b",40),
            candidate("x","C2","UP",0), result("x"),
            path("x",10,0,.01), path("x",20,0,.00),
        ]
        out = m.analyze(rows)
        self.assertEqual(out["coverage_scope"], "SERIAL_ELIGIBLE_CONTRACTS_ONLY")
        self.assertFalse(out["automatic_selection"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
