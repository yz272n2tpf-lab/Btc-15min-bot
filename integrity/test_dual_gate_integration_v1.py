import unittest
from datetime import datetime, timedelta, timezone

from integrity.evidence_integrity_adapter_v1 import aggregate_contract
from integrity.evidence_integrity_reconciler_v1 import Classification, reconcile_contract


BASE = datetime(2026, 9, 17, 3, 0, tzinfo=timezone.utc)


def make_path(**overrides):
    rows = []
    for i in range(0, 841, 5):
        row = {
            "contract_id": "KXBTC15M-INTEGRATION",
            "observed_at_utc": (BASE + timedelta(seconds=i)).isoformat(),
            "seconds_left": 896 - i,
            "service_deployment_ok": True,
            "process_alive": True,
            "storage_ok": True,
            "collector_advancing": True,
            "scorer_advancing": True,
            "runtime_config_match": True,
            "cutoff_valid": True,
            "kalshi_age_sec": 1.0,
            "brti_age_sec": 1.0,
            "coinbase_age_sec": 1.0,
            "parity_ok": True,
            "brti_attempts_total": 1000 + i,
            "brti_429_total": 10,
        }
        row.update(overrides)
        rows.append(row)
    return rows


class DualGateIntegrationTests(unittest.TestCase):
    def test_clean_adapter_output_is_certifiable(self):
        record = aggregate_contract("KXBTC15M-INTEGRATION", make_path())
        assessment = reconcile_contract(record)
        self.assertEqual(assessment.classification, Classification.CLEAN)
        self.assertTrue(assessment.valid_for_certification)

    def test_brti_stale_contract_is_quarantined(self):
        rows = make_path()
        rows[80]["brti_age_sec"] = 25.0
        record = aggregate_contract("KXBTC15M-INTEGRATION", rows)
        assessment = reconcile_contract(record)
        self.assertEqual(assessment.classification, Classification.INVALID_FOR_CERT)
        self.assertTrue(assessment.quarantine)

    def test_parity_failure_is_quarantined(self):
        rows = make_path()
        rows[50]["parity_ok"] = False
        record = aggregate_contract("KXBTC15M-INTEGRATION", rows)
        assessment = reconcile_contract(record)
        self.assertEqual(assessment.classification, Classification.INVALID_FOR_CERT)
        self.assertTrue(any("FAIL_PARITY" in x for x in assessment.reasons))

    def test_operational_failure_is_quarantined_even_with_clean_feed(self):
        rows = make_path()
        rows[20]["scorer_advancing"] = False
        record = aggregate_contract("KXBTC15M-INTEGRATION", rows)
        assessment = reconcile_contract(record)
        self.assertEqual(assessment.classification, Classification.INVALID_FOR_CERT)
        self.assertFalse(assessment.operational_health_pass)

    def test_high_429_share_is_partial_not_certifiable(self):
        rows = make_path()
        rows[-1]["brti_429_total"] = 210
        record = aggregate_contract("KXBTC15M-INTEGRATION", rows)
        assessment = reconcile_contract(record)
        self.assertEqual(assessment.classification, Classification.PARTIAL)
        self.assertFalse(assessment.valid_for_certification)


if __name__ == "__main__":
    unittest.main()
