#!/usr/bin/env python3
"""Synthetic regression fixtures; these tests provide no market efficacy evidence."""
import copy
import csv
import io
import json
import threading
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener

import scalp_nextgen_shadow_v2 as runtime
import scalp_nextgen_v2_core as v2

T0 = datetime(2026, 9, 17, tzinfo=timezone.utc)
CUTOFF = T0.isoformat()


def stamp(seconds):
    return (T0 + timedelta(seconds=seconds)).isoformat()


def candidate(cid="A", contract="C", offset=5, ask=.45, strong=False):
    return {"record_type": "CANDIDATE", "candidate_id": cid, "contract": contract,
            "timestamp_utc": stamp(offset), "entry_ask": ask, "side": "UP",
            "seconds_left": 900-offset, "btc_move30_side": 20,
            "btc_move5_norm": .8, "btc_move15_norm": .7,
            "confirm_count": 2 if strong else 1, "structure_ok": "1.0",
            "brti_status": "PRIMARY_OK", "btc_against_side": "0.0",
            "brti_against_side": False, "dual_reversal_evidence": "false"}


def path(c, elapsed, gain, ask=None):
    bid = c["entry_ask"] + gain
    return {"record_type": "PATH", "candidate_id": c["candidate_id"], "contract": c["contract"],
            "timestamp_utc": (v2.strict_time(c["timestamp_utc"]) + timedelta(seconds=elapsed)).isoformat(),
            "elapsed_sec": elapsed, "exec_gain": gain, "current_bid": bid,
            "current_ask": bid+.005 if ask is None else ask}


def opportunity(strong=False, ask=.45, gains=None):
    c = candidate(ask=ask, strong=strong)
    values = gains if gains is not None else [(2, 0), (4, .01), (8, .08), (10, .077), (12, .074), (14, .072), (20, .02)]
    paths = [path(c, t, g) for t, g in values]
    rows = [c, *paths, {"record_type": "RESULT", "candidate_id": "A"}]
    return v2.q.build_serial_opportunities(rows)[0]


def fixture_rows():
    rows = []
    # Quiet full contract remains in the coverage denominator.
    for contract in ("C", "QUIET"):
        rows += [{"record_type": "SNAPSHOT", "contract": contract,
                  "timestamp_utc": stamp(t), "seconds_left": 900-t} for t in (0, 899)]
    for cid, offset, ask, strong in (("A", 5, .45, True), ("B", 50, .65, False)):
        c = candidate(cid, offset=offset, ask=ask, strong=strong)
        rows.append(c)
        values = [(2, 0), (4, .01), (8, .08), (10, .077), (12, .074), (14, .072), (20, .02)]
        if cid == "B": values += [(25, -.17), (30, -.09), (40, -.15)]
        rows.extend(path(c, t, g) for t, g in values)
        rows.append({"record_type": "RESULT", "candidate_id": cid, "contract": "C",
                     "timestamp_utc": stamp(offset+60), "seconds_left": 900-offset-60})
    rows += [{"record_type": "SNAPSHOT", "contract": "OLD", "timestamp_utc": stamp(t),
              "seconds_left": left} for t, left in ((-1, 900), (898, 1))]
    rows += [{"record_type": "SNAPSHOT", "contract": "PARTIAL", "timestamp_utc": stamp(800), "seconds_left": 100}]
    # Exercise the real CSV string schema, not only Python-number fixtures.
    fields = sorted({k for r in rows for k in r})
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fields)
    writer.writeheader()
    writer.writerows(rows)
    return list(csv.DictReader(io.StringIO(buf.getvalue())))


