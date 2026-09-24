import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from fair_input_candidate import (completed_candles, frame_at_cut, load_frozen_inputs,
                                  price_at_or_before, select_frozen_rows)

ROOT = Path(__file__).resolve().parents[1]


class AvailabilityCandidate(unittest.TestCase):
    def setUp(self):
        self.cut = pd.Timestamp('2026-09-23T12:35:00Z')
        index = pd.date_range('2026-09-23T12:10Z', periods=31, freq='min')
        closes = np.arange(len(index), dtype=float) + 85000
        self.raw = pd.DataFrame(dict(Open=closes, High=closes+1, Low=closes-1,
                                     Close=closes, Volume=1.), index=index)
        self.empty = pd.DataFrame(columns=['source_utc','observed_utc','price'])
        tree = ast.parse((ROOT/'bot_two_output_build_v4_13_profit_protection_shadow.py').read_text())
        nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                 and n.name == '_fair_build_snapshot']
        self.env = dict(pd=pd, np=np, _fair_price_at_or_before=price_at_or_before)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), '<existing snapshot>', 'exec'), self.env)

    def snapshot(self, frame):
        return self.env['_fair_build_snapshot'](frame, self.cut-pd.Timedelta(minutes=5), 85000., _cut=self.cut)

    def test_unavailable_completed_candle_cannot_change_any_feature(self):
        original = frame_at_cut(completed_candles(self.raw), self.empty, self.cut)
        changed = self.raw.copy()
        changed.loc[changed.index >= self.cut, ['Open','High','Low','Close']] += 10000
        candidate = frame_at_cut(completed_candles(changed), self.empty, self.cut)
        self.assertEqual(self.snapshot(original), self.snapshot(candidate))
        self.assertEqual(original.index.max(), self.cut)
        self.assertEqual(original.iloc[-1].Close, self.raw.loc[self.cut-pd.Timedelta(minutes=1), 'Close'])

    def test_completion_boundary_is_exact(self):
        completed = completed_candles(self.raw)
        before = frame_at_cut(completed, self.empty, self.cut-pd.Timedelta(nanoseconds=1))
        at = frame_at_cut(completed, self.empty, self.cut)
        self.assertEqual(len(at), len(before)+1)

    def test_future_and_late_observed_ticks_do_not_change_earlier_cut(self):
        ticks = pd.DataFrame([
            dict(source_utc='2026-09-23T12:34:59Z', observed_utc='2026-09-23T12:35:01Z', price=99000),
            dict(source_utc='2026-09-23T12:36:00Z', observed_utc='2026-09-23T12:36:00Z', price=1)])
        plain = frame_at_cut(completed_candles(self.raw), self.empty, self.cut)
        candidate = frame_at_cut(completed_candles(self.raw), ticks, self.cut)
        pd.testing.assert_frame_equal(candidate, plain)

    def test_partial_tick_preserves_source_and_receipt_separately(self):
        ticks = pd.DataFrame([dict(source_utc='2026-09-23T12:35:04Z', observed_utc='2026-09-23T12:35:05Z', price=85123)])
        candidate = frame_at_cut(completed_candles(self.raw), ticks, self.cut+pd.Timedelta(seconds=5))
        self.assertEqual(candidate.index[-1], pd.Timestamp('2026-09-23T12:35:05Z'))
        self.assertEqual(candidate.iloc[-1].source_utc, pd.Timestamp('2026-09-23T12:35:04Z'))
        self.assertEqual(candidate.iloc[-1].Close, 85123)

    def test_boundary_tick_keeps_preceding_candle_range(self):
        ticks = pd.DataFrame([dict(source_utc=self.cut, observed_utc=self.cut, price=85123)])
        candidate = frame_at_cut(completed_candles(self.raw), ticks, self.cut)
        self.assertFalse(candidate.index.has_duplicates)
        self.assertEqual(candidate.iloc[-1].Close, 85123)
        self.assertEqual(candidate.iloc[-1].Low, self.raw.loc[self.cut-pd.Timedelta(minutes=1), 'Low'])

    def test_received_future_source_is_rejected(self):
        ticks = pd.DataFrame([dict(source_utc=self.cut+pd.Timedelta(seconds=1), observed_utc=self.cut, price=85000)])
        with self.assertRaisesRegex(ValueError, 'Future-source'):
            frame_at_cut(completed_candles(self.raw), ticks, self.cut)

    def test_receipt_cannot_refresh_old_spot(self):
        frame = completed_candles(self.raw).iloc[:1].copy()
        frame.index = pd.DatetimeIndex([self.cut])
        self.assertTrue(np.isnan(price_at_or_before(frame, self.cut)[0]))

    def test_invalid_historical_schema_fails_closed(self):
        for defect in ('naive','duplicate','infinite','ohlc','off_minute'):
            raw = self.raw.copy()
            if defect=='naive': raw.index=raw.index.tz_localize(None)
            elif defect=='duplicate': raw=pd.concat([raw,raw.iloc[:1]])
            elif defect=='infinite': raw.iloc[0,0]=np.inf
            elif defect=='ohlc': raw.iloc[0,1]=1
            else: raw.index=raw.index+pd.Timedelta(seconds=1)
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                completed_candles(raw)


class FrozenSupportCandidate(unittest.TestCase):
    def test_committed_frozen_support_does_not_depend_on_wall_clock(self):
        manifest, labels, completed = load_frozen_inputs(ROOT, ROOT/'completion_audit/fair_candidate_replay_manifest.json')
        self.assertEqual([len(manifest['roles'][r]) for r in manifest['roles']], [331,133,199])
        self.assertEqual(len(labels), 663)
        self.assertEqual(len(completed), 50399)
        # The loader has no runtime date input and does not call a wall clock.
        with patch('pandas.Timestamp.now', side_effect=AssertionError('wall clock must not be consulted')):
            again = load_frozen_inputs(ROOT, ROOT/'completion_audit/fair_candidate_replay_manifest.json')
        pd.testing.assert_frame_equal(completed, again[2])

    def test_changed_artifact_is_rejected(self):
        manifest=json.loads((ROOT/'completion_audit/fair_candidate_replay_manifest.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in manifest['input_sha256']:
                (root/name).write_bytes(b'changed input')
            path=root/'manifest.json';path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                load_frozen_inputs(root,path)

    def test_missing_membership_never_resplits(self):
        roles=dict(fit=['A'], calibration=['B'], historical_evaluation_already_opened=['C'])
        rows=pd.DataFrame([dict(ticker=t,elapsed=m) for t in 'ABC' for m in range(1,15)])
        selected=select_frozen_rows(rows,dict(roles=roles))
        self.assertEqual(set(selected['calibration'].ticker), {'B'})
        with self.assertRaisesRegex(ValueError,'do not re-split'):
            select_frozen_rows(rows[rows.ticker!='A'],dict(roles=roles))
        with self.assertRaisesRegex(ValueError,'insufficient'):
            select_frozen_rows(rows[~((rows.ticker=='A') & (rows.elapsed>3))],dict(roles=roles))
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            select_frozen_rows(pd.concat([rows, rows.iloc[:1]]),dict(roles=roles))


if __name__ == '__main__': unittest.main()
