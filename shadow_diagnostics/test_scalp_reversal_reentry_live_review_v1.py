#!/usr/bin/env python3
import unittest
import scalp_reversal_reentry_live_review_v1 as live


class ReversalReentryLiveReviewTests(unittest.TestCase):
    def test_compact_exposes_validation_only(self):
        result = {
            "status":"REVERSAL_REENTRY_LADDER_READY",
            "baseline_candidate_gate_unchanged":True,
            "legacy_protection_lifecycle_unchanged":True,
            "serial_meta":{"x":1},
            "validation":{"serial_eligible_contracts":10,"SERIAL_UNION":{"signals":12,"plus10_rate":.7}},
            "holdout":{"serial_eligible_contracts":99,"SERIAL_UNION":{"signals":99,"plus10_rate":1.0}},
        }
        out = live.compact(result)
        self.assertTrue(out["holdout_sealed"])
        self.assertFalse(out["automatic_selection"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])
        self.assertEqual(out["coverage_scope"], "SERIAL_ELIGIBLE_CONTRACTS_ONLY")
        self.assertEqual(out["validation"]["serial_eligible_contracts"], 10)
        self.assertNotIn("holdout", out)


if __name__ == "__main__":
    unittest.main()
