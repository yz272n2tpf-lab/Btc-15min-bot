import unittest

import scalp_v6_log_schema_audit_v1 as audit


class V6LogSchemaAuditTests(unittest.TestCase):
    def test_current_record_shapes_pass(self):
        lines = [
            "SCALP LEAD SHADOW V6 START | V5 baseline + resilient BRTI + burst/expansion scalp scoring | NO ORDERS\n",
            "LEAD_V6 CANDIDATE | V6_QUALIFIED | TICKER | UP | zone PREFERRED_7_30C | ask 0.200 | btc5 +25.00 | btc15 +30.00 | btc30 +5.00 | accel +12.00 | brti5 +20.00 | brti15 +10.00 | ask5 +0.010 | ask15 +0.020 | left 500s\n",
            "LEAD_V6 RESULT | V6_QUALIFIED | TICKER | UP | zone PREFERRED_7_30C | style BURST | entry 0.200 | max_exec_gain +0.150 | adverse -0.020 | hit10 True | hit20 False | to_exec+5c 5.0 | to_exec+10c 10.0 | to_exec+20c None | kalshi_reprice+5c 3.0\n",
            "LEAD_V6 HEARTBEAT | TICKER | 8.00m | BTC 100000.00 | BRTI 100001.00 | UP 0.200 | DOWN 0.810 | pending 1\n",
            "LEAD_V6 CONTRACT_SUMMARY | TICKER | V5 n=0 | V6 n=0 | rejects price=1 degraded=2 base=3 high=4\n",
            "LEAD_V6 CUMULATIVE | TICKER | V5 n=0 | V6 n=0\n",
            "LEAD_V6 MIDCONTRACT | TICKER | V5 n=0 | V6 n=0 | rejects price=1 degraded=2 base=3 high=4\n",
            "LEAD_V6 WARNING | TimeoutError: sample\n",
        ]
        report = audit.audit_lines(lines)
        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(report["issue_count"], 0)
        self.assertEqual(report["v6_lines"], 8)

    def test_missing_required_candidate_field_is_flagged(self):
        line = "LEAD_V6 CANDIDATE | V6_QUALIFIED | T | UP | zone PREFERRED_7_30C | ask 0.2 | btc5 +1 | btc15 +2 | btc30 +3 | accel +4 | brti5 +5 | brti15 +6 | ask5 +.01 | left 10s\n"
        result = audit.validate_line(line, 7)
        self.assertIn("missing:ask15", result["issues"])

    def test_unknown_v6_record_is_drift(self):
        result = audit.validate_line("LEAD_V6 NEW_EVENT | TICKER | x=1\n", 4)
        self.assertEqual(result["kind"], "UNKNOWN_V6")
        self.assertEqual(result["issues"], ["unknown_v6_record"])

    def test_unrelated_runtime_line_is_ignored(self):
        report = audit.audit_lines(["railway health check ok\n"])
        self.assertTrue(report["ok"])
        self.assertEqual(report["counts"], {"IGNORED": 1})

    def test_populated_score_summary_requires_rate_fields(self):
        line = "LEAD_V6 CUMULATIVE | T | V5 n=1 | V6 n=0\n"
        result = audit.validate_line(line, 2)
        self.assertIn("missing:V5.hit5", result["issues"])
        self.assertIn("missing:V5.avgAdv", result["issues"])


if __name__ == "__main__":
    unittest.main()
