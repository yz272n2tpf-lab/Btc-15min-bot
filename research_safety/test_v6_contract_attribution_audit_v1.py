import json
import unittest

from v6_contract_attribution_audit_v1 import audit_messages, normalize_messages


class ContractAttributionAuditTests(unittest.TestCase):
    def test_reconstructs_results_by_embedded_contract(self):
        lines = [
            "LEAD_V6 RESULT | V5_BASELINE | A | DOWN | zone V5_RULES | style BURST | entry 0.120",
            "LEAD_V6 RESULT | V6_QUALIFIED | A | DOWN | zone PREFERRED_7_30C | style BURST | entry 0.120",
            "LEAD_V6 RESULT | V5_BASELINE | B | UP | zone V5_RULES | style BURST | entry 0.150",
        ]
        result = audit_messages(lines)
        self.assertEqual(result["reconstructed"]["A"], {"v5_results": 1, "v6_results": 1})
        self.assertEqual(result["reconstructed"]["B"], {"v5_results": 1, "v6_results": 0})

    def test_flags_result_after_its_contract_summary(self):
        lines = [
            "LEAD_V6 CONTRACT_SUMMARY | A | V5 n=0 | V6 n=0 | rejects price=0 degraded=0 base=0 high=0",
            "LEAD_V6 RESULT | V6_QUALIFIED | A | DOWN | zone PREFERRED_7_30C | style BURST | entry 0.120",
        ]
        result = audit_messages(lines)
        self.assertEqual(len(result["post_summary_results"]), 1)
        self.assertFalse(result["ok"])

    def test_flags_midcontract_carryover_before_matching_results(self):
        lines = [
            "LEAD_V6 HEARTBEAT | B | 14.49m | BTC 1 | BRTI 1 | UP 0.5 | DOWN 0.5 | pending 0",
            "LEAD_V6 MIDCONTRACT | B | V5 n=1 hit5=100.0% | V6 n=1 hit5=100.0% | rejects price=0 degraded=0 base=0 high=0",
        ]
        result = audit_messages(lines)
        self.assertEqual(len(result["carryover_suspects"]), 1)
        self.assertEqual(
            result["carryover_suspects"][0]["unattributed_excess"],
            {"V5_BASELINE": 1, "V6_QUALIFIED": 1},
        )

    def test_normal_midcontract_counts_do_not_flag(self):
        lines = [
            "LEAD_V6 RESULT | V5_BASELINE | B | UP | zone V5_RULES | style BURST | entry 0.150",
            "LEAD_V6 RESULT | V6_QUALIFIED | B | UP | zone PREFERRED_7_30C | style BURST | entry 0.150",
            "LEAD_V6 MIDCONTRACT | B | V5 n=1 hit5=100.0% | V6 n=1 hit5=100.0% | rejects price=0 degraded=0 base=0 high=0",
        ]
        result = audit_messages(lines)
        self.assertEqual(result["carryover_suspects"], [])
        self.assertTrue(result["ok"])

    def test_accepts_railway_json_payload(self):
        payload = {
            "deploy": [
                {"timestamp": "2026-09-10T10:00:00Z", "message": "LEAD_V6 RESULT | V6_QUALIFIED | A | UP | zone PREFERRED_7_30C | style BURST | entry 0.120"}
            ]
        }
        messages = normalize_messages(json.dumps(payload))
        self.assertEqual(len(messages), 1)
        self.assertIn("V6_QUALIFIED", messages[0])


if __name__ == "__main__":
    unittest.main()
