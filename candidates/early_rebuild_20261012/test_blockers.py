"""Behavioral evidence for the bounded corrections; synthetic execution stays fixture-only."""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import gzip,json,unittest
from .assessment import Rules,source_reasons
from .engine import Engine
from .management import ThesisRecoveryManagement
from .test_engine import warm,fixture
from .resale import build_label,causal_features,vector,digest,Estimator,METHOD
from .execution import DepthBook,ExecutionRegistry,execution_assessment,bind_fee_changes
from .blocker_diagnostics import ROOT,OUT,native_row


def envelope(r):
    f=r['native_frame'];q=f['quote']
    return dict(evidence_class='SYNTHETIC_FIXTURE',stream_epoch='fixture-book-stream',received_ts=f['feature_cutoff']-.05,
        payload=dict(type='orderbook_snapshot',sending_ts_ms=q['exchange_ts_ms'],sid=99,seq=1,
          msg=dict(market_ticker=r['contract'],market_id=q['market_id'],
            yes_dollars_fp=[[str(r['up_bid']),'5.00']],no_dollars_fp=[[str(r['down_bid']),'5.00']])))


def fixture_packet():
    r=native_row();r['evidence_class']='SYNTHETIC_FIXTURE';f=r['native_frame']
    iso=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
    fee=dict(evidence_class='SYNTHETIC_FIXTURE',contract=r['contract'],role='TAKER',currency='USD',
        effective_from=f['official_open'],effective_until=f['official_close'],review_available_ts=f['feature_cutoff']-1,
        account_scope_reference='fixture-only',override_evidence_sha256='a'*64,formula_evidence_sha256='b'*64,
        schedule_evidence_sha256='c'*64,multiplier=1,fee_type='quadratic')
    packet=dict(evidence_class='SYNTHETIC_FIXTURE',native_frame_sha256=digest(f),
        market=dict(received_ts=f['feature_cutoff']-5,payload=dict(market=dict(ticker=r['contract'],market_type='binary',
        strike_type='greater',floor_strike=r['target'],open_time=iso(f['official_open']),close_time=iso(f['official_close']),
        event_ticker=r['contract'].rsplit('-',1)[0],rules_primary='SYNTHETIC TEST ONLY'))),
        intended_quantity='2',entry_delay_seconds=10,exit_delay_seconds=10,
        book_messages=[envelope(r)],fee_policy_sha256=digest(fee))
    r['execution_packet_sha256']=digest(packet)
    return r,packet,fee


