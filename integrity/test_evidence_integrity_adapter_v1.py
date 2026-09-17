import unittest
from datetime import datetime, timedelta, timezone

from integrity.evidence_integrity_adapter_v1 import AdapterPolicy, aggregate_contract


BASE = datetime(2026, 9, 17, 3, 0, tzinfo=timezone.utc)


def event(i: int, left: float, **overrides):
    row = {
        "contract_id": "KXBTC15M-TEST",
        "observed_at_utc": (BASE + timedelta(seconds=i)).isoformat(),
        "seconds_left": left,
        "service_deployment_ok": True,
        "process_alive": True,
        "storage_ok": True,
        "collector_advancing": True,
        "scorer_advancing": True,
        "runtime_config_match": True,
        "cutoff_valid": True,
        "kalshi_age_sec": 1.0,
        "brti_age_sec": 1.0,
        "coinbase_age_sec": 1.0,
        "parity_ok": True,
        "brti_attempts_total": 1000 + i,
        "brti_429_total": 10,
    }
    row.update(overrides)
    return row


def clean_path():
    return [event(i, 896 - i) for i in range(0, 841, 5)]


class AdapterTests(unittest.TestCase):
    def test_clean_full_path(self):
        r = aggregate_contract("KXBTC15M-TEST", clean_path())
        self.assertTrue(r["has_start_observation"])
        self.assertTrue(r["has_end_observation"])
        self.assertTrue(r["continuous_path_complete"])
        self.assertEqual(r["rollover_lag_sec"], 4.0)
        self.assertEqual(r["max_source_gap_sec"], 5.0)
        self.assertEqual(r["max_clock_drift_sec"], 0.0)

    def test_late_rollover_is_not_start_complete(self):
        rows = [event(i, 880 - i) for i in range(0, 821, 5)]
        r = aggregate_contract("KXBTC15M-TEST", rows)
        self.assertFalse(r["has_start_observation"])
        self.assertFalse(r["continuous_path_complete"])
        self.assertEqual(r["rollover_lag_sec"], 20.0)

    def test_middle_gap_breaks_continuity(self):
        rows = clean_path()
        rows = [r for r in rows if not (300 <= (datetime.fromisoformat(r["observed_at_utc"]).replace(tzinfo=None) - BASE.replace(tzinfo=None)).total_seconds() <= 330)]
        r = aggregate_contract("KXBTC15M-TEST", rows)
        self.assertFalse(r["continuous_path_complete"])
        self.assertGreater(r["max_source_gap_sec"], 10.0)

    def test_contract_clock_jump_breaks_continuity(self):
        rows = clean_path()
        rows[30] = dict(rows[30], seconds_left=rows[30]["seconds_left"] - 30)
        r = aggregate_contract("KXBTC15M-TEST", rows)
        self.assertFalse(r["continuous_path_complete"])
        self.assertGreater(r["max_clock_drift_sec"], 2.0)

    def test_operational_only_heartbeat_cannot_fill_path_gap(self):
        rows = [event(0, 896), event(20, 876), event(840, 56)]
        for i in range(5, 840, 5):
            if i in {20}:
                continue
            rows.append({
                "contract_id": "KXBTC15M-TEST",
                "observed_at_utc": (BASE + timedelta(seconds=i)).isoformat(),
                "service_deployment_ok": True,
                "process_alive": True,
            })
        r = aggregate_contract("KXBTC15M-TEST", rows)
        self.assertFalse(r["continuous_path_complete"])
        self.assertEqual(r["path_sample_count"], 3)

    def test_missing_feed_measurement_stays_missing(self):
        rows = clean_path()
        for row in rows:
            row.pop("brti_age_sec", None)
        r = aggregate_contract("KXBTC15M-TEST", rows)
        self.assertIsNone(r["brti_max_age_sec"])

    def test_any_known_operational_false_dominates(self):
        rows = clean_path()
        rows[40]["storage_ok"] = False
        r = aggregate_contract("KXBTC15M-TEST", rows)
        self.assertFalse(r["storage_ok"])

    def test_counter_reset_returns_unknown_delta(self):
        rows = clean_path()
        rows[-1]["brti_attempts_total"] = 1
        rows[-1]["brti_429_total"] = 0
        r = aggregate_contract("KXBTC15M-TEST", rows)
        self.assertIsNone(r["brti_attempts"])
        self.assertIsNone(r["brti_429_count"])

    def test_parity_fail_count_derived_from_samples(self):
        rows = clean_path()
        rows[10]["parity_ok"] = False
        r = aggregate_contract("KXBTC15M-TEST", rows)
        self.assertEqual(r["parity_fail_count"], 1)


if __name__ == "__main__":
    unittest.main()
