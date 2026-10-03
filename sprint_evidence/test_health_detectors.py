from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from sprint_evidence.health_detectors import inspect_database, inspect_events
from sprint_evidence.passive_capture import digest, pack
from directional_shadow_examples_v1 import fixture as legacy_fixture


def fixture(*args, **kwargs):
    state = legacy_fixture(*args, **kwargs)
    state["generated_utc"] = state["source_timestamp_utc"]
    state["market"].update(target=100000., brti_ready=True, brti_age_seconds=.1)
    state["parity"] = {"status": "PASS", "contract": state["contract"], "api_contract": state["contract"], "timestamp_utc": state["source_timestamp_utc"]}
    return state


def packet(seq=1, kind="PROTECTED_GENERATION", state=None, **body_changes):
    state = fixture() if state is None else state
    body = {"state": state, "state_sha256": digest(pack(state)), "generation_id": "generation-1"}
    if kind == "PROTECTED_FILE_WRITE_COMPLETED":
        body.update(linkage_status="OBSERVED_SAME_OBJECT_UNCHANGED", browser_delivery_utc=None)
    body.update(body_changes)
    event = {"identity": {"producer_id": "protected", "run_id": "run", "boot_id": "boot", "build_sha": "build"},
             "sequence": seq, "kind": kind, "body": body, "orders": False, "signal_only": True,
             "prior_dropped": 0, "hook_read": {"clock_qualified": False}}
    return seal(event)


def seal(event):
    return {"event": event, "sha256": digest(pack(event))}


def codes(result):
    return {x["what_changed"] for x in result["findings"]}


