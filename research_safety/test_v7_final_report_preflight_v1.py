import unittest

from v7_final_report_preflight_v1 import assert_report_safe, validate_report


def base_report():
    return {
        "schema_version": 6,
        "collector_identity": "LEAD_V7",
        "result_source_authority": {
            "scoring_source": "RESULT_STREAM",
            "contract_summary_role": "ADVISORY_ONLY",
        },
        "scorecard": {},
        "evidence_decomposition": {},
        "contract_independence": {},
        "brti_reliability": {},
        "data_quality_incidents": {},
        "summary_staleness": {},
        "freeze_gate": {
            "lanes": {
                "MOMENTUM_EXPANSION": {"decision": "MORE_DATA", "reasons": ["n"]},
                "ULTRA_CHEAP_REVERSAL": {"decision": "REJECT", "reasons": ["x"]},
            }
        },
        "production_promotion": "NOT_PERFORMED",
        "architecture_decision": {
            "collector_identity": "LEAD_V7",
            "overall_architecture_status": "MORE_DATA",
            "production_promotion": "NOT_PERFORMED",
            "lanes": {
                "MOMENTUM_EXPANSION": {"freeze_decision": "MORE_DATA"},
                "ULTRA_CHEAP_REVERSAL": {"freeze_decision": "REJECT"},
            },
        },
    }


class V7FinalReportPreflightTests(unittest.TestCase):
    def test_valid_report_passes(self):
        result = assert_report_safe(base_report())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["checks_total"], result["checks_passed"])

    def test_missing_required_section_fails(self):
        report = base_report()
        del report["brti_reliability"]
        result = validate_report(report)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("MISSING_OR_INVALID_SECTION:brti_reliability", result["failure_codes"])

    def test_production_promotion_attempt_fails_closed(self):
        report = base_report()
        report["production_promotion"] = "PERFORMED"
        result = validate_report(report)
        self.assertIn("PRODUCTION_PROMOTION_NOT_LOCKED", result["failure_codes"])

    def test_wrong_collector_identity_fails(self):
        report = base_report()
        report["collector_identity"] = "LEAD_V6"
        result = validate_report(report)
        self.assertIn("COLLECTOR_IDENTITY_MISMATCH", result["failure_codes"])

    def test_unknown_freeze_decision_fails(self):
        report = base_report()
        report["freeze_gate"]["lanes"]["MOMENTUM_EXPANSION"]["decision"] = "PROMOTE"
        result = validate_report(report)
        self.assertIn("FREEZE_GATE_DECISION_INVALID:MOMENTUM_EXPANSION", result["failure_codes"])

    def test_architecture_lane_set_mismatch_fails(self):
        report = base_report()
        del report["architecture_decision"]["lanes"]["ULTRA_CHEAP_REVERSAL"]
        result = validate_report(report)
        self.assertIn("ARCHITECTURE_LANE_SET_MISMATCH", result["failure_codes"])

    def test_architecture_decision_mismatch_fails(self):
        report = base_report()
        report["architecture_decision"]["lanes"]["MOMENTUM_EXPANSION"]["freeze_decision"] = "KEEP"
        result = validate_report(report)
        self.assertIn(
            "ARCHITECTURE_FREEZE_DECISION_MISMATCH:MOMENTUM_EXPANSION",
            result["failure_codes"],
        )

    def test_bad_result_authority_fails(self):
        report = base_report()
        report["result_source_authority"]["scoring_source"] = "CONTRACT_SUMMARY"
        result = validate_report(report)
        self.assertIn("SCORING_SOURCE_NOT_RESULT_STREAM", result["failure_codes"])


if __name__ == "__main__":
    unittest.main()
