import json
from pathlib import Path
import tempfile
import unittest

from integrity_sentinel.recorder_core_v1 import (
    AppendOnlyHashChainLedger, membership_events, source_sample_body,
)
from integrity_sentinel.source_adapters_v1 import adapt_brti_shared


class RecorderCoreTests(unittest.TestCase):
    def test_hash_chain_round_trip_and_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "evidence.jsonl"
            ledger = AppendOnlyHashChainLedger(path)
            ledger.append({"record_type": "X", "n": 1})
            ledger.append({"record_type": "X", "n": 2})
            self.assertEqual(ledger.verify().records, 2)
            reopened = AppendOnlyHashChainLedger(path)
            self.assertEqual(reopened.status().last_sequence, 2)
            reopened.append({"record_type": "X", "n": 3})
            self.assertEqual(reopened.verify().records, 3)

    def test_hash_chain_detects_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "evidence.jsonl"
            ledger = AppendOnlyHashChainLedger(path)
            ledger.append({"record_type": "X", "n": 1})
            row = json.loads(path.read_text())
            row["body"]["n"] = 999
            path.write_text(json.dumps(row) + "\n")
            with self.assertRaises(ValueError):
                AppendOnlyHashChainLedger(path)

    def test_strict_json_rejects_nan(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = AppendOnlyHashChainLedger(Path(td) / "x.jsonl")
            with self.assertRaises(ValueError):
                ledger.append({"bad": float("nan")})

    def test_source_sample_preserves_payload_hash_and_no_orders(self):
        body = source_sample_body(
            source="brti_shared", observed_at_utc="2026-09-17T12:00:00Z",
            http_status=200, latency_ms=5.0, payload={"x": 1},
            normalized={"brti_age_sec": 1.0},
        )
        self.assertFalse(body["orders"])
        self.assertFalse(body["source_mutation"])
        self.assertEqual(len(body["payload_sha256"]), 64)

    def test_early_membership_uses_exact_contract_ids(self):
        payload = {"live": {"call_records": [
            {"contract": "KXBTC15M-TEST", "side": "UP", "ask": .31}
        ], "settled_records": []}}
        rows = membership_events("early_membership", payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["contract_id"], "KXBTC15M-TEST")
        self.assertFalse(rows[0]["rescore_performed"])

    def test_final_membership_dictionary_key_becomes_contract(self):
        payload = {"live": {"lock_records": {
            "KXBTC15M-TEST": {"side": "DOWN", "preferred_ask": .49}
        }}}
        rows = membership_events("final_membership", payload)
        self.assertEqual(rows[0]["record"]["contract"], "KXBTC15M-TEST")

    def test_brti_adapter_preserves_negative_states_and_counters(self):
        payload = {
            "status": "PRIMARY_ERROR", "clean_for_qualification": False,
            "age_ms": 120000, "sequence": 10, "upstream_attempts": 100,
            "upstream_ok": 80, "upstream_errors": 20, "http_429": 15,
            "last_error_type": "http_429",
        }
        row = adapt_brti_shared(payload)
        self.assertFalse(row["brti_feed_clean"])
        self.assertEqual(row["brti_age_sec"], 120.0)
        self.assertEqual(row["brti_429_total"], 15)


if __name__ == "__main__":
    unittest.main()
