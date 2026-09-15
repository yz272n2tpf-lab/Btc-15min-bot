#!/usr/bin/env python3
import unittest

import BTC15_SCALP_BLUEPRINT_REVIEW_GATE_V1 as g
import BTC15_SCALP_UNARMED_TERMINAL_HANDOFF_AUDIT_V1 as terminal_audit
from test_BTC15_SCALP_SERIAL_STATE_BRIDGE_SHADOW_V1 import SerialStateBridgeTests


class ReviewGateTests(unittest.TestCase):
    def forward(self):
        return {
            "status": "READY_FOR_REVIEW",
            "completed_serial_opportunities": 25,
            "max_opportunities_in_one_contract": 4,
            "meaningful_10c_rate": .76,
            "orders": False,
            "manual_execution_only": True,
            "review_gate": {"met": True},
            "blueprint": {
                "entry_price_filter_applied": False,
                "price_zone_trigger": False,
                "high_price_cutoff_selected": False,
                "orders": False,
            },
            "failed_primary": {"completed_failed_primary_n": 0},
            "timer_audit": {
                "samples_valid": 200,
                "samples_total": 220,
                "contract_match_rate": 1.0,
                "canonical_clock_rate": 1.0,
                "within_5s_rate": .95,
            },
            "entry_price_bands": {
                "70-80c": {"n": 5, "plus10_rate": .8, "plus20_rate": .4, "median_peak_gain": .16},
                "80c+": {"n": 2, "plus10_rate": .5, "plus20_rate": 0.0, "median_peak_gain": .10},
            },
        }

    def coverage(self):
        return {
            "orders": False,
            "post_exit_missed_qualified": 0,
            "failed_prearm_blocked_candidates": 0,
        }

    def protection(self):
        return {
            "orders": False,
            "protected_exit_records": 20,
            "first_crossing_ok_rate": 1.0,
        }

    def lifecycle(self):
        return {
            "orders": False,
            "manual_execution_only": True,
            "protected_thresholds_changed": False,
            "stop_loss_rule_selected": False,
            "ended_unarmed_is_actionable_exit": False,
            "entry_price_filter_applied": False,
            "lifecycle_reset_review_ready": True,
            "ended_unarmed_n": 2,
            "armed_no_validated_exit_n": 17,
            "armed_no_validated_exit_preserved_blocking": True,
            "armed_no_validated_exit_reclassified_as_ended_unarmed_n": 0,
            "baseline_completed_serial_opportunities": 25,
            "projected_completed_serial_opportunities": 27,
            "true_post_exit_missed_meaningful_10c": 0,
        }

    def failed_forward_and_coverage(self):
        f = self.forward(); f["failed_primary"] = {"completed_failed_primary_n": 2}
        c = self.coverage(); c["failed_prearm_blocked_candidates"] = 3
        return f, c

    def test_actual_forward_schema_is_understood(self):
        out = g.compose_review(
            self.forward(), self.coverage(), self.protection(),
            timer_visual_accepted=True,
        )
        self.assertEqual(out["completed_serial_opportunities"], 25)
        self.assertEqual(out["max_opportunities_in_one_contract"], 4)
        self.assertNotIn("FORWARD_SAMPLE_NOT_READY", out["blockers"])
        self.assertNotIn("MULTI_SCALP_RESET_NOT_OBSERVED", out["blockers"])
        self.assertFalse(out["auto_freeze_allowed"])

    def test_failed_prearm_without_lifecycle_is_hard_freeze_blocker(self):
        f, c = self.failed_forward_and_coverage()
        out = g.compose_review(f, c, self.protection(), timer_visual_accepted=True)
        self.assertIn("FAILED_PREARM_CLOSE_RESET_RULE_UNRESOLVED", out["blockers"])
        self.assertIn("LIFECYCLE_EVIDENCE_NOT_ATTACHED", out["failed_prearm_lifecycle_checks"])
        self.assertFalse(out["failed_prearm_lifecycle_resolved"])
        self.assertEqual(out["status"], "NOT_READY_TO_FREEZE")

    def test_valid_ended_unarmed_evidence_resolves_lifecycle_while_armed_winners_stay_protected(self):
        f, c = self.failed_forward_and_coverage()
        out = g.compose_review(
            f, c, self.protection(), self.lifecycle(),
            timer_visual_accepted=True,
        )
        self.assertNotIn("FAILED_PREARM_CLOSE_RESET_RULE_UNRESOLVED", out["blockers"])
        self.assertIn("FAILED_PREARM_LIFECYCLE_RESOLVED_BY_ENDED_UNARMED", out["review_items"])
        self.assertIn("ARMED_NO_EXIT_WINNERS_REMAIN_PROTECTED", out["review_items"])
        self.assertTrue(out["failed_prearm_lifecycle_resolved"])
        self.assertEqual(out["lifecycle_armed_no_validated_exit_n"], 17)
        self.assertTrue(out["lifecycle_armed_no_exit_preserved_blocking"])
        self.assertEqual(out["status"], "READY_FOR_MANUAL_FREEZE_REVIEW")
        self.assertFalse(out["stop_loss_rule_required"])
        self.assertFalse(out["auto_freeze_allowed"])

    def test_actionable_ended_unarmed_or_stop_loss_cannot_resolve_blocker(self):
        f, c = self.failed_forward_and_coverage()
        lifecycle = self.lifecycle()
        lifecycle["ended_unarmed_is_actionable_exit"] = True
        lifecycle["stop_loss_rule_selected"] = True
        out = g.compose_review(f, c, self.protection(), lifecycle, timer_visual_accepted=True)
        self.assertIn("FAILED_PREARM_CLOSE_RESET_RULE_UNRESOLVED", out["blockers"])
        self.assertIn("ENDED_UNARMED_MUST_NOT_BE_ACTIONABLE_EXIT", out["failed_prearm_lifecycle_checks"])
        self.assertIn("STOP_LOSS_RULE_MUST_REMAIN_UNSELECTED", out["failed_prearm_lifecycle_checks"])

    def test_armed_no_exit_must_remain_protected_blocking(self):
        f, c = self.failed_forward_and_coverage()
        lifecycle = self.lifecycle(); lifecycle["armed_no_validated_exit_preserved_blocking"] = False
        out = g.compose_review(f, c, self.protection(), lifecycle, timer_visual_accepted=True)
        self.assertIn("FAILED_PREARM_CLOSE_RESET_RULE_UNRESOLVED", out["blockers"])
        self.assertIn("ARMED_NO_EXIT_MUST_REMAIN_PROTECTED_BLOCKING", out["failed_prearm_lifecycle_checks"])

    def test_armed_no_exit_cannot_be_reclassified_as_ended_unarmed(self):
        f, c = self.failed_forward_and_coverage()
        lifecycle = self.lifecycle(); lifecycle["armed_no_validated_exit_reclassified_as_ended_unarmed_n"] = 1
        out = g.compose_review(f, c, self.protection(), lifecycle, timer_visual_accepted=True)
        self.assertIn("FAILED_PREARM_CLOSE_RESET_RULE_UNRESOLVED", out["blockers"])
        self.assertIn("ARMED_NO_EXIT_WAS_RECLASSIFIED_AS_ENDED_UNARMED", out["failed_prearm_lifecycle_checks"])

    def test_lifecycle_true_post_exit_miss_keeps_prearm_blocker(self):
        f, c = self.failed_forward_and_coverage()
        lifecycle = self.lifecycle(); lifecycle["true_post_exit_missed_meaningful_10c"] = 1
        out = g.compose_review(f, c, self.protection(), lifecycle, timer_visual_accepted=True)
        self.assertIn("FAILED_PREARM_CLOSE_RESET_RULE_UNRESOLVED", out["blockers"])
        self.assertIn("LIFECYCLE_TRUE_POST_EXIT_MISS_PRESENT", out["failed_prearm_lifecycle_checks"])

    def test_true_post_exit_miss_is_hard_blocker(self):
        c = self.coverage(); c["post_exit_missed_qualified"] = 1
        out = g.compose_review(self.forward(), c, self.protection(), timer_visual_accepted=True)
        self.assertIn("POST_EXIT_QUALIFIED_SCALP_MISSED", out["blockers"])

    def test_protection_must_hit_first_observed_four_cent_crossing(self):
        p = self.protection(); p["first_crossing_ok_rate"] = .95
        out = g.compose_review(self.forward(), self.coverage(), p, timer_visual_accepted=True)
        self.assertIn("PROTECTION_FIRST_4C_CROSSING_MISMATCH", out["blockers"])

    def test_visual_timer_acceptance_remains_required(self):
        out = g.compose_review(self.forward(), self.coverage(), self.protection())
        self.assertIn("TIMER_VISUAL_ACCEPTANCE_PENDING", out["blockers"])

    def test_high_price_sample_never_auto_becomes_filter(self):
        f = self.forward(); f["entry_price_bands"]["80c+"]["n"] = 50
        out = g.compose_review(f, self.coverage(), self.protection(), timer_visual_accepted=True)
        self.assertTrue(out["high_price_audit"]["80c+"]["enough_sample_to_even_discuss_cutoff"])
        self.assertTrue(out["high_price_audit"]["80c+"]["price_is_telemetry_only"])
        self.assertFalse(out["auto_freeze_allowed"])

    def test_unapproved_price_suppression_blocks_review(self):
        f = self.forward(); f["blueprint"]["entry_price_filter_applied"] = True
        out = g.compose_review(f, self.coverage(), self.protection(), timer_visual_accepted=True)
        self.assertIn("UNAPPROVED_PRICE_SUPPRESSION_PRESENT", out["blockers"])

    def test_ten_cent_rate_is_reported_without_invented_threshold(self):
        out = g.compose_review(self.forward(), self.coverage(), self.protection(), timer_visual_accepted=True)
        self.assertAlmostEqual(out["meaningful_10c_rate"], .76)
        self.assertIn("TEN_CENT_TARGET_NOT_HIT_BY_EVERY_SELECTED_SCALP", out["review_items"])
        self.assertIn("TEN_CENT_ACCEPTANCE_PERCENTAGE_NOT_YET_FROZEN", out["review_items"])


