import unittest
from unittest.mock import patch

import scalp_market_regime_live_review_v1 as live


class MarketRegimeLiveReviewV1Tests(unittest.TestCase):
    def test_compact_remains_descriptive_and_unselected(self):
        fake = {
            "status": "READY",
            "tag_definitions": {"TREND_ALIGNED": {}},
            "validation": {"overall": {"signals": 10}, "primary_regimes": {}, "by_opportunity_index": {}},
            "holdout": {"overall": {"signals": 8}, "primary_regimes": {}, "by_opportunity_index": {}},
            "validation_to_holdout_shift": {},
        }
        out = live.compact(fake)
        self.assertTrue(out["descriptive_only"])
        self.assertTrue(out["no_threshold_selection"])
        self.assertTrue(out["no_signal_suppression_or_rescue"])
        self.assertFalse(out["automatic_promotion"])
        self.assertFalse(out["orders"])

    def test_analyze_rows_preserves_source_identity(self):
        fake = {
            "status": "READY",
            "tag_definitions": {},
            "validation": {},
            "holdout": {},
            "validation_to_holdout_shift": {},
        }
        with patch.object(live.regime, "analyze", return_value=fake):
            out = live.analyze_rows([{"record_type": "CANDIDATE"}], sha="abc", source_bytes=99)
        self.assertTrue(out["ok"])
        self.assertEqual(out["source_sha256"], "abc")
        self.assertEqual(out["source_bytes"], 99)
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
