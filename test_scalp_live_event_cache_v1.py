#!/usr/bin/env python3
from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scalp_live_event_cache_v1 import LiveEventCache
import scalp_integration_state_bridge_v4 as v4

FIELDS = [
    "record_type","timestamp_utc","contract","candidate_id","side",
    "seconds_left","entry_ask","btc30","elapsed_sec","exec_gain",
]


def row(typ, ts, contract, **kw):
    d={k:"" for k in FIELDS}
    d.update(record_type=typ,timestamp_utc=ts,contract=contract)
    d.update({k:str(v) for k,v in kw.items()})
    return d


def state_key(x):
    return (
        x.get("contract"),x.get("state"),x.get("side"),x.get("entry_price"),
        x.get("current_bid"),x.get("exec_gain"),x.get("peak_exec_gain"),
        x.get("armed"),x.get("exit_triggered"),x.get("source_fresh"),
    )


class ScalpLiveEventCacheV1Tests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory()
        self.path=Path(self.td.name)/"events.csv"
        self.rows=[
            row("SNAPSHOT","2026-09-14T12:00:00Z","A",seconds_left=800),
            row("CANDIDATE","2026-09-14T12:01:00Z","A",candidate_id="a1",side="DOWN",seconds_left=700,entry_ask=.40,btc30=20),
            row("PATH","2026-09-14T12:01:05Z","A",candidate_id="a1",elapsed_sec=5,exec_gain=.06),
            row("SNAPSHOT","2026-09-14T12:15:00Z","B",seconds_left=850),
            row("CANDIDATE","2026-09-14T12:16:00Z","B",candidate_id="b1",side="UP",seconds_left=780,entry_ask=.30,btc30=20),
            row("PATH","2026-09-14T12:16:05Z","B",candidate_id="b1",elapsed_sec=5,exec_gain=.03),
        ]
        with self.path.open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(self.rows)
        self.cache=LiveEventCache(self.path,max_recent_contracts=3)
        self.cache.initialize()
        self.now=datetime(2026,9,14,12,16,6,tzinfo=timezone.utc)

    def tearDown(self):
        self.cache.stop();self.td.cleanup()

    def _append(self,r):
        with self.path.open("a",newline="",encoding="utf-8") as f:
            csv.DictWriter(f,fieldnames=FIELDS).writerow(r)
        self.rows.append(r)
        self.cache.poll_once()

    def assert_parity(self,now=None):
        now=now or self.now
        full=v4.build_state(self.rows,now=now)
        cached=v4.build_state(self.cache.state_rows(),now=now)
        self.assertEqual(state_key(cached),state_key(full))
        return cached

    def test_initial_active_state_matches_full_tape(self):
        s=self.assert_parity()
        self.assertEqual(s["contract"],"B")
        self.assertEqual(s["state"],"ACTIVE")
        self.assertLess(len(self.cache.state_rows()),len(self.rows)+1)

    def test_incremental_protect_then_exit_matches_full_tape(self):
        self._append(row("PATH","2026-09-14T12:16:06Z","B",candidate_id="b1",elapsed_sec=6,exec_gain=.06))
        s=self.assert_parity(datetime(2026,9,14,12,16,6,tzinfo=timezone.utc))
        self.assertEqual(s["state"],"PROTECT")
        self.assertTrue(s["armed"])

        self._append(row("PATH","2026-09-14T12:16:07Z","B",candidate_id="b1",elapsed_sec=7,exec_gain=.01))
        s=self.assert_parity(datetime(2026,9,14,12,16,7,tzinfo=timezone.utc))
        self.assertEqual(s["state"],"EXIT")
        self.assertTrue(s["exit_triggered"])

        # Later recovery must not resurrect the frozen EXIT latch.
        self._append(row("PATH","2026-09-14T12:16:08Z","B",candidate_id="b1",elapsed_sec=8,exec_gain=.10))
        s=self.assert_parity(datetime(2026,9,14,12,16,8,tzinfo=timezone.utc))
        self.assertEqual(s["state"],"EXIT")

    def test_rollover_drops_prior_action_from_current_state(self):
        self._append(row("SNAPSHOT","2026-09-14T12:30:00Z","C",seconds_left=895))
        # A late prior-contract PATH can arrive after rollover; it must not leak.
        self._append(row("PATH","2026-09-14T12:30:01Z","B",candidate_id="b1",elapsed_sec=900,exec_gain=.50))
        s=self.assert_parity(datetime(2026,9,14,12,30,1,tzinfo=timezone.utc))
        self.assertEqual(s["contract"],"C")
        self.assertEqual(s["state"],"PASS")

    def test_partial_appended_line_waits_for_completion(self):
        r=row("PATH","2026-09-14T12:16:06Z","B",candidate_id="b1",elapsed_sec=6,exec_gain=.06)
        import io
        buf=io.StringIO();csv.DictWriter(buf,fieldnames=FIELDS,lineterminator="\n").writerow(r)
        raw=buf.getvalue().encode()
        cut=len(raw)//2
        with self.path.open("ab") as f:f.write(raw[:cut])
        self.assertEqual(self.cache.poll_once(),0)
        before=v4.build_state(self.cache.state_rows(),now=self.now)
        self.assertEqual(before["state"],"ACTIVE")
        with self.path.open("ab") as f:f.write(raw[cut:])
        self.rows.append(r)
        self.assertEqual(self.cache.poll_once(),1)
        after=self.assert_parity(self.now)
        self.assertEqual(after["state"],"PROTECT")

    def test_cache_never_writes_event_tape(self):
        before=self.path.read_bytes()
        self.cache.poll_once();self.cache.state_rows();self.cache.diagnostics()
        self.assertEqual(self.path.read_bytes(),before)
        self.assertFalse(self.cache.diagnostics()["orders"])


if __name__=="__main__":unittest.main()
