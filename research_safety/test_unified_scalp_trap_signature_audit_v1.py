import unittest

from unified_scalp_trap_signature_audit_v1 import audit_lines, price_zone


def candidate(lane, ticker, side, entry, *, btc5=20, btc15=20, btc30=20, accel=10,
              brti5=20, brti15=20, ask5=0, ask15=0, left=500):
    return (
        f"LEAD_V7 CANDIDATE | lane {lane} | {ticker} | {side} | zone Z | ask {entry:.3f} "
        f"| btc5 {btc5:+.2f} | btc15 {btc15:+.2f} | btc30 {btc30:+.2f} | accel {accel:+.2f} "
        f"| brti5 {brti5:+.2f} | brti15 {brti15:+.2f} | ask5 {ask5:+.3f} | ask15 {ask15:+.3f} | left {left}s"
    )


def result(lane, ticker, side, entry, *, gain=.20, adverse=-.01, t10="20.0", style="EXPANSION"):
    return (
        f"LEAD_V7 RESULT | lane {lane} | {ticker} | {side} | zone Z | style {style} | entry {entry:.3f} "
        f"| max_gain {gain:+.3f} | adverse {adverse:+.3f} | to+5c 10.0 | to+10c {t10} "
        f"| to+20c None | reprice+5c 10.0"
    )


class TrapSignatureAuditTests(unittest.TestCase):
    def test_price_is_diagnostic_not_separate_standard(self):
        lines = [
            candidate("MOMENTUM_EXPANSION", "T1", "UP", .04),
            result("MOMENTUM_EXPANSION", "T1", "UP", .04, t10="30.0"),
            candidate("MOMENTUM_EXPANSION", "T2", "UP", .40),
            result("MOMENTUM_EXPANSION", "T2", "UP", .40, t10="30.0"),
        ]
        report = audit_lines(lines)
        self.assertEqual(report["matched_results"], 2)
        self.assertEqual(report["zones"]["3_7C"]["hit10_rate"], 1.0)
        self.assertEqual(report["zones"]["30_45C"]["hit10_rate"], 1.0)
        self.assertTrue(report["price_zone_is_diagnostic_only"])
        self.assertFalse(report["cheap_price_override"])
        self.assertEqual(report["decision"]["qualification_threshold_change"], "MORE_DATA")

    def test_legacy_reversal_is_excluded_from_graduation_evidence(self):
        lines = [
            candidate("ULTRA_CHEAP_REVERSAL", "T1", "UP", .05),
            result("ULTRA_CHEAP_REVERSAL", "T1", "UP", .05, t10="15.0"),
        ]
        report = audit_lines(lines)
        self.assertEqual(report["matched_results"], 0)
        self.assertEqual(report["legacy_reversal_candidates_research_only"], 1)
        self.assertEqual(report["legacy_reversal_results_research_only"], 1)
        self.assertEqual(report["decision"]["separate_ultra_cheap_graduation_path"], "REJECT")

    def test_out_of_order_completion_does_not_discard_earlier_different_entry(self):
        lines = [
            candidate("MOMENTUM_EXPANSION", "T1", "UP", .17),
            candidate("MOMENTUM_EXPANSION", "T1", "UP", .29),
            result("MOMENTUM_EXPANSION", "T1", "UP", .29, t10="14.0"),
            result("MOMENTUM_EXPANSION", "T1", "UP", .17, t10="None", gain=.02, adverse=-.10, style="NO_EXPANSION"),
        ]
        report = audit_lines(lines)
        self.assertEqual(report["matched_results"], 2)
        self.assertEqual(report["unmatched_results"], 0)
        self.assertEqual([row["candidate"]["entry"] for row in report["matched"]], [.29, .17])

    def test_duplicate_same_entry_matches_fifo(self):
        lines = [
            candidate("MOMENTUM_EXPANSION", "T1", "UP", .21, left=500),
            candidate("MOMENTUM_EXPANSION", "T1", "UP", .21, left=400),
            result("MOMENTUM_EXPANSION", "T1", "UP", .21, t10="20.0"),
            result("MOMENTUM_EXPANSION", "T1", "UP", .21, t10="None", style="NO_EXPANSION"),
        ]
        report = audit_lines(lines)
        self.assertEqual([row["candidate"]["left_seconds"] for row in report["matched"]], [500.0, 400.0])

    def test_negative_ask15_is_not_treated_as_a_safe_separator(self):
        lines = [
            candidate("MOMENTUM_EXPANSION", "S", "UP", .28, ask15=-.06),
            result("MOMENTUM_EXPANSION", "S", "UP", .28, t10="17.0"),
            candidate("MOMENTUM_EXPANSION", "F", "DOWN", .17, ask15=-.04),
            result("MOMENTUM_EXPANSION", "F", "DOWN", .17, t10="None", style="NO_EXPANSION"),
        ]
        report = audit_lines(lines)
        diag = report["simple_filter_counterexamples"]["ask15_negative"]
        self.assertEqual(diag["success"], 1)
        self.assertEqual(diag["failure"], 1)
        self.assertEqual(diag["assessment"], "NON_SEPARATING_COUNTEREXAMPLES_PRESENT")
        self.assertEqual(report["decision"]["adverse_trap_tightening"], "MORE_DATA")

    def test_unknown_lane_fails_closed_in_report(self):
        lines = [candidate("UNKNOWN", "T1", "UP", .20)]
        report = audit_lines(lines)
        self.assertEqual(report["unknown_lane_records"], 1)

    def test_entry_match_tolerance(self):
        lines = [
            candidate("MOMENTUM_EXPANSION", "T1", "UP", .2000),
            result("MOMENTUM_EXPANSION", "T1", "UP", .2010, t10="20.0"),
        ]
        self.assertEqual(audit_lines(lines)["matched_results"], 1)

    def test_out_of_range_zone_is_diagnostic(self):
        self.assertEqual(price_zone(.02), "OUT_OF_RANGE")
        self.assertEqual(price_zone(.46), "OUT_OF_RANGE")


if __name__ == "__main__":
    unittest.main()
