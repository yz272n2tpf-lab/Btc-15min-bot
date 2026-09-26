#!/usr/bin/env python3
import unittest

import scalp_coverage_gap_ledger_v1 as g


class CoverageGapLedgerTests(unittest.TestCase):
    def test_gap_reasons_and_affordable_statuses(self):
        scored = [
            {"contract": "A", "quality_prob": .91, "specialist_union": True, "entry_ask": .35, "primary_lane": "MOMENTUM"},
            {"contract": "B", "quality_prob": .58, "specialist_union": False, "entry_ask": .42, "primary_lane": "UNCLASSIFIED"},
            {"contract": "C", "quality_prob": .40, "specialist_union": True, "entry_ask": .30, "primary_lane": "KALSHI_LAG"},
            {"contract": "D", "quality_prob": .88, "specialist_union": True, "entry_ask": .72, "primary_lane": "MOMENTUM"},
        ]
        selected = [
            {**scored[0], "selection_tier": "CORE"},
            {**scored[1], "selection_tier": "COVERAGE_RESCUE"},
            {**scored[3], "selection_tier": "CORE"},
        ]
        ledger = g.build_ledger(scored, selected, {"A", "B", "C", "D", "E"}, .80, .50)
        by = {r["contract"]: r for r in ledger}
        self.assertEqual(by["A"]["coverage_status"], "COVERED_CORE")
        self.assertEqual(by["B"]["coverage_status"], "COVERED_RESCUE")
        self.assertEqual(by["C"]["gap_reason"], "BELOW_RESCUE_THRESHOLD")
        self.assertEqual(by["D"]["affordable_status"], "COVERED_ONLY_ABOVE_50C")
        self.assertEqual(by["E"]["gap_reason"], "NO_BASELINE_CANDIDATE")

    def test_summary_uses_true_denominator(self):
        ledger = [
            {"coverage_status": "COVERED_CORE", "gap_reason": "NONE", "affordable_status": "AFFORDABLE_COVERED"},
            {"coverage_status": "COVERED_RESCUE", "gap_reason": "NONE", "affordable_status": "COVERED_ONLY_ABOVE_50C"},
            {"coverage_status": "UNCOVERED", "gap_reason": "NO_BASELINE_CANDIDATE", "affordable_status": "NO_AFFORDABLE_BASELINE_CANDIDATE"},
            {"coverage_status": "UNCOVERED", "gap_reason": "BELOW_RESCUE_THRESHOLD", "affordable_status": "AFFORDABLE_CANDIDATE_NOT_SELECTED"},
        ]
        s = g.summarize(ledger)
        self.assertAlmostEqual(s["true_contract_coverage"], .50)
        self.assertAlmostEqual(s["affordable_true_contract_coverage_le50"], .25)
        self.assertFalse(s["orders"])
        self.assertFalse(s["automatic_promotion"])


if __name__ == "__main__":
    unittest.main()
