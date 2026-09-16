#!/usr/bin/env python3
import unittest

import scalp_baseline_coverage_gap_audit_v1 as g


class BaselineCoverageGapAuditTests(unittest.TestCase):
    def snap(self, contract, left, ts):
        return {"record_type":"SNAPSHOT","contract":contract,"seconds_left":str(left),"timestamp_utc":ts}

    def candidate(self, contract, candidate_id, btc30, left=600, ask=.35, ts="2026-09-16T00:05:00Z"):
        return {
            "record_type":"CANDIDATE","contract":contract,"candidate_id":candidate_id,
            "timestamp_utc":ts,"side":"UP","seconds_left":str(left),"btc30":str(btc30),
            "entry_ask":str(ask),
        }

    def path(self, contract, candidate_id, gain, elapsed=30):
        return {
            "record_type":"PATH","contract":contract,"candidate_id":candidate_id,
            "timestamp_utc":"2026-09-16T00:05:30Z","elapsed_sec":str(elapsed),"exec_gain":str(gain),
            "seconds_left":"570",
        }

    def result(self, contract, candidate_id):
        return {"record_type":"RESULT","contract":contract,"candidate_id":candidate_id,"seconds_left":"400"}

    def full_observation(self, contract, minute):
        return [
            self.snap(contract, 890, f"2026-09-16T{minute:02d}:00:10Z"),
            self.snap(contract, 30, f"2026-09-16T{minute:02d}:14:30Z"),
        ]

    def test_audit_classifies_missing_and_recoverable_contracts(self):
        rows = []
        for c, m in (("A",0),("B",1),("C",2),("D",3)):
            rows += self.full_observation(c, m)

        # A is covered by the current baseline.
        rows += [self.candidate("A","a1",20), self.path("A","a1",.12), self.result("A","a1")]
        # B has no candidate rows at all.
        # C has a complete +10 path but btc30 is below the baseline 15 gate.
        rows += [self.candidate("C","c1",10,ask=.35), self.path("C","c1",.12), self.result("C","c1")]
        # D has a baseline-qualified candidate but no RESULT.
        rows += [self.candidate("D","d1",25), self.path("D","d1",.15)]

        out = g.audit(rows)
        summary = out["summary"]
        ledger = {r["contract"]: r for r in out["ledger"]}

        self.assertEqual(summary["full_observed_contracts"], 4)
        self.assertEqual(summary["baseline_covered_contracts"], 1)
        self.assertEqual(summary["uncovered_contracts"], 3)
        self.assertEqual(ledger["B"]["reason"], "NO_CANDIDATE_ROWS")
        self.assertEqual(ledger["C"]["reason"], "BTC30_BELOW_BASELINE_15")
        self.assertEqual(ledger["D"]["reason"], "QUALIFIED_CANDIDATE_NO_RESULT")
        self.assertTrue(ledger["C"]["hindsight_any_plus10"])
        self.assertTrue(ledger["C"]["hindsight_early_affordable_plus10"])
        self.assertTrue(ledger["C"]["hindsight_nonbaseline_plus10"])
        self.assertFalse(summary["automatic_promotion"])
        self.assertTrue(summary["hindsight_ceiling_is_not_a_signal"])

    def test_late_only_reason_is_separate_from_weak_btc30(self):
        c = self.candidate("X","x1",30,left=90)
        reason, detail = g.classify_gap([c], set(), set())
        self.assertEqual(reason, "LATE_ONLY_CANDIDATES")
        self.assertEqual(detail["early_candidates_ge120s"], 0)

    def test_missing_btc30_reason_fails_closed(self):
        c = self.candidate("X","x1",20)
        c.pop("btc30")
        reason, _ = g.classify_gap([c], set(), set())
        self.assertEqual(reason, "BTC30_MISSING_ON_EARLY_CANDIDATES")

    def test_hindsight_ceiling_does_not_require_baseline_qualification(self):
        c = self.candidate("X","x1",5,left=500,ask=.40)
        paths = {"x1":[self.path("X","x1",.21)]}
        out = g.candidate_path_ceiling([c], paths, {"x1"})
        self.assertTrue(out["hindsight_any_plus10"])
        self.assertTrue(out["hindsight_any_plus20"])
        self.assertTrue(out["hindsight_nonbaseline_plus10"])
        self.assertTrue(out["hindsight_early_affordable_plus10"])


if __name__ == "__main__":
    unittest.main()
