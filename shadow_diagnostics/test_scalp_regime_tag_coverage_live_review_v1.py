import unittest
from unittest.mock import patch

import scalp_regime_tag_coverage_live_review_v1 as live


class RegimeTagCoverageLiveReviewV1Tests(unittest.TestCase):
    def test_compact_never_selects_or_promotes(self):
        fake = {
            "status": "READY",
            "all_serial_opportunities": {"rows": 10, "trend_blockers": {"blockers": []}},
            "validation": {"rows": 4, "trend_blockers": {"blockers": []}},
            "holdout": {"rows": 3, "trend_blockers": {"blockers": []}},
        }
        out = live.compact(fake)
        self.assertTrue(out["causal_feature_audit"])
        self.assertFalse(out["threshold_selection"])
        self.assertFalse(out["outcomes_used_for_blockers_or_distributions"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])

    def test_compact_limits_blocker_rows(self):
        blockers = [{"reason": f"R{i}", "count": i} for i in range(20)]
        fake = {"status": "READY",
                "all_serial_opportunities": {"rows": 1, "trend_blockers": {"blockers": blockers}},
                "validation": {}, "holdout": {}}
        out = live.compact(fake)
        self.assertEqual(len(out["all_serial_opportunities"]["trend_blockers"]["blockers"]), 8)

    def test_analyze_rows_preserves_source_identity(self):
        fake = {"status": "READY", "all_serial_opportunities": {}, "validation": {}, "holdout": {}}
        with patch.object(live.audit, "analyze", return_value=fake):
            out = live.analyze_rows([{"record_type": "CANDIDATE"}], sha="abc", source_bytes=101)
        self.assertTrue(out["ok"])
        self.assertEqual(out["source_sha256"], "abc")
        self.assertEqual(out["source_bytes"], 101)
        self.assertEqual(out["source_rows"], 1)
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
