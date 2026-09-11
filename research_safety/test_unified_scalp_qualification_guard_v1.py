import unittest

from unified_scalp_qualification_guard_v1 import (
    LEGACY_REVERSAL_SOURCE,
    UNIFIED_STANDARD,
    QualificationRecord,
    audit_architecture,
    audit_record,
    graduation_eligible,
    price_zone,
    summarize,
)


class UnifiedGuardTests(unittest.TestCase):
    def test_same_evidence_same_result_at_3c_and_45c(self):
        low = QualificationRecord(0.03, UNIFIED_STANDARD, True, True)
        high = QualificationRecord(0.45, UNIFIED_STANDARD, True, True)
        self.assertTrue(graduation_eligible(low))
        self.assertTrue(graduation_eligible(high))
        self.assertEqual(audit_record(low), [])
        self.assertEqual(audit_record(high), [])

    def test_cheap_price_cannot_rescue_failed_evidence(self):
        r = QualificationRecord(0.031, UNIFIED_STANDARD, False, True)
        self.assertFalse(graduation_eligible(r))
        self.assertIn("PRICE_OR_OTHER_OVERRIDE_BYPASSED_EVIDENCE", audit_record(r))

    def test_legacy_reversal_is_research_only_even_if_evidence_passes(self):
        r = QualificationRecord(
            0.04, UNIFIED_STANDARD, True, True, source=LEGACY_REVERSAL_SOURCE
        )
        self.assertFalse(graduation_eligible(r))
        self.assertIn("LEGACY_REVERSAL_CANNOT_GRADUATE", audit_record(r))

    def test_non_unified_standard_cannot_graduate(self):
        r = QualificationRecord(0.20, "CHEAP_SPECIAL", True, True)
        self.assertFalse(graduation_eligible(r))
        self.assertIn("NON_UNIFIED_STANDARD_CANNOT_GRADUATE", audit_record(r))

    def test_price_zones_are_diagnostic(self):
        self.assertEqual(price_zone(0.03), "3_7C")
        self.assertEqual(price_zone(0.07), "7_15C")
        self.assertEqual(price_zone(0.15), "15_30C")
        self.assertEqual(price_zone(0.30), "30_45C")
        self.assertEqual(price_zone(0.451), "OUT_OF_RANGE")

    def test_architecture_rejects_cheap_override(self):
        config = {
            "graduation_paths": [UNIFIED_STANDARD],
            "cheap_price_override": True,
            "price_adjusts_evidence_standard": False,
            "research_only_sources": [LEGACY_REVERSAL_SOURCE],
            "production_promotion": "NOT_PERFORMED",
        }
        self.assertEqual(audit_architecture(config), ["CHEAP_PRICE_OVERRIDE_FORBIDDEN"])

    def test_architecture_requires_legacy_reversal_research_only(self):
        config = {
            "graduation_paths": [UNIFIED_STANDARD],
            "cheap_price_override": False,
            "price_adjusts_evidence_standard": False,
            "research_only_sources": [],
            "production_promotion": "NOT_PERFORMED",
        }
        self.assertIn("LEGACY_REVERSAL_MUST_STAY_RESEARCH_ONLY", audit_architecture(config))

    def test_valid_architecture_passes(self):
        config = {
            "graduation_paths": [UNIFIED_STANDARD],
            "cheap_price_override": False,
            "price_adjusts_evidence_standard": False,
            "research_only_sources": [LEGACY_REVERSAL_SOURCE],
            "production_promotion": "NOT_PERFORMED",
        }
        self.assertEqual(audit_architecture(config), [])

    def test_summary_keeps_adverse_metrics_diagnostic(self):
        rows = [
            QualificationRecord(0.04, UNIFIED_STANDARD, True, True, max_gain=0.12, adverse=-0.08),
            QualificationRecord(0.20, UNIFIED_STANDARD, True, True, max_gain=0.04, adverse=-0.03),
        ]
        s = summarize(rows)
        self.assertEqual(s["graduation_eligible"], 2)
        self.assertEqual(s["production_promotion"], "NOT_PERFORMED")
        self.assertAlmostEqual(s["zones"]["3_7C"]["worst_adverse"], -0.08)
        self.assertEqual(s["violations"], [])


if __name__ == "__main__":
    unittest.main()
