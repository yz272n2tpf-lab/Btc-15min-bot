import unittest

from integrity.evidence_integrity_reconciler_v1 import (
    Classification,
    ReconcilerPolicy,
    reconcile_contract,
    summary,
)


def clean_record():
    return {
        "contract_id": "KXBTC15M-TEST",
        "service_deployment_ok": True,
        "process_alive": True,
        "storage_ok": True,
        "collector_advancing": True,
        "scorer_advancing": True,
        "runtime_config_match": True,
        "cutoff_valid": True,
        "has_start_observation": True,
        "has_end_observation": True,
        "continuous_path_complete": True,
        "kalshi_max_age_sec": 1.0,
        "brti_max_age_sec": 1.0,
        "coinbase_max_age_sec": 1.0,
        # Complete per-feed coverage is now mandatory for a clean fixture.
        "kalshi_sample_count": 169,
        "kalshi_has_start_observation": True,
        "kalshi_has_end_observation": True,
        "kalshi_max_observation_gap_sec": 5.0,
        "kalshi_coverage_complete": True,
        "brti_sample_count": 169,
        "brti_has_start_observation": True,
        "brti_has_end_observation": True,
        "brti_max_observation_gap_sec": 5.0,
        "brti_coverage_complete": True,
        "coinbase_sample_count": 169,
        "coinbase_has_start_observation": True,
        "coinbase_has_end_observation": True,
        "coinbase_max_observation_gap_sec": 5.0,
        "coinbase_coverage_complete": True,
        "max_source_gap_sec": 2.0,
        "rollover_lag_sec": 4.0,
        "parity_fail_count": 0,
        "brti_attempts": 1000,
        "brti_429_count": 0,
    }


class ReconcilerTests(unittest.TestCase):
    def test_clean_requires_both_gates(self):
        row = reconcile_contract(clean_record())
        self.assertEqual(row.classification, Classification.CLEAN)
        self.assertTrue(row.operational_health_pass)
        self.assertTrue(row.evidence_integrity_pass)
        self.assertTrue(row.valid_for_certification)
        self.assertFalse(row.quarantine)

    def test_green_service_does_not_override_bad_evidence(self):
        record = clean_record()
        record["brti_max_age_sec"] = 120.0
        row = reconcile_contract(record)
        self.assertTrue(row.operational_health_pass)
        self.assertFalse(row.evidence_integrity_pass)
        self.assertEqual(row.classification, Classification.INVALID_FOR_CERT)
        self.assertFalse(row.valid_for_certification)
        self.assertTrue(row.quarantine)

    def test_good_evidence_does_not_override_bad_operational_health(self):
        record = clean_record()
        record["storage_ok"] = False
        row = reconcile_contract(record)
        self.assertFalse(row.operational_health_pass)
        self.assertTrue(row.evidence_integrity_pass)
        self.assertEqual(row.classification, Classification.INVALID_FOR_CERT)

    def test_missing_required_measurement_is_unknown_not_clean(self):
        record = clean_record()
        del record["continuous_path_complete"]
        row = reconcile_contract(record)
        self.assertIsNone(row.evidence_integrity_pass)
        self.assertEqual(row.classification, Classification.UNKNOWN)
        self.assertFalse(row.valid_for_certification)

    def test_429_rate_is_warning_when_freshness_remained_clean(self):
        record = clean_record()
        record["brti_429_count"] = 200
        record["brti_attempts"] = 1000
        row = reconcile_contract(record)
        self.assertTrue(row.operational_health_pass)
        self.assertTrue(row.evidence_integrity_pass)
        self.assertEqual(row.classification, Classification.PARTIAL)
        self.assertFalse(row.valid_for_certification)
        self.assertTrue(any("BRTI_429_SHARE" in x for x in row.warnings))

    def test_parity_failure_is_hard_by_default(self):
        record = clean_record()
        record["parity_fail_count"] = 1
        row = reconcile_contract(record)
        self.assertEqual(row.classification, Classification.INVALID_FOR_CERT)
        self.assertFalse(row.evidence_integrity_pass)

    def test_rollover_late_is_invalid_for_cert(self):
        record = clean_record()
        record["rollover_lag_sec"] = 31.0
        row = reconcile_contract(record)
        self.assertEqual(row.classification, Classification.INVALID_FOR_CERT)
        self.assertTrue(any("ROLLOVER_LATE" in x for x in row.reasons))

    def test_policy_can_disable_unused_feed_dependency(self):
        record = clean_record()
        del record["coinbase_max_age_sec"]
        policy = ReconcilerPolicy(require_coinbase=False)
        row = reconcile_contract(record, policy)
        self.assertEqual(row.classification, Classification.CLEAN)

    def test_summary_preserves_quarantine_counts(self):
        clean = clean_record()
        bad = clean_record()
        bad["contract_id"] = "KXBTC15M-BAD"
        bad["storage_ok"] = False
        rows = [reconcile_contract(clean), reconcile_contract(bad)]
        report = summary(rows)
        self.assertEqual(report["contracts"], 2)
        self.assertEqual(report["certifiable_contracts"], 1)
        self.assertEqual(report["quarantined_contracts"], 1)
        self.assertFalse(report["orders"])
        self.assertFalse(report["source_mutation"])


if __name__ == "__main__":
    unittest.main()