class RecordedDiagnosticsTests(unittest.TestCase):
    def test_valid_recorded_state_never_healthy(self):
        raw = packet(); original = deepcopy(raw)
        result = inspect_events([raw])
        self.assertEqual(result["state"], "UNAVAILABLE")
        self.assertEqual(result["source_timestamps_created"], 0)
        self.assertEqual(result["strategy_mutations"], 0)
        self.assertEqual(result["findings"], [])
        self.assertEqual(raw, original)

    def test_parity_ticker_start_clock_flags_and_stale_context(self):
        state = fixture()
        state["parity"].update(api_contract="another", target_match="False", clock_match=False)
        result = inspect_events([packet(state=state)])
        self.assertIn("RECORDED_TICKER_PARITY_MISMATCH", codes(result))
        self.assertIn("RECORDED_PARITY_TARGET_MATCH_FALSE", codes(result))
        self.assertIn("RECORDED_PARITY_CLOCK_MATCH_FALSE", codes(result))
        for item in result["findings"]:
            self.assertTrue(all(item[k] for k in ("what_changed", "why_it_matters", "affected", "evidence", "safest_next_check")))

    def test_recorded_window_mismatch_not_clock_certification(self):
        state = fixture(); state["timer"]["seconds_left"] = 700
        result = inspect_events([packet(state=state)])
        self.assertIn("RECORDED_WINDOW_LABEL_CONFLICT", codes(result))
        state = fixture(); state["contract"] = "WRONG"
        self.assertIn("RECORDED_TICKER_CLOSE_CONFLICT", codes(inspect_events([packet(state=state)])))

    def test_frozen_two_second_tolerance_and_invalid_remaining(self):
        state = fixture(); state["timer"]["seconds_left"] += 2
        self.assertNotIn("RECORDED_WINDOW_LABEL_CONFLICT", codes(inspect_events([packet(state=state)])))
        state["timer"]["seconds_left"] += .0001
        self.assertIn("RECORDED_WINDOW_LABEL_CONFLICT", codes(inspect_events([packet(state=state)])))
        state["timer"]["seconds_left"] = 10**50
        self.assertIn("RECORDED_REMAINING_OUTSIDE_CONTRACT", codes(inspect_events([packet(state=state)])))

    def test_brti_boundary_wait_and_telemetry_not_source(self):
        for value, invalid in ((5, False), (5.000001, True), (-.1, True)):
            state = fixture(); state["market"]["brti_age_seconds"] = value
            result = inspect_events([packet(state=state)])
            self.assertEqual("RECORDED_BRTI_AGE_OUTSIDE_5S" in codes(result), invalid)
            self.assertEqual(result["source_timestamps_created"], 0)
        state = fixture(); state["market"]["brti_ready"] = False; state["health"]["source_fresh"] = False
        result = inspect_events([packet(state=state)])
        self.assertIn("RECORDED_BRTI_WAIT_OR_NOT_FRESH", codes(result))
        self.assertIn("RECORDED_SOURCE_FRESH_FALSE", codes(result))

    def test_crossed_invalid_and_absent_quotes(self):
        for value in (.99, 1.01, -.01):
            state = fixture(); state["market"]["up_bid"] = value
            self.assertIn("RECORDED_INVALID_OR_CROSSED_UP_QUOTE", codes(inspect_events([packet(state=state)])))
        state = fixture(); state["market"]["up_bid"] = None
        result = inspect_events([packet(state=state)])
        self.assertIn("up_original_quote_pair", result["missing"])
        self.assertEqual(result["state"], "UNAVAILABLE")

    def test_exact_early_final_source_and_ready_false_not_exit(self):
        state = fixture(final_ready=False, final_side="DOWN")
        self.assertEqual(inspect_events([packet(state=state)])["findings"], [])
        state["final"]["source"] = "startup_two_final"; state["early"]["source"] = "shadow"
        result = inspect_events([packet(state=state)])
        self.assertIn("WRONG_FINAL_SOURCE_LABEL", codes(result)); self.assertIn("WRONG_EARLY_SOURCE_LABEL", codes(result))
        self.assertFalse(any("EXIT" in code for code in codes(result)))

    def test_start_price_immutable_per_contract_and_epoch(self):
        changed = fixture(); changed["market"]["target"] += 1
        result = inspect_events([packet(), packet(seq=2, state=changed, generation_id="g2")])
        self.assertIn("RECORDED_CONTRACT_START_PRICE_CHANGED", codes(result))
        p2 = packet(seq=1, state=changed); p2["event"]["identity"]["boot_id"] = "new"
        self.assertNotIn("RECORDED_CONTRACT_START_PRICE_CHANGED", codes(inspect_events([packet(), seal(p2["event"])])))

    def test_explicit_generation_write_link_not_browser_delivery(self):
        result = inspect_events([packet(), packet(seq=2, kind="PROTECTED_FILE_WRITE_COMPLETED")])
        self.assertEqual(len(result["observed"]), 1)
        self.assertFalse(result["observed"][0]["browser_delivery_proven"])
        self.assertEqual(result["state"], "UNAVAILABLE")

    def test_generation_missing_outside_slice_conflict_and_rewrite(self):
        result = inspect_events([packet(seq=2, kind="PROTECTED_FILE_WRITE_COMPLETED")])
        self.assertIn("generation_outside_archive_slice", result["missing"])
        changed = fixture(); changed["market"]["target"] += 1
        result = inspect_events([packet(), packet(seq=2, kind="PROTECTED_FILE_WRITE_COMPLETED", state=changed)])
        self.assertIn("PROTECTED_WRITE_GENERATION_CONFLICT", codes(result))
        result = inspect_events([packet(), packet(seq=2, state=changed)])
        self.assertIn("IMMUTABLE_GENERATION_REWRITTEN", codes(result))
        result = inspect_events([packet(seq=2, kind="PROTECTED_FILE_WRITE_COMPLETED", generation_id=None, linkage_status="UNAVAILABLE_GENERATION_LINK")])
        self.assertIn("PROTECTED_WRITE_GENERATION_LINK_UNAVAILABLE", codes(result))

    def test_sequence_build_drop_and_no_order_checks(self):
        second = packet(seq=3); second["event"]["prior_dropped"] = 1; second["event"]["orders"] = True
        result = inspect_events([packet(), seal(second["event"])], expected_build="another")
        for code in ("RECORDED_SEQUENCE_GAP_OR_REPLAY", "PRODUCER_REPORTED_DROPPED_EVIDENCE", "PRODUCER_BUILD_MISMATCH", "SIGNAL_ONLY_FLAG_VIOLATION_OR_MISSING"):
            self.assertIn(code, codes(result))

    def test_native_target_ticker_quote_brti_facts(self):
        body = {"ticker": "A", "target": 100, "snap": {"contract": "B", "target": 99, "up_bid": .8, "up_ask": .3}, "_brti_contract": {"ready": False, "age": 6}}
        sample = packet(kind="NATIVE_WAIT"); sample["event"]["body"] = body
        result = inspect_events([seal(sample["event"])])
        for code in ("RECORDED_NATIVE_WAIT", "NATIVE_SNAPSHOT_TICKER_CONFLICT", "NATIVE_SNAPSHOT_START_PRICE_CONFLICT", "RECORDED_BRTI_AGE_OUTSIDE_5S", "RECORDED_INVALID_OR_CROSSED_UP_QUOTE"):
            self.assertIn(code, codes(result))

    def test_hash_conflict_and_malformed_fail_closed(self):
        changed = packet(); changed["event"]["orders"] = True
        self.assertIn("DETACHED_HASH_MISMATCH", codes(inspect_events([changed])))
        self.assertEqual(inspect_events([None, [], {"event": None}])["state"], "UNAVAILABLE")
        self.assertEqual(inspect_events([packet()]*513)["reason"], "MALFORMED_OR_OVERSIZED_ARCHIVE_SLICE")
        sample = packet(); sample["event"]["body"]["state_sha256"] = "false"
        self.assertIn("PROTECTED_STATE_HASH_MISMATCH", codes(inspect_events([seal(sample["event"])])))

    def test_extreme_timestamp_labels_fail_closed(self):
        state = fixture()
        state["source_timestamp_utc"] = "9999-12-31T23:59:00+00:00"
        state["timer"]["close_utc"] = "9999-12-31T23:59:00+00:00"
        result = inspect_events([packet(state=state)])
        self.assertIn("RECORDED_WINDOW_LABEL_OVERFLOW", codes(result))
        self.assertEqual(result["state"], "UNAVAILABLE")

    def test_receiver_database_is_read_only_and_retains_exact_order(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"receiver.sqlite"
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE producer_events (raw BLOB)")
                for item in (packet(), packet(seq=2, kind="PROTECTED_FILE_WRITE_COMPLETED")):
                    db.execute("INSERT INTO producer_events VALUES (?)", (pack(item),))
            original = path.read_bytes()
            result = inspect_database(path)
            self.assertEqual(len(result["observed"]), 1)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(inspect_database(path.parent/"missing")["state"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
