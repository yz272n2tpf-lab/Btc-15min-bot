"""History-readiness mechanics only. No fitting, calibration or strategy replay."""
from copy import deepcopy
from dataclasses import fields,replace
import hashlib,json
from pathlib import Path
import unittest
from .assessment import SAFETY
from .test_engine import fixture
from .engine import Engine
from .continuation import causal_vector,ContinuationEstimator,METHOD
from .continuation_engine import ContinuationEngine
from .underlying_history import Observation,Snapshot,UnderlyingHistory,FIXTURE,PROXY,NATIVE,observed_proxy

ROOT=Path(__file__).resolve().parents[2]


def observation(r):
    return Observation(time=r['time'],received=r['received'],btc=r['btc'],brti=r['brti'],
        source_id='FIXTURE_PAIR',source_epoch='pair1',record_id=str(r['time']),evidence_class=FIXTURE,
        btc_source_time=r['time'],btc_received_time=r['received'],brti_source_time=r['time'],
        brti_received_time=r['received'],btc_source_id='FIXTURE_BTC',brti_source_id='FIXTURE_BRTI',
        btc_epoch='btc1',brti_epoch='brti1')


def crossing(side='UP'):
    e=ContinuationEngine(underlying_history=UnderlyingHistory());a=Engine()
    for t in range(760,946,5):
        r=fixture(t,side,ask=.35,contract='A' if t<900 else 'B',close=900 if t<900 else 1800)
        if t>=900:r['target']=100200.
        e.ingest_underlying(observation(r),r['received']);e.process(r);a.process(r)
    return e,a


