#!/usr/bin/env python3
import inspect
import unittest

import BTC15_FINAL_V4_REVIEW_LIVE_V1 as live
import test_BTC15_FINAL_V4_FROZEN_REVIEW_REPORT_V1 as fixture


class FinalV4LiveReviewTests(unittest.TestCase):
    def test_waiting_snapshot_is_safe(self):
        z = live.build_snapshot(fixture.payload())
        self.assertTrue(z["ok"])
        self.assertFalse(z["manual_review_ready"])
        self.assertFalse(z["auto_promote_allowed"])
        self.assertFalse(z["threshold_retune_allowed"])
        self.assertFalse(z["orders"])

    def test_ready_snapshot_is_manual_review_only(self):
        z = live.build_snapshot(
            fixture.payload(eligible=30, locks=16, settled=14, correct=14, sample_ready=True)
        )
        self.assertTrue(z["manual_review_ready"])
        self.assertEqual(z["review"]["status"], "FINAL_V4_MANUAL_REVIEW_READY")
        self.assertFalse(z["auto_promote_allowed"])
        self.assertTrue(z["manual_execution_only"])

    def test_invalid_upstream_snapshot_fails_closed(self):
        p = fixture.payload()
        p["live"]["production_behavior_changed"] = True
        z = live.build_snapshot(p)
        self.assertFalse(z["ok"])
        self.assertEqual(z["review"]["status"], "INVALID_SNAPSHOT_FAIL_CLOSED")

    def test_wrapper_does_not_expose_numeric_flip_risk(self):
        z = live.build_snapshot(fixture.payload())
        self.assertFalse(z["numeric_flip_risk_validated"])
        self.assertNotIn("flip_risk_percent", str(z))

    def test_source_targets_only_authoritative_final_state(self):
        self.assertTrue(live.FINAL_STATE_URL.endswith("final-forward-scorecard-v1-production.up.railway.app/state"))
        self.assertEqual(live.review.EXPECTED_COLLECTOR_VERSION, "BTC15_FINAL_FORWARD_SCORECARD_V4")

    def test_network_client_is_get_only(self):
        src = inspect.getsource(live)
        self.assertIn("requests.get(", src)
        for forbidden in ("requests.post(", "requests.put(", "requests.patch(", "requests.delete("):
            self.assertNotIn(forbidden, src)

    def test_no_order_or_signal_mutation_path(self):
        src = inspect.getsource(live)
        for forbidden in (
            "place_order", "create_order", "submit_order", "qualify_final",
            "protected_final_thresholds_changed = True", "auto_promote_allowed = True",
        ):
            self.assertNotIn(forbidden, src)
        self.assertIn("READ ONLY", src)
        self.assertIn("NO ORDERS", src)

    def test_text_report_preserves_metric_separation(self):
        z = live.build_snapshot(fixture.payload())
        text = live.review.render_text(z["review"])
        self.assertIn("FINAL accuracy", text)
        self.assertIn("FINAL-only coverage", text)
        self.assertIn("Locked-side ask", text)
        self.assertIn("manual review only", text)


if __name__ == "__main__":
    unittest.main()
