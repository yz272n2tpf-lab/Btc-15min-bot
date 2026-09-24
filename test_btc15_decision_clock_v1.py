import ast
from collections import deque
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from btc15_decision_clock_v1 import decision_time, record_model_input
from completion_audit.fair_input_candidate import frame_at_cut, price_at_or_before

ROOT=Path(__file__).resolve().parent


class DecisionClockTests(unittest.TestCase):
    def setUp(self):
        self.opened=datetime(2026,9,24,12,0,tzinfo=timezone.utc)
        self.closed=self.opened+timedelta(minutes=15)
        self.now=self.opened+timedelta(minutes=5,seconds=30)
        self.source=self.now-timedelta(milliseconds=100)
        self.received=self.now-timedelta(milliseconds=10)

    def test_receipt_cutoff_preserves_source_clock(self):
        self.assertEqual(decision_time(self.opened,self.closed,self.source,self.received,self.now),self.now)
        self.assertNotEqual(self.source,self.now)

    def test_network_read_crossing_close_fails_closed(self):
        with self.assertRaises(ValueError):
            decision_time(self.opened,self.closed,self.closed-timedelta(seconds=1),self.closed,self.closed)

    def test_stale_future_and_unobserved_inputs_fail(self):
        for source,received,now in [
            (self.now-timedelta(seconds=10.001),self.received,self.now),
            (self.now+timedelta(seconds=1),self.received,self.now),
            (self.source,self.now+timedelta(seconds=1),self.now),
        ]:
            with self.assertRaises(ValueError):decision_time(self.opened,self.closed,source,received,now)

    def test_wrong_official_window_fails(self):
        for opened,closed in [(self.opened,self.closed+timedelta(seconds=1)),
                              (self.opened+timedelta(seconds=1),self.closed+timedelta(seconds=1))]:
            with self.assertRaises(ValueError):decision_time(opened,closed,self.source,self.received,self.now)

    def test_pre_request_cut_loses_current_tick_fixed_cut_includes_it(self):
        source=ROOT/'bot_two_output_build_v4_13_profit_protection_shadow.py'
        tree=ast.parse(source.read_text())
        names={'_fair_build_snapshot','_ec_append_btc_tick','_ec_live_ticks','_live_fair_shadow'}
        functions=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in names]
        class Forest:
            def predict_proba(self,x):
                self.features=x.iloc[0].to_dict()
                return np.array([[.9,.1]])
        class Sigmoid:
            def predict_proba(self,x):return np.array([[.9,.1]])
        completed=pd.DataFrame({'Open':100.,'High':101.,'Low':99.,'Close':100.,'Volume':0.},
            index=pd.date_range(self.opened-timedelta(minutes=6),self.now.replace(second=0),freq='min'))
        completed['source_utc']=completed.index
        forest=Forest()
        features=['elapsed','remaining','current_side','dist_target','abs_dist_target','dist_target_pct',
            'move_from_start','move_from_start_pct','move1','move2','move3','move5','support1','support2',
            'support3','support5','range5','vol5','dist_per_min_remaining','dist_over_range5']
        with tempfile.TemporaryDirectory() as directory:
            env=dict(pd=pd,np=np,deque=deque,_fair_ready=True,_fair_btc=completed,
                _fair_frame_at_cut=frame_at_cut,_fair_price_at_or_before=price_at_or_before,
                _fair_parse_contract_times=lambda ticker:(pd.Timestamp(self.opened),pd.Timestamp(self.closed)),
                _ec_btc_ticks=deque(),_fair_rf=forest,_fair_sigmoid=Sigmoid(),_fair_features=features,
                _fair_model_weights_sha256='w'*64,_fair_model_artifact_sha256='a'*64,
                _btc15_data_path=lambda name:Path(directory)/name)
            exec(compile(ast.Module(body=functions,type_ignores=[]),str(source),'exec'),env)
            # Existing old cutoff is before receipt: independent boundary reader
            # properly excludes that tick. The caller, not the reader, was wrong.
            ticks=pd.DataFrame([dict(source_utc=self.source,observed_utc=self.received,price=110.)])
            old=self.received-timedelta(milliseconds=100)
            oldframe=frame_at_cut(completed,ticks,old)
            self.assertEqual(price_at_or_before(oldframe,old)[0],100.)
            fresh=decision_time(self.opened,self.closed,self.source,self.received,self.now)
            output=env['_live_fair_shadow'](fresh,'KXBTC15M-TEST',105.,110.,.4,.6,self.source,self.received)
            self.assertEqual(forest.features['current_side'],1)
            self.assertEqual(forest.features['dist_target'],5.)
            self.assertEqual(output['dist_target'],110.-105.)
            record=json.loads((Path(directory)/'kalshi_fair_input_frames_v1.jsonl').read_text())
            self.assertEqual(record['btc_source_utc'],self.source.isoformat())
            self.assertEqual(record['btc_observed_utc'],self.received.isoformat())
            self.assertEqual(record['decision_utc'],fresh.isoformat())
            self.assertEqual(set(record['features']),set(features))
            self.assertNotIn('final_side',record['features'])
            self.assertFalse(record['orders'])

    def test_unavailable_future_tick_cannot_change_features(self):
        index=pd.DatetimeIndex([self.opened]);base=pd.DataFrame(dict(Open=[100.],High=[100.],Low=[100.],Close=[100.],Volume=[0.],source_utc=index),index=index)
        ticks=pd.DataFrame([dict(source_utc=self.source,observed_utc=self.received,price=110.),
                            dict(source_utc=self.now+timedelta(seconds=1),observed_utc=self.now+timedelta(seconds=2),price=999.)])
        a=frame_at_cut(base,ticks,self.now);ticks.loc[1,'price']=1.
        b=frame_at_cut(base,ticks,self.now)
        pd.testing.assert_frame_equal(a,b)

    def test_journal_append_preserves_prior_rows_and_rejects_outcome_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input.jsonl'
            kwargs=dict(ticker='KXBTC15M-TEST',target=100.,decision=self.now,btc_source=self.source,
                btc_observed=self.received,btc_price=110.,features={'x':1.,'final_side':0},
                feature_names=['x'],weights_sha256='w'*64,artifact_sha256='a'*64)
            record_model_input(path,**kwargs);prefix=path.read_bytes();record_model_input(path,**kwargs)
            self.assertTrue(path.read_bytes().startswith(prefix))
            self.assertEqual(len(path.read_text().splitlines()),2)
            self.assertNotIn('final_side',json.loads(path.read_text().splitlines()[0])['features'])
            with self.assertRaises(ValueError):record_model_input(path,**dict(kwargs,decision=self.source))


if __name__=='__main__':unittest.main()
