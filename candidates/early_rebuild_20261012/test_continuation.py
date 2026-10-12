"""Fixture tests establish implementation behavior, never observed profitability."""
from copy import deepcopy
import unittest
import numpy as np
from .assessment import SAFETY
from .test_engine import fixture
from .continuation import causal_vector,solve,sigmoid,calibrate,fit,ContinuationEstimator
from .continuation_engine import ContinuationEngine
from .durability import label


def scenario(side='UP',end=890,high_start=20,high_end=600,adverse=None):
    tape=[]
    for t in range(0,end+1,5):
        bid=.64 if high_start<=t<=high_end else .34
        if adverse is not None and t==adverse:bid=.10
        r=fixture(t,side,ask=bid+.01);r['left']=900-t
        tape.append(dict(row=r,sides={side:dict(eligible=True,setup_id='s',reasons=[])}))
    # Entry and decision ASK are35c; subsequent favorable quote64c.
    lm=dict(id='lm',setup_id='s',contract=tape[0]['row']['contract'],side=side,period='fixture',
            decision_time=0,context='PRE_CROSSING',features=None,index=0)
    return lm,tape


class ContinuationTests(unittest.TestCase):
    def test_six_features_up_down_reflection(self):
        vectors=[]
        for side in ('UP','DOWN'):
            rows=[fixture(t,side,ask=.35) for t in range(0,126,5)]
            vectors.append(causal_vector(rows,rows[-1],side))
        np.testing.assert_allclose(vectors[0],vectors[1]);self.assertEqual(len(vectors[0]),6)

    def test_future_receipt_and_endpoint_contamination_rejected(self):
        rows=[fixture(t) for t in range(0,126,5)]
        with self.assertRaisesRegex(ValueError,'ENDPOINT'):causal_vector(rows+[fixture(130)],rows[-1],'UP')
        rows[5]['received']=150
        with self.assertRaisesRegex(ValueError,'FUTURE'):causal_vector(rows,rows[-1],'UP')

    def test_missing_history_stale_and_identity(self):
        rows=[fixture(t) for t in range(0,126,5)]
        with self.assertRaises(ValueError):causal_vector(rows[10:],rows[-1],'UP')
        rows[4]['target']+=1
        with self.assertRaisesRegex(ValueError,'IDENTITY'):causal_vector(rows,rows[-1],'UP')
        rows=[fixture(t) for t in range(0,126,5)];rows[-1]['received']+=11
        with self.assertRaisesRegex(ValueError,'INVALID'):causal_vector(rows,rows[-1],'UP')

    def test_reversal_not_universal_long_positive_gate(self):
        rows=[fixture(t,delta=-t if t<90 else -90+2*(t-90),ask=.35) for t in range(0,126,5)]
        v=causal_vector(rows,rows[-1],'UP');self.assertLess(v[4],0);self.assertGreater(v[2],0)

    def test_primary_price_only(self):
        for ask in (.24,.56,.58,.59):
            rows=[fixture(t,ask=ask) for t in range(0,126,5)]
            with self.assertRaisesRegex(ValueError,'PRIMARY'):causal_vector(rows,rows[-1],'UP')

    def test_up_down_durable_and_delayed_sale(self):
        for side in ('UP','DOWN'):
            lm,t= scenario(side);r=label(lm,t)
            self.assertEqual((r['y'],r['status']),(1,'DURABLE_SUCCESS'))
            self.assertEqual(r['delayed_liquidation']['certificate_at'],80)
            self.assertEqual(r['delayed_liquidation']['sale_at'],90)
            self.assertEqual(r['evidence_class'],'SYNTHETIC_FIXTURE')
            self.assertFalse(r['native_execution_verified'])

    def test_burst_not_durable(self):
        lm,t=scenario(high_end=50);r=label(lm,t)
        self.assertEqual(r['status'],'BURST_ONLY');self.assertEqual(r['y'],0)

    def test_sale_reaction_cannot_use_best_quote(self):
        lm,t=scenario(high_end=80);r=label(lm,t)
        self.assertEqual(r['y'],0);self.assertFalse(r['episodes'][0]['checkpoints']['60']['delayed_accessible'])

    def test_adverse_first_later_rebound_not_success(self):
        lm,t=scenario(high_start=40,adverse=20);r=label(lm,t)
        self.assertEqual(r['status'],'ADVERSE_FIRST');self.assertTrue(r['episodes'])

    def test_gap_breaks_certificate_and_event_order(self):
        lm,t=scenario();t=[z for z in t if z['row']['time']!=30];r=label(lm,t)
        self.assertIsNone(r['y']);self.assertEqual(r['status'],'CENSORED_PATH')
        self.assertEqual(r['episodes'][0]['span'],5)

    def test_missing_tail_not_failure(self):
        lm,t=scenario(end=100,high_start=950);r=label(lm,t)
        self.assertIsNone(r['y']);self.assertEqual(r['status'],'CENSORED_PATH')

    def test_known_cancel_counts_delivery_not_loss(self):
        lm,t=scenario();t[1]['sides']['UP']=dict(eligible=False,setup_id='s',reasons=['PRIMARY_PRICE_WINDOW_LOST'])
        t[1]['row']['up_ask']=.60;t[1]['row']['up_bid']=.59
        r=label(lm,t);self.assertEqual(r['y'],0);self.assertIsNone(r['entry']);self.assertTrue(r['price_lost'])

    def test_qualification_recovery_does_not_uncancel(self):
        lm,t=scenario();t[1]['sides']['UP']['eligible']=False
        self.assertEqual(label(lm,t)['status'],'CANCELED_ENTRY')

    def test_delayed_entry_missing(self):
        lm,t=scenario();t=t[:2]+t[5:]
        self.assertEqual(label(lm,t)['reasons'],['DELAYED_ENTRY_OBSERVATION_MISSING'])

    def test_price_loss_after_cancellation_still_reported(self):
        lm,t=scenario();t[1]['sides']['UP']['eligible']=False
        t[2]['row']['up_ask']=.65;t[2]['row']['up_bid']=.64
        t[2]['row']['down_ask']=.36;t[2]['row']['down_bid']=.35
        r=label(lm,t);self.assertEqual(r['status'],'CANCELED_ENTRY')
        self.assertFalse(r['delayed_price_observation']['primary']);self.assertIsNone(r['entry'])

    def test_actual_retained_evidence_alias_is_quote_only(self):
        import json,gzip
        from pathlib import Path
        root=Path(__file__).resolve().parents[2]
        data=json.loads(gzip.decompress((root/'audit/early_condition_20261011/diagnostic_inputs.json.gz').read_bytes()))
        r=next(iter(data.values()))[0]
        self.assertEqual(r['evidence_class'],'COMMON_OBSERVED_NO_NATIVE_RECEIPT')
        lm=dict(id='actual-domain',setup_id='s',contract=r['contract'],side='UP',period='test',decision_time=r['received'],context='PRE_CROSSING',features=None,index=0)
        got=label(lm,[dict(row=r,sides={})])
        self.assertNotIn('UNKNOWN_EVIDENCE_DOMAIN',got['reasons']);self.assertFalse(got['native_execution_verified'])

    def test_native_missing_not_imputed_from_fixture(self):
        lm,t=scenario();r=label(lm,t,native=True);self.assertIsNone(r['y']);self.assertFalse(r['native_execution_verified'])

    def test_duration_checkpoints_are_descriptive(self):
        lm,t=scenario();r=label(lm,t)
        self.assertEqual(r['delayed_liquidation']['sale_at'],90)
        for seconds in (120,180,240,300,420):self.assertEqual(r['checkpoints'][str(seconds)]['accessible'],1)
        self.assertGreater(r['episodes'][0]['span'],420)

    def test_future_price_changes_cannot_change_feature(self):
        rows=[fixture(t) for t in range(0,151,5)];prefix=rows[:26]
        before=causal_vector(prefix,prefix[-1],'UP')
        rows[-1]['btc']+=5000;rows[-1]['up_bid']=.99
        self.assertEqual(before,causal_vector(prefix,prefix[-1],'UP'))

    def test_logistic_and_intercept_calibration(self):
        x=np.array([[-2.],[-1.],[1.],[2.]]);y=np.array([0.,0.,1.,1.]);w=np.ones(4)
        b=solve(x,y,w);self.assertGreater(b[1],0)
        logits=np.column_stack([np.ones(4),x])@b
        shift=calibrate(logits,y,w);self.assertAlmostEqual(shift,0,places=8)
        with self.assertRaisesRegex(ValueError,'CLASSES'):solve(x,np.ones(4),w)

    def test_fixture_labels_cannot_train_empirical_artifact(self):
        lm,t=scenario();r=label(lm,t);r['period']='sep26_27_development'
        with self.assertRaisesRegex(ValueError,'EVIDENCE'):fit([r],[],{})

    def test_artifact_hash_rejected(self):
        with self.assertRaisesRegex(ValueError,'IDENTITY'):ContinuationEstimator({'body':{},'artifact_sha256':'bad'},expected_sha256='bad')

    def test_engine_cadence_duplicates_origin_and_authority(self):
        e=ContinuationEngine()
        for t in range(0,201,5):e.process(fixture(t,ask=.35))
        marks=deepcopy(e.landmarks);e.process(fixture(200,ask=.35))
        self.assertEqual(marks,e.landmarks)
        self.assertTrue(all(b['decision_time']-a['decision_time']>=10 for a,b in zip(marks,marks[1:])))
        self.assertFalse(e.tickets);self.assertFalse(e.last_output['actionable'])
        started=e.start_simulation('UP','fixture-only',200);self.assertTrue(started['accepted'])
        origin=deepcopy(e.managers[0].origin)
        e.tick(211);self.assertEqual(origin,e.managers[0].origin);self.assertIsNone(e.managers[0].core.terminal)

    def test_reset_allows_new_setup_not_cheap_price(self):
        e=ContinuationEngine()
        for t in range(0,201,5):e.process(fixture(t,ask=.35))
        first=e.setups['UP']['id']
        for t in range(205,251,5):e.process(fixture(t,ask=.30))
        self.assertEqual(first,e.setups['UP']['id'])
        for t in range(255,351,5):e.process(fixture(t,delta=200-3*(t-250),ask=.30))
        for t in range(355,451,5):e.process(fixture(t,delta=-100+3*(t-350),ask=.30))
        self.assertNotEqual(first,e.setups['UP']['id'])

    def test_out_of_order_and_future_quote_cannot_certify(self):
        for field in ('time','received'):
            lm,t=scenario();t[6]['row'][field]=1000
            r=label(lm,t);self.assertNotEqual(r['y'],1)

    def test_continuation_hook_preserves_baseline_management(self):
        from .engine import Engine
        a=Engine();b=ContinuationEngine()
        for e in (a,b):
            for t in range(0,201,5):e.process(fixture(t,ask=.35))
            self.assertTrue(e.start_simulation('UP','same',200)['accepted'])
            for t in range(205,401,5):e.process(fixture(t,delta=180-3*(t-200),ask=.30))
        self.assertEqual(a.managers[0].origin,b.managers[0].origin)
        self.assertEqual(a.managers[0].core.terminal,b.managers[0].core.terminal)
        self.assertEqual(a.managers[0].core.events,b.managers[0].core.events)


class ArtifactIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json,gzip
        from pathlib import Path
        cls.root=Path(__file__).resolve().parents[2];p=cls.root/'audit/early_continuation_20261012/evaluation'
        cls.artifact=json.loads((p/'CONTINUATION_ARTIFACT.json').read_text())
        cls.estimator=ContinuationEstimator(cls.artifact,expected_sha256=cls.artifact['artifact_sha256'])
        marks=json.loads(gzip.decompress((p/'LANDMARKS.json.gz').read_bytes()))
        cls.lm=next(m for m in marks if m['score']['probability'] is not None)
        manifest=json.loads((p/'SOURCE_MANIFEST.json').read_text());item=next(v for v in manifest if v['period']==cls.lm['period'])
        seq=json.loads(gzip.decompress((cls.root/item['path']).read_bytes()))[cls.lm['contract']]
        cls.prefix=[r for r in seq if r['received']<=cls.lm['decision_time']];cls.row=cls.prefix[-1]

    def test_actual_artifact_inference_reproduces_and_stays_uncalibrated(self):
        p=self.estimator.infer(self.row,self.lm['side'],self.prefix,self.lm['context'])
        self.assertAlmostEqual(p['probability'],self.lm['score']['probability'])
        self.assertEqual(p['status'],'UNCALIBRATED_EXPLORATORY_ESTIMATE')
        self.assertFalse(p['ready']);self.assertFalse(p['diagnostic_selected']);self.assertFalse(p['actionable'])
        self.assertEqual(len(self.artifact['body']['bootstrap']),200)

    def test_corrupt_shape_method_and_calibration_rejected(self):
        from .resale import digest
        for which in ('shape','method','calibration'):
            a=deepcopy(self.artifact)
            if which=='shape':a['body']['model']['coefficients'].pop()
            elif which=='method':a['body']['method']['C']=2
            else:a['body']['model']['calibration_intercept']=1
            a['artifact_sha256']=digest(a['body'])
            with self.assertRaises(ValueError):ContinuationEstimator(a,expected_sha256=a['artifact_sha256'])

    def test_artifact_chronology_and_fixture_domain_rejected(self):
        for which in ('chronology','fixture'):
            r=deepcopy(self.row)
            if which=='chronology':r['received']=self.artifact['body']['available_after']
            else:r['evidence_class']='SYNTHETIC_FIXTURE'
            p=self.estimator.infer(r,self.lm['side'],self.prefix,self.lm['context'])
            self.assertIsNone(p['probability']);self.assertFalse(p['diagnostic_selected'])

    def test_settlement_probability_not_a_predictor(self):
        prefix=deepcopy(self.prefix);prefix[-1]['p']=.99
        p=self.estimator.infer(prefix[-1],self.lm['side'],prefix,self.lm['context'])
        self.assertEqual(p['probability'],self.lm['score']['probability'])

    def test_expired_score_cannot_be_refreshed_by_tick(self):
        e=ContinuationEngine(self.estimator)
        for r in self.prefix:e.process(r)
        count=len(e.landmarks);e.tick(self.row['received']+10)
        self.assertEqual(count,len(e.landmarks));self.assertFalse(e.latest_scores)
        self.assertFalse(e.last_output['research_qualified'])

if __name__=='__main__':unittest.main()