class Decisions(unittest.TestCase):
    def test_strong_confirms_without_future_outcomes(self):
        op = opportunity(True, gains=[])
        rec = v2.dynamic_verify_record(op)
        self.assertEqual(rec["decision_reason"], "IMMEDIATE_STRONG")
        self.assertEqual(rec["actual_delay_sec"], 0)
        self.assertFalse(rec["movement_scoreable"])
        self.assertIsNone(rec["plus5"])
        self.assertEqual(v2.econ_summary([rec], 1, 1)["unscoreable_entries"], 1)

    def test_missing_safety_flags_prevent_immediate_strong(self):
        op = opportunity(True, gains=[])
        del op["_candidate"]["dual_reversal_evidence"]
        self.assertIsNone(v2.dynamic_verify_decision(op))

    def test_weak_requires_two_distinct_events(self):
        op = opportunity()
        decision = v2.dynamic_verify_decision(op)
        self.assertEqual(decision["entry_elapsed_sec"], 4)
        op["_paths"] = [op["_paths"][1], copy.deepcopy(op["_paths"][1])]
        self.assertIsNone(v2.dynamic_verify_decision(op))

    def test_future_mutation_does_not_change_decision(self):
        op = opportunity()
        op["_paths"] = op["_paths"][:2]
        before = v2.dynamic_verify_decision(op)
        op["_paths"].append(path(op["_candidate"], 9, -.20))
        op.update(plus10=1, protected_exit_gain=.40, peak_gain=.90)
        self.assertEqual(v2.dynamic_verify_decision(op), before)

    def test_same_timestamp_with_different_elapsed_is_not_new_evidence(self):
        op = opportunity(gains=[(2, .01), (2.1, .01)])
        op["_paths"][1]["timestamp_utc"] = op["_paths"][0]["timestamp_utc"]
        self.assertIsNone(v2.dynamic_verify_decision(op))

    def test_label_field_does_not_confirm(self):
        op = opportunity(gains=[(2, -.02), (4, -.01)])
        for row in op["_paths"]: row["exec_gain"] = .20
        self.assertIsNone(v2.dynamic_verify_decision(op))

    def test_missing_quote_and_long_gap_reset_confirmation(self):
        for case in ("missing", "gap"):
            op = opportunity(gains=[(2, .01), (4, .01), (6, .01)])
            if case == "missing": del op["_paths"][1]["current_bid"]
            else: op["_paths"] = [op["_paths"][0], path(op["_candidate"], 15, .01)]
            self.assertIsNone(v2.dynamic_verify_decision(op), case)

    def test_invalid_clocks_chase_and_timeout_are_rejected(self):
        for case in ("negative", "conflict", "chase", "timeout", "crossed"):
            op = opportunity(gains=[(2, .01), (4, .01)])
            for row in op["_paths"]:
                if case == "negative": row["elapsed_sec"] = -1
                if case == "conflict": row["timestamp_utc"] = stamp(-1)
                if case == "chase": row["current_ask"] = .49
                if case == "crossed": row["current_bid"] = .90
                if case == "timeout": row.update(elapsed_sec=40, timestamp_utc=stamp(45))
            self.assertIsNone(v2.dynamic_verify_decision(op), case)

    def test_scoring_excludes_pre_entry_peak(self):
        op = opportunity(ask=.65, gains=[(2, .20), (8, -.17), (12, -.15)])
        rec = v2.selective_pullback_record(op, "V2_PRICE_DISCIPLINED")
        self.assertEqual(rec["entry_elapsed_sec"], 8)
        self.assertFalse(rec["plus5"])
        self.assertAlmostEqual(rec["peak_gain"], .015)
        self.assertFalse(rec["protected_exit_observed"])

    def test_pullback_immediate_has_complete_accounting(self):
        rec = v2.selective_pullback_record(opportunity(True), "V2_BALANCED")
        summary = v2.econ_summary([rec], 1, 1)
        self.assertEqual(summary["movement_scoreable_entries"], 1)
        self.assertEqual(summary["protected_exit_signals"], 1)
        self.assertEqual(summary["avg_entry_improvement_c_vs_candidate"], 0)
        self.assertIsNotNone(summary["one_lot_taker_taker_avg_net_c"])

    def test_pullback_lanes_are_distinct_for_expensive_strong(self):
        op = opportunity(True, ask=.65, gains=[(2, -.17), (8, -.09)])
        self.assertEqual(v2.selective_pullback_decision(op, "V2_BALANCED")["entry_elapsed_sec"], 0)
        self.assertEqual(v2.selective_pullback_decision(op, "V2_PRICE_DISCIPLINED")["entry_elapsed_sec"], 2)

    def test_missing_pullback_remains_a_skip(self):
        op = opportunity(ask=.65)
        self.assertIsNone(v2.selective_pullback_record(op, "V2_BALANCED"))
        self.assertEqual(v2.econ_summary([], 1, 1)["unavailable_or_skipped_entries"], 1)


