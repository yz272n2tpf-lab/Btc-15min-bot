#!/usr/bin/env python3
import unittest

from unified_scalp_tightening_candidate_audit_v1 import evaluate_lines


def candidate(ticker, entry, *, btc5=20, btc15=20, btc30=20, accel=10, brti5=20, brti15=20, ask5=0, ask15=0, left=500):
    return (
        f"LEAD_V7 CANDIDATE | lane MOMENTUM_EXPANSION | {ticker} | DOWN | zone TEST | ask {entry:.3f} "
        f"| btc5 {btc5:+.2f} | btc15 {btc15:+.2f} | btc30 {btc30:+.2f} | accel {accel:+.2f} "
        f"| brti5 {brti5:+.2f} | brti15 {brti15:+.2f} | ask5 {ask5:+.3f} | ask15 {ask15:+.3f} | left {left}s"
    )


def result(ticker, entry, t10, gain=0.12, adverse=-0.02):
    t10_text = "None" if t10 is None else f"{t10:.1f}"
    style = "NO_EXPANSION" if t10 is None else ("BURST" if t10 <= 30 else "EXPANSION")
    return (
        f"LEAD_V7 RESULT | lane MOMENTUM_EXPANSION | {ticker} | DOWN | zone TEST | style {style} | entry {entry:.3f} "
        f"| max_gain {gain:+.3f} | adverse {adverse:+.3f} | to+5c {'None' if t10 is None else '10.0'} "
        f"| to+10c {t10_text} | to+20c None | reprice+5c {'None' if t10 is None else '10.0'}"
    )


class TighteningCandidateAuditTests(unittest.TestCase):
    def test_price_dependent_rule_rejected(self):
        report = evaluate_lines([], {"name": "cheap", "conditions": [{"feature": "entry", "op": "<", "value": 0.10}]})
        self.assertEqual(report["decision"]["candidate_tightening"], "REJECT")
        self.assertIn("PRICE_DEPENDENT_RULE_FORBIDDEN", report["proposal_errors"])
        self.assertFalse(report["cheap_price_override"])

    def test_lookahead_rule_rejected(self):
        report = evaluate_lines([], {"name": "bad", "conditions": [{"feature": "adverse", "op": "<", "value": -0.05}]})
        self.assertEqual(report["decision"]["candidate_tightening"], "REJECT")
        self.assertIn("LOOKAHEAD_RESULT_FEATURE_FORBIDDEN", report["proposal_errors"])

    def test_fast_winner_counterexample_rejects(self):
        lines = [
            candidate("A", .20, accel=5), result("A", .20, 18),
            candidate("B", .20, accel=4), result("B", .20, None),
            candidate("C", .20, accel=4), result("C", .20, None),
            candidate("D", .20, accel=4), result("D", .20, None),
        ]
        proposal = {"name": "weak_accel", "conditions": [{"feature": "accel", "op": "<", "value": 7}]}
        report = evaluate_lines(lines, proposal)
        self.assertEqual(report["decision"]["candidate_tightening"], "REJECT")
        self.assertEqual(report["would_block_fast_success_n"], 1)

    def test_success_counterexample_requires_more_data(self):
        lines = [
            candidate("A", .20, accel=5), result("A", .20, 60),
            candidate("B", .20, accel=4), result("B", .20, None),
            candidate("C", .20, accel=4), result("C", .20, None),
            candidate("D", .20, accel=4), result("D", .20, None),
        ]
        proposal = {"name": "weak_accel", "conditions": [{"feature": "accel", "op": "<", "value": 7}]}
        report = evaluate_lines(lines, proposal)
        self.assertEqual(report["decision"]["candidate_tightening"], "MORE_DATA")
        self.assertEqual(report["would_block_success_n"], 1)

    def test_three_independent_failure_contracts_can_emit_research_tighten(self):
        lines = [
            candidate("W", .20, accel=12), result("W", .20, 20),
            candidate("F1", .10, accel=4), result("F1", .10, None),
            candidate("F2", .20, accel=5), result("F2", .20, None),
            candidate("F3", .34, accel=6), result("F3", .34, None),
        ]
        proposal = {"name": "weak_accel", "conditions": [{"feature": "accel", "op": "<", "value": 7}]}
        report = evaluate_lines(lines, proposal)
        self.assertEqual(report["decision"]["candidate_tightening"], "TIGHTEN")
        self.assertEqual(report["would_block_failure_n"], 3)
        self.assertEqual(report["would_block_success_n"], 0)
        self.assertFalse(report["qualification_threshold_change_performed"])
        self.assertEqual(set(report["by_diagnostic_price_zone"]), {"7_15C", "15_30C", "30_45C"})

    def test_repeated_failure_same_contract_does_not_fake_independence(self):
        lines = [
            candidate("W", .20, accel=12), result("W", .20, 20),
            candidate("F", .10, accel=4), result("F", .10, None),
            candidate("F", .20, accel=5), result("F", .20, None),
            candidate("F", .34, accel=6), result("F", .34, None),
        ]
        proposal = {"name": "weak_accel", "conditions": [{"feature": "accel", "op": "<", "value": 7}]}
        report = evaluate_lines(lines, proposal)
        self.assertEqual(report["decision"]["candidate_tightening"], "MORE_DATA")
        self.assertEqual(report["would_block_failure_contracts"], ["F"])

    def test_legacy_reversal_is_excluded(self):
        lines = [
            "LEAD_V7 CANDIDATE | lane ULTRA_CHEAP_REVERSAL | L | DOWN | zone REV | ask 0.040 | btc5 +1 | btc15 +1 | btc30 +1 | accel +1 | brti5 +1 | brti15 +1 | ask5 +0 | ask15 +0 | left 300s",
            "LEAD_V7 RESULT | lane ULTRA_CHEAP_REVERSAL | L | DOWN | zone REV | style NO_EXPANSION | entry 0.040 | max_gain +0.000 | adverse -0.030 | to+5c None | to+10c None | to+20c None | reprice+5c None",
            candidate("W", .20, accel=12), result("W", .20, 20),
            candidate("F1", .20, accel=4), result("F1", .20, None),
        ]
        proposal = {"name": "weak_accel", "conditions": [{"feature": "accel", "op": "<", "value": 7}]}
        report = evaluate_lines(lines, proposal)
        self.assertEqual(report["legacy_reversal_candidates_research_only"], 1)
        self.assertEqual(report["legacy_reversal_results_research_only"], 1)
        self.assertEqual(report["matched_results"], 2)
        self.assertFalse(report["legacy_reversal_graduation_allowed"])

    def test_unknown_lane_fails_closed(self):
        lines = [
            "LEAD_V7 RESULT | lane MYSTERY | X | DOWN | zone TEST | style NO_EXPANSION | entry 0.200 | max_gain +0.000 | adverse -0.030 | to+5c None | to+10c None | to+20c None | reprice+5c None"
        ]
        proposal = {"name": "weak_accel", "conditions": [{"feature": "accel", "op": "<", "value": 7}]}
        report = evaluate_lines(lines, proposal)
        self.assertEqual(report["decision"]["candidate_tightening"], "REJECT")
        self.assertEqual(report["unknown_lane_records"], 1)


if __name__ == "__main__":
    unittest.main()