class ExecutionTests(unittest.TestCase):
    def test_real_frame_partial_binding_and_missing_inputs_visible(self):
        r=native_row();a=execution_assessment(r,'UP',r['received'])
        self.assertTrue(a['coverage']['contract_target_official_window'])
        self.assertTrue(a['coverage']['observed_series_fee_terms'])
        self.assertFalse(a['valid']);self.assertFalse(a['coverage']['original_quote_receipt'])
        self.assertIn('DEPTH_SIZE_BINDING_UNSUPPORTED',a['blockers'])

    def test_fixture_complete_packet_and_both_sides(self):
        r,p,f=fixture_packet();reg=ExecutionRegistry([p],[f],permit_fixtures=True)
        for side in ('UP','DOWN'):
            a=execution_assessment(r,side,r['received'],reg,2)
            self.assertTrue(a['valid'],a);self.assertFalse(a['coverage']['entry_depth']['actual_fill'])
            self.assertFalse(a['actionable'])

    def test_fixture_never_authorizes_actual_frame(self):
        r,p,f=fixture_packet();r['evidence_class']='RETAINED_NATIVE_FRAME'
        a=execution_assessment(r,'UP',r['received'],ExecutionRegistry([p],[f],permit_fixtures=True),2)
        self.assertFalse(a['valid']);self.assertIn('FIXTURE_CANNOT_AUTHORIZE_NATIVE_OBSERVATION',a['blockers'])

    def test_registry_size_fees_and_packet_identity(self):
        r,p,f=fixture_packet()
        for reg,n in [(ExecutionRegistry([p],[],permit_fixtures=True),2),
                      (ExecutionRegistry([p],[f],permit_fixtures=True),3),
                      (ExecutionRegistry([],[],permit_fixtures=True),2)]:
            self.assertFalse(execution_assessment(r,'UP',r['received'],reg,n)['valid'])

    def test_stale_future_malformed_mismatch_and_negative_book(self):
        r=native_row();e=envelope(r)
        variants=[]
        for path,value in [('received_ts',r['received']+1)]:
            z=deepcopy(e);z[path]=value;variants.append(z)
        z=deepcopy(e);z['payload']['sending_ts_ms']-=20000;variants.append(z)
        z=deepcopy(e);z['payload']['msg']['market_ticker']='wrong';variants.append(z)
        for pair in [['.82','-1'],['NaN','2'],['.82'],['.82','Infinity']]:
            z=deepcopy(e);z['payload']['msg']['yes_dollars_fp']=[pair];variants.append(z)
        for z in variants:
            b=DepthBook(r['contract'])
            with self.assertRaises(ValueError):b.feed(z,r['received'])
            self.assertFalse(b.valid)

    def test_depth_price_coverage_sequence_and_latched_gap(self):
        r=native_row();e=envelope(r);b=DepthBook(r['contract']);b.feed(e,r['received'])
        with self.assertRaisesRegex(ValueError,'INSUFFICIENT'):b.coverage('UP','BUY',6,r['up_ask'],r['received'])
        with self.assertRaisesRegex(ValueError,'INSUFFICIENT'):b.coverage('UP','BUY',1,r['up_ask']-.01,r['received'])
        z=deepcopy(e);z['received_ts']+=.01;z['payload'].update(type='orderbook_delta',seq=2)
        z['payload']['msg']=dict(market_ticker=r['contract'],market_id=e['payload']['msg']['market_id'],
               price_dollars=str(r['down_bid']),delta_fp='2.00',side='no',ts_ms=e['payload']['sending_ts_ms'])
        b.feed(z,r['received']);self.assertEqual(b.coverage('UP','BUY',7,r['up_ask'],r['received'])['quantity'],'7')
        z['payload']['seq']=4
        with self.assertRaisesRegex(ValueError,'GAP'):b.feed(z,r['received'])
        z['payload']['seq']=3
        with self.assertRaisesRegex(ValueError,'SNAPSHOT'):b.feed(z,r['received'])

    def test_out_of_order_future_event_and_stale_decision(self):
        r=native_row();e=envelope(r)
        b=DepthBook(r['contract']);b.feed(e,r['received'])
        with self.assertRaises(ValueError):b.coverage('DOWN','SELL',1,r['down_bid'],r['received']+20)
        z=deepcopy(e);z['received_ts']-=1;z['payload']['seq']=2
        with self.assertRaises(ValueError):b.feed(z,r['received'])
        b=DepthBook(r['contract']);b.feed(e,r['received'])
        z=deepcopy(e);z['payload'].update(type='orderbook_delta',seq=2)
        z['payload']['msg'].update(side='yes',price_dollars='.82',delta_fp='1',ts_ms=e['payload']['sending_ts_ms']+100)
        with self.assertRaisesRegex(ValueError,'FUTURE'):b.feed(z,r['received'])

    def test_native_mismatch_and_future_clock_are_rejected(self):
        r=native_row()
        for key,value in [('target',1),('received',r['time']-1),('up_bid',.01)]:
            z=deepcopy(r);z[key]=value
            self.assertTrue(execution_assessment(z,'UP',r['received'])['blockers'])

    def test_fee_effective_period_not_source_updated_time(self):
        response=dict(series_fee_change_arr=[dict(id='fixture1',series_ticker='KXBTC15M',fee_type='quadratic',
            fee_multiplier=1,scheduled_ts='2026-10-11T00:00:00Z'),dict(id='fixture2',series_ticker='KXBTC15M',
            fee_type='quadratic',fee_multiplier=2,scheduled_ts='2026-10-12T00:00:00Z')])
        a=bind_fee_changes(response,'KXBTC15M',1791729376)
        self.assertEqual(a['multiplier'],1);self.assertFalse(a['applicable_account_fee_verified'])
        with self.assertRaises(ValueError):bind_fee_changes(response,'KXBTC15M',1)
        r,p,f=fixture_packet();f['effective_until']=r['received']-1;p['fee_policy_sha256']=digest(f);r['execution_packet_sha256']=digest(p)
        self.assertFalse(execution_assessment(r,'UP',r['received'],ExecutionRegistry([p],[f],permit_fixtures=True),2)['valid'])


