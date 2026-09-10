import json
import unittest

from v6_contract_coverage_audit_v1 import audit_messages, normalize_messages


class ContractCoverageAuditTests(unittest.TestCase):
    def test_complete_transition_passes_and_new_contract_can_be_active(self):
        lines = [
            "LEAD_V6 HEARTBEAT | A | 1.00m | BTC 1 | BRTI 1 | UP 0.5 | DOWN 0.5 | pending 0",
            "LEAD_V6 CONTRACT_SUMMARY | A | V5 n=0 | V6 n=0 | rejects price=0 degraded=0 base=0 high=0",
            "LEAD_V6 HEARTBEAT | B | 14.99m | BTC 1 | BRTI 1 | UP 0.5 | DOWN 0.5 | pending 0",
        ]
        result = audit_messages(lines)
        self.assertTrue(result["ok"])
        self.assertEqual(result["heartbeat_contract_order"], ["A", "B"])
        self.assertEqual(result["newest_heartbeat_contract"], "B")
        self.assertEqual(result["missing_summary_before_transition"], [])

    def test_missing_summary_before_heartbeat_transition_is_flagged(self):
        lines = [
            "LEAD_V6 HEARTBEAT | A | 0.20m | BTC 1 | BRTI 1 | UP 0.5 | DOWN 0.5 | pending 0",
            "LEAD_V6 HEARTBEAT | B | 14.99m | BTC 1 | BRTI 1 | UP 0.5 | DOWN 0.5 | pending 0",
        ]
        result = audit_messages(lines)
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["missing_summary_before_transition"]), 1)
        self.assertEqual(result["missing_summary_before_transition"][0]["from_contract"], "A")

    def test_duplicate_summary_is_flagged(self):
        lines = [
            "LEAD_V6 HEARTBEAT | A | 1.00m | BTC 1 | BRTI 1 | UP 0.5 | DOWN 0.5 | pending 0",
            "LEAD_V6 CONTRACT_SUMMARY | A | V5 n=0 | V6 n=0 | rejects price=0 degraded=0 base=0 high=0",
            "LEAD_V6 CONTRACT_SUMMARY | A | V5 n=0 | V6 n=0 | rejects price=0 degraded=0 base=0 high=0",
        ]
        result = audit_messages(lines)
        self.assertFalse(result["ok"])
        self.assertEqual(result["duplicate_summaries"][0]["count"], 2)

    def test_late_result_does_not_create_false_heartbeat_transition(self):
        lines = [
            "LEAD_V6 HEARTBEAT | A | 0.10m | BTC 1 | BRTI 1 | UP 0.5 | DOWN 0.5 | pending 1",
            "LEAD_V6 CONTRACT_SUMMARY | A | V5 n=1 | V6 n=0 | rejects price=0 degraded=0 base=0 high=0",
            "LEAD_V6 HEARTBEAT | B | 14.90m | BTC 1 | BRTI 1 | UP 0.5 | DOWN 0.5 | pending 0",
            "LEAD_V6 RESULT | V5_BASELINE | A | DOWN | zone V5_RULES | style BURST | entry 0.120",
            "LEAD_V6 HEARTBEAT | B | 13.90m | BTC 1 | BRTI 1 | UP 0.5 | DOWN 0.5 | pending 0",
        ]
        result = audit_messages(lines)
        self.assertTrue(result["ok"])
        self.assertEqual(result["heartbeat_contract_order"], ["A", "B"])
        self.assertEqual(result["per_contract"]["A"]["v5_results"], 1)

    def test_counts_staged_and_contract_events(self):
        lines = [
            "LEAD_V6 HEARTBEAT | A | 10.00m | BTC 1 | BRTI 1 | UP 0.5 | DOWN 0.5 | pending 0",
            "LEAD_V6 CANDIDATE | V5_BASELINE | A | DOWN | zone V5_RULES | ask 0.300",
            "LEAD_V6 CANDIDATE | V6_QUALIFIED | A | DOWN | zone PREFERRED_7_30C | ask 0.300",
            "LEAD_V6 RESULT | V5_BASELINE | A | DOWN | zone V5_RULES | style BURST | entry 0.300",
            "LEAD_V6 RESULT | V6_QUALIFIED | A | DOWN | zone PREFERRED_7_30C | style BURST | entry 0.300",
            "LEAD_V6 MIDCONTRACT | A | V5 n=1 hit5=100.0% | V6 n=1 hit5=100.0%",
        ]
        result = audit_messages(lines)
        counts = result["per_contract"]["A"]
        self.assertEqual(
            [counts["heartbeats"], counts["midcontract"], counts["v5_candidates"],
             counts["v6_candidates"], counts["v5_results"], counts["v6_results"]],
            [1, 1, 1, 1, 1, 1],
        )

    def test_accepts_railway_json_payload(self):
        payload = {
            "deploy": [
                {
                    "timestamp": "2026-09-10T12:00:00Z",
                    "message": "LEAD_V6 HEARTBEAT | A | 10.00m | BTC 1 | BRTI 1 | UP 0.5 | DOWN 0.5 | pending 0",
                }
            ]
        }
        messages = normalize_messages(json.dumps(payload))
        self.assertEqual(len(messages), 1)
        self.assertIn("HEARTBEAT", messages[0])


if __name__ == "__main__":
    unittest.main()
