import unittest

from v7_data_quality_incident_audit_v1 import audit_incidents


class V7DataQualityIncidentAuditTests(unittest.TestCase):
    def test_compound_incident_classifies_timeout_na_and_suppression(self):
        text = """
LEAD_V7 WARNING | ReadTimeout: HTTPSConnectionPool(host='api.exchange.coinbase.com', port=443): Read timed out. (read timeout=5)
LEAD_V7 HEARTBEAT | A | 5.00m | BTC 1.00 | BRTI N/A | UP 0.400 | DOWN 0.600 | pending 0
LEAD_V7 HEARTBEAT | A | 4.50m | BTC 1.00 | BRTI N/A | UP 0.400 | DOWN 0.600 | pending 0
LEAD_V7 MIDCONTRACT | A | MOM n=0 | REV n=0 | BRTI BRTI_RESILIENCE | samples=10 | primary_ok=8 (80.0%) | retry_recovered=2 | missing=0 | errors=2 | verifier_ok=0 | verifier_disagree=0 | diag_cache=8
LEAD_V7 REJECTS | {'MOM_BRTI_DEGRADED': 42, 'REV_BRTI_DEGRADED': 3}
"""
        report = audit_incidents(text)
        self.assertEqual(report["transport_warnings"]["READ_TIMEOUT"], 1)
        self.assertEqual(report["brti_na_count"], 2)
        self.assertEqual(report["max_consecutive_na"], 2)
        self.assertEqual(report["max_observed_brti_suppression"]["MOMENTUM_EXPANSION"], 42)
        self.assertIn("COMPOUND_DATA_QUALITY_INCIDENT", report["incident_classes"])

    def test_connection_reset_is_specific_not_generic_connection_error(self):
        report = audit_incidents(
            "LEAD_V7 WARNING | ConnectionError: ('Connection aborted.', "
            "ConnectionResetError(104, 'Connection reset by peer'))"
        )
        self.assertEqual(report["transport_warnings"], {"CONNECTION_RESET": 1})

    def test_na_streak_is_scoped_per_contract(self):
        text = """
LEAD_V7 HEARTBEAT | A | 1.00m | BTC 1 | BRTI N/A | UP 0.4 | DOWN 0.6 | pending 0
LEAD_V7 HEARTBEAT | B | 1.00m | BTC 1 | BRTI N/A | UP 0.4 | DOWN 0.6 | pending 0
"""
        report = audit_incidents(text)
        self.assertEqual(report["max_consecutive_na"], 1)
        self.assertNotIn("BRTI_UNAVAILABLE_STREAK", report["incident_classes"])

    def test_reject_counts_use_max_snapshot_not_sum(self):
        text = """
LEAD_V7 MIDCONTRACT | A | MOM n=0 | REV n=0
LEAD_V7 REJECTS | {'MOM_BRTI_DEGRADED': 7}
LEAD_V7 MIDCONTRACT | A | MOM n=0 | REV n=0
LEAD_V7 REJECTS | {'MOM_BRTI_DEGRADED': 12}
"""
        report = audit_incidents(text)
        self.assertEqual(report["max_observed_brti_suppression"]["MOMENTUM_EXPANSION"], 12)

    def test_malformed_reject_is_fail_soft_for_read_only_audit(self):
        text = """
LEAD_V7 MIDCONTRACT | A | MOM n=0 | REV n=0
LEAD_V7 REJECTS | {'MOM_BRTI_DEGRADED':
"""
        report = audit_incidents(text)
        self.assertEqual(report["max_observed_brti_suppression"]["MOMENTUM_EXPANSION"], 0)

    def test_clean_input_reports_no_incident(self):
        text = "LEAD_V7 HEARTBEAT | A | 1.00m | BTC 1 | BRTI 1.10 | UP 0.4 | DOWN 0.6 | pending 0"
        report = audit_incidents(text)
        self.assertEqual(report["incident_classes"], ["NO_DATA_QUALITY_INCIDENT_OBSERVED"])
        self.assertFalse(report["production_mutation"])


if __name__ == "__main__":
    unittest.main()
