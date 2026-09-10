#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

from v6_heartbeat_integrity_audit_v1 import audit_heartbeat_integrity, parse_records


def rec(
    ts,
    *,
    ticker="T",
    left=10.0,
    btc=77000.0,
    brti=77001.0,
    up=0.5,
    down=0.5,
    pending=0,
):
    return {
        "timestamp": datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc),
        "ticker": ticker,
        "left": left,
        "btc": btc,
        "brti": brti,
        "up": up,
        "down": down,
        "pending": pending,
    }


class HeartbeatIntegrityAuditTests(unittest.TestCase):
    def test_ok_when_heartbeats_are_separated(self):
        result = audit_heartbeat_integrity([
            rec("2026-09-10T15:00:00Z"),
            rec("2026-09-10T15:00:30Z"),
        ])
        self.assertEqual(result["status"], "OK")

    def test_detects_brti_availability_conflict(self):
        result = audit_heartbeat_integrity([
            rec("2026-09-10T15:00:00Z", brti=None),
            rec("2026-09-10T15:00:00.2Z", brti=77001.0),
        ])
        self.assertEqual(result["status"], "BRTI_AVAILABILITY_CONFLICTS")
        self.assertEqual(result["brti_availability_conflict_count"], 1)

    def test_detects_other_field_conflict(self):
        result = audit_heartbeat_integrity([
            rec("2026-09-10T15:00:00Z"),
            rec("2026-09-10T15:00:00.4Z", up=0.51),
        ])
        self.assertEqual(result["status"], "NEAR_DUPLICATE_FIELD_CONFLICTS")

    def test_detects_identical_duplicate(self):
        result = audit_heartbeat_integrity([
            rec("2026-09-10T15:00:00Z"),
            rec("2026-09-10T15:00:00.1Z"),
        ])
        self.assertEqual(result["status"], "IDENTICAL_NEAR_DUPLICATES")

    def test_different_contracts_are_not_paired(self):
        result = audit_heartbeat_integrity([
            rec("2026-09-10T15:00:00Z", ticker="A"),
            rec("2026-09-10T15:00:00.1Z", ticker="B"),
        ])
        self.assertEqual(result["status"], "OK")

    def test_parses_jsonl_brti_na(self):
        rows = parse_records([
            '{"timestamp":"2026-09-10T15:00:00Z","message":"LEAD_V6 HEARTBEAT | T | 10.00m | BTC 77000.00 | BRTI N/A | UP 0.500 | DOWN 0.500 | pending 0"}'
        ])
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["brti"])


if __name__ == "__main__":
    unittest.main()
