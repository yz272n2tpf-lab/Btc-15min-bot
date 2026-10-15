"""Offline differential and crash-boundary tests; never imports production bot."""

import csv
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from btc15_cohort_closeout_incremental_research_v1 import (
    COHORT_SCHEMA, EvidenceChanged, IncrementalCloseout,
)

FIELDS = ["timestamp_utc", "contract", "target", "seconds_left",
          "coinbase_spot", "direct_brti", "brti_timestamp_utc",
          "brti_age_seconds", "brti_minus_coinbase", "brti_gap_to_target",
          "brti_side", "final60_count", "final60_average", "final60_gap_to_target",
          "final60_side", "final60_complete", "direct_brti_ready"]


def parity_row(contract, **overrides):
    row = dict.fromkeys(FIELDS, "")
    row.update(timestamp_utc="2026-10-15T13:40:00Z", contract=contract,
               target="110250.2", final60_count="60", final60_average="110251.5",
               final60_side="UP", final60_complete="True")
    row.update(overrides)
    return row


def legacy_select(rows, existing=()):
    """Unmodified eligibility and bytes from the original closeout block."""
    seen = set(existing)
    out, dispatched = [], []
    for r in rows:
        ticker = r.get("contract")
        if not ticker or ticker in seen:
            continue
        if str(r.get("final60_complete", "")).lower() not in ("true", "1"):
            continue
        if int(float(r.get("final60_count") or 0)) != 60:
            continue
        avg, side, target = (r.get(k) for k in
                             ("final60_average", "final60_side", "target"))
        if avg in (None, "") or side not in ("UP", "DOWN") or target in (None, ""):
            continue
        row = dict(schema=COHORT_SCHEMA, timestamp_utc=r.get("timestamp_utc"),
                   contract=ticker, target=float(target), seconds_left=0.0,
                   up_bid=None, up_ask=None, down_bid=None, down_ask=None,
                   final_status="CLOSEOUT_ONLY", final_side=None,
                   final_confidence=None, final_call_source="BRTI_CLOSEOUT",
                   early=None, unified_row_count=0, true_scalp_pending=0,
                   profit_pending=0,
                   brti=dict(contract=ticker, target=float(target), final60_count=60,
                             final60_average=float(avg), final60_side=side,
                             final60_complete=True),
                   signal_only=True, orders=False)
        out.append(json.dumps(row, separators=(",", ":"), sort_keys=True,
                              default=str) + "\n")
        dispatched.append((ticker, row["brti"]))
        seen.add(ticker)
    return out, dispatched


