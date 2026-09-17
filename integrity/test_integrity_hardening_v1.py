"""Regression coverage for the seven mandatory verification findings."""

import copy
import itertools
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from integrity import evidence_bundle_builder_v1 as builder
from integrity import evidence_integrity_reconciler_v1 as reconciler
from integrity.evidence_integrity_adapter_v1 import AdapterPolicy, aggregate_contract
from integrity.railway_evidence_log_adapter_v1 import (
    build_contract_windows, parse_many, to_integrity_observations,
)
from integrity.safe_outputs_v1 import validate_output_paths, write_new_text
from integrity.test_evidence_integrity_adapter_v1 import clean_path
from integrity.test_evidence_integrity_reconciler_v1 import clean_record


CID = "KXBTC15M-TEST"
BAD_NUMBERS = (float("nan"), float("inf"), float("-inf"), -1.0, True, "bad", None)
TARGETS = ("summary.json", "parsed_events.jsonl", "contract_windows.json",
           "integrity_observations.jsonl", "contract_records.jsonl", "assessments.jsonl")


def aggregate(rows):
    return aggregate_contract(CID, rows)


def parsed_observations(message, at="2026-09-17T03:05:00Z"):
    rows = [
        {"timestamp": "2026-09-17T03:00:50Z", "message":
         "ROLLOVER PROBE V3 SUMMARY | boundary=2026-09-17T03:00:00Z | "
         f"target={CID} | exact_active_quoted=1.0 | NO ORDERS"},
        {"timestamp": at, "message": message},
    ]
    events = parse_many(rows, source="synthetic")
    return to_integrity_observations(events, build_contract_windows(events))


