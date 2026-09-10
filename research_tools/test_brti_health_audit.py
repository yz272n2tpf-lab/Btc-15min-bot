import json
import unittest

from brti_health_audit import audit_lines, extract_message


class BrtiHealthAuditTests(unittest.TestCase):
    def test_outage_and_recovery(self):
        lines = [
            "LEAD_V6 HEARTBEAT | T1 | 10.00m | BTC 1 | BRTI 2.00 | UP .5 | DOWN .5 | pending 0",
            "LEAD_V6 HEARTBEAT | T1 | 9.50m | BTC 1 | BRTI N/A | UP .5 | DOWN .5 | pending 0",
            "LEAD_V6 HEARTBEAT | T1 | 9.00m | BTC 1 | BRTI N/A | UP .5 | DOWN .5 | pending 0",
            "LEAD_V6 HEARTBEAT | T1 | 8.50m | BTC 1 | BRTI 2.00 | UP .5 | DOWN .5 | pending 0",
        ]
        r = audit_lines(lines)
        self.assertEqual(r["heartbeats"]["total"], 4)
        self.assertEqual(r["heartbeats"]["brti_na"], 2)
        self.assertEqual(r["heartbeats"]["recoveries"], 1)
        self.assertEqual(r["heartbeats"]["max_outage_seconds_est"], 60.0)

    def test_degraded_uses_per_contract_max(self):
        lines = [
            "LEAD_V6 MIDCONTRACT | T1 | V5 n=0 | V6 n=0 | rejects price=0 degraded=10 base=0 high=0",
            "LEAD_V6 CONTRACT_SUMMARY | T1 | V5 n=0 | V6 n=0 | rejects price=0 degraded=42 base=0 high=0",
            "LEAD_V6 CONTRACT_SUMMARY | T2 | V5 n=0 | V6 n=0 | rejects price=0 degraded=5 base=0 high=0",
        ]
        r = audit_lines(lines)
        self.assertEqual(r["degraded_rejects"]["sum_contract_max"], 47)
        self.assertEqual(r["degraded_rejects"]["max_per_contract"], 42)

    def test_candidate_integrity_and_boundary_flag(self):
        lines = [
            "LEAD_V6 CANDIDATE | V5_BASELINE | T1 | UP | zone V5_RULES | ask 0.200 | btc5 +1.00 | btc15 +2.00 | btc30 +3.00 | accel +1.00 | brti5 +1.00 | brti15 N/A | ask5 +0.000 | ask15 +0.000 | left 500s",
            "LEAD_V6 CANDIDATE | V6_QUALIFIED | T1 | UP | zone PREFERRED_7_30C | ask 0.200 | btc5 +1.00 | btc15 +2.00 | btc30 +3.00 | accel +1.00 | brti5 N/A | brti15 +2.00 | ask5 +0.000 | ask15 +0.000 | left 500s",
            "LEAD_V6 RESULT | V6_QUALIFIED | T1 | UP | zone PREFERRED_7_30C | style NO_EXPANSION | entry 0.200 | max_exec_gain +0.100 | adverse -0.010 | hit10 False | hit20 False | to_exec+5c 10.0 | to_exec+10c None | to_exec+20c None | kalshi_reprice+5c 10.0",
        ]
        r = audit_lines(lines)
        self.assertEqual(r["candidate_impact"]["v5_candidates_missing_brti"], 1)
        self.assertEqual(r["integrity"]["v6_missing_brti_violations"], 1)
        self.assertEqual(r["integrity"]["display_hit10_boundary_anomalies"], 1)

    def test_jsonl_message_extraction(self):
        line = json.dumps({"timestamp": "x", "message": "hello"})
        self.assertEqual(extract_message(line), "hello")


if __name__ == "__main__":
    unittest.main()
