import json
import unittest

from v6_log_snapshot_normalizer_v1 import normalize_records, render_jsonl


class LogSnapshotNormalizerTests(unittest.TestCase):
    def test_railway_payload_filters_noise_and_keeps_timestamp(self):
        payload = {
            "deploy": [
                {"timestamp": "2026-09-10T12:00:00Z", "message": "Starting container"},
                {
                    "timestamp": "2026-09-10T12:00:01Z",
                    "message": "LEAD_V6 HEARTBEAT | A | 10.00m | BTC 1 | BRTI 1",
                },
            ]
        }
        result = normalize_records(json.dumps(payload))
        self.assertEqual(result["input_records"], 2)
        self.assertEqual(result["v6_records"], 1)
        self.assertEqual(result["noise_records"], 1)
        self.assertEqual(result["records"][0]["timestamp"], "2026-09-10T12:00:01Z")

    def test_raw_lines_are_supported(self):
        text = "noise\nLEAD_V6 CANDIDATE | V5_BASELINE | A | DOWN\n"
        result = normalize_records(text)
        self.assertEqual(result["v6_records"], 1)
        self.assertEqual(result["records"][0]["index"], 0)

    def test_jsonl_is_supported(self):
        text = "\n".join(
            [
                json.dumps({"timestamp": "t1", "message": "LEAD_V6 HEARTBEAT | A | x"}),
                json.dumps({"timestamp": "t2", "message": "LEAD_V6 HEARTBEAT | A | y"}),
            ]
        )
        result = normalize_records(text)
        self.assertEqual([r["timestamp"] for r in result["records"]], ["t1", "t2"])

    def test_duplicates_are_preserved(self):
        line = "LEAD_V6 RESULT | V6_QUALIFIED | A | DOWN"
        result = normalize_records(line + "\n" + line)
        self.assertEqual(result["v6_records"], 2)
        self.assertEqual(result["records"][0]["message"], result["records"][1]["message"])

    def test_render_jsonl_is_deterministic(self):
        records = [
            {"index": 0, "timestamp": None, "message": "LEAD_V6 HEARTBEAT | A | x"}
        ]
        first = render_jsonl(records)
        second = render_jsonl(records)
        self.assertEqual(first, second)
        parsed = json.loads(first)
        self.assertEqual(parsed["index"], 0)

    def test_empty_input_is_clean(self):
        result = normalize_records("   ")
        self.assertEqual(
            {k: v for k, v in result.items() if k != "records"},
            {"input_records": 0, "v6_records": 0, "noise_records": 0},
        )
        self.assertEqual(result["records"], [])


if __name__ == "__main__":
    unittest.main()