class WatchAndEconomics(unittest.TestCase):
    def test_trend_can_warn_materially_earlier_with_exact_same_exit(self):
        op = opportunity()
        records = v2.watch_records([op])
        v1, vnew = records["V1_1C"][0], records["V2_FALLING_TREND"][0]
        self.assertEqual(vnew["warning_time_sec"], 12)
        self.assertEqual(v1["warning_time_sec"], 20)
        self.assertEqual(vnew["exit_time_sec"], v1["exit_time_sec"])
        self.assertEqual(vnew["exit_gain"], v1["exit_gain"])
        self.assertEqual(vnew["one_lot_taker_taker_net_c"], v1["one_lot_taker_taker_net_c"])
        summary = v2.summarize_watch(records)["V2_FALLING_TREND"]
        self.assertEqual(summary["paired_lead_improvement_sec_vs_v1_1c"], 8)

    def test_unresolved_warning_is_not_labeled_false(self):
        op = opportunity(gains=[(2, .08), (4, .077), (6, .074)])
        summary = v2.summarize_watch(v2.watch_records([op]))["V2_FALLING_TREND"]
        self.assertEqual(summary["unresolved_warnings"], 1)
        self.assertEqual(summary["warning_without_exit_rate"], 1)
        self.assertEqual(summary["false_warning_proxy_new_high_rate"], 0)

    def test_frozen_watch_economics_boundary_discrepancy_is_disclosed(self):
        op = opportunity(gains=[(1, .0499999999999), (2, .0)])
        summary = v2.summarize_watch(v2.watch_records([op]))["V1_1C"]
        self.assertEqual(summary["frozen_exit_signals"], 1)
        self.assertEqual(summary["legacy_economics_exit_discrepancies"], 1)
        self.assertEqual(summary["protected_exits_with_fee_scores"], 0)
        self.assertIsNone(summary["one_lot_taker_taker_avg_net_c"])

    def test_recovery_is_separately_counted(self):
        op = opportunity(gains=[(2, .08), (4, .077), (6, .074), (8, .09)])
        r = v2.watch_measure(op, "V2_FALLING_TREND")
        self.assertTrue(r["recovered_new_high_after_warning"])
        self.assertFalse(r["unresolved_warning"])

    def test_opportunity_two_only_and_omitted_economics_visible(self):
        first, second = opportunity(), opportunity(ask=.65)
        second.update(candidate_id="B", opportunity_index=2)
        records = v2.scalp2_records([first, second])
        summary = v2.summarize_family(records, records["CONTROL_V1_SCALP2"], 2)
        self.assertEqual(summary["CONTROL_V1_SCALP2"]["signals"], 1)
        self.assertEqual(summary["AFFORDABLE_LE50"]["signals"], 0)
        self.assertEqual(summary["AFFORDABLE_LE50"]["paired_vs_immediate_control"]["omitted_control_protected_exits"], 1)

    def test_unprotected_outcomes_never_become_zero_profit(self):
        rec = v2.score_entry(opportunity(True, gains=[]), v2.entry_decision(.45, 0, "TEST"))
        summary = v2.econ_summary([rec], 1, 1)
        self.assertEqual(summary["without_protected_exit"], 1)
        self.assertIsNone(summary["one_lot_taker_taker_avg_net_c"])
        self.assertIsNone(summary["plus5_rate"])


