import unittest
from unittest.mock import patch

import scalp_economics_exit_live_review_v1 as live


class ScalpEconomicsLiveReviewTests(unittest.TestCase):
    def test_compact_is_read_only_and_historical_only(self):
        result = {
            "status": "READY",
            "fee_schedule": {"effective": "2026-07-07"},
            "overall": {"signals": 10},
            "by_opportunity_index": {"1": {"signals": 5}},
            "movement_vs_realized_warning": "+10 touch is not treated as realized +10",
        }
        out = live.compact(result)
        self.assertFalse(out["orders"])
        self.assertFalse(out["automatic_promotion"])
        self.assertTrue(out["historical_diagnostic_only"])
        self.assertFalse(out["production_logic_changed"])
        self.assertEqual(out["overall"]["signals"], 10)

    def test_analyze_rows_preserves_source_identity(self):
        fake = {
            "status": "READY",
            "fee_schedule": {},
            "overall": {"signals": 1},
            "by_opportunity_index": {},
            "movement_vs_realized_warning": "warning",
        }
        with patch.object(live.econ, "analyze", return_value=fake):
            out = live.analyze_rows([{"record_type": "CANDIDATE"}], sha="abc", source_bytes=123)
        self.assertTrue(out["ok"])
        self.assertEqual(out["source_sha256"], "abc")
        self.assertEqual(out["source_bytes"], 123)
        self.assertEqual(out["source_rows"], 1)
        self.assertFalse(out["orders"])


if __name__ == "__main__":
    unittest.main()
