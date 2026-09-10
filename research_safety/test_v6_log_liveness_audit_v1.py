import unittest
from datetime import datetime, timezone

from v6_log_liveness_audit_v1 import LivenessAuditError, audit_liveness, parse_lines


def rec(ts, msg):
    return {"timestamp": datetime.fromisoformat(ts.replace("Z", "+00:00")), "message": msg}


class V6LogLivenessAuditTests(unittest.TestCase):
    def test_regular_heartbeats_pass(self):
        records = [
            rec("2026-09-10T08:00:00Z", "LEAD_V6 HEARTBEAT | T | 10.00m | BTC 1 | BRTI 1 | UP .5 | DOWN .5 | pending 0"),
            rec("2026-09-10T08:00:30Z", "LEAD_V6 HEARTBEAT | T | 9.50m | BTC 1 | BRTI 1 | UP .5 | DOWN .5 | pending 0"),
        ]
        result = audit_liveness(records, as_of=datetime(2026,9,10,8,1,0,tzinfo=timezone.utc))
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "OK")

    def test_post_contract_silence_is_distinct(self):
        records = [rec("2026-09-10T06:59:32Z", "LEAD_V6 HEARTBEAT | T | 0.50m | BTC 1 | BRTI 1 | UP .5 | DOWN .5 | pending 0")]
        result = audit_liveness(records, as_of=datetime(2026,9,10,8,9,48,tzinfo=timezone.utc))
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "POST_CONTRACT_SILENCE")
        self.assertGreater(result["silent_tail_seconds"], 4000)

    def test_in_contract_silence_is_flagged(self):
        records = [rec("2026-09-10T08:00:00Z", "LEAD_V6 HEARTBEAT | T | 8.00m | BTC 1 | BRTI 1 | UP .5 | DOWN .5 | pending 0")]
        result = audit_liveness(records, as_of=datetime(2026,9,10,8,5,0,tzinfo=timezone.utc))
        self.assertEqual(result["status"], "IN_CONTRACT_OR_UNKNOWN_SILENCE")

    def test_heartbeat_gap_is_detected(self):
        records = [
            rec("2026-09-10T08:00:00Z", "LEAD_V6 HEARTBEAT | T | 10.00m | BTC 1 | BRTI 1 | UP .5 | DOWN .5 | pending 0"),
            rec("2026-09-10T08:02:00Z", "LEAD_V6 HEARTBEAT | T | 8.00m | BTC 1 | BRTI 1 | UP .5 | DOWN .5 | pending 0"),
        ]
        result = audit_liveness(records, as_of=datetime(2026,9,10,8,2,30,tzinfo=timezone.utc))
        self.assertEqual(result["status"], "HEARTBEAT_GAPS")
        self.assertEqual(result["heartbeat_gap_count"], 1)

    def test_warning_is_reported(self):
        records = [
            rec("2026-09-10T08:00:00Z", "LEAD_V6 HEARTBEAT | T | 10.00m | BTC 1 | BRTI 1 | UP .5 | DOWN .5 | pending 0"),
            rec("2026-09-10T08:00:10Z", "LEAD_V6 WARNING | RuntimeError: x"),
        ]
        result = audit_liveness(records, as_of=datetime(2026,9,10,8,0,30,tzinfo=timezone.utc))
        self.assertEqual(result["status"], "WARNINGS_PRESENT")
        self.assertEqual(result["warning_count"], 1)

    def test_jsonl_parser(self):
        lines = ['{"timestamp":"2026-09-10T08:00:00Z","message":"LEAD_V6 HEARTBEAT | T | 1.00m | x"}']
        parsed = parse_lines(lines)
        self.assertEqual(len(parsed), 1)

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(LivenessAuditError):
            parse_lines(["2026-09-10T08:00:00 LEAD_V6 HEARTBEAT | T | 1.00m | x"])


if __name__ == "__main__":
    unittest.main()
