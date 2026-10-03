import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from sprint_evidence.monitoring import (AlertLatch, AlertStore, EARLY_RULE,
    REQUIRED_CHECKS, alert, check_system, inspect_receiver_database, main,
    performance_checkpoint, summarize_lane, utc, wilson)

NOW = "2026-09-29T20:00:00Z"


def healthy():
    return {"observed_at_utc": NOW, "admitted_until_utc": "2026-09-29T20:00:05Z",
            "admission": "QUALIFIED", "evidence_id": "health-evidence", "build_sha": "build",
            "run_id": "run", "producer_id": "producer", "clock_epoch": "epoch",
            "checks": {k: {"status": "PASS", "evidence_ids": ["original-"+k], "detail": "qualified fixture"} for k in REQUIRED_CHECKS}}


def row(lane="EARLY", contract="C1", **changes):
    metrics = {"correct": True, "ask_cents": 30., "seconds_remaining": 420.} if lane == "EARLY" else (
        {"linkage_complete": True, "opposing_ready_false_count": 2, "opposing_ready_true_count": 1, "hold_count": 2, "protect_count": 1}
        if lane == "FINAL" else {"ask_later_bid_valid": True, "v81_lifecycle_complete": True,
                                 "ask_cents": 57, "published_entry_cents": 40, "first_post_publication_ask_cents": 57,
                                 "target_first_count": 0, "stop_first_count": 1, "mfe_cents": 2, "mae_cents": -5})
    result = {"record_id": "record-"+contract, "contract_id": contract, "lane": lane,
              "policy_hash": "policy", "partition_id": "forward", "evidence_role": "PROSPECTIVE",
              "evidence_ids": ["original-"+contract], "assessed_at_utc": "2026-09-29T19:59:00Z",
              "official_close_utc": "2026-09-29T19:45:00Z", "status": "SIGNAL", "complete": True,
              "authoritative_settlement_id": "settled-"+contract, "metrics": metrics}
    result.update(changes)
    return result


class SystemTests(unittest.TestCase):
    def evaluate(self, data, now=NOW):
        return check_system(data, now_utc=now, expected_build="build", expected_run="run")

    def test_complete_witnessed_health(self):
        self.assertEqual(self.evaluate(healthy())["state"], "HEALTHY")

    def test_each_required_check_fail_closed(self):
        for name in REQUIRED_CHECKS:
            with self.subTest(name=name):
                data = healthy()
                del data["checks"][name]
                result = self.evaluate(data)
                self.assertEqual(result["state"], "UNAVAILABLE")
                item = result["alerts"][0]
                self.assertTrue(all(item[k] for k in ("what_changed", "why_it_matters", "affected", "evidence", "safest_next_check")))

    def test_pass_needs_evidence(self):
        data = healthy()
        data["checks"]["clock_certificate"]["evidence_ids"] = []
        self.assertEqual(self.evaluate(data)["state"], "UNAVAILABLE")

    def test_watch_drift_failure(self):
        data = healthy()
        for status, expected in (("WATCH", "WATCH"), ("CHANGED", "DRIFT"), ("FAIL", "UNAVAILABLE")):
            data["checks"]["native_cadence"]["status"] = status
            self.assertEqual(self.evaluate(data)["state"], expected)

    def test_expiry_future_restart_build_and_stale(self):
        for key,value in (("observed_at_utc", "2026-09-29T20:00:01Z"),
                          ("observed_at_utc", "2026-09-29T19:59:40Z"),
                          ("admitted_until_utc", "2026-09-29T19:59:59Z"),
                          ("clock_epoch", None), ("build_sha", "different"),
                          ("admission", "UNAVAILABLE")):
            data = healthy(); data[key] = value
            self.assertEqual(self.evaluate(data)["state"], "UNAVAILABLE")

    def test_malformed_timestamps_and_checks_do_not_crash(self):
        for data in (None, [], {"observed_at_utc": None}, {"observed_at_utc": 42}):
            self.assertEqual(self.evaluate(data)["state"], "UNAVAILABLE")
        data = healthy(); data["checks"] = []
        self.assertEqual(self.evaluate(data)["state"], "UNAVAILABLE")


