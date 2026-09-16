#!/usr/bin/env python3
import unittest

import scalp_specialist_union_frontier_v2 as s


class SpecialistUnionV2Tests(unittest.TestCase):
    def test_unclassified_candidate_can_rescue_but_not_core(self):
        scored = [
            {
                "contract": "A", "specialist_union": True, "primary_lane": "KALSHI_LAG",
                "quality_prob": 0.91, "plus10": 1,
            },
            {
                "contract": "B", "specialist_union": False, "primary_lane": "UNCLASSIFIED",
                "quality_prob": 0.72, "plus10": 1,
            },
            {
                "contract": "C", "specialist_union": True, "primary_lane": "MOMENTUM",
                "quality_prob": 0.40, "plus10": 0,
            },
        ]
        z = s.select_core_rescue(scored, {"A", "B", "C", "D"}, 0.80, 0.50)
        by_contract = {r["contract"]: r for r in z}
        self.assertEqual(by_contract["A"]["selection_tier"], "CORE")
        self.assertEqual(by_contract["B"]["selection_tier"], "COVERAGE_RESCUE")
        self.assertTrue(by_contract["B"]["rescue_unclassified"])
        self.assertNotIn("C", by_contract)
        self.assertNotIn("D", by_contract)

    def test_unclassified_high_probability_never_enters_core(self):
        scored = [
            {
                "contract": "A", "specialist_union": False, "primary_lane": "UNCLASSIFIED",
                "quality_prob": 0.99, "plus10": 1,
            },
        ]
        z = s.select_core_rescue(scored, {"A"}, 0.80, 0.50)
        self.assertEqual(len(z), 1)
        self.assertEqual(z[0]["selection_tier"], "COVERAGE_RESCUE")
        self.assertTrue(z[0]["rescue_unclassified"])

    def test_specialist_core_prevents_lower_tier_rescue(self):
        scored = [
            {
                "contract": "A", "specialist_union": True, "primary_lane": "MOMENTUM",
                "quality_prob": 0.83, "plus10": 1,
            },
            {
                "contract": "A", "specialist_union": False, "primary_lane": "UNCLASSIFIED",
                "quality_prob": 0.95, "plus10": 1,
            },
        ]
        z = s.select_core_rescue(scored, {"A"}, 0.80, 0.50)
        self.assertEqual(len(z), 1)
        self.assertEqual(z[0]["selection_tier"], "CORE")
        self.assertEqual(z[0]["primary_lane"], "MOMENTUM")

    def test_tier_diagnostics_show_incremental_rescue_coverage(self):
        selected = [
            {"contract": "A", "selection_tier": "CORE", "plus10": 1, "rescue_unclassified": False},
            {"contract": "B", "selection_tier": "COVERAGE_RESCUE", "plus10": 1, "rescue_unclassified": True},
            {"contract": "C", "selection_tier": "COVERAGE_RESCUE", "plus10": 0, "rescue_unclassified": False},
        ]
        d = s.tier_diagnostics(selected, {"A", "B", "C", "D"})
        self.assertAlmostEqual(d["core_true_contract_coverage"], 0.25)
        self.assertAlmostEqual(d["coverage_gain_from_rescue"], 0.50)
        self.assertEqual(d["unclassified_rescue_contracts"], 1)
        self.assertAlmostEqual(d["coverage_rescue_plus10_rate"], 0.50)

    def test_no_candidate_contract_is_never_forced(self):
        scored = [
            {
                "contract": "A", "specialist_union": True, "primary_lane": "KALSHI_LAG",
                "quality_prob": 0.95, "plus10": 1,
            },
        ]
        z = s.select_core_rescue(scored, {"A", "B"}, 0.80, 0.50)
        self.assertEqual({r["contract"] for r in z}, {"A"})


if __name__ == "__main__":
    unittest.main()