class CloseoutOffline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.parity = self.root / "parity.csv"
        self.cohort = self.root / "cohort.jsonl"
        self.dispatched = []
        with self.parity.open("w", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()

    def append(self, rows):
        with self.parity.open("a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writerows(rows)

    def reader(self, dispatcher=None):
        return IncrementalCloseout(self.parity, self.cohort,
                                   dispatcher or (lambda t, v: self.dispatched.append((t, v))))

    def actual(self):
        if not self.cohort.exists():
            return []
        return [line for line in self.cohort.read_text().splitlines(True)
                if json.loads(line).get("final_status") == "CLOSEOUT_ONLY"]

    def test_exact_legacy_bytes_and_settlement_values(self):
        rows = [parity_row("A", final60_count="59"),
                parity_row("B", final60_complete="False"),
                parity_row("C", final60_side="FLAT"),
                parity_row("D", final60_average=""),
                parity_row("E", final60_count="60.5"),
                parity_row("E", final60_average="110251.6"),
                parity_row("F", final60_side="DOWN", target="110250.10"),
                parity_row("F", final60_average="110254.8"),
                parity_row("G", final60_count="60", final60_complete="1")]
        self.append(rows)
        baseline_bytes, baseline_callbacks = legacy_select(rows)
        reader = self.reader()
        self.assertEqual(reader.poll_once(), ["E", "F", "G"])
        self.assertEqual(self.actual(), baseline_bytes)
        self.assertEqual(self.dispatched, baseline_callbacks)
        self.assertEqual(reader.poll_once(), [])
        self.assertEqual(self.actual(), baseline_bytes)
        self.assertTrue(all(json.loads(x)["orders"] is False for x in self.actual()))

    def test_late_completion_and_rollover(self):
        self.append([parity_row("KX1", final60_count="44"),
                     parity_row("KX2")])
        obj = self.reader()
        self.assertEqual(obj.poll_once(), ["KX2"])
        self.append([parity_row("KX1", final60_count="60", final60_complete="True"),
                     parity_row("KX3"), parity_row("KX1"), parity_row("KX2")])
        self.assertEqual(obj.poll_once(), ["KX1", "KX3"])
        self.assertEqual(len(self.actual()), 3)
        self.assertEqual(len(self.dispatched), 3)

    def test_partial_parity_line_never_commits_until_newline(self):
        row = parity_row("PARTIAL")
        sio = __import__('io').StringIO(newline="")
        csv.DictWriter(sio, fieldnames=FIELDS).writerow(row)
        raw = sio.getvalue().encode()
        half = len(raw)//2
        with self.parity.open("ab") as f:
            f.write(raw[:half])
        obj = self.reader()
        self.assertEqual(obj.poll_once(), [])
        self.assertEqual(obj.poll_once(), [])
        with self.parity.open("ab") as f:
            f.write(raw[half:])
        self.assertEqual(obj.poll_once(), ["PARTIAL"])
        self.assertEqual(len(self.actual()), 1)

    def test_restart_rebuilds_dedupe_and_appended_rows_only(self):
        self.append([parity_row("A"), parity_row("A"), parity_row("B")])
        self.assertEqual(self.reader().poll_once(), ["A", "B"])
        callback_count = len(self.dispatched)
        second = self.reader()
        self.assertEqual(second.poll_once(), [])
        self.assertEqual(len(self.dispatched), callback_count)
        self.append([parity_row("C"), parity_row("A")])
        self.assertEqual(second.poll_once(), ["C"])
        self.assertEqual(len(self.actual()), 3)

    def test_native_non_closeout_cohort_rows_are_tailed(self):
        with self.cohort.open("a") as f:
            f.write(json.dumps(dict(schema=COHORT_SCHEMA, contract="RAW", final_status="PASS")) + "\n")
        self.append([parity_row("A")])
        obj = self.reader()
        self.assertEqual(obj.poll_once(), ["A"])
        with self.cohort.open("a") as f:
            f.write(json.dumps(dict(schema=COHORT_SCHEMA, contract="RAW2", final_status="PASS")) + "\n")
        self.append([parity_row("B")])
        self.assertEqual(obj.poll_once(), ["B"])
        self.assertEqual(len(self.actual()), 2)

    def test_trailing_partial_cohort_record_is_quarantined(self):
        # Native's concurrent unfinished row must not be merged with a closeout.
        self.cohort.write_text('{"schema":"BTC15_COHORT_NATIVE_V1","final_status":"PASS","contract":"A"')
        self.append([parity_row("A")])
        obj = self.reader()
        with self.assertRaisesRegex(EvidenceChanged, "COHORT_PARTIAL_TRAILER"):
            obj.poll_once()
        self.assertEqual(self.dispatched, [])
        with self.cohort.open("a") as f:
            f.write("}\n")
        self.assertEqual(obj.poll_once(), ["A"])
        self.assertEqual(len(self.actual()), 1)

    def test_source_rotation_fails_closed(self):
        self.append([parity_row("A")]);obj=self.reader();obj.poll_once()
        replacement = self.root / 'replacement.csv'
        with replacement.open('w', newline='') as f:
            w=csv.DictWriter(f, fieldnames=FIELDS);w.writeheader();w.writerow(parity_row('B'))
        os.replace(replacement,self.parity)
        with self.assertRaisesRegex(EvidenceChanged,"REPLACED_OR_TRUNCATED"):
            obj.poll_once()
        self.assertEqual(len(self.actual()), 1)

    def test_truncate_fails_closed(self):
        self.append([parity_row("A")]);obj=self.reader();obj.poll_once()
        self.parity.write_text("tiny\n")
        with self.assertRaises(EvidenceChanged):obj.poll_once()
        self.assertEqual(len(self.actual()), 1)

    def test_prefix_overwrite_fails_closed(self):
        self.append([parity_row("A")]);obj=self.reader();obj.poll_once()
        with self.parity.open("r+b") as f:
            f.write(b"NOT CSV")
        with self.assertRaisesRegex(EvidenceChanged,"PREFIX_CHANGED"):
            obj.poll_once()

    def test_crash_after_cohort_fsync_before_settlement_is_detected(self):
        self.append([parity_row("A")])
        def fail(*args):
            raise RuntimeError("CRASH_AFTER_COHORT_BEFORE_ACK")
        obj=self.reader(dispatcher=fail)
        with self.assertRaisesRegex(RuntimeError,"CRASH_AFTER_COHORT"):
            obj.poll_once()
        self.assertEqual(len(self.actual()),1)
        with self.assertRaisesRegex(EvidenceChanged,"RECONCILIATION_REQUIRED"):
            obj.poll_once()
        with self.assertRaisesRegex(EvidenceChanged,"AMBIGUOUS_SETTLEMENT_WINDOW"):
            self.reader().poll_once()
        self.assertEqual(len(self.dispatched),0)

    def test_crash_before_cohort_append_is_detected(self):
        self.append([parity_row("A")])
        obj = self.reader()
        saved_open = Path.open
        def deny_cohort_open(path, *args, **kwargs):
            if path == self.cohort and args and args[0] == "a":
                raise OSError("WRITE_BLOCKED")
            return saved_open(path, *args, **kwargs)
        with mock.patch.object(Path, "open", new=deny_cohort_open):
            with self.assertRaisesRegex(OSError, "WRITE_BLOCKED"):
                obj.poll_once()
        with self.assertRaisesRegex(EvidenceChanged,"AMBIGUOUS_SETTLEMENT_WINDOW"):
            self.reader().poll_once()
        self.assertEqual(self.actual(),[])

    def test_crash_after_dispatch_before_audit_ack_detected(self):
        self.append([parity_row("A")]);calls=[]
        obj=self.reader(dispatcher=lambda t,v:calls.append((t,v)))
        original=obj._append_audit
        def append_audit(t,h,phase):
            if phase=="ENQUEUED":raise RuntimeError("CRASH_AFTER_QUEUE")
            return original(t,h,phase)
        with mock.patch.object(obj,"_append_audit",side_effect=append_audit):
            with self.assertRaisesRegex(RuntimeError,"CRASH_AFTER_QUEUE"):
                obj.poll_once()
        self.assertEqual(len(calls),1)
        with self.assertRaisesRegex(EvidenceChanged,"AMBIGUOUS_SETTLEMENT_WINDOW"):
            self.reader().poll_once()
        self.assertEqual(len(self.actual()),1)

    def test_partial_audit_is_quarantined(self):
        self.append([parity_row("A")]);self.assertEqual(self.reader().poll_once(),["A"])
        audit=self.cohort.with_suffix(".closeout-audit.jsonl")
        with audit.open('a') as f:
            f.write('{"schema":')
        with self.assertRaisesRegex(EvidenceChanged,"AUDIT_PARTIAL_TRAILER"):
            self.reader().poll_once()

    def test_no_repeated_full_history_scans(self):
        self.append([parity_row("LATE",final60_count="59")]*1000)
        obj=self.reader();self.assertEqual(obj.poll_once(),[])
        first=obj.stats();self.assertGreater(first['parity_bytes_read'],50000)
        for _ in range(10):self.assertEqual(obj.poll_once(),[])
        second=obj.stats();self.assertEqual(second['parity_bytes_read'],first['parity_bytes_read'])
        self.append([parity_row("LATE")]);self.assertEqual(obj.poll_once(),["LATE"])
        third=obj.stats();self.assertLess(third['parity_bytes_read']-first['parity_bytes_read'],300)

    def test_no_orders_methods_or_network_dependencies(self):
        import btc15_cohort_closeout_incremental_research_v1 as module
        from inspect import getsource
        src=getsource(module)
        self.assertNotIn('requests.',src)
        self.assertNotIn('urllib.',src)
        self.assertNotIn('place_order',src)
        self.assertNotIn('create_order',src)
        self.assertIn('production_ready=False',src)


if __name__=='__main__':unittest.main()
