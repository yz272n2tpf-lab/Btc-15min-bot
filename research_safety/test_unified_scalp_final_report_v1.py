import unittest
from unittest.mock import patch

from unified_scalp_final_report_v1 import build_report


def result(lane, ticker, entry, gain, adverse, t10, style="EXPANSION"):
    return (
        f"LEAD_V7 RESULT | lane {lane} | {ticker} | UP | zone Z | style {style} "
        f"| entry {entry:.3f} | max_gain {gain:+.3f} | adverse {adverse:+.3f} "
        f"| to+5c 10.0 | to+10c {t10} | to+20c None | reprice+5c 10.0"
    )


class UnifiedFinalReportTests(unittest.TestCase):
    def test_valid_current_unified_report_passes(self):
        lines = [
            result("MOMENTUM_EXPANSION", "T1", .23, .20, -.01, "51.0"),
            result("ULTRA_CHEAP_REVERSAL", "T1", .05, .95, -.001, "68.0"),
        ]
        report = build_report(lines)
        self.assertEqual(report["preflight"], "PASS")
        self.assertEqual(report["current_architecture"], "ONE_UNIFIED_SCALP_EXPANSION_ENGINE")
        self.assertEqual(report["scorecard"]["unified_results"], 1)
        self.assertEqual(report["scorecard"]["legacy_reversal_research_only"], 1)
        self.assertEqual(report["decisions"]["separate_ultra_cheap_graduation_path"], "REJECT")
        self.assertEqual(report["decisions"]["adverse_trap_tightening"], "MORE_DATA")
        self.assertEqual(report["production_promotion"], "NOT_PERFORMED")

    def test_unknown_lane_fails_closed(self):
        report = build_report([
            result("UNKNOWN_EXPERIMENT", "T1", .20, .20, -.01, "20.0")
        ])
        self.assertEqual(report["preflight"], "FAIL")
        self.assertFalse(report["checks"]["score_no_unknown_lane"])
        self.assertFalse(report["checks"]["adverse_no_unknown_lane"])

    def test_empty_report_still_preserves_architecture(self):
        report = build_report([])
        self.assertEqual(report["preflight"], "PASS")
        self.assertEqual(report["decisions"]["unified_scalp_expansion_engine"], "KEEP")
        self.assertEqual(report["decisions"]["qualification_threshold_change"], "MORE_DATA")

    @patch("unified_scalp_final_report_v1.audit_lines")
    def test_count_disagreement_fails_closed(self, mock_audit):
        mock_audit.return_value = {
            "research_only": True,
            "signal_only": True,
            "production_promotion": "NOT_PERFORMED",
            "unknown_lane_results": 0,
            "legacy_reversal_research_only": 0,
            "unified_results": 99,
            "decision": {
                "unified_scalp_expansion_path": "KEEP",
                "separate_ultra_cheap_graduation_path": "REJECT",
                "adverse_trap_tightening": "MORE_DATA",
            },
        }
        report = build_report([
            result("MOMENTUM_EXPANSION", "T1", .23, .20, -.01, "51.0")
        ])
        self.assertEqual(report["preflight"], "FAIL")
        self.assertFalse(report["checks"]["unified_counts_agree"])


if __name__ == "__main__":
    unittest.main()