class LaneTests(unittest.TestCase):
    def summarize(self, rows, lane="EARLY", contracts=("C1",)):
        return summarize_lane(lane, rows, eligible_contracts=contracts, now_utc=NOW, policy_hash="policy", partition_id="forward")

    def test_accuracy_economics_missing_denominator(self):
        result = self.summarize([row()], contracts=("C1", "C2"))
        self.assertEqual(result["state"], "UNAVAILABLE")
        self.assertEqual(result["coverage"], .5)
        self.assertEqual(result["unavailable_contracts"], 1)
        self.assertEqual(result["economics"]["ideal_25_35c"], 1)
        self.assertEqual(result["metrics"]["correct"]["count"], 1)
        self.assertLess(result["metrics"]["correct"]["wilson95"][0], .5)

    def test_duplicate_is_not_extra_contract(self):
        self.assertEqual(self.summarize([row(), row()])["signal_contracts"], 1)
        changed = row(); changed["metrics"]["correct"] = False
        self.assertEqual(self.summarize([row(), changed])["state"], "UNAVAILABLE")

    def test_historical_shadow_foreign_future_and_bad_metrics(self):
        examples = [row(evidence_role="HISTORICAL"), row(policy_hash="old-shadow"),
                    row(partition_id="development"), row(complete=False), row(authoritative_settlement_id=None),
                    row(official_close_utc="2026-09-29T20:15:00Z"), row(assessed_at_utc=None),
                    row(metrics={"correct": True, "ask_cents": float("nan")}), [], None]
        for sample in examples:
            self.assertEqual(self.summarize([sample])["state"], "UNAVAILABLE")

    def test_pass_is_not_missing_or_loss(self):
        result = self.summarize([row(status="PASS", metrics={})])
        self.assertEqual(result["pass_contracts"], 1)
        self.assertEqual(result["signal_contracts"], 0)
        self.assertEqual(result["metrics"]["correct"]["count"], 0)

    def test_final_opposition_strata_not_exit(self):
        result = self.summarize([row("FINAL")], "FINAL")
        self.assertEqual(result["metrics"]["opposing_ready_false_count"]["sum"], 2)
        self.assertEqual(result["metrics"]["opposing_ready_true_count"]["sum"], 1)
        self.assertNotIn("exit_count", result["metrics"])
        bad = row("FINAL"); bad["metrics"]["linkage_complete"] = False
        self.assertEqual(self.summarize([bad], "FINAL")["state"], "UNAVAILABLE")

    def test_scalp_published_entry_not_rebased(self):
        result = self.summarize([row("SCALP")], "SCALP")
        self.assertEqual(result["metrics"]["ask_cents"]["mean"], 57)
        self.assertEqual(result["metrics"]["published_entry_cents"]["mean"], 40)
        self.assertEqual(result["economics"]["at_most_50c"], 0)
        bad = row("SCALP"); bad["metrics"]["ask_later_bid_valid"] = False
        self.assertEqual(self.summarize([bad], "SCALP")["state"], "UNAVAILABLE")