class UnarmedTerminalLifecycleTests(unittest.TestCase):
    CONTRACT = "KXBTC15M-26SEP150000-00"

    def candidate(self, ts, cid, ask="0.31", side="UP"):
        return {
            "record_type": "CANDIDATE", "timestamp_utc": ts,
            "candidate_id": cid, "contract": self.CONTRACT,
            "entry_ask": ask, "side": side, "seconds_left": "600", "btc30": "20",
        }

    def path(self, ts, cid, gain, elapsed):
        return {
            "record_type": "PATH", "timestamp_utc": ts,
            "candidate_id": cid, "contract": self.CONTRACT,
            "exec_gain": str(gain), "elapsed_sec": str(elapsed),
        }

    def result(self, ts, cid):
        return {
            "record_type": "RESULT", "timestamp_utc": ts,
            "candidate_id": cid, "contract": self.CONTRACT,
        }

    def test_completed_unarmed_is_nonactionable_terminal_and_can_handoff(self):
        rows = [
            self.candidate("2026-09-15T00:00:00Z", "a"),
            self.path("2026-09-15T00:00:20Z", "a", 0.02, 20),
            self.result("2026-09-15T00:01:00Z", "a"),
            self.candidate("2026-09-15T00:01:10Z", "b", ask="0.86", side="DOWN"),
            self.path("2026-09-15T00:01:20Z", "b", 0.11, 10),
            self.path("2026-09-15T00:01:30Z", "b", 0.06, 20),
            self.result("2026-09-15T00:02:00Z", "b"),
        ]
        out = terminal_audit.audit(rows)
        self.assertEqual(out["ended_unarmed_n"], 1)
        self.assertEqual(out["post_unarmed_later_qualified_n"], 1)
        self.assertEqual(out["post_unarmed_later_plus10_n"], 1)
        self.assertAlmostEqual(out["recovered_handoffs"][0]["to_entry_ask"], .86)
        self.assertFalse(out["ended_unarmed_is_actionable_exit"])
        self.assertTrue(out["armed_no_validated_exit_preserved_blocking"])
        self.assertEqual(out["armed_no_validated_exit_reclassified_as_ended_unarmed_n"], 0)
        self.assertFalse(out["entry_price_filter_applied"])
        self.assertFalse(out["orders"])

    def test_incomplete_candidate_does_not_invent_terminal(self):
        rows = [
            self.candidate("2026-09-15T00:00:00Z", "a"),
            self.path("2026-09-15T00:00:20Z", "a", -0.12, 20),
            self.candidate("2026-09-15T00:00:30Z", "b"),
            self.path("2026-09-15T00:00:40Z", "b", 0.20, 10),
            self.result("2026-09-15T00:01:00Z", "b"),
        ]
        out = terminal_audit.audit(rows)
        self.assertEqual(out["ended_unarmed_n"], 0)
        self.assertEqual(out["projected_completed_serial_opportunities"], 0)

    def test_protected_exit_path_is_not_reclassified(self):
        rows = [
            self.candidate("2026-09-15T00:00:00Z", "a"),
            self.path("2026-09-15T00:00:10Z", "a", 0.06, 10),
            self.path("2026-09-15T00:00:20Z", "a", 0.01, 20),
            self.result("2026-09-15T00:00:40Z", "a"),
        ]
        out = terminal_audit.audit(rows)
        self.assertEqual(out["projected_ladder"][0]["terminal_kind"], "PROTECTED_EXIT")
        self.assertEqual(out["ended_unarmed_n"], 0)
        self.assertFalse(out["protected_thresholds_changed"])

    def test_armed_without_validated_exit_stays_protected_and_blocking(self):
        rows = [
            self.candidate("2026-09-15T00:00:00Z", "a"),
            self.path("2026-09-15T00:00:10Z", "a", 0.06, 10),
            self.path("2026-09-15T00:00:20Z", "a", 0.04, 20),
            self.result("2026-09-15T00:00:40Z", "a"),
            self.candidate("2026-09-15T00:00:50Z", "b"),
            self.path("2026-09-15T00:01:00Z", "b", 0.20, 10),
            self.result("2026-09-15T00:01:10Z", "b"),
        ]
        out = terminal_audit.audit(rows)
        self.assertEqual(out["armed_no_validated_exit_n"], 1)
        self.assertEqual(out["projected_ladder"][0]["terminal_kind"], "ARMED_NO_VALIDATED_EXIT")
        self.assertEqual(len(out["projected_ladder"]), 1)
        self.assertEqual(out["ended_unarmed_n"], 0)
        self.assertTrue(out["armed_no_validated_exit_preserved_blocking"])
        self.assertEqual(out["armed_no_validated_exit_reclassified_as_ended_unarmed_n"], 0)


if __name__ == "__main__":
    unittest.main()
