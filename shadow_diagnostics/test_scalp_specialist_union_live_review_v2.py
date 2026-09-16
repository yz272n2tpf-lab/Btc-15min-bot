#!/usr/bin/env python3
import unittest
from unittest.mock import patch

import scalp_specialist_union_live_review_v2 as r


class LiveReviewV2Tests(unittest.TestCase):
    def test_empty_rows_fail_closed(self):
        state = r.analyze_rows([], sha="abc", source_bytes=0)
        self.assertFalse(state["ok"])
        self.assertEqual(state["status"], "FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE")
        self.assertFalse(state["orders"])
        self.assertFalse(state["production_logic_changed"])

    def test_refresh_uses_read_only_v1_fetcher(self):
        rows = []
        with patch.object(r.live_v1, "fetch_rows", return_value=(rows, "sha1", 10)) as fetch:
            state = r.refresh_once()
        fetch.assert_called_once_with()
        self.assertEqual(state["source_sha256"], "sha1")
        self.assertFalse(state["orders"])

    def test_analysis_exposes_union_lag_and_zone_sections(self):
        rows = [
            {"record_type":"SNAPSHOT","contract":"A","seconds_left":"890","timestamp_utc":"2026-09-16T00:00:10Z"},
            {"record_type":"SNAPSHOT","contract":"A","seconds_left":"30","timestamp_utc":"2026-09-16T00:14:30Z"},
        ]
        with patch.object(r.q, "build_serial_opportunities", return_value=[]), \
             patch.object(r.union_v2, "model_frontier", return_value=([], None, None, [])), \
             patch.object(r.lag, "score_frontier", return_value=([], None, None)):
            state = r.analyze_rows(rows, sha="sha2", source_bytes=20)
        self.assertTrue(state["ok"])
        self.assertIn("specialist_union", state)
        self.assertIn("normalized_kalshi_lag", state)
        self.assertIn("contract_zone_map", state)
        self.assertIn("cumulative_coverage", state)
        self.assertFalse(state["automatic_promotion"])
        self.assertFalse(state["orders"])


if __name__ == "__main__":
    unittest.main()