class PerformanceTests(unittest.TestCase):
    def samples(self, n=140, correct=True):
        rows = []
        start = utc("2026-10-01T00:00:00Z")
        for i in range(n):
            when = (start+timedelta(days=i%7, minutes=15*(i//7))).isoformat()
            item = row(contract=str(i), official_close_utc=when)
            item["metrics"]["correct"] = correct
            rows.append(item)
        return rows

    def run_check(self, rows, rule=EARLY_RULE, **changes):
        options = dict(checkpoint_index=1, block_start_utc="2026-10-01T00:00:00Z",
                       block_end_utc="2026-10-08T00:00:00Z", now_utc="2026-10-08T00:00:00Z",
                       evidence_ids=["block-manifest"], anchor_utc="2026-10-01T00:00:00Z")
        options.update(changes)
        return performance_checkpoint(rule, rows, **options)

    def test_tiny_bad_sample_not_drift(self):
        result = self.run_check(self.samples(12, False))
        self.assertEqual(result["state"], "WATCH")
        self.assertEqual(result["reason"], "LIMITED_SAMPLE_NOT_DRIFT")

    def test_sufficient_bad_screen_and_no_retune(self):
        result = self.run_check(self.samples(correct=False))
        self.assertEqual(result["state"], "DRIFT")
        self.assertEqual(result["alerts"][0]["action"], "ALERT_AND_PRESERVE_EVIDENCE_ONLY")
        self.assertIn("dependence assumptions unverified", result["inference_limit"])

    def test_healthy_means_no_alarm_and_null_baseline_watch(self):
        self.assertEqual(self.run_check(self.samples())["state"], "HEALTHY")
        self.assertEqual(self.run_check(self.samples(), rule=None)["state"], "WATCH")

    def test_no_mixed_policy_duplicate_or_invalid_rows(self):
        samples = self.samples(); samples[2]["policy_hash"] = "another"
        self.assertEqual(self.run_check(samples)["state"], "UNAVAILABLE")
        samples = self.samples(); samples.append(samples[0])
        self.assertEqual(self.run_check(samples)["state"], "UNAVAILABLE")
        for sample in (None, [], row(official_close_utc=None)):
            self.assertEqual(self.run_check([sample])["state"], "UNAVAILABLE")

    def test_no_posthoc_shift_or_early_peek(self):
        self.assertEqual(self.run_check(self.samples(), anchor_utc="2026-09-30T00:00:00Z")["state"], "WATCH")
        self.assertEqual(self.run_check(self.samples(), now_utc="2026-10-07T23:59:00Z")["state"], "WATCH")


class OutboxTests(unittest.TestCase):
    def item(self):
        return alert("UNAVAILABLE", "CLOCK", "clock expired", "SYSTEM", ["cert-1"], "inspect cert").__dict__

    def test_latch_checkpoint_no_duplicate_or_unbounded_growth(self):
        latch = AlertLatch(maximum_keys=1)
        self.assertIsNotNone(latch.emit("clock", self.item()))
        self.assertIsNone(latch.emit("clock", self.item()))
        reloaded = AlertLatch(latch.checkpoint(), maximum_keys=1)
        self.assertIsNone(reloaded.emit("clock", self.item()))
        self.assertEqual(reloaded.emit("other", self.item())["state"], "UNAVAILABLE")

    def test_outbox_restart_duplicate_missing_and_quota(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder)/"alerts.sqlite")
            with self.assertRaises(ValueError): AlertStore(path)
            store = AlertStore(path, initialize=True, max_alerts=1)
            self.assertEqual(store.record("clock", self.item())["state"], "RECORDED")
            self.assertTrue(AlertStore(path).record("clock", self.item())["duplicate"])
            other = dict(self.item(), what_changed="NEW_CLOCK", alert_id="new")
            self.assertEqual(store.record("clock", other)["reason"], "ALERT_OUTBOX_FULL")
            with self.assertRaises(ValueError): AlertStore(path, initialize=True)
            Path(path).unlink()
            self.assertEqual(store.record("clock", self.item())["state"], "UNAVAILABLE")

    def test_store_locked_and_full_fail_contained(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder)/"alerts.sqlite")
            store = AlertStore(path, initialize=True)
            conn = sqlite3.connect(path); conn.execute("BEGIN IMMEDIATE")
            try:
                self.assertEqual(store.record("clock", self.item())["state"], "UNAVAILABLE")
            finally:
                conn.rollback(); conn.close()
            self.assertEqual(store.record("clock", self.item())["state"], "RECORDED")

    def test_receiver_bridge_never_qualifies_unobserved_health(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder)/"receiver.sqlite")
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE producer_events (producer TEXT,run TEXT,seq INTEGER,digest TEXT,raw BLOB,status TEXT,reason TEXT)")
            raw = json.dumps({"event": {"identity": {"build_sha": "build"}, "orders": False, "signal_only": True, "kind": "NATIVE_CYCLE", "prior_dropped": 1}})
            conn.execute("INSERT INTO producer_events VALUES (?,?,?,?,?,?,?)", ("producer", "run", 1, "hash", raw, "UNQUALIFIED_CLOCK", "GAP")); conn.commit(); conn.close()
            result = inspect_receiver_database(path, now_utc=NOW, expected_build="build", expected_run="run")
            self.assertEqual(result["state"], "UNAVAILABLE")
            self.assertTrue(any(a["what_changed"] == "DETACHED_EVIDENCE_GAP" for a in result["alerts"]))
            self.assertTrue(any(a["what_changed"] == "REAL_CLOCK_AND_COMPLETE_HEALTH_DETECTORS_NOT_ADMITTED" for a in result["alerts"]))

    def test_protocol_frozen_dates_and_long_horizon_untouched(self):
        protocol = json.loads((Path(__file__).parent/"sprint_protocol.json").read_text())
        self.assertEqual((utc(protocol["completion_deadline_utc"])-utc(protocol["mandate_utc"])).total_seconds(), 7*86400)
        self.assertEqual(protocol["latest_candidate_freeze_utc"], "2026-10-01T19:00:00Z")
        self.assertFalse(protocol["long_horizon_T0_activated"])
        self.assertIsNone(protocol["capture_T0_utc"])


if __name__ == "__main__":
    unittest.main()
