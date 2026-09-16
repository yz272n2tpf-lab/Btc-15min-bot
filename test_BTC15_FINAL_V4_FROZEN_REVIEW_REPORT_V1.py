#!/usr/bin/env python3
import copy
import unittest

import BTC15_FINAL_V4_FROZEN_REVIEW_REPORT_V1 as r


def payload(*, eligible=24, locks=14, settled=14, correct=14, sample_ready=False):
    coverage = None if eligible == 0 else locks / eligible
    accuracy = None if settled == 0 else correct / settled
    le50 = 0
    le50_rate = None if locks == 0 else 0.0
    return {
        "ok": True,
        "version": "BTC15_FINAL_FORWARD_SCORECARD_V4",
        "orders": False,
        "manual_execution_only": True,
        "live": {
            "version": "BTC15_FINAL_FORWARD_SCORECARD_V4",
            "status": "LIVE_SMOKE_SAMPLE_READY" if sample_ready else "COLLECTING_LIVE_FORWARD",
            "live_cutoff_utc": "2026-09-15T20:00:00Z",
            "coverage_universe_semantics": "FIRST_SEEN_BEFORE_FINAL_ELIGIBILITY_WINDOW",
            "final_eligibility_open_seconds_left": 480.0,
            "eligibility_complete_contracts": eligible,
            "coverage_excluded_late_n": 1,
            "lock_calls": locks,
            "settled_lock_calls": settled,
            "settled_correct_n": correct,
            "qualified_accuracy": accuracy,
            "final_only_coverage": coverage,
            "avg_minutes_left": 4.83,
            "median_minutes_left": 4.88,
            "avg_preferred_ask": .900,
            "median_preferred_ask": .924,
            "ask_le_50c_n": le50,
            "ask_le_50c_rate": le50_rate,
            "settled_ask_le_50c_n": 0,
            "settled_ask_le_50c_accuracy": None,
            "calls_ge_5m_n": 7,
            "sample_ready": sample_ready,
            "full_contract_from_second_zero_required": False,
            "full_contract_from_second_zero_claimed": False,
            "protected_final_thresholds_changed": False,
            "price_filter_applied": False,
            "auto_promote_allowed": False,
            "production_behavior_changed": False,
            "numeric_flip_risk_validated": False,
            "orders": False,
            "manual_execution_only": True,
        },
    }


class FinalV4ReviewTests(unittest.TestCase):
    def test_current_like_sample_waits_only_on_gate(self):
        z = r.build_report(payload())
        self.assertEqual(z["status"], "WAITING_FOR_FROZEN_GATE")
        self.assertTrue(z["integrity"]["pass"])
        self.assertEqual(z["frozen_gate"]["remaining_eligible"], 6)
        self.assertEqual(z["frozen_gate"]["remaining_settled"], 0)
        self.assertFalse(z["frozen_gate"]["manual_review_ready"])

    def test_count_gate_without_collector_ready_fails_closed(self):
        z = r.build_report(payload(eligible=30, locks=16, settled=14, correct=14, sample_ready=False))
        self.assertTrue(z["frozen_gate"]["counts_ready"])
        self.assertFalse(z["frozen_gate"]["manual_review_ready"])
        self.assertEqual(z["status"], "WAITING_FOR_FROZEN_GATE")

    def test_ready_gate_opens_manual_review_only(self):
        z = r.build_report(payload(eligible=30, locks=16, settled=14, correct=14, sample_ready=True))
        self.assertEqual(z["status"], "FINAL_V4_MANUAL_REVIEW_READY")
        self.assertTrue(z["frozen_gate"]["manual_review_ready"])
        self.assertFalse(z["decision_controls"]["auto_promote_allowed"])
        self.assertFalse(z["decision_controls"]["threshold_retune_allowed_from_confirmation_sample"])

    def test_wrong_collector_version_invalid(self):
        p = payload()
        p["version"] = "BTC15_FINAL_FORWARD_SCORECARD_V3"
        p["live"]["version"] = "BTC15_FINAL_FORWARD_SCORECARD_V3"
        z = r.build_report(p)
        self.assertEqual(z["status"], "INVALID_SNAPSHOT_FAIL_CLOSED")
        self.assertIn("collector_version:BTC15_FINAL_FORWARD_SCORECARD_V3", z["integrity"]["errors"])

    def test_wrong_denominator_semantics_invalid(self):
        p = payload()
        p["live"]["coverage_universe_semantics"] = "SECOND_ZERO_ONLY"
        z = r.build_report(p)
        self.assertIn("coverage_semantics", z["integrity"]["errors"])

    def test_threshold_or_production_change_invalid(self):
        p = payload()
        p["live"]["protected_final_thresholds_changed"] = True
        z = r.build_report(p)
        self.assertIn("protected_thresholds_changed", z["integrity"]["errors"])
        p2 = payload()
        p2["live"]["production_behavior_changed"] = True
        z2 = r.build_report(p2)
        self.assertIn("production_behavior_changed", z2["integrity"]["errors"])

    def test_orders_true_invalid(self):
        p = payload()
        p["orders"] = True
        z = r.build_report(p)
        self.assertIn("orders_not_false", z["integrity"]["errors"])

    def test_accuracy_math_mismatch_invalid(self):
        p = payload(settled=14, correct=13)
        p["live"]["qualified_accuracy"] = 1.0
        z = r.build_report(p)
        self.assertIn("accuracy_math", z["integrity"]["errors"])

    def test_coverage_math_mismatch_invalid(self):
        p = payload(eligible=24, locks=14)
        p["live"]["final_only_coverage"] = .99
        z = r.build_report(p)
        self.assertIn("coverage_math", z["integrity"]["errors"])

    def test_zero_cheap_settled_accuracy_must_be_null(self):
        p = payload()
        p["live"]["settled_ask_le_50c_accuracy"] = 1.0
        z = r.build_report(p)
        self.assertIn("le50_accuracy_should_be_null", z["integrity"]["errors"])

    def test_project_accuracy_markers_are_descriptive(self):
        p = payload(eligible=30, locks=20, settled=20, correct=19, sample_ready=True)
        z = r.build_report(p)
        self.assertTrue(z["direction"]["project_93pct_floor_met"])
        self.assertTrue(z["direction"]["project_95pct_stretch_met"])
        self.assertFalse(z["decision_controls"]["auto_promote_allowed"])

        p2 = payload(eligible=30, locks=20, settled=20, correct=18, sample_ready=True)
        z2 = r.build_report(p2)
        self.assertFalse(z2["direction"]["project_93pct_floor_met"])
        self.assertFalse(z2["direction"]["project_95pct_stretch_met"])

    def test_render_keeps_metrics_separate(self):
        z = r.build_report(payload())
        text = r.render_text(z)
        self.assertIn("FINAL accuracy", text)
        self.assertIn("FINAL-only coverage", text)
        self.assertIn("Locked-side ask", text)
        self.assertIn("no auto-promotion", text)
        self.assertNotIn("union accuracy", text.lower())


if __name__ == "__main__":
    unittest.main()