class ManagementTests(unittest.TestCase):
    def pair(self,side):
        a=warm(side=side,pre=True);b=warm(Engine(management_class=ThesisRecoveryManagement),side=side,pre=True)
        for e in (a,b):self.assertTrue(e.start_simulation(side,'test',60)['accepted'])
        return a,b

    def test_up_down_warning_recovers_without_crossing_and_exit_unchanged(self):
        for side in ('UP','DOWN'):
            a,b=self.pair(side);origin=b.managers[0].origin
            for t in range(65,126,5):
                for e in (a,b):e.process(fixture(t,side,delta=-270))
            self.assertEqual(b.managers[0].core.guidance,'WATCH')
            for t in range(130,201,5):
                for e in (a,b):e.process(fixture(t,side,delta=-270+.5*(t-125)))
            self.assertEqual(a.managers[0].core.guidance,'WATCH');self.assertEqual(b.managers[0].core.guidance,'HOLD')
            self.assertEqual(b.managers[0].view()['display'],'WATCH')
            for t in range(205,281,5):
                for e in (a,b):e.process(fixture(t,side,delta=-230-2*(t-200),ask=.40))
            self.assertIsNotNone(b.managers[0].core.terminal)
            self.assertEqual(a.managers[0].core.terminal,b.managers[0].core.terminal)
            self.assertEqual(b.managers[0].origin,origin)

    def test_protection_outage_and_no_timer_are_preserved(self):
        a,b=self.pair('UP');m=b.managers[0]
        m.protect_latched=True
        for t in range(65,126,5):b.process(fixture(t,delta=-270))
        for t in range(130,201,5):b.process(fixture(t,delta=-270+.5*(t-125)))
        self.assertEqual(m.view()['internal_state'],'PROTECT')
        m.protect_latched=False;b.tick(211)
        self.assertEqual(m.core.guidance,'WATCH');self.assertIsNone(m.approach_recovery_since)
        for t in range(215,751,5):b.process(fixture(t,delta=-230+.2*(t-210)))
        self.assertIsNone(m.core.terminal);self.assertGreater(b.last['time']-m.origin.entry_time,420)


class LabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(gzip.decompress((ROOT/'audit/early_condition_20261011/development_inputs.json.gz').read_bytes()))
        rr=json.loads((ROOT/'audit/early_rebuild_20261012/evaluation/sep26_27_development.json').read_text())['setups']
        cls.rec=next(r for r in rr if r['hypothetical_after_cost']);cls.seq=cls.data[cls.rec['setup']['contract']]

    def test_retained_label_binds_first_exit_and_declared_costs(self):
        a=build_label(self.rec,self.seq)
        self.assertIsNone(a['label_error']);self.assertEqual(a['net_cents'],self.rec['hypothetical_after_cost']['net_cents'])
        for mutate in ('price','time','cost','cancel'):
            r=deepcopy(self.rec)
            if mutate=='price':r['hypothetical_after_cost']['exit_bid']+=.01
            if mutate=='time':r['hypothetical_after_cost']['exit_observed_at']+=5
            if mutate=='cost':r['hypothetical_after_cost']['reserve']=0
            if mutate=='cancel':r['cancellation_reasons']=['CANCELED']
            self.assertIsNotNone(build_label(r,self.seq)['label_error'])

    def test_future_and_probability_do_not_change_causal_vector(self):
        at=self.rec['observational_qualification']['time'];side=self.rec['setup']['side']
        r,x=causal_features(self.seq,at,side);a=vector(r,side,x)
        seq=deepcopy(self.seq)
        for z in seq:
            z['p']=.99
            if z['received']>at:z['btc']=1;z['brti']=1
        r,x=causal_features(seq,at,side);self.assertEqual(a,vector(r,side,x))


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.artifact=json.loads((OUT/'EXPLORATORY_RESALE_ARTIFACT.json').read_text())
        self.sha=self.artifact['artifact_sha256'];self.management=self.artifact['body']['management_sha256']
        self.est=Estimator(self.artifact,expected_sha256=self.sha,management_sha256=self.management)
        ledger=json.loads((OUT/'LABEL_LEDGER.json').read_text())
        self.example=next(x for x in ledger if x['period']!='sep26_27_development' and x['features'] is not None)

    def test_artifact_identity_policy_and_nonfinite_checks(self):
        with self.assertRaises(ValueError):Estimator(self.artifact,expected_sha256='0'*64,management_sha256=self.management)
        with self.assertRaises(ValueError):Estimator(self.artifact,expected_sha256=self.sha,management_sha256='bad')
        bad=deepcopy(self.artifact);bad['body']['method']['ridge']=0;bad['artifact_sha256']=digest(bad['body'])
        with self.assertRaises(ValueError):Estimator(bad,expected_sha256=bad['artifact_sha256'],management_sha256=self.management)
        with self.assertRaises(FileNotFoundError):Estimator.load(OUT/'missing.json',expected_sha256=self.sha,management_sha256=self.management)

    def test_malformed_pinned_artifact_rejects_bad_support(self):
        for mode in ('shape','scale','time'):
            a=deepcopy(self.artifact);c=next(iter(a['body']['cells'].values()))
            if mode=='shape':c['min']=[]
            if mode=='scale':c['scale'][0]=0
            if mode=='time':a['body']['trained_through']='unknown'
            a['artifact_sha256']=digest(a['body'])
            with self.assertRaises(ValueError):Estimator(a,expected_sha256=a['artifact_sha256'],management_sha256=self.management)

    def test_estimate_cannot_attach_to_a_different_management_policy(self):
        with self.assertRaisesRegex(ValueError,'FROZEN_BASELINE_MANAGEMENT'):
            Engine(conditional_estimator=self.est,management_class=ThesisRecoveryManagement)
        from dataclasses import replace
        with self.assertRaisesRegex(ValueError,'FROZEN_BASELINE_MANAGEMENT'):
            Engine(conditional_estimator=self.est,rules=replace(Rules(),exit_seconds=10))

    def test_engine_actual_record_inference_matches_frozen_diagnostic(self):
        pp=json.loads((OUT/'EXPOSED_LATER_PREDICTIONS.json').read_text())
        expected=next(p for p in pp if p['estimate']['status']=='EXPLORATORY_QUOTE_ESTIMATE')
        manifest=json.loads((ROOT/'audit/early_rebuild_20261012/evaluation/INPUTS.json').read_text())
        item=next(m for m in manifest if expected['contract'] in m['contracts'])
        seq=json.loads(gzip.decompress((ROOT/item['path']).read_bytes()))[expected['contract']]
        e=Engine(conditional_estimator=self.est)
        for row in seq:e.process(row)
        actual=next(v['economics'] for v in e.events if v['event']=='EXPLORATORY_RESALE_ASSESSMENT' and v['setup_id']==expected['setup_id'])
        self.assertEqual(actual,expected['estimate']);self.assertFalse(e.tickets)

    def test_real_estimate_is_not_buy_authority_or_fixture_support(self):
        predictions=json.loads((OUT/'EXPOSED_LATER_PREDICTIONS.json').read_text())
        a=next(p['estimate'] for p in predictions if p['estimate']['status']=='EXPLORATORY_QUOTE_ESTIMATE')
        self.assertIsInstance(a['expected_net_cents'],float);self.assertIsInstance(a['downside_tail_cents'],float)
        self.assertFalse(a['ready']);self.assertFalse(a['actionable']);self.assertTrue(a['reasons'])
        e=warm(Engine(conditional_estimator=self.est));self.assertFalse(e.tickets)
        self.assertTrue(any(v['event']=='EXPLORATORY_RESALE_ASSESSMENT' for v in e.events))

    def test_unsupported_price_context_time_and_selection_fail_closed(self):
        r=native_row();x=dict(context='PRE_CROSSING',move_short=1,brti_short=1,short_range=10,
                             short_efficiency=.5,brti_efficiency=.5)
        for side in ('UP','DOWN'):
            a=self.est.infer(r,side,x,selection_point=True)
            self.assertEqual(a['status'],'UNESTIMATED');self.assertIsNone(a['expected_net_cents'])
        r['up_ask']=.45;r['up_bid']=.44;r['down_bid']=.55;r['down_ask']=.56
        r['received']=r['time']=1
        a=self.est.infer(r,'UP',x,selection_point=True)
        self.assertIn('ARTIFACT_LABELS_NOT_AVAILABLE_AT_DECISION',a['reasons'])
        self.assertIn('FIRST_QUALIFICATION_SELECTION_REQUIRED',self.est.infer(r,'UP',x)['reasons'])

if __name__=='__main__':unittest.main()
