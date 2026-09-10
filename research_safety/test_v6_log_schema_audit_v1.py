#!/usr/bin/env python3
import json
import unittest

from v6_log_schema_audit_v1 import audit_text, classify_message


CANDIDATE = (
    "LEAD_V6 CANDIDATE | V6_QUALIFIED | TICKER | UP | zone PREFERRED_7_30C "
    "| ask 0.270 | btc5 +25.00 | btc15 +30.00 | btc30 +40.00 | accel +12.00 "
    "| brti5 +20.00 | brti15 +10.00 | ask5 +0.020 | ask15 +0.040 | left 420s"
)
RESULT = (
    "LEAD_V6 RESULT | V6_QUALIFIED | TICKER | UP | zone PREFERRED_7_30C "
    "| style BURST | entry 0.270 | max_exec_gain +0.120 | adverse -0.030 "
    "| hit10 True | hit20 False | to_exec+5c 7.2 | to_exec+10c 18.0 "
    "| to_exec+20c None | kalshi_reprice+5c 8.4"
)
HEARTBEAT = (
    "LEAD_V6 HEARTBEAT | TICKER | 7.00m | BTC 77000.00 | BRTI N/A "
    "| UP 0.270 | DOWN 0.740 | pending 1"
)
SUMMARY = (
    "LEAD_V6 CONTRACT_SUMMARY | TICKER | "
    "V5 n=2 hit5=50.0% hit10=50.0% burst10<=30s=50.0% expand10<=120s=50.0% "
    "hit20=0.0% expand20<=180s=0.0% avgGain=+0.080 avgAdv=-0.020 | "
    "V6 n=0 | rejects price=3 degraded=1 base=2 high=0"
)
CUMULATIVE = "LEAD_V6 CUMULATIVE | TICKER | V5 n=0 | V6 n=0"
WARNING = "LEAD_V6 WARNING | ConnectionError: upstream reset"


class LogSchemaAuditTests(unittest.TestCase):
    def test_accepts_all_known_record_shapes(self):
        text = "\n".join(
            json.dumps({"timestamp": "2026-09-10T17:00:00Z", "message": msg})
            for msg in [CANDIDATE, RESULT, HEARTBEAT, SUMMARY, CUMULATIVE, WARNING]
        )
        result = audit_text(text)
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["v6_records"], 6)
        self.assertEqual(result["malformed_count"], 0)
        self.assertEqual(result["unknown_type_count"], 0)

    def test_malformed_known_record_fails_closed(self):
        result = audit_text(json.dumps({"message": HEARTBEAT.replace("pending 1", "pending one")}))
        self.assertEqual(result["status"], "SCHEMA_DRIFT")
        self.assertEqual(result["malformed_count"], 1)
        self.assertEqual(result["issues"][0]["record_type"], "HEARTBEAT")

    def test_unknown_v6_type_is_flagged(self):
        result = audit_text(json.dumps({"message": "LEAD_V6 NEW_EVENT | TICKER | x 1"}))
        self.assertEqual(result["status"], "SCHEMA_DRIFT")
        self.assertEqual(result["unknown_type_count"], 1)
        self.assertEqual(result["issues"][0]["kind"], "UNKNOWN_TYPE")

    def test_noise_is_ignored_but_counted(self):
        text = "\n".join([
            json.dumps({"message": "ordinary Railway line"}),
            json.dumps({"message": WARNING}),
        ])
        result = audit_text(text)
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["noise_records"], 1)
        self.assertEqual(result["type_counts"], {"WARNING": 1})

    def test_no_v6_data_does_not_false_pass(self):
        result = audit_text(json.dumps({"message": "ordinary Railway line"}))
        self.assertEqual(result["status"], "NO_V6_DATA")
        self.assertFalse(result["ok"])

    def test_na_candidate_optional_data_is_valid(self):
        candidate = CANDIDATE.replace("btc30 +40.00", "btc30 N/A").replace(
            "brti5 +20.00", "brti5 N/A"
        )
        record_type, valid = classify_message(candidate)
        self.assertEqual(record_type, "CANDIDATE")
        self.assertTrue(valid)

    def test_example_cap_is_enforced(self):
        text = "\n".join(
            json.dumps({"message": f"LEAD_V6 FUTURE_{i} | x"}) for i in range(4)
        )
        result = audit_text(text, max_examples=2)
        self.assertEqual(result["unknown_type_count"], 4)
        self.assertEqual(len(result["issues"]), 2)

    def test_negative_example_cap_is_rejected(self):
        with self.assertRaises(ValueError):
            audit_text(json.dumps({"message": WARNING}), max_examples=-1)


if __name__ == "__main__":
    unittest.main()
