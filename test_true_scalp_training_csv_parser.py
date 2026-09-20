#!/usr/bin/env python3
"""Focused regression tests for frozen True Scalp CSV loading. NO ORDERS."""
import ast
import csv
import hashlib
from pathlib import Path
import tempfile
import types
import unittest
import pandas as pd

SOURCE = Path(__file__).with_name("bot_two_output_build_v4_13_profit_protection_shadow.py")
FIELDS = [
    "event_id","contract","side","entry_timestamp_utc","entry_ask","entry_bid",
    "target","btc_price","btc_gap","seconds_left",
    "btc_move_15s","btc_move_30s","btc_move_60s",
    "ask_move_15s","ask_move_30s","ask_move_60s",
    "recent_low_60s","recent_high_60s","bounce_from_low","drawdown_from_high",
    "outcome_timestamp_utc","observed_seconds",
    "max_future_bid","max_gain_vs_entry_ask","min_future_bid","max_adverse_vs_entry_ask",
    "hit_8c","seconds_to_8c","hit_10c","seconds_to_10c",
    "hit_15c","seconds_to_15c","hit_20c","seconds_to_20c",
    "stop_10c_hit","stop_seconds","notes",
]
CUTOFF = pd.Timestamp("2026-09-03T14:24:57.562191+00:00")

def load_module():
    tree=ast.parse(SOURCE.read_text())
    wanted={"_git_blob_sha","_load_true_scalp_training_events"}
    fns=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
    m=types.ModuleType("loader_under_test")
    m.__dict__.update(csv=csv,pd=pd,hashlib=hashlib,EVENT_FIELDS=FIELDS)
    exec(compile(ast.Module(body=fns,type_ignores=[]),str(SOURCE),"exec"),m.__dict__)
    return m

def row(ts, extra=0):
    r=[""]*len(FIELDS)
    r[0]="event"; r[1]="contract"; r[2]="UP"; r[3]=ts; r[4]="0.30"; r[28]="True"
    return r + (["EXTRA"]*extra)

class Parser(unittest.TestCase):
    def setUp(self):
        self.m=load_module()
        self.load=self.m._load_true_scalp_training_events

    def write(self, rows, header=FIELDS):
        td=tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        p=Path(td.name)/"events.csv"
        with p.open("w",newline="") as f:
            w=csv.writer(f); w.writerow(header); w.writerows(rows)
        return p

    def test_committed_frozen_source_blob_and_pre_cutoff_count(self):
        p=SOURCE.with_name("kalshi_scalp_shadow_events_v1.csv")
        self.assertEqual(
            self.m._git_blob_sha(p),
            "c579fd22127e5af3bd14e287cb27b631459fbcd7",
        )
        d=self.load(p,CUTOFF)
        ts=pd.to_datetime(d["entry_timestamp_utc"],errors="coerce",utc=True)
        self.assertEqual(int((ts.notna() & (ts <= CUTOFF)).sum()),1474)

    def test_valid_frozen_rows_preserved(self):
        p=self.write([row("2026-09-03T14:00:00+00:00")])
        d=self.load(p,CUTOFF)
        self.assertEqual(len(d),1)
        self.assertEqual(list(d.columns),FIELDS)

    def test_malformed_post_cutoff_row_is_irrelevant(self):
        p=self.write([
            row("2026-09-03T14:00:00+00:00"),
            row("2026-09-20T18:00:00+00:00",15),
        ])
        d=self.load(p,CUTOFF)
        self.assertEqual(len(d),1)

    def test_52_field_post_cutoff_regression(self):
        p=self.write([row("2026-09-20T18:00:00+00:00",15)])
        self.assertEqual(len(row("2026-09-20T18:00:00+00:00",15)),52)
        self.assertEqual(len(self.load(p,CUTOFF)),0)

    def test_malformed_frozen_row_fails_closed(self):
        p=self.write([row("2026-09-03T14:00:00+00:00",15)])
        with self.assertRaisesRegex(RuntimeError,"frozen true-scalp training row malformed"):
            self.load(p,CUTOFF)

    def test_unknown_timestamp_malformed_row_fails_closed(self):
        p=self.write([row("not-a-time",15)])
        with self.assertRaises(RuntimeError):
            self.load(p,CUTOFF)

    def test_header_drift_fails_closed(self):
        p=self.write([],header=FIELDS[:-1])
        with self.assertRaisesRegex(RuntimeError,"header mismatch"):
            self.load(p,CUTOFF)

if __name__=="__main__":
    unittest.main(verbosity=2)
