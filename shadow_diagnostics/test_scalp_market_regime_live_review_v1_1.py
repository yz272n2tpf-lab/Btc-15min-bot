import unittest
from unittest.mock import patch

import scalp_market_regime_live_review_v1_1 as live


class MarketRegimeLiveReviewV11Tests(unittest.TestCase):
    def test_compact_marks_holdout_descriptive_only(self):
        fake = {
            "status": "READY",
            "semantic_repair": {"thresholds_changed": False},
            "tag_definitions": {},
            "validation": {"overall": {"signals": 10}},
            "holdout": {"overall": {"signals": 8}},
            "validation_to_holdout_shift": {},
        }
        out = live.compact(fake)
        self.assertTrue(out["semantic_repair_only"])
        self.assertTrue(out["holdout_is_descriptive_after_semantic_repair"])
        self.assertTrue(out["holdout_cannot_select_v1_1_rule"])
        self.assertTrue(out["no_threshold_selection"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])

    def test_analyze_rows_preserves_source_identity(self):
        fake = {"status": "READY", "semantic_repair": {}, "tag_definitions": {},
                "validation": {}, "holdout": {}, "validation_to_holdout_shift": {}}
        with patch.object(live.regime, "analyze", return_value=fake):
            out = live.analyze_rows([{"record_type": "CANDIDATE"}], sha="abc", source_bytes=55)
        self.assertTrue(out["ok"])
        self.assertEqual(out["source_sha256"], "abc")
        self.assertEqual(out["source_bytes"], 55)
        self.assertFalse(out["production_logic_changed"])
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
