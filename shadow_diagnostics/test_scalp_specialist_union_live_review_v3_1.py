#!/usr/bin/env python3
import unittest

import scalp_specialist_union_live_review_v3_1 as v


class LiveReviewV31Tests(unittest.TestCase):
    def test_missing_designed_features_fail_closed_before_model_fit(self):
        rows = [
            {"record_type":"CANDIDATE","contract":"A","seconds_left":"880","timestamp_utc":"2026-09-16T00:00:10Z","side":"UP","btc30":"20"},
            {"record_type":"PATH","contract":"A","seconds_left":"30","timestamp_utc":"2026-09-16T00:14:30Z","candidate_id":"x","exec_gain":"0.1"},
        ]
        out = v.analyze_rows(rows, sha="abc", source_bytes=123)
        self.assertEqual(out["status"], "SCHEMA_ADAPTATION_REQUIRED")
        self.assertFalse(out["model_fit_attempted"])
        self.assertFalse(out["orders"])
        self.assertIn("spread", out["designed_features_missing"])

    def test_schema_state_keeps_source_identity(self):
        rows = [{"record_type":"CANDIDATE","contract":"A","seconds_left":"880","timestamp_utc":"2026-09-16T00:00:10Z"}]
        out = v.analyze_rows(rows, sha="sha123", source_bytes=456)
        self.assertEqual(out["source_sha256"], "sha123")
        self.assertEqual(out["source_bytes"], 456)
        self.assertEqual(out["source_rows"], 1)
        self.assertFalse(out["automatic_promotion"])


if __name__ == "__main__":
    unittest.main()
