#!/usr/bin/env python3
import unittest

import scalp_gap_recovery_feature_audit_v1 as g


class GapRecoveryFeatureAuditTests(unittest.TestCase):
    def test_feature_summary_handles_small_samples(self):
        rows = [{"x": 1.0}, {"x": 2.0}, {"x": 4.0}]
        out = g.feature_summary(rows, "x")
        self.assertEqual(out["n"], 3)
        self.assertEqual(out["median"], 2.0)
        self.assertAlmostEqual(out["mean"], 7/3)
        self.assertEqual(out["q25"], 1.5)
        self.assertEqual(out["q75"], 3.0)

    def test_group_summary_uses_contract_union_not_candidate_count(self):
        rows = [
            {"contract":"A","plus10":True,"early_affordable":True},
            {"contract":"A","plus10":False,"early_affordable":False},
            {"contract":"B","plus10":True,"early_affordable":False},
        ]
        out = g.group_summary(rows, 10)
        self.assertEqual(out["candidate_paths"], 3)
        self.assertEqual(out["contracts"], 2)
        self.assertEqual(out["contracts_with_plus10"], 2)
        self.assertEqual(out["contracts_with_early_affordable_plus10"], 1)
        self.assertAlmostEqual(out["incremental_contract_coverage_ceiling_if_all_plus10_were_causally_detectable"], .2)

    def test_no_threshold_selection_or_promotion_is_exposed(self):
        # The descriptive audit must not advertise production selection behavior.
        self.assertNotIn("threshold", g.VERSION.lower())
        self.assertTrue(g.FEATURES)
        forbidden = {"peak_gain","plus10","plus20","future_bid","outcome"}
        self.assertTrue(forbidden.isdisjoint(set(g.FEATURES)))


if __name__ == "__main__":
    unittest.main()