class OutputProtectionTests(unittest.TestCase):
    def test_reconciler_all_input_output_overlaps_preserve_bytes(self):
        for output_option, protected in itertools.product(("--output", "--summary"), ("input", "policy")):
            with self.subTest(output=output_option, protected=protected), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                source = root / "input"
                policy = root / "policy"
                source.write_text(json.dumps(clean_record()) + "\n")
                policy.write_text("{}\n")
                original = {p: p.read_bytes() for p in (source, policy)}
                args = {"--input": source, "--policy": policy,
                        "--output": root / "out", "--summary": root / "summary"}
                args[output_option] = root / protected
                argv = ["reconciler"] + [str(x) for pair in args.items() for x in pair]
                with patch("sys.argv", argv), self.assertRaises(ValueError):
                    reconciler.main()
                self.assertEqual(original, {p: p.read_bytes() for p in original})
                self.assertEqual({p.name for p in root.iterdir()}, {"input", "policy"})

    def test_reconciler_outputs_cannot_alias_each_other(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "input"
            source.write_text("{}\n")
            argv = ["reconciler", "--input", str(source), "--output", str(root / "result"),
                    "--summary", str(root / "." / "result")]
            with patch("sys.argv", argv), self.assertRaises(ValueError):
                reconciler.main()
            self.assertEqual(list(root.iterdir()), [source])

    def test_symlink_hardlink_relative_and_parent_aliases_are_blocked(self):
        for kind in ("symlink", "hardlink", "relative", "parent_symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                source = root / "source"
                source.write_text("immutable evidence")
                target = root / "alias"
                if kind == "symlink":
                    target.symlink_to(source)
                elif kind == "hardlink":
                    os.link(source, target)
                elif kind == "relative":
                    (root / "child").mkdir()
                    target = root / "child" / ".." / "source"
                else:
                    target.symlink_to(root, target_is_directory=True)
                    target = target / "source"
                with self.assertRaises(ValueError):
                    validate_output_paths([source], [target])
                self.assertEqual(source.read_text(), "immutable evidence")

    def test_bundle_all_generated_names_protect_all_input_types_before_any_write(self):
        for name, kind in itertools.product(TARGETS, ("log", "manifest", "policy")):
            with self.subTest(name=name, kind=kind), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                logs = root / (name if kind == "log" else "source.jsonl")
                logs.write_text('{"timestamp":"2026-09-17T03:00:00Z","message":"test"}\n')
                source = logs
                argv = ["builder", "--log", f"test={logs}", "--out-dir", str(root)]
                if kind != "log":
                    source = root / name
                    source.write_text("{}\n")
                    argv += ["--operational-manifest" if kind == "manifest" else "--policy", str(source)]
                before = {p: p.read_bytes() for p in root.iterdir()}
                with patch("sys.argv", argv), self.assertRaises(ValueError):
                    builder.main()
                self.assertEqual(before, {p: p.read_bytes() for p in root.iterdir()})

    def test_existing_derived_output_and_dangling_symlink_are_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "input"
            source.write_text("{}\n")
            existing = root / "derived"
            existing.write_text("prior result")
            dangling = root / "dangling"
            dangling.symlink_to(root / "absent")
            for target in (existing, dangling):
                with self.subTest(target=target), self.assertRaises(ValueError):
                    validate_output_paths([source], [target])
            self.assertEqual(existing.read_text(), "prior result")
            self.assertFalse((root / "absent").exists())

    def test_exclusive_creation_rejects_file_appearing_after_preflight(self):
        with tempfile.TemporaryDirectory() as td:
            target = validate_output_paths([], [Path(td) / "result"])[0]
            target.write_text("appeared concurrently")
            with self.assertRaises(FileExistsError):
                write_new_text(target, "replacement")
            self.assertEqual(target.read_text(), "appeared concurrently")

    def test_safe_cli_outputs_succeed_and_preserve_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "input"
            source.write_text(json.dumps(clean_record()) + "\n")
            before = source.read_bytes()
            argv = ["reconciler", "--input", str(source), "--output", str(root / "out"),
                    "--summary", str(root / "summary")]
            with patch("sys.argv", argv):
                self.assertEqual(reconciler.main(), 0)
            self.assertEqual(json.loads((root / "summary").read_text())["certifiable_contracts"], 1)
            self.assertEqual(source.read_bytes(), before)

    def test_safe_bundle_cli_writes_six_outputs_and_refuses_rerun(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "logs.jsonl"
            source.write_text('{"timestamp":"2026-09-17T03:00:00Z","message":"synthetic"}\n')
            before = source.read_bytes()
            output = root / "bundle"
            argv = ["builder", "--log", f"synthetic={source}", "--out-dir", str(output)]
            with patch("sys.argv", argv):
                self.assertEqual(builder.main(), 0)
            self.assertEqual({p.name for p in output.iterdir()}, set(TARGETS))
            saved = {p: p.read_bytes() for p in output.iterdir()}
            with patch("sys.argv", argv), self.assertRaises(ValueError):
                builder.main()
            self.assertEqual(saved, {p: p.read_bytes() for p in output.iterdir()})
            self.assertEqual(source.read_bytes(), before)


class MeasurementHardeningTests(unittest.TestCase):
    def assertNotCertifiable(self, record):
        assessment = reconciler.reconcile_contract(record)
        self.assertNotEqual(assessment.classification, reconciler.Classification.CLEAN)
        self.assertFalse(assessment.valid_for_certification)
        return assessment

    def test_invalid_numeric_contract_measurements_never_clean(self):
        fields = ("kalshi_max_age_sec", "brti_max_age_sec", "coinbase_max_age_sec",
                  "max_source_gap_sec", "rollover_lag_sec",
                  "kalshi_max_observation_gap_sec", "brti_max_observation_gap_sec",
                  "coinbase_max_observation_gap_sec")
        for field, value in itertools.product(fields, BAD_NUMBERS):
            with self.subTest(field=field, value=value):
                record = clean_record()
                record[field] = value
                self.assertNotCertifiable(record)

    def test_invalid_observation_cannot_be_diluted_by_healthy_samples(self):
        fields = ("kalshi_age_sec", "brti_age_sec", "coinbase_age_sec", "seconds_left",
                  "max_source_gap_sec", "rollover_lag_sec", "rollover_quote_lag_sec",
                  "exact_ticker_rollover_quote_lag_sec", "combined_first_seen_lag_sec")
        for field, value in itertools.product(fields, BAD_NUMBERS):
            with self.subTest(field=field, value=value):
                rows = clean_path()
                rows[80][field] = value
                result = aggregate(rows)
                self.assertIn(field, result["invalid_measurements"])
                self.assertNotCertifiable(result)

    def test_parser_preserves_invalid_age_and_lag_evidence(self):
        for value in ("NaN", "Infinity", "-Infinity", "-1", "bad"):
            messages = (
                "BRTI_SHARED HEARTBEAT | status=PRIMARY_OK | clean=True | "
                f"age_ms={value} | seq=1 | upstream_ok=1/1200 (100%) | 429=10 | errors=0",
                f"PARITY PASS | {CID} | age {value}s | BRTI delta @ 1.0s | BRTI",
                f"DIRECT BRTI | price | age {value}s | ready True",
                f"ROLLOVER PROBE V3 SUMMARY | boundary=2026-09-17T03:00:00Z | target={CID} | exact_active_quoted={value}",
                f"COMBINED V2 LATE START | {CID} | first_seen_lag={value}s | EXCLUDED FROM GATE",
            )
            for message in messages:
                with self.subTest(value=value, message=message):
                    observations = parsed_observations(message)
                    self.assertEqual(len(observations), 2)
                    record = aggregate(clean_path() + observations)
                    self.assertTrue(record["invalid_measurements"])
                    self.assertNotCertifiable(record)

    def test_invalid_policy_thresholds_are_rejected(self):
        for field in ("max_kalshi_age_sec", "max_brti_age_sec", "max_coinbase_age_sec",
                      "max_source_gap_sec", "max_rollover_lag_sec", "max_429_share"):
            for value in BAD_NUMBERS:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    reconciler.ReconcilerPolicy(**{field: value})
        for value in BAD_NUMBERS:
            with self.subTest(adapter=value), self.assertRaises(ValueError):
                AdapterPolicy(max_source_gap_sec=value)

    def test_one_feed_sample_among_169_path_samples_is_not_coverage(self):
        for feed in ("kalshi", "brti", "coinbase"):
            with self.subTest(feed=feed):
                rows = clean_path()
                for i, row in enumerate(rows):
                    if i != 80:
                        row.pop(f"{feed}_age_sec")
                result = aggregate(rows)
                self.assertEqual(result["path_sample_count"], 169)
                self.assertEqual(result[f"{feed}_sample_count"], 1)
                self.assertIs(result[f"{feed}_coverage_complete"], False)
                self.assertNotCertifiable(result)

    def test_feed_specific_start_end_and_middle_gaps_cannot_borrow_other_feeds(self):
        for feed, gap in itertools.product(("kalshi", "brti", "coinbase"), ("start", "end", "middle")):
            with self.subTest(feed=feed, gap=gap):
                rows = clean_path()
                indices = {"start": range(4), "end": range(167, 169), "middle": range(50, 54)}[gap]
                for i in indices:
                    rows[i].pop(f"{feed}_age_sec")
                result = aggregate(rows)
                self.assertTrue(result["continuous_path_complete"])
                self.assertIs(result[f"{feed}_coverage_complete"], False)
                self.assertNotCertifiable(result)

    def test_missing_feed_coverage_stays_unknown_and_disabled_feed_is_exempt(self):
        rows = clean_path()
        for row in rows:
            row.pop("coinbase_age_sec")
        result = aggregate(rows)
        self.assertIsNone(result["coinbase_coverage_complete"])
        self.assertEqual(result["coinbase_sample_count"], 0)
        self.assertNotCertifiable(result)
        self.assertTrue(reconciler.reconcile_contract(result, reconciler.ReconcilerPolicy(require_coinbase=False)).valid_for_certification)

    def test_coverage_boolean_alone_cannot_certify_or_mask_invalid_statistics(self):
        for feed in ("kalshi", "brti", "coinbase"):
            for field, value in (("sample_count", 1), ("has_start_observation", False),
                                 ("has_end_observation", False), ("max_observation_gap_sec", 99)):
                with self.subTest(feed=feed, field=field):
                    result = clean_record()
                    result[f"{feed}_{field}"] = value
                    self.assertNotCertifiable(result)
            result = clean_record()
            del result[f"{feed}_coverage_complete"]
            self.assertNotCertifiable(result)

    def test_zero_cumulative_parity_never_masks_explicit_failure(self):
        rows = clean_path()
        for row in rows:
            row["parity_fail_count"] = 0
        rows[80]["parity_ok"] = False
        result = aggregate(rows)
        self.assertEqual(result["parity_fail_count"], 1)
        self.assertFalse(result["parity_ok"])
        self.assertNotCertifiable(result)

    def test_parity_failure_without_path_measurement_survives(self):
        rows = clean_path() + [{"contract_id": CID, "parity_ok": False, "parity_fail_count": 0}]
        result = aggregate(rows)
        self.assertEqual(result["parity_fail_count"], 1)
        self.assertNotCertifiable(result)

    def test_direct_record_explicit_parity_failure_is_hard_even_with_warning_policy(self):
        result = dict(clean_record(), parity_ok=False)
        self.assertNotCertifiable(result)
        assessment = reconciler.reconcile_contract(result, reconciler.ReconcilerPolicy(parity_fail_is_hard=False))
        self.assertIs(assessment.evidence_integrity_pass, False)

    def test_intermediate_counter_reset_cannot_recover_to_clean(self):
        for field in ("brti_attempts_total", "brti_429_total", "brti_errors_total", "brti_upstream_ok_total", "brti_seq"):
            with self.subTest(field=field):
                rows = clean_path()
                for row in rows:
                    row.pop(field, None)
                for i, value in ((0, 1000), (80, 1), (168, 1840)):
                    rows[i][field] = value
                result = aggregate(list(reversed(rows)))
                counter = result["brti_counter_metadata"][field]
                self.assertTrue(counter["reset_detected"])
                self.assertIsNone(counter["delta"])
                self.assertEqual(counter["resets"][0]["before"], 1000)
                self.assertEqual(counter["resets"][0]["after"], 1)
                self.assertTrue(result["brti_counter_reset"])
                self.assertNotCertifiable(result)

    def test_invalid_counter_measurements_cannot_disappear(self):
        for value in (*BAD_NUMBERS, 1.5):
            with self.subTest(value=value):
                rows = clean_path()
                rows[80]["brti_attempts_total"] = value
                result = aggregate(rows)
                self.assertIsNone(result["brti_attempts"])
                self.assertNotCertifiable(result)

    def test_explicit_feed_trouble_survives_all_pipeline_stages(self):
        messages = (
            ("BRTI_SHARED HEARTBEAT | status=PRIMARY_ERROR | clean=False | age_ms=500 | "
             "seq=1 | upstream_ok=1/1300 (90%) | 429=10 | errors=0", "brti_feed_clean", False),
            ("DIRECT BRTI | price | age 0.5s | ready False", "direct_brti_ready", False),
            ("Coinbase ReadTimeout", "coinbase_timeout", True),
        )
        for message, field, bad in messages:
            with self.subTest(field=field):
                observations = parsed_observations(message)
                self.assertEqual(len(observations), 2)
                result = aggregate(clean_path() + observations)
                self.assertIs(result[field], bad)
                assessment = self.assertNotCertifiable(result)
                self.assertIn(f"FAIL_{field.upper()}", assessment.reasons)

    def test_feed_trouble_dominates_later_healthy_status(self):
        for field, bad, good in (("brti_clean", False, True), ("brti_feed_clean", False, True),
                                 ("direct_brti_ready", False, True), ("coinbase_timeout", True, False)):
            with self.subTest(field=field):
                rows = clean_path()
                rows[20][field] = bad
                rows[-1][field] = good
                self.assertNotCertifiable(aggregate(rows))

    def test_recorded_rollover_35_7_beats_inferred_one_second(self):
        for field in ("exact_ticker_rollover_quote_lag_sec", "combined_first_seen_lag_sec", "rollover_quote_lag_sec", "rollover_lag_sec"):
            with self.subTest(field=field):
                rows = clean_path()
                for row in rows:
                    row["seconds_left"] += 3
                rows[60][field] = 35.7
                result = aggregate(rows)
                self.assertEqual(result["rollover_lag_sec"], 35.7)
                assessment = self.assertNotCertifiable(result)
                self.assertTrue(any("FAIL_ROLLOVER_LATE" in r for r in assessment.reasons))

    def test_rollover_worst_record_survives_later_smaller_summary(self):
        messages = []
        for at, lag in (("2026-09-17T03:00:50Z", 35.7), ("2026-09-17T03:00:55Z", 1.0)):
            messages.append({"timestamp": at, "message":
                f"ROLLOVER PROBE V3 SUMMARY | boundary=2026-09-17T03:00:00Z | target={CID} | exact_active_quoted={lag}"})
        events = parse_many(messages, source="synthetic")
        windows = build_contract_windows(events)
        self.assertEqual(windows[0].rollover_quote_lag_sec, 35.7)
        observations = to_integrity_observations(events, windows)
        self.assertTrue(all(r["exact_ticker_rollover_quote_lag_sec"] == 35.7 for r in observations))
        result = aggregate(clean_path() + observations)
        self.assertEqual(result["rollover_lag_sec"], 35.7)
        self.assertNotCertifiable(result)

    def test_direct_record_recorded_rollover_cannot_be_masked(self):
        for value in (35.7, *BAD_NUMBERS):
            with self.subTest(value=value):
                result = dict(clean_record(), rollover_lag_sec=1.0, exact_ticker_rollover_quote_lag_sec=value)
                self.assertNotCertifiable(result)

    def test_dual_gate_full_pass_fail_unknown_truth_table(self):
        for op, ev in itertools.product((True, False, None), repeat=2):
            with self.subTest(op=op, ev=ev):
                result = clean_record()
                result["process_alive"] = op
                result["continuous_path_complete"] = ev
                assessment = reconciler.reconcile_contract(result)
                self.assertIs(assessment.operational_health_pass, op)
                self.assertIs(assessment.evidence_integrity_pass, ev)
                self.assertIs(assessment.valid_for_certification, op is True and ev is True)
                self.assertIs(assessment.quarantine, not assessment.valid_for_certification)

    def test_aggregation_and_reconciliation_do_not_mutate_observations(self):
        rows = clean_path()
        rows[50]["brti_clean"] = False
        before = copy.deepcopy(rows)
        result = aggregate(rows)
        record_before = copy.deepcopy(result)
        self.assertNotCertifiable(result)
        self.assertEqual(rows, before)
        self.assertEqual(result, record_before)


if __name__ == "__main__":
    unittest.main()
