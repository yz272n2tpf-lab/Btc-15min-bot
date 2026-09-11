import unittest

from v7_architecture_decision_v1 import synthesize


def report_with(decisions):
    return {
        "collector_identity": "LEAD_V7",
        "production_promotion": "NOT_PERFORMED",
        "result_source_authority": {
            "scoring_source": "RESULT_STREAM",
            "contract_summary_role": "ADVISORY_ONLY",
        },
        "summary_staleness": {"status": "SUMMARY_STALE_FINDINGS"},
        "freeze_gate": {
            "lanes": {
                lane: {"decision": decision, "reasons": [decision]}
                for lane, decision in decisions.items()
            }
        },
    }


class ArchitectureDecisionTests(unittest.TestCase):
    def test_more_data_defers_architecture(self):
        out = synthesize(report_with({"MOMENTUM_EXPANSION": "KEEP", "ULTRA_CHEAP_REVERSAL": "MORE_DATA"}))
        self.assertEqual(out["overall_architecture_status"], "MORE_DATA")
        self.assertEqual(out["lanes"]["MOMENTUM_EXPANSION"]["architecture_action"], "INCLUDE_UNCHANGED")
        self.assertEqual(out["lanes"]["ULTRA_CHEAP_REVERSAL"]["architecture_action"], "DEFER_PENDING_MORE_DATA")
        self.assertEqual(out["production_promotion"], "NOT_PERFORMED")

    def test_ready_for_manual_finalization_when_all_lanes_resolved(self):
        out = synthesize(report_with({"MOMENTUM_EXPANSION": "KEEP", "ULTRA_CHEAP_REVERSAL": "REJECT"}))
        self.assertEqual(out["overall_architecture_status"], "READY_FOR_MANUAL_FINALIZATION")
        self.assertEqual(out["lanes"]["ULTRA_CHEAP_REVERSAL"]["architecture_action"], "EXCLUDE_FROM_FINAL_ARCHITECTURE")

    def test_all_reject_is_explicit(self):
        out = synthesize(report_with({"MOMENTUM_EXPANSION": "REJECT", "ULTRA_CHEAP_REVERSAL": "REJECT"}))
        self.assertEqual(out["overall_architecture_status"], "REJECT_ALL_LANES")

    def test_tighten_never_applies_changes_automatically(self):
        out = synthesize(report_with({"MOMENTUM_EXPANSION": "TIGHTEN"}))
        self.assertEqual(out["lanes"]["MOMENTUM_EXPANSION"]["architecture_action"], "INCLUDE_ONLY_AFTER_EXPLICIT_TIGHTEN_POLICY")
        self.assertEqual(out["overall_architecture_status"], "READY_FOR_MANUAL_FINALIZATION")

    def test_wrong_collector_fails_closed(self):
        report = report_with({"MOMENTUM_EXPANSION": "KEEP"})
        report["collector_identity"] = "LEAD_V6"
        with self.assertRaises(ValueError):
            synthesize(report)

    def test_non_preserved_promotion_fails_closed(self):
        report = report_with({"MOMENTUM_EXPANSION": "KEEP"})
        report["production_promotion"] = "PROMOTED"
        with self.assertRaises(ValueError):
            synthesize(report)

    def test_unknown_decision_fails_closed(self):
        report = report_with({"MOMENTUM_EXPANSION": "MAYBE"})
        with self.assertRaises(ValueError):
            synthesize(report)


if __name__ == "__main__":
    unittest.main()
