import unittest

from unified_scalp_adverse_path_audit_v1 import audit_lines


def result(lane, ticker, entry, gain, adverse, t10, style="EXPANSION", side="UP"):
    return (
        f"LEAD_V7 RESULT | lane {lane} | {ticker} | {side} | zone Z | style {style} "
        f"| entry {entry:.3f} | max_gain {gain:+.3f} | adverse {adverse:+.3f} "
        f"| to+5c 10.0 | to+10c {t10} | to+20c None | reprice+5c 10.0"
    )


class AdversePathAuditTests(unittest.TestCase):
    def test_fast_success_with_large_adverse_is_not_confirmed_trap(self):
        report = audit_lines([
            result("MOMENTUM_EXPANSION", "T1", .43, .13, -.20, "7.0", "BURST")
        ])
        self.assertEqual(report["classifications"]["SUCCESS_ADVERSE_ORDER_UNKNOWN"], 1)
        self.assertEqual(report["decision"]["adverse_trap_tightening"], "MORE_DATA")
        self.assertEqual(report["decision"]["confirmed_failed_expansion_observations"], 0)

    def test_failed_expansion_adverse_is_scored(self):
        report = audit_lines([
            result("MOMENTUM_EXPANSION", "T1", .32, .06, -.317, "None", "NO_EXPANSION")
        ])
        zone = report["zones"]["30_45C"]
        self.assertEqual(zone["failed_expansion"], 1)
        self.assertAlmostEqual(zone["failed_worst_adverse"], -.317)
        self.assertAlmostEqual(zone["failed_avg_adverse_to_entry"], .317 / .32)

    def test_success_at_3_7c_uses_same_unified_path(self):
        report = audit_lines([
            result("MOMENTUM_EXPANSION", "T1", .05, .20, -.01, "20.0", "BURST")
        ])
        self.assertEqual(report["unified_results"], 1)
        self.assertEqual(report["zones"]["3_7C"]["hit10_in_window"], 1)
        self.assertEqual(report["decision"]["unified_scalp_expansion_path"], "KEEP")

    def test_legacy_reversal_is_audit_only(self):
        report = audit_lines([
            result("ULTRA_CHEAP_REVERSAL", "T1", .05, .95, -.001, "68.0")
        ])
        self.assertEqual(report["unified_results"], 0)
        self.assertEqual(report["legacy_reversal_research_only"], 1)
        self.assertEqual(report["decision"]["separate_ultra_cheap_graduation_path"], "REJECT")

    def test_late_hit_outside_window_counts_as_failed_expansion(self):
        report = audit_lines([
            result("MOMENTUM_EXPANSION", "T1", .21, .13, -.10, "181.0")
        ])
        self.assertEqual(report["classifications"]["FAILED_EXPANSION"], 1)

    def test_unknown_lane_fails_closed(self):
        report = audit_lines([
            result("SOMETHING_NEW", "T1", .20, .15, -.02, "30.0")
        ])
        self.assertEqual(report["unknown_lane_results"], 1)
        self.assertEqual(report["unified_results"], 0)

    def test_empty_input_keeps_more_data(self):
        report = audit_lines([])
        self.assertEqual(report["parsed_results"], 0)
        self.assertEqual(report["decision"]["adverse_trap_tightening"], "MORE_DATA")


if __name__ == "__main__":
    unittest.main()
