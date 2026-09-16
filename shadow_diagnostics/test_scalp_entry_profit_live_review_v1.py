#!/usr/bin/env python3
import unittest
import scalp_entry_profit_live_review_v1 as live


class EntryProfitLiveReviewTests(unittest.TestCase):
    def test_compact_exposes_validation_not_holdout(self):
        result = {
            "status":"ENTRY_PROFIT_POLICY_GRID_READY",
            "entry_policies":{"A":{}},
            "exit_policies":{"X":{}},
            "policy_grid":[{
                "entry_policy":"A","exit_policy":"X",
                "validation":{"signals":3,"plus10_rate":2/3,"true_contract_coverage":.8},
                "holdout":{"signals":99,"plus10_rate":1.0},
            }],
        }
        out = live.compact(result)
        self.assertTrue(out["holdout_sealed"])
        self.assertFalse(out["automatic_selection"])
        self.assertFalse(out["orders"])
        self.assertEqual(out["validation_policy_grid"][0]["signals"], 3)
        self.assertNotIn("holdout", out)
        self.assertNotIn("holdout", out["validation_policy_grid"][0])


if __name__ == "__main__":
    unittest.main()
