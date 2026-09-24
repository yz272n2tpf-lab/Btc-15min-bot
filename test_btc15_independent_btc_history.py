"""Regression for fresh BTC discarded behind a missing Kalshi quote gate."""
import ast
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
from completion_audit.fair_input_candidate import frame_at_cut,price_at_or_before

SOURCE=Path(__file__).with_name('bot_two_output_build_v4_13_profit_protection_shadow.py')

class IndependentBtcHistoryTests(unittest.TestCase):
    def env(self):
        tree=ast.parse(SOURCE.read_text());names={'_fair_build_snapshot','_ec_append_btc_tick','_ec_live_ticks'}
        functions=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in names]
        env=dict(pd=pd,np=np,_ec_btc_ticks=deque(),_fair_price_at_or_before=price_at_or_before)
        exec(compile(ast.Module(body=functions,type_ignores=[]),str(SOURCE),'exec'),env)
        return env
    def ticks(self,env,start,end):
        for when in pd.date_range(start,end,freq='5s'):
            env['_ec_append_btc_tick'](when-pd.Timedelta(milliseconds=100),when,100.+(when.second%11)/10)
    def empty_bars(self):
        f=pd.DataFrame(columns=['Open','High','Low','Close','Volume','source_utc'],index=pd.DatetimeIndex([],tz='UTC'))
        return f
    def test_quote_outage_does_not_erase_next_contract_preopen_reference(self):
        start=pd.Timestamp('2026-09-24T14:30Z');cut=start+pd.Timedelta(minutes=5,seconds=20)
        old=self.env();new=self.env()
        for env in (old,new):self.ticks(env,start-pd.Timedelta(minutes=8),start-pd.Timedelta(minutes=3))
        # Same real BTC reads are available during a three-minute book outage.
        # Legacy placement discards them. Corrected placement retains their clocks.
        self.ticks(new,start-pd.Timedelta(minutes=3)+pd.Timedelta(seconds=5),start)
        for env in (old,new):self.ticks(env,start+pd.Timedelta(seconds=5),cut)
        oldframe=frame_at_cut(self.empty_bars(),old['_ec_live_ticks'](),cut)
        newframe=frame_at_cut(self.empty_bars(),new['_ec_live_ticks'](),cut)
        self.assertIsNone(old['_fair_build_snapshot'](oldframe,start,100.,_cut=cut))
        repaired=new['_fair_build_snapshot'](newframe,start,100.,_cut=cut)
        self.assertIsNotNone(repaired);self.assertAlmostEqual(repaired['remaining'],15-5-20/60)
        self.assertEqual(new['_ec_live_ticks']().iloc[-1]['source_utc'],cut-pd.Timedelta(milliseconds=100))
    def test_quote_healthy_path_is_identical_with_idempotent_early_capture(self):
        a=self.env();b=self.env();start=pd.Timestamp('2026-09-24T13:00Z')
        for when in pd.date_range(start,start+pd.Timedelta(minutes=9),freq='5s'):
            args=(when-pd.Timedelta(milliseconds=100),when,100.+when.second/100)
            a['_ec_append_btc_tick'](*args)
            b['_ec_append_btc_tick'](*args);b['_ec_append_btc_tick'](*args)
        pd.testing.assert_frame_equal(a['_ec_live_ticks'](),b['_ec_live_ticks']())
    def test_ingestion_order_precedes_target_and_quote_wait_without_moving_signal_gates(self):
        tree=ast.parse(SOURCE.read_text());loop=next(n for n in tree.body if isinstance(n,ast.While) and isinstance(n.test,ast.Name) and n.test.id=='running')
        calls=[n for n in ast.walk(loop) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
        line=lambda name:next(n.lineno for n in calls if n.func.id==name)
        self.assertLess(line('decision_time'),line('_ec_append_btc_tick'))
        self.assertLess(line('_ec_append_btc_tick'),line('consume_ws_quotes'))
        self.assertLess(line('consume_ws_quotes'),line('_live_fair_shadow'))
        self.assertLess(line('consume_ws_quotes'),line('_maybe_true_scalp_signal'))
        waits=[n for n in ast.walk(loop) if isinstance(n,ast.If) and ast.unparse(n.test)=='quotes is None']
        self.assertTrue(any(isinstance(n,ast.Continue) for n in ast.walk(waits[0])))
    def test_stale_future_and_naive_clocks_still_fail(self):
        env=self.env();now=pd.Timestamp('2026-09-24T14:30Z')
        for source,observed in [(now-pd.Timedelta(seconds=10.001),now),(now+pd.Timedelta(seconds=1),now),(now.tz_localize(None),now)]:
            with self.assertRaises(RuntimeError):env['_ec_append_btc_tick'](source,observed,100.)
        self.assertEqual(len(env['_ec_live_ticks']()),0)
    def test_retention_and_future_receipts_remain_bounded(self):
        env=self.env();now=pd.Timestamp('2026-09-24T14:30Z')
        self.ticks(env,now-pd.Timedelta(minutes=25),now)
        self.assertEqual(len(env['_ec_live_ticks']()),241)
        before=frame_at_cut(self.empty_bars(),env['_ec_live_ticks'](),now)
        self.ticks(env,now+pd.Timedelta(seconds=5),now+pd.Timedelta(seconds=10))
        after=frame_at_cut(self.empty_bars(),env['_ec_live_ticks'](),now)
        pd.testing.assert_frame_equal(before.loc[before.index>now-pd.Timedelta(minutes=19)],after.loc[after.index>now-pd.Timedelta(minutes=19)])

if __name__=='__main__':unittest.main()
