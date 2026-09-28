#!/usr/bin/env python3
import unittest

import scalp_lane_complementarity_v1 as c


class LaneComplementarityTests(unittest.TestCase):
    def setUp(self):
        self.den = {"A", "B", "C", "D", "E"}
        self.opps = [
            {"contract":"A", "lane_tags":["KALSHI_LAG"], "entry_ask":.30, "plus5":1, "plus10":1, "plus20":0, "peak_gain":.12, "adverse_gain":0, "protected_exit_gain":.08, "t10_sec":20},
            {"contract":"B", "lane_tags":["MOMENTUM"], "entry_ask":.40, "plus5":1, "plus10":1, "plus20":1, "peak_gain":.22, "adverse_gain":-.01, "protected_exit_gain":.10, "t10_sec":30},
            {"contract":"C", "lane_tags":["KALSHI_LAG","MOMENTUM"], "entry_ask":.60, "plus5":1, "plus10":0, "plus20":0, "peak_gain":.07, "adverse_gain":-.03, "protected_exit_gain":.03, "t10_sec":None},
            {"contract":"D", "lane_tags":["REVERSAL_RECROSS"], "entry_ask":.25, "plus5":1, "plus10":1, "plus20":0, "peak_gain":.15, "adverse_gain":-.01, "protected_exit_gain":.09, "t10_sec":25},
        ]

    def test_unique_lane_coverage_counts_only_nonoverlap(self):
        rows = {r["lane"]: r for r in c.unique_lane_coverage(self.opps, self.den)}
        self.assertEqual(rows["KALSHI_LAG"]["covered_contracts"], 2)
        self.assertEqual(rows["KALSHI_LAG"]["unique_contracts"], 1)
        self.assertEqual(rows["MOMENTUM"]["unique_contracts"], 1)
        self.assertEqual(rows["REVERSAL_RECROSS"]["unique_contracts"], 1)
        self.assertEqual(rows["REENTRY_CONTINUATION"]["unique_contracts"], 0)

    def test_pairwise_overlap_reports_shared_contract(self):
        pairs = c.pairwise_overlap(self.opps, self.den)
        row = next(r for r in pairs if r["lane_a"] == "KALSHI_LAG" and r["lane_b"] == "MOMENTUM")
        self.assertEqual(row["intersection_contracts"], 1)
        self.assertEqual(row["union_contracts"], 3)
        self.assertAlmostEqual(row["jaccard_overlap"], 1/3)

    def test_subset_frontier_uses_true_denominator(self):
        rows = c.subset_frontier(self.opps, self.den)
        lag = next(r for r in rows if r["lanes"] == "KALSHI_LAG")
        lag_mom = next(r for r in rows if r["lanes"] == "KALSHI_LAG+MOMENTUM")
        self.assertEqual(lag["true_contract_denominator"], 5)
        self.assertAlmostEqual(lag["true_contract_coverage"], 2/5)
        self.assertAlmostEqual(lag_mom["true_contract_coverage"], 3/5)

    def test_all_nonempty_subsets_are_reported(self):
        rows = c.subset_frontier(self.opps, self.den)
        self.assertEqual(len(rows), 15)


if __name__ == "__main__":
    unittest.main()
