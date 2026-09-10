#!/usr/bin/env python3
import json
import unittest

from collector_log_identity_audit_v1 import audit_identity


class CollectorLogIdentityAuditTests(unittest.TestCase):
    def test_v6_start_and_records_match_expected_v6(self):
        text = "\n".join([
            "SCALP LEAD SHADOW V6 START | V5 baseline | NO ORDERS",
            "LEAD_V6 HEARTBEAT | T | 1.00m | BTC 1.00 | BRTI 1.00 | UP 0.5 | DOWN 0.5 | pending 0",
        ])
        result = audit_identity(text, expected_version="V6")
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["observed_versions"], ["6"])

    def test_v7_fails_when_v6_expected(self):
        text = "\n".join([
            "SCALP LEAD SPLIT V7 START | RESEARCH ONLY | NO ORDERS",
            "LEAD_V7 HEARTBEAT | T | 1.00m | BTC 1.00",
        ])
        result = audit_identity(text, expected_version=6)
        self.assertEqual(result["status"], "VERSION_MISMATCH")
        self.assertEqual(result["observed_versions"], ["7"])

    def test_mixed_versions_fail_closed(self):
        result = audit_identity(
            "LEAD_V6 HEARTBEAT | a\nLEAD_V7 HEARTBEAT | b",
            expected_version=6,
        )
        self.assertEqual(result["status"], "MIXED_VERSIONS")

    def test_no_version_evidence_does_not_false_pass(self):
        result = audit_identity("Starting Container\nordinary line", expected_version=6)
        self.assertEqual(result["status"], "NO_VERSION_DATA")
        self.assertFalse(result["ok"])

    def test_reads_nested_railway_envelope(self):
        payload = {
            "deploymentId": "x",
            "deploy": [
                {"timestamp": "t", "message": "SCALP LEAD SPLIT V7 START | NO ORDERS"},
                {"timestamp": "t2", "message": "LEAD_V7 HEARTBEAT | T"},
            ],
        }
        result = audit_identity(json.dumps(payload), expected_version=7)
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["message_count"], 2)
        self.assertEqual(result["startup_version_counts"], {"7": 1})
        self.assertEqual(result["record_version_counts"], {"7": 1})

    def test_invalid_expected_version_is_rejected(self):
        with self.assertRaises(ValueError):
            audit_identity("LEAD_V6 HEARTBEAT | x", expected_version="current")


if __name__ == "__main__":
    unittest.main()
