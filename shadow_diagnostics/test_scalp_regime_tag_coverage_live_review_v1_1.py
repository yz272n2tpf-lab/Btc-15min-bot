import unittest
from unittest.mock import patch

import scalp_regime_tag_coverage_audit_v1_1 as audit_v11
import scalp_regime_tag_coverage_live_review_v1_1 as live


class RegimeTagCoverageLiveReviewV11Tests(unittest.TestCase):
    def test_wrapper_uses_semantic_repair_audit(self):
        self.assertIs(live.base.audit, audit_v11)
        self.assertEqual(live.base.VERSION, live.VERSION)
        self.assertFalse(live.base.STATE.get("orders"))
        self.assertTrue(live.base.STATE.get("shadow_only"))

    def test_analyze_reports_v11_version_and_no_promotion(self):
        fake = {
            "status": "REGIME_TAG_COVERAGE_AUDIT_V1_1_READY",
            "all_serial_opportunities": {},
            "validation": {},
            "holdout": {},
            "threshold_selection": False,
            "outcomes_used_for_blockers_or_distributions": False,
            "no_signal_suppression_or_rescue": True,
            "automatic_promotion": False,
            "orders": False,
        }
        with patch.object(audit_v11, "analyze", return_value=fake):
            out = live.analyze_rows([], sha="abc", source_bytes=0)
        self.assertTrue(out["ok"])
        self.assertEqual(out["version"], live.VERSION)
        self.assertFalse(out["threshold_selection"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])
        self.assertFalse(out["production_logic_changed"])


if __name__ == "__main__":
    unittest.main()
