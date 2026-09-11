import unittest

from unified_scalp_heartbeat_pairing_guard_v1 import audit_lines


def candidate(ticker="T1", side="UP", entry=.20, left=180, lane="MOMENTUM_EXPANSION"):
    return (
        f"LEAD_V7 CANDIDATE | lane {lane} | {ticker} | {side} | zone Z "
        f"| ask {entry:.3f} | btc5 +1 | btc15 +1 | btc30 +1 | accel +1 | brti5 +1 "
        f"| brti15 +1 | ask5 +0 | ask15 +0 | left {left}s"
    )


def result(ticker="T1", side="UP", entry=.20, lane="MOMENTUM_EXPANSION"):
    return (
        f"LEAD_V7 RESULT | lane {lane} | {ticker} | {side} | zone Z | style EXPANSION "
        f"| entry {entry:.3f} | max_gain +0.150 | adverse -0.020 "
        f"| to+5c 20.0 | to+10c 60.0 | to+20c None | reprice+5c 20.0"
    )


class UnifiedHeartbeatPairingGuardTests(unittest.TestCase):
    def test_in_order_pairing_is_stable(self):
        report = audit_lines([candidate(entry=.20), result(entry=.20)])
        self.assertFalse(report["pairing_regression_detected"])
        self.assertEqual(report["robust_matched_results"], 1)
        self.assertEqual(report["destructive_fifo_matched_results"], 1)
        self.assertEqual(report["decision"]["heartbeat_pairing_auditor"], "KEEP")

    def test_out_of_order_completion_exposes_fifo_candidate_loss(self):
        report = audit_lines([
            candidate(entry=.20),
            candidate(entry=.30),
            result(entry=.30),
            result(entry=.20),
        ])
        self.assertEqual(report["robust_matched_results"], 2)
        self.assertEqual(report["destructive_fifo_matched_results"], 1)
        self.assertEqual(report["false_unmatched_results_from_destructive_fifo"], 1)
        self.assertTrue(report["pairing_regression_detected"])
        self.assertEqual(report["decision"]["heartbeat_pairing_auditor"], "TIGHTEN")
        self.assertEqual(report["decision"]["qualification_threshold_change"], "MORE_DATA")

    def test_repeated_same_price_candidates_pair_without_loss(self):
        report = audit_lines([
            candidate(entry=.20),
            candidate(entry=.20),
            result(entry=.20),
            result(entry=.20),
        ])
        self.assertEqual(report["robust_matched_results"], 2)
        self.assertEqual(report["destructive_fifo_matched_results"], 2)
        self.assertFalse(report["pairing_regression_detected"])

    def test_legacy_reversal_stays_audit_only(self):
        report = audit_lines([
            candidate(entry=.05, lane="ULTRA_CHEAP_REVERSAL"),
            result(entry=.05, lane="ULTRA_CHEAP_REVERSAL"),
        ])
        self.assertEqual(report["unified_results"], 0)
        self.assertEqual(report["legacy_reversal_research_only"], 1)
        self.assertEqual(report["decision"]["separate_ultra_cheap_graduation_path"], "REJECT")
        self.assertFalse(report["cheap_price_evidence_override"])

    def test_unknown_lane_fails_closed(self):
        report = audit_lines([result(lane="OTHER")])
        self.assertEqual(report["unknown_lane_records"], 1)
        self.assertEqual(report["production_promotion"], "NOT_PERFORMED")


if __name__ == "__main__":
    unittest.main()
