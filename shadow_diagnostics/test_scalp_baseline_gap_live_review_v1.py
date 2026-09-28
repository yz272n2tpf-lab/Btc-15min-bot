#!/usr/bin/env python3
import unittest
from unittest.mock import patch

import scalp_baseline_gap_live_review_v1 as v


class BaselineGapLiveReviewTests(unittest.TestCase):
    def test_ready_audit_preserves_source_identity_and_safety(self):
        fake = {
            "summary": {
                "status": "READY",
                "full_observed_contracts": 271,
                "baseline_covered_contracts": 241,
                "uncovered_contracts": 30,
                "contracts_needed_to_reach_90pct": 3,
                "automatic_promotion": False,
            },
            "ledger": [{"contract": "X", "reason": "NO_CANDIDATE_ROWS"}],
        }
        with patch.object(v.gap, "audit", return_value=fake):
            out = v.analyze_rows([], sha="abc123", source_bytes=456)
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "BASELINE_GAP_AUDIT_READY")
        self.assertEqual(out["source_sha256"], "abc123")
        self.assertEqual(out["source_bytes"], 456)
        self.assertEqual(out["summary"]["contracts_needed_to_reach_90pct"], 3)
        self.assertFalse(out["orders"])
        self.assertFalse(out["automatic_promotion"])
        self.assertTrue(out["shadow_only"])
        self.assertFalse(out["production_logic_changed"])

    def test_failed_audit_stays_fail_closed(self):
        fake = {
            "version": "GAP",
            "status": "FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE",
            "orders": False,
            "automatic_promotion": False,
        }
        with patch.object(v.gap, "audit", return_value=fake):
            out = v.analyze_rows([], sha="abc123", source_bytes=456)
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], "FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE")
        self.assertEqual(out["source_sha256"], "abc123")
        self.assertFalse(out["orders"])
        self.assertTrue(out["shadow_only"])

    def test_refresh_reuses_unchanged_source_without_reauditing(self):
        old = dict(v.STATE)
        try:
            v.STATE.clear()
            v.STATE.update({
                "ok": True,
                "status": "BASELINE_GAP_AUDIT_READY",
                "source_sha256": "same",
                "orders": False,
            })
            with patch.object(v.live_v1, "fetch_rows", return_value=([], "same", 10)), \
                 patch.object(v, "analyze_rows") as analyze:
                out = v.refresh_once()
            analyze.assert_not_called()
            self.assertEqual(out["source_sha256"], "same")
            self.assertIn("last_poll_utc", out)
        finally:
            v.STATE.clear()
            v.STATE.update(old)


if __name__ == "__main__":
    unittest.main()
