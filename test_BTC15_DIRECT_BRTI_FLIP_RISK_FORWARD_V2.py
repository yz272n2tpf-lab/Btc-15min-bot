import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd

import BTC15_DIRECT_BRTI_FLIP_RISK_FORWARD_V2 as m


def state(contract='A', left=880.0, *, price=101.0, target=100.0, generated=None, chart=None):
    generated=generated or datetime(2026,9,15,22,0,tzinfo=timezone.utc)
    return {
        'contract':contract,
        'generated_utc':generated.isoformat().replace('+00:00','Z'),
        'timer':{'seconds_left':left},
        'market':{'brti_value':price,'target':target},
        'chart':{'points':chart or []},
    }


def chart_points(now, *, current=101.0, seconds=305, step=5):
    pts=[]
    for back in range(seconds,0,-step):
        t=now-timedelta(seconds=back)
        pts.append({'t':t.isoformat().replace('+00:00','Z'),'brti':current-0.001*back,'brti_age_sec':1.0})
    return pts


class FlipRiskForwardV2Tests(unittest.TestCase):
    def setUp(self):
        m.reset_state_for_tests()
        self.t0=datetime(2026,9,15,22,0,tzinfo=timezone.utc)

    def test_startup_contract_excluded_and_first_rollover_arms(self):
        m.observer_cycle(state('A',700),self.t0)
        self.assertFalse(m.STATE['live_scoring_armed'])
        self.assertEqual(m.STATE['startup_contract'],'A')
        self.assertEqual(m.STATE['eligible_contracts'],[])
        m.observer_cycle(state('B',885),self.t0+timedelta(seconds=5))
        self.assertTrue(m.STATE['live_scoring_armed'])
        self.assertIn('B',m.STATE['eligible_contracts'])
        self.assertNotIn('A',m.STATE['eligible_contracts'])

    def test_late_first_seen_contract_excluded_fail_closed(self):
        m.observer_cycle(state('A',700),self.t0)
        m.observer_cycle(state('B',839.9),self.t0+timedelta(seconds=5))
        self.assertNotIn('B',m.STATE['eligible_contracts'])
        self.assertAlmostEqual(m.STATE['excluded_late']['B'],839.9)

    def test_live_feature_builder_uses_causal_five_minute_chart(self):
        now=self.t0
        pts=chart_points(now,current=101.0,seconds=305,step=5)
        d=state('B',540.0,price=101.0,target=100.0,generated=now,chart=pts)
        feat=m.live_features(d,9)
        self.assertIsNotNone(feat)
        self.assertEqual(feat['current_side'],'UP')
        self.assertTrue(all(k in feat for k in m.v1.FEATURES))
        self.assertGreater(feat['aligned_move_1m_pct'],0)
        # Future chart point must never become a lag source.
        hist=m.chart_frame(d)
        future=pd.DataFrame([{'timestamp_utc':pd.Timestamp(now+timedelta(seconds=1)),'direct_brti':999.0,'brti_age_sec':1.0}])
        hist=pd.concat([hist,future],ignore_index=True).sort_values('timestamp_utc')
        lag=m._lag_from_chart(hist,pd.Timestamp(now),60.0)
        self.assertIsNotNone(lag)
        self.assertNotEqual(lag,999.0)

    def test_prediction_is_immutable_once_captured(self):
        m.observer_cycle(state('A',700),self.t0)
        m.observer_cycle(state('B',885),self.t0+timedelta(seconds=5))
        feat={k:0.01 for k in m.v1.FEATURES}
        feat.update({'current_side':'UP','current_brti':101.0,'target':100.0,'generated_utc':'2026-09-15T22:06:00Z'})
        d=state('B',540.0,generated=self.t0+timedelta(minutes=6))
        with patch.object(m,'live_features',return_value=feat), patch.object(m,'predict_from_features',return_value=(0.2,0.1)):
            m.observer_cycle(d,self.t0+timedelta(minutes=6))
        first=dict(m.STATE['predictions']['B'][9])
        with patch.object(m,'live_features',return_value=feat), patch.object(m,'predict_from_features',return_value=(0.9,0.8)):
            m.observer_cycle(d,self.t0+timedelta(minutes=6,seconds=2))
        self.assertEqual(m.STATE['predictions']['B'][9],first)
        self.assertAlmostEqual(first['flip_prob'],0.1)

    def test_sparse_high_stay_cohort_keeps_collecting_after_base_sample(self):
        m.MODEL['historical_training_prior']=0.25
        m.MODEL['ready']=True
        for i in range(30):
            c=f'C{i:02d}'
            m.STATE['eligible_contracts'].append(c)
            m.STATE['ended_contracts'].append(c)
            m.STATE['settlements'][c]='UP'
            bucket={}
            for minute in range(1,9):
                bucket[minute]={
                    'contract':c,'target_remaining_min':minute,'current_side':'UP',
                    'raw_flip_prob':0.20,'flip_prob':0.20,'stay_prob':0.80,
                }
            m.STATE['predictions'][c]=bucket
        s=m.summarize_state()
        self.assertEqual(s['prediction_complete_contracts'],30)
        self.assertEqual(s['settled_review_predictions'],240)
        self.assertTrue(s['sample_ready'])
        self.assertFalse(s['decision_ready'])
        self.assertEqual(s['status'],'COLLECTING_HIGH_STAY_COHORT')
        self.assertFalse(s['gate_pass'])

    def test_historical_split_constants_are_effectively_70_then_24(self):
        ordered=[f'C{i}' for i in range(94)]
        train=ordered[:70]
        cal=ordered[70:94]
        self.assertEqual(len(train),70)
        self.assertEqual(len(cal),24)
        self.assertFalse(set(train)&set(cal))
        self.assertEqual(train[-1],'C69')
        self.assertEqual(cal[0],'C70')
        self.assertEqual(cal[-1],'C93')


if __name__=='__main__':
    unittest.main()