class UnderlyingHistoryTests(unittest.TestCase):
    def test_immediate_rollover_context_both_directions(self):
        for side in ('UP','DOWN'):
            e=ContinuationEngine(underlying_history=UnderlyingHistory())
            for t in range(780,901,5):
                r=fixture(t,side,ask=.35,contract='A' if t<900 else 'B',close=900 if t<900 else 1800)
                if t==900:r['target']=100200.
                e.ingest_underlying(observation(r),t);out=e.process(r)
            v=e.continuation_context(side)
            self.assertEqual(len(e.history),1);self.assertFalse(e.setups)
            self.assertEqual(v[:2],[35.,15.]);self.assertAlmostEqual(v[2],1);self.assertAlmostEqual(v[3],1)
            self.assertAlmostEqual(v[4],1);self.assertAlmostEqual(v[5],32.5/60)
            self.assertFalse(out['research_qualified'])

    def test_contract_specific_state_never_carried(self):
        e,a=crossing()
        self.assertTrue(all(r['contract']=='B' and r['target']==100200 for r in e.history))
        self.assertTrue(all(s['contract']=='B' for s in e.setups.values()))
        self.assertEqual(e.close,1800);self.assertTrue(e.landmarks[-1]['features'])
        self.assertEqual([(s['id'],s['confirmed']) for s in e.setups.values()],[(s['id'],s['confirmed']) for s in a.setups.values()])
        self.assertEqual(e.history,a.history)
        self.assertFalse(e.tickets);self.assertFalse(e.managers)

    def test_schema_has_no_contract_target_quotes_or_origin(self):
        names={f.name for f in fields(Observation)}
        self.assertFalse(names&{'contract','target','left','close','up_bid','up_ask','ticket','origin','manager'})
        with self.assertRaises(TypeError):Observation(**{**observation(fixture(1)).__dict__,'target':1})

    def test_identical_same_contract_features(self):
        rows=[fixture(t,ask=.35) for t in range(0,151,5)];h=UnderlyingHistory()
        for r in rows:h.ingest(observation(r),r['received'])
        for side in ('UP','DOWN'):
            r=deepcopy(rows[-1]);r.update(up_bid=.49,up_ask=.50,down_bid=.50,down_ask=.51)
            hist=rows[:-1]+[r]
            self.assertEqual(causal_vector(hist,r,side),causal_vector(hist,r,side,underlying_history=h.snapshot()))

    def test_no_input_preserves_old_unavailability_and_baseline(self):
        a=ContinuationEngine();b=ContinuationEngine(underlying_history=None)
        for t in range(0,101,5):
            r=fixture(t,ask=.35);self.assertEqual(a.process(r),b.process(r))
        self.assertEqual(a.landmarks,b.landmarks)
        with self.assertRaisesRegex(ValueError,'120S'):a.continuation_context('UP')

    def test_explicit_missing_input_does_not_fallback(self):
        e=ContinuationEngine(underlying_history=UnderlyingHistory())
        for t in range(0,151,5):e.process(fixture(t,ask=.35))
        with self.assertRaisesRegex(ValueError,'UNAVAILABLE'):e.continuation_context('UP')

    def test_component_age_rechecked_at_decision_not_old_receipt(self):
        rows=[fixture(t,ask=.35) for t in range(0,126,5)];h=UnderlyingHistory()
        for r in rows:h.ingest(observation(r),r['received'])
        r=deepcopy(rows[-1]);r['received']+=6
        with self.assertRaisesRegex(ValueError,'CURRENT_COMPONENT_STALE'):
            causal_vector([r],r,'UP',underlying_history=h.snapshot())
        e,_=crossing();e.tick(e.clock+6)
        with self.assertRaisesRegex(ValueError,'CURRENT_COMPONENT_STALE'):e.continuation_context('UP')

    def test_invalid_independent_source_does_not_change_onset_or_final(self):
        e,a=crossing();before=deepcopy(e.setups);clock=e.clock
        with self.assertRaises(ValueError):e.ingest_underlying(replace(observation(fixture(clock+1)),brti=-1),clock+1)
        self.assertEqual(before,e.setups);self.assertEqual(clock,e.clock)
        self.assertFalse(e.latest_scores);self.assertFalse(e.last_output['actionable'])

    def test_invalid_clocks_prices_and_source_identity(self):
        good=observation(fixture(150))
        bad=[replace(good,time=151),replace(good,received=151),replace(good,btc=float('nan')),
             replace(good,btc_source_time=None),replace(good,brti_source_time=144),
             replace(good,btc_source_time=139),replace(good,btc_received_time=151),
             replace(good,brti_source_id=None),replace(good,btc_epoch=None),
             replace(good,time=139),replace(good,source_epoch='')]
        for z in bad:
            with self.subTest(z=z),self.assertRaises(ValueError):UnderlyingHistory().ingest(z,150)

    def test_out_of_order_invalidates_buffer(self):
        h=UnderlyingHistory();h.ingest(observation(fixture(150)),150)
        with self.assertRaises(ValueError):h.ingest(observation(fixture(145)),150)
        with self.assertRaises(ValueError):h.snapshot().rows_at(fixture(150))

    def test_future_snapshot_rejected_without_silent_prefix_trimming(self):
        rows=[fixture(t,ask=.35) for t in range(0,131,5)];h=UnderlyingHistory()
        for r in rows:h.ingest(observation(r),r['received'])
        with self.assertRaises(ValueError):causal_vector(rows[:-1],rows[-2],'UP',underlying_history=h.snapshot())

    def test_source_gap_and_epoch_change_rebuild_real_context(self):
        for change in ('gap','epoch'):
            h=UnderlyingHistory()
            for t in range(0,126,5):h.ingest(observation(fixture(t)),t)
            z=observation(fixture(145 if change=='gap' else 130))
            if change=='epoch':z=replace(z,btc_epoch='new')
            h.ingest(z,z.received)
            self.assertEqual(len(h.snapshot().observations),1)
            r=fixture(z.time,ask=.35)
            with self.assertRaisesRegex(ValueError,'120S'):causal_vector([r],r,'UP',underlying_history=h.snapshot())

    def test_component_source_clock_cannot_reverse_or_reprice(self):
        for conflict in ('reverse','reprice'):
            h=UnderlyingHistory();h.ingest(observation(fixture(100)),100)
            z=observation(fixture(105))
            z=replace(z,btc_source_time=99 if conflict=='reverse' else 100,btc_received_time=100)
            with self.assertRaises(ValueError):h.ingest(z,105)

    def test_duplicates_do_not_advance_or_refresh(self):
        h=UnderlyingHistory();z=observation(fixture(100));h.ingest(z,100)
        self.assertFalse(h.ingest(z,105));self.assertEqual(h.snapshot().observations,(z,))
        with self.assertRaises(ValueError):h.ingest(replace(z,btc=z.btc+1),105)

    def test_fixture_and_proxy_never_supply_native_support(self):
        rows=[fixture(t,ask=.35) for t in range(0,126,5)];h=UnderlyingHistory()
        for r in rows:h.ingest(observation(r),r['received'])
        r=deepcopy(rows[-1]);r['evidence_class']='COMMON_OBSERVED_NO_NATIVE_RECEIPT'
        with self.assertRaisesRegex(ValueError,'FIXTURE'):causal_vector([r],r,'UP',underlying_history=h.snapshot())
        proxy=observed_proxy(r,source_id='retained-file-sha')
        self.assertIsNone(proxy.btc_source_time);self.assertIsNone(proxy.brti_received_time)
        with self.assertRaises(ValueError):UnderlyingHistory().ingest(proxy,r['received'])
        with self.assertRaises(ValueError):ContinuationEngine(underlying_history=UnderlyingHistory(allow_observation_proxy=True))

    def test_unhealthy_retained_rows_break_proxy_history(self):
        h=UnderlyingHistory(allow_observation_proxy=True)
        for t in range(0,126,5):
            r=fixture(t);r['evidence_class']='OBSERVATION_NO_NATIVE_RECEIPT'
            h.ingest(observed_proxy(r,source_id='manifest-file'),t)
        r=fixture(130);r.update(evidence_class='OBSERVATION_NO_NATIVE_RECEIPT',healthy=False)
        with self.assertRaisesRegex(ValueError,'HEALTH_UNVERIFIED'):observed_proxy(r,source_id='manifest-file')
        h.invalidate('RETAINED_UNDERLYING_HEALTH_UNVERIFIED')
        r=fixture(135,ask=.35);r['evidence_class']='OBSERVATION_NO_NATIVE_RECEIPT'
        h.ingest(observed_proxy(r,source_id='manifest-file'),135)
        with self.assertRaisesRegex(ValueError,'120S'):causal_vector([r],r,'UP',underlying_history=h.snapshot(),allow_observation_proxy=True)

    def test_actual_artifact_is_explicitly_incompatible_and_unchanged(self):
        p=ROOT/'audit/early_continuation_20261012/evaluation/CONTINUATION_ARTIFACT.json'
        a=json.loads(p.read_text());before=hashlib.sha256(p.read_bytes()).hexdigest()
        self.assertEqual(a['body']['method'],METHOD)
        with self.assertRaisesRegex(ValueError,'ARTIFACT_HISTORY_PROVENANCE_UNSUPPORTED'):
            ContinuationEstimator(a,expected_sha256=a['artifact_sha256'])
        self.assertEqual(before,hashlib.sha256(p.read_bytes()).hexdigest())

    def test_forged_digest_still_rejected_first(self):
        with self.assertRaisesRegex(ValueError,'IDENTITY'):
            ContinuationEstimator({'body':{},'artifact_sha256':'bad'},expected_sha256='bad')

    def test_expiry_and_ingest_do_not_create_buy_or_change_base_clock(self):
        e,a=crossing();clock=e.clock
        e.tick(clock+10)
        with self.assertRaisesRegex(ValueError,'EXPIRED'):e.continuation_context('UP')
        self.assertFalse(e.last_output['research_qualified'])
        for k,v in SAFETY.items():self.assertIs(e.last_output[k],v)
        with self.assertRaisesRegex(ValueError,'BEFORE_ENGINE'):e.ingest_underlying(observation(fixture(clock)),clock)

    def test_rollover_keeps_old_manager_owned_and_cancels_old_ticket(self):
        e=ContinuationEngine(underlying_history=UnderlyingHistory())
        for t in range(0,151,5):
            r=fixture(t,ask=.35);e.ingest_underlying(observation(r),t);e.process(r)
        self.assertTrue(e.start_simulation('UP','fixture-origin',150)['accepted'])
        origin=deepcopy(e.managers[0].origin)
        # Direct fixture ticket represents an already valid old-contract ticket;
        # it grants no empirical economics, and only rollover ownership is tested.
        e.current_ticket=dict(id='fixture-ticket',setup_id=e.setups['UP']['id'],side='UP',contract='A',status='VALID',expires_at=160)
        r=fixture(155,ask=.40,contract='B',close=1800);e.ingest_underlying(observation(r),155);e.process(r)
        self.assertEqual(e.current_ticket['status'],'CANCELED');self.assertIn('CONTRACT_ROLLOVER',e.current_ticket['reasons'])
        self.assertEqual(origin,e.managers[0].origin);self.assertEqual(e.managers[0].core.history,[])
        self.assertIn('CONTRACT_ROLLOVER_NO_NEW_CONTRACT_PRICE',e.managers[0].view()['reasons'])
        self.assertEqual(e.history,[r]);self.assertEqual(e.setups,{})

    def test_current_target_floor_and_quotes_only(self):
        rows=[fixture(t,delta=1,ask=.35) for t in range(0,126,5)];h=UnderlyingHistory()
        for r in rows:h.ingest(observation(r),r['received'])
        r=deepcopy(rows[-1]);r['target']=200000.;r['contract']='B';r['left']=800
        v=causal_vector([r],r,'UP',underlying_history=h.snapshot())
        self.assertEqual(v,[35.,800/60,0.,0.,0.,0.])

if __name__=='__main__':unittest.main()
