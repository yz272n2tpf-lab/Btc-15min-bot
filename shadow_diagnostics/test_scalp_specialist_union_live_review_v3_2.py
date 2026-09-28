#!/usr/bin/env python3
import unittest
from unittest.mock import patch

import scalp_specialist_union_live_review_v3_2 as v


class LiveReviewV32Tests(unittest.TestCase):
    def candidate(self):
        return {
            "record_type":"CANDIDATE","contract":"A","candidate_id":"x","side":"UP","timestamp_utc":"2026-09-16T00:01:00Z",
            "entry_ask":"0.35","seconds_left":"600","confirm_count":"2","structure_ok":"1",
            "btc_against_side":"0","brti_against_side":"0","dual_reversal_evidence":"0","brti_status":"PRIMARY_OK",
            "entry_spread":"0.02","max_possible_upside_c":"65",
            "btc5":"5","btc15":"12","btc30":"25","brti5":"4","brti15":"10",
            "ask5":"0.01","ask15":"0.02","accel":"3","recent_btc_range60":"40",
            "btc5_norm":"0.2","btc15_norm":"0.4","brti_latency_ms":"250",
        }

    def test_ready_schema_adapts_before_v3_analysis(self):
        rows = [self.candidate()]
        captured = {}
        def fake(adapted, sha="", source_bytes=0):
            captured["row"] = adapted[0]
            return {"ok": True, "status": "TEST_READY", "orders": False}
        with patch.object(v.v3, "analyze_rows", side_effect=fake):
            out = v.analyze_rows(rows, sha="abc", source_bytes=123)
        self.assertEqual(out["status"], "TEST_READY")
        self.assertEqual(out["schema_adaptation"], "PASS_EXPLICIT_ALIASES_AND_UNITS_ONLY")
        self.assertEqual(captured["row"]["spread"], 0.02)
        self.assertEqual(captured["row"]["brti_latency_sec"], 0.25)
        self.assertEqual(captured["row"]["max_possible_upside"], 0.65)
        self.assertTrue(out["model_fit_attempted"])
        self.assertFalse(out["automatic_promotion"])

    def test_missing_alias_dependency_fails_before_v3(self):
        row = self.candidate()
        row.pop("brti15")
        with patch.object(v.v3, "analyze_rows") as model:
            out = v.analyze_rows([row], sha="abc", source_bytes=123)
        model.assert_not_called()
        self.assertEqual(out["status"], "SCHEMA_ADAPTATION_REQUIRED")
        self.assertFalse(out["model_fit_attempted"])
        self.assertIn("brti_move15_side", out["schema_adapter"]["missing_source_dependencies"])


if __name__ == "__main__":
    unittest.main()
