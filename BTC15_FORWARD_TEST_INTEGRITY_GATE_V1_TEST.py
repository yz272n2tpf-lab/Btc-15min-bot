#!/usr/bin/env python3
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import BTC15_FORWARD_TEST_INTEGRITY_GATE_V1 as gate


class IntegrityGateTests(unittest.TestCase):
    def _event(self, ts, msg):
        return {"timestamp": gate.parse_ts(ts), "message": msg}

    def test_complete_contract_with_degradation_is_preserved_and_flagged(self):
        ticker = "KXBTC15M-26SEP092000-00"
        events = [
            self._event("2026-09-10T00:00:30Z", f"LEAD_V6 HEARTBEAT | {ticker} | 14.5m | BTC 1 | BRTI 2 | UP 0.5 | DOWN 0.5 | pending 0"),
            self._event("2026-09-10T00:01:00Z", f"LEAD_V6 HEARTBEAT | {ticker} | 14.0m | BTC 1 | BRTI N/A | UP 0.5 | DOWN 0.5 | pending 0"),
            self._event("2026-09-10T00:01:30Z", f"LEAD_V6 HEARTBEAT | {ticker} | 13.5m | BTC 1 | BRTI N/A | UP 0.5 | DOWN 0.5 | pending 0"),
            self._event("2026-09-10T00:02:00Z", f"LEAD_V6 HEARTBEAT | {ticker} | 13.0m | BTC 1 | BRTI 2 | UP 0.5 | DOWN 0.5 | pending 0"),
            self._event("2026-09-10T00:15:20Z", f"LEAD_V6 CONTRACT_SUMMARY | {ticker} | V5 n=0 | V6 n=0 | rejects price=1 degraded=7 base=2 high=0"),
        ]
        report = gate.audit(events)
        row = report["contracts"][0]
        self.assertTrue(row["collection_complete"])
        self.assertEqual(row["brti_na"], 2)
        self.assertEqual(row["max_brti_na_streak"], 2)
        self.assertIn("BRTI_DEGRADED", row["flags"])
        self.assertEqual(row["rejects"]["degraded"], 7)

    def test_heartbeat_gap_is_flagged(self):
        ticker = "KXBTC15M-26SEP092015-15"
        events = [
            self._event("2026-09-10T00:15:30Z", f"LEAD_V6 HEARTBEAT | {ticker} | 14.5m | BTC 1 | BRTI 2 | UP 0.5 | DOWN 0.5 | pending 0"),
            self._event("2026-09-10T00:17:00Z", f"LEAD_V6 HEARTBEAT | {ticker} | 13.0m | BTC 1 | BRTI 2 | UP 0.5 | DOWN 0.5 | pending 0"),
            self._event("2026-09-10T00:30:20Z", f"LEAD_V6 CONTRACT_SUMMARY | {ticker} | V5 n=0 | V6 n=0 | rejects price=0 degraded=0 base=0 high=0"),
        ]
        row = gate.audit(events, gap_seconds=75.0)["contracts"][0]
        self.assertFalse(row["collection_complete"])
        self.assertIn("HEARTBEAT_GAP", row["flags"])
        self.assertEqual(row["max_heartbeat_gap_seconds"], 90.0)

    def test_loader_accepts_railway_json(self):
        payload = {
            "deploy": [
                {
                    "timestamp": "2026-09-10T00:00:30Z",
                    "message": "SCALP LEAD SHADOW V6 START | NO ORDERS",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "logs.json"
            p.write_text(json.dumps(payload), encoding="utf-8")
            events = gate.load_events(p)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["timestamp"], datetime(2026, 9, 10, 0, 0, 30, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
