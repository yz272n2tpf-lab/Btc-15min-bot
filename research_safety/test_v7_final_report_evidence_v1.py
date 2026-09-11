import unittest

from v7_final_report_v1 import build_final_report

LOG = """
LEAD_V7 CANDIDATE | lane MOMENTUM_EXPANSION | A | UP | zone MOMENTUM_PREFERRED_7_30C | ask 0.120 | btc5 +20.00 | btc15 +25.00 | btc30 +10.00 | accel +10.00 | brti5 +15.00 | brti15 +5.00 | ask5 +0.000 | ask15 +0.000 | left 400s
LEAD_V7 RESULT | lane MOMENTUM_EXPANSION | A | UP | zone MOMENTUM_PREFERRED_7_30C | style EXPANSION | entry 0.120 | max_gain +0.200 | adverse -0.050 | to+5c 10 | to+10c 90 | to+20c None | reprice+5c 5
LEAD_V7 HEARTBEAT | A | 5.00m | BTC 1.00 | BRTI N/A | UP 0.400 | DOWN 0.600 | pending 0
LEAD_V7 WARNING | ReadTimeout: HTTPSConnectionPool(host='api.exchange.coinbase.com', port=443): Read timed out. (read timeout=5)
LEAD_V7 MIDCONTRACT | A | MOM n=1 | REV n=0 | BRTI BRTI_RESILIENCE | samples=9 | primary_ok=8 (88.9%) | retry_recovered=1 | missing=0 | errors=1 | verifier_ok=0 | verifier_disagree=0 | diag_cache=8
LEAD_V7 REJECTS | {'MOM_BRTI_DEGRADED': 2}
LEAD_V7 CONTRACT_SUMMARY | A | MOM n=1 | REV n=0 | BRTI BRTI_RESILIENCE | samples=10 | primary_ok=9 (90.0%) | retry_recovered=1 | missing=0 | errors=1 | verifier_ok=0 | verifier_disagree=0 | diag_cache=9
"""


class FinalReportEvidenceTests(unittest.TestCase):
    def test_final_report_includes_all_research_audits_and_never_promotes(self):
        report = build_final_report(LOG, None)
        self.assertEqual(report["schema_version"], 5)
        self.assertEqual(report["production_promotion"], "NOT_PERFORMED")
        self.assertEqual(report["result_source_authority"]["scoring_source"], "RESULT_STREAM")
        self.assertEqual(report["result_source_authority"]["contract_summary_role"], "ADVISORY_ONLY")
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
        self.assertIn("HEARTBEAT_NA_OBSERVED", report["brti_reliability"]["failure_classes"])
        incidents = report["data_quality_incidents"]
        self.assertEqual(incidents["transport_warnings"]["READ_TIMEOUT"], 1)
        self.assertIn("COMPOUND_DATA_QUALITY_INCIDENT", incidents["incident_classes"])
        self.assertEqual(report["summary_staleness"]["status"], "CLEAN")
        self.assertEqual(report["freeze_gate"]["lanes"]["MOMENTUM_EXPANSION"]["decision"], "MORE_DATA")


if __name__ == "__main__":
    unittest.main()