class IntegrationAndRuntime(unittest.TestCase):
    def analyze(self):
        return runtime.analyze_rows(fixture_rows(), "fixture", 123, CUTOFF, development=True)

    def test_real_csv_full_pipeline_quiet_denominator_and_cutoff(self):
        state = self.analyze()
        self.assertTrue(state["ok"])
        self.assertEqual(state["future_full_contracts"], 2)
        self.assertEqual(state["serial_signals"], 2)
        self.assertEqual(state["scalp2_economics_v2"]["CONTROL_V1_SCALP2"]["signals"], 1)
        self.assertEqual(state["candidate_verify_v2"]["V1_IMMEDIATE"]["true_contract_coverage"], .5)
        self.assertEqual(state["selective_pullback_v2"]["V2_BALANCED"]["movement_scoreable_entries"], 2)
        self.assertTrue(state["runtime_integrity"]["all_checks_pass"])
        self.assertFalse(state["prospective_window"])
        self.assertFalse(state["evidence_readiness"]["sample_ready"])
        json.dumps(state, allow_nan=False)

    def test_frozen_fixed_delays_and_pullbacks_match_imported_controls(self):
        op = opportunity()
        lanes = v2.verify_records([op])
        for delay in (5., 10., 15., 30.):
            expected, _ = v2.verify_v1.build_policy_records([op], delay)
            self.assertEqual(lanes[f"V1_FIXED_{int(delay)}S"], expected)
        for target in v2.pullback_v1.TARGETS:
            for window in v2.pullback_v1.WINDOWS_SEC:
                r = v2.pullback_v1.replay_from_pullback(op, target, window)
                self.assertEqual(v2.pullback_records([op])[f"V1_LE{int(target*100)}_{int(window)}S"], [] if r is None else [r])

    def test_incomplete_family_and_false_readiness_fail_closed(self):
        state = self.analyze()
        state["selective_pullback_v2"].pop("V1_LE35_60S")
        self.assertFalse(runtime.integrity_report(state)["all_checks_pass"])
        state = self.analyze()
        state["evidence_readiness"]["sample_ready"] = True
        self.assertFalse(runtime.integrity_report(state)["all_checks_pass"])
        state = self.analyze()
        state["watch_exit_v2"]["V2_FALLING_TREND"]["frozen_exit_time_gain_mismatches"] = 1
        self.assertFalse(runtime.integrity_report(state)["all_checks_pass"])

    def test_activation_requires_aware_fresh_cutoff_and_code_pin(self):
        for cutoff in ("", "not-a-time", "2026-09-17T00:00:00"):
            self.assertFalse(runtime.analyze_rows([], cutoff_text=cutoff)["ok"])
        self.assertFalse(runtime.analyze_rows([], cutoff_text=CUTOFF, expected_code_sha256="")["ok"])
        fp = runtime.code_fingerprint()
        self.assertFalse(runtime.analyze_rows([], cutoff_text="2026-09-16T19:50:00Z", expected_code_sha256=fp)["ok"])
        self.assertTrue(runtime.analyze_rows([], cutoff_text=CUTOFF, expected_code_sha256=fp)["ok"])

    def test_refresh_failure_clears_scores_and_same_hash_recovers(self):
        rows = [{"record_type": "SNAPSHOT", "timestamp_utc": runtime.now()}]
        with patch.object(runtime, "CUTOFF_TEXT", CUTOFF), patch.object(runtime, "EXPECTED_CODE_SHA256", runtime.code_fingerprint()), patch.object(runtime.source, "fetch_rows") as fetch:
            fetch.side_effect = [(rows, "same", 123), RuntimeError("TOKEN_SHOULD_NOT_APPEAR"), (rows, "same", 123)]
            self.assertTrue(runtime.refresh_once()["ok"])
            failed = runtime.refresh_once()
            self.assertFalse(failed["ok"])
            self.assertNotIn("candidate_verify_v2", failed)
            self.assertNotIn("TOKEN_SHOULD_NOT_APPEAR", json.dumps(failed))
            self.assertTrue(runtime.refresh_once()["ok"])

    def test_stale_source_and_readiness_are_distinct_from_liveness(self):
        with patch.object(runtime, "CUTOFF_TEXT", CUTOFF), patch.object(runtime, "EXPECTED_CODE_SHA256", runtime.code_fingerprint()), patch.object(runtime.source, "fetch_rows", return_value=([{"timestamp_utc": "2020-01-01T00:00:00Z"}], "x", 10)):
            failed = runtime.refresh_once()
            self.assertEqual(failed["status"], "FAIL_CLOSED_STALE_SOURCE")
            self.assertEqual(runtime.response("/health", failed)[0], 200)
            self.assertEqual(runtime.response("/ready", failed)[0], 503)
            self.assertEqual(runtime.response("/state", failed)[0], 503)

    def test_missing_activation_does_not_contact_source(self):
        with patch.object(runtime, "CUTOFF_TEXT", ""), patch.object(runtime.source, "fetch_rows") as fetch:
            self.assertFalse(runtime.refresh_once()["ok"])
            fetch.assert_not_called()

    def test_exit_guard_does_not_depend_on_python_assertions(self):
        runtime.assert_integrity()
        with patch.object(runtime.q, "GIVEBACK", .03):
            with self.assertRaises(RuntimeError): runtime.assert_integrity()

    def test_http_health_ready_and_audit_use_real_handler(self):
        opener = build_opener(ProxyHandler({}))
        state = self.analyze()
        state["last_poll_utc"] = runtime.now()
        with patch.dict(runtime.STATE, state, clear=True):
            server = runtime.ThreadingHTTPServer(("127.0.0.1", 0), runtime.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                for route in ("/health", "/ready", "/state", "/audit"):
                    with opener.open(base+route, timeout=3) as r:
                        data = json.load(r)
                        self.assertEqual(r.status, 200)
                        self.assertFalse(data["orders"])
                        self.assertTrue(data["ok"])
                runtime.STATE["ok"] = False
                with self.assertRaises(HTTPError) as err: opener.open(base+"/ready", timeout=3)
                self.assertEqual(err.exception.code, 503)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__": unittest.main()
