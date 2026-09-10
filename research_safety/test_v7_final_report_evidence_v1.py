import unittest

from v7_final_report_v1 import build_final_report

LOG = """
LEAD_V7 CANDIDATE | lane MOMENTUM_EXPANSION | A | UP | zone MOMENTUM_PREFERRED_7_30C | ask 0.120 | btc5 +20.00 | btc15 +25.00 | btc30 +10.00 | accel +10.00 | brti5 +15.00 | brti15 +5.00 | ask5 +0.000 | ask15 +0.000 | left 400s
LEAD_V7 RESULT | lane MOMENTUM_EXPANSION | A | UP | zone MOMENTUM_PREFERRED_7_30C | style EXPANSION | entry 0.120 | max_gain +0.200 | adverse -0.050 | to+5c 10 | to+10c 90 | to+20c None | reprice+5c 5
LEAD_V7 CONTRACT_SUMMARY | A | MOM n=1 | REV n=0 | BRTI BRTI_RESILIENCE | samples=10 | primary_ok=10 (100.0%) | retry_recovered=0 | missing=0 | errors=0 | verifier_ok=0 | verifier_disagree=0 | diag_cache=0
"""


class FinalReportEvidenceTests(unittest.TestCase):
    def test_final_report_includes_decomposition_independence_and_never_promotes(self):
        report = build_final_report(LOG, None)
        self.assertEqual(report["schema_version"], 3)
        self.assertEqual(report["production_promotion"], "NOT_PERFORMED")
        evidence = report["evidence_decomposition"]
        self.assertEqual(evidence["result_count"], 1)
        self.assertEqual(
            evidence["lanes"]["MOMENTUM_EXPANSION"]["overall"]["expansion_1_3m_pct"],
            100.0,
        )
        independence = report["contract_independence"]["lanes"]["MOMENTUM_EXPANSION"]
        self.assertEqual(independence["samples"], 1)
        self.assertEqual(independence["unique_contracts"], 1)
        self.assertEqual(independence["concentration_warning"], "SINGLE_CONTRACT_ONLY")
        self.assertEqual(report["freeze_gate"]["lanes"]["MOMENTUM_EXPANSION"]["decision"], "MORE_DATA")


if __name__ == "__main__":
    unittest.main()
