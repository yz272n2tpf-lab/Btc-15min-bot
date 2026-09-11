import unittest

from unified_scalp_summary_timing_audit_v1 import audit_lines


def result(ticker="T1", lane="MOMENTUM_EXPANSION"):
    return f"LEAD_V7 RESULT | lane {lane} | {ticker} | UP | zone Z | style EXPANSION | entry 0.200"


def summary(ticker="T1", n=1):
    return f"LEAD_V7 CONTRACT_SUMMARY | {ticker} | MOM n={n} hit5=0.0%"


def cumulative(ticker="T1", n=1):
    return f"LEAD_V7 CUMULATIVE | {ticker} | MOM n={n} hit5=0.0%"


class UnifiedSummaryTimingAuditTests(unittest.TestCase):
    def test_on_time_result_is_clean(self):
        report = audit_lines([result(), summary(), cumulative()])
        self.assertFalse(report["summary_timing_regression_detected"])
        self.assertEqual(report["decision"]["summary_timing_auditor"], "KEEP")

    def test_late_result_after_summary_and_cumulative_detected(self):
        report = audit_lines([summary(n=0), cumulative(n=57), result()])
        self.assertTrue(report["summary_timing_regression_detected"])
        self.assertEqual(report["late_unified_results_after_contract_summary"], 1)
        self.assertEqual(report["late_unified_results_after_cumulative"], 1)
        self.assertEqual(report["decision"]["summary_timing_auditor"], "TIGHTEN")
        self.assertEqual(report["decision"]["qualification_threshold_change"], "MORE_DATA")

    def test_legacy_reversal_is_audit_only(self):
        report = audit_lines([summary(n=0), result(lane="ULTRA_CHEAP_REVERSAL")])
        self.assertEqual(report["unified_results"], 0)
        self.assertEqual(report["legacy_reversal_research_only"], 1)
        self.assertEqual(report["decision"]["separate_ultra_cheap_graduation_path"], "REJECT")

    def test_other_contract_summary_does_not_flag(self):
        report = audit_lines([summary(ticker="T1", n=0), result(ticker="T2")])
        self.assertFalse(report["summary_timing_regression_detected"])

    def test_unknown_lane_fails_closed(self):
        report = audit_lines([result(lane="OTHER")])
        self.assertEqual(report["unknown_lane_results"], 1)
        self.assertEqual(report["production_promotion"], "NOT_PERFORMED")


if __name__ == "__main__":
    unittest.main()
