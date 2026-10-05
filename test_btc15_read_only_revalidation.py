"""Read-only action-clock, freshness, disagreement and product continuity gates."""
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from btc15_information_v1 import ARTIFACT,WEIGHTS,pack
from btc15_ladder_product_v1 import Directional
from btc15_ladder_journal_v1 import atomic_json
from btc15_v2_product.journal import ProcessorEnvelope,public_view
from btc15_v2_product.revalidation import Revalidator,apply,binding,InputProjection
from test_btc15_ladder_completion_v1 import frame,OPEN

OUT=Path(__file__).parent/'qualification/v2_product_20261004'


class Evaluator:
    def __init__(self,p=.6):self.p=p;self.calls=0
    def evaluate(self,f,q):
        self.calls+=1
        return dict(probability_up=self.p,probability_down=1-self.p,dist_over_range5=2.)


def source(f,at,age=2.,sequence=None):
    a=dict(schema='BTC15_NATIVE_INFORMATION_ANCHOR_V1',epoch='anchor',decision=f['feature_cutoff'],
        captured=f['captured_ts'],ticker=f['contract'],opened=f['official_open'],closed=f['official_close'],
        target=f['target'],btc=dict(value=f['btc_price'],source=f['btc_source'],received=f['btc_received']),
        completed=[],ticks=[[f['btc_source'],f['btc_received'],f['btc_price']]],
        probability_up=f['fair']['up_fair'],seconds_left=f['official_close']-f['feature_cutoff'],artifact=ARTIFACT,weights=WEIGHTS)
    b=dict(value=f['brti']['value'],cf_ts=at-age,observed_ts=at-.001,owner_epoch='b')
    q=dict(status='AVAILABLE',official_identity={k:f[k] for k in ('contract','target','official_open','official_close')},
        epoch='q',market_id='market',sid=1,sequence=sequence or int((at-OPEN)*100),exchange_ts=at-.05,
        accepted_ts=at-.02,published_ts=at-.01,served_ts=at,expires_at=min(at+5.95,f['official_close']),
        **{k:f[k] for k in ('up_bid','up_ask','down_bid','down_ask')})
    return dict(anchor=a,brti=b,quote=q,cut=at)


def view(f,engine=None):
    engine=engine or ProcessorEnvelope(Directional(),'main')
    if not hasattr(engine.processor,'state'):engine.restore({})
    _,_,v=engine.process((f,'attempt'),f['captured_ts']+.001)
    return v


class RevalidationTests(unittest.TestCase):
    def test_buy_final_hold_protect_counts_and_timestamps_are_native_only(self):
        engines=[ProcessorEnvelope(Directional(),'main') for _ in range(2)]
        for engine in engines:engine.restore({})
        now=[OPEN+425];e=Evaluator();r=Revalidator(e,lambda:now[0]);records=[]
        for n,(p,ask,side) in enumerate([(.6,.6,'UP'),(.8,.35,'UP'),(.95,.7,'UP'),(.6,.7,'DOWN'),(.95,.7,'UP')]):
            f=frame(offset=425+n*5,sequence=n+1,p=p,ask=ask,side=side);now[0]=f['captured_ts']+.001
            a=engines[0].process((deepcopy(f),'attempt'),now[0]);b=engines[1].process((deepcopy(f),'attempt'),now[0])
            self.assertEqual(a,b);records.append(a[0]);snapshot=pack(engines[0].processor.checkpoint())
            for fast in range(1,50):
                now[0]=f['captured_ts']+fast/10;e.p=f['fair']['up_fair'] if fast!=10 else 1-f['fair']['up_fair']
                r.step(a[2],source(f,now[0],age=min(1.,now[0]-f['brti']['cf_ts'])))
            self.assertEqual(snapshot,pack(engines[0].processor.checkpoint()))
        self.assertEqual([x.get('event') for x in records],[None,'BUY','HOLD','PROTECT',None])
        self.assertEqual(len({x['published_ts'] for x in records}),5)
        self.assertEqual(engines[0].processor.checkpoint(),engines[1].processor.checkpoint())

    def test_real_frozen_model_and_native_loop_effects_remain_identical(self):
        from test_btc15_information_v1 import Rig,FrozenRuntime,completed
        from test_btc15_isolated_decision_v2 import fixture
        from completion_audit.isolated_decision_v2 import stable
        from btc15_information_v1 import FairAssessment
        from btc15_ladder_product_v1 import native_frame,iso
        from btc15_v2_product.bootstrap import Pool
        from btc15_v2_product.quote_view import QuoteProjection
        from test_btc15_v2_product_r1 import InertProvider
        initial=FrozenRuntime(completed());rig=Rig(initial,offset=305,ask=.61)
        baseline=initial.fork();expected=baseline.step(fixture(305,ask=.61))
        self.assertEqual(stable(rig.output),stable(expected))
        pool=Pool(InertProvider,lambda:rig.at);inp=fixture(305,ask=.61)
        pool.select(inp['market'],100000.)
        p=pool.current;p.book=rig.provider.book;p.epoch=rig.provider.epoch
        with patch('btc15_v2_product.bootstrap.time.time',return_value=rig.at):p._accepted_clock(p.book,p.epoch)
        projection=InputProjection(rig.export,QuoteProjection(pool,lambda:rig.at),lambda:rig.at)
        prices=[rig.runtime.ns[k] for k in ('up_bid','up_ask','down_bid','down_ask')]
        q=dict(ticker=inp['market']['ticker'],source_time=iso(rig.at),close_ms=int((rig.at-305+900)*1000),
            exchange_ts_ms=p.book.ts_ms,consumed_ms=rig.at*1000,epoch=p.epoch,sid=p.book.sid,seq=p.book.seq,
            market_id=p.book.market_id,quotes=prices)
        f=native_frame(rig.runtime.ns,q,'native',1,rig.at+.001);v=view(f)
        self.assertEqual(v['status'],'PASS',v)
        r=Revalidator(FairAssessment(),lambda:rig.at)
        before=(stable(rig.output),stable(rig.runtime.ns['_ec_btc_ticks']),stable(rig.runtime.ns['_ec_live']))
        confirmations=0
        for n in range(1,10):
            rig.at=inp['decision']+n*.1
            with p.lock:
                s=projection.capture()  # Busy quote owner cannot suppress valid accepted book.
            result=r.step(v,s)
            confirmations+=result['status']=='CONFIRMED'
        self.assertGreater(confirmations,0)
        self.assertEqual(before,(stable(rig.output),stable(rig.runtime.ns['_ec_btc_ticks']),stable(rig.runtime.ns['_ec_live'])))
        _,actual=rig.tick(310,ask=.61);expected=baseline.step(fixture(310,ask=.61))
        self.assertEqual(stable(actual),stable(expected))

    def test_native_5s_clock_continuous_qualified_sources_and_no_mutation(self):
        results=[]
        for initial_age in (1.,2.,3.,4.9):
            native=ProcessorEnvelope(Directional(),'main');native.restore({})
            baseline=ProcessorEnvelope(Directional(),'main');baseline.restore({})
            now=[OPEN+305.01];r=Revalidator(Evaluator(),lambda:now[0]);holes=0;confirmations=0
            native_records=[];baseline_records=[]
            with tempfile.TemporaryDirectory() as td:
                for step in range(12):
                    f=frame(offset=305+step*5,sequence=step+1,p=.6,ask=.6)
                    f['brti']['cf_ts']=f['captured_ts']-initial_age
                    f['brti']['delivery']['observed_ts']=f['feature_cutoff']-.001
                    now[0]=f['captured_ts']+.001
                    actual=native.process((deepcopy(f),'attempt'),now[0]);expected=baseline.process((deepcopy(f),'attempt'),now[0])
                    self.assertEqual(actual,expected)
                    native_records.append(actual);baseline_records.append(expected)
                    v=actual[2];atomic_json(Path(td)/'main.json',v)
                    before=pack(native.processor.checkpoint());raw=(Path(td)/'main.json').read_bytes()
                    # Age can reach 4.9 at the native cut; continuing BRTI owner
                    # delivery provides newer qualified ticks before that lease
                    # ends. This is NOT a frozen 4.9-second transport delay.
                    for sample in range(1,500):
                        now[0]=f['captured_ts']+sample/100
                        if sample==1 or sample%10==0:
                            cf=max(f['brti']['cf_ts'],math.floor(now[0])-2)
                            p=r.step(v,source(f,now[0],age=now[0]-cf))
                            self.assertEqual(p['status'],'CONFIRMED',p)
                            confirmations+=1
                        visible=public_view(td,'main',now[0],confirmation=p)
                        holes+=visible['status']=='UNAVAILABLE'
                        self.assertLess(now[0],visible['expires_at'])
                        for key in ('native_epoch','native_sequence','published_ts','origin','early','final','context','position_path'):
                            self.assertEqual(visible[key],v[key])
                    self.assertEqual(pack(native.processor.checkpoint()),before)
                    self.assertEqual((Path(td)/'main.json').read_bytes(),raw)
            self.assertEqual(holes,0);self.assertEqual(native_records,baseline_records)
            results.append(dict(brti_native_age=initial_age,native_evaluations=12,fast_confirmations=confirmations,
                visible_samples=12*499,holes=holes,native_records_byte_equivalent=True))
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'read_only_continuity.json').write_text(json.dumps(dict(status='PASS',native_cadence_seconds=5,
            faster_layer='READ_ONLY',results=results,scope='Continuously qualified advancing owner sources; no synthetic freshness extension.'),indent=2)+'\n')

    def test_stale_and_near_expired_sources_never_get_unearned_time(self):
        f=frame(offset=305,p=.6,ask=.6);f['brti']['cf_ts']=OPEN+300.1;v=view(f);now=[OPEN+306]
        r=Revalidator(Evaluator(),lambda:now[0]);p=r.step(v,source(f,now[0],age=4.9))
        self.assertEqual(p['status'],'CONFIRMED');self.assertAlmostEqual(p['expires_at'],now[0]+.1)
        now[0]=p['expires_at'];self.assertEqual(apply(v,p,now[0])['status'],'UNAVAILABLE')
        for field,delta in (('brti',5.001),('btc',10.001),('quote',6.001)):
            now[0]=OPEN+306;s=source(f,now[0])
            if field=='brti':s['brti']['cf_ts']=now[0]-delta
            if field=='btc':
                s['anchor']['btc']['source']=now[0]-delta;s['anchor']['ticks'][-1][0]=now[0]-delta
            if field=='quote':s['quote']['exchange_ts']=now[0]-delta;s['quote']['expires_at']=now[0]-.001
            self.assertEqual(r.step(v,s)['status'],'PENDING')

    def test_disagreement_latches_until_next_native_and_cannot_create_events(self):
        f=frame(offset=425,p=.6,ask=.35);v=view(f);now=[OPEN+426];e=Evaluator(.95);r=Revalidator(e,lambda:now[0])
        before=deepcopy(v)
        with (patch('btc15_ladder_product_v1.Directional.process',side_effect=AssertionError('LIFECYCLE CALLED')),
             patch('btc15_directional_signal_authority_v1.reduce_signal',side_effect=AssertionError('REDUCER CALLED'))):
            p=r.step(v,source(f,now[0]));self.assertEqual(p['status'],'PENDING')
            self.assertIn('DISAGREES',p['reason']);self.assertEqual(apply(v,p,now[0])['status'],'UNAVAILABLE')
            e.p=.6;now[0]+=.1
            self.assertEqual(r.step(v,source(f,now[0]))['status'],'PENDING')
            f2=frame(offset=430,sequence=2,p=.6,ask=.35)
        v2=view(f2);now[0]=OPEN+431
        self.assertEqual(r.step(v2,source(f2,now[0]))['status'],'CONFIRMED');self.assertEqual(v,before)

    def test_every_gate_and_origin_context_disagreement_is_pending(self):
        f=frame(offset=425,p=.95,ask=.35);v=view(f);now=[OPEN+426]
        self.assertEqual(v['early']['guidance'],'ENTER')
        cases=[]
        s=source(f,now[0]);s['quote']['up_ask']=.46;cases.append(s)
        s=source(f,now[0]);s['brti']['value']=79920;cases.append(s)
        s=source(f,now[0]);s['anchor']['btc']['value']=80020;s['anchor']['ticks'][-1][2]=80020;cases.append(s)
        for s in cases:
            r=Revalidator(Evaluator(.95),lambda:now[0]);self.assertEqual(r.step(v,s)['status'],'PENDING')
        r=Revalidator(Evaluator(.95),lambda:now[0]);before=deepcopy(v)
        p=r.step(v,source(f,now[0]));self.assertEqual(p['status'],'CONFIRMED',p)
        shown=apply(v,p,now[0]);self.assertEqual(shown['origin'],v['origin']);self.assertEqual(shown['early']['guidance'],'ENTER')
        self.assertEqual(v,before)

    def test_wrong_identity_anchor_future_source_and_rollover_fail_closed(self):
        f=frame(offset=305,p=.6,ask=.6);v=view(f);now=[OPEN+306]
        mutations=[lambda s:s['quote']['official_identity'].update(target=1),
            lambda s:s['anchor'].update(decision=OPEN+304),lambda s:s['brti'].update(observed_ts=now[0]+1),
            lambda s:s['quote'].update(accepted_ts=now[0]+1),lambda s:s.update(cut=now[0]+1),
            lambda s:s['anchor'].update(artifact='fake')]
        for mutation in mutations:
            s=source(f,now[0]);mutation(s)
            self.assertEqual(Revalidator(Evaluator(),lambda:now[0]).step(v,s)['status'],'PENDING')
        r=Revalidator(Evaluator(),lambda:now[0]);p=r.step(v,source(f,now[0]));now[0]=OPEN+900
        self.assertEqual(apply(v,p,now[0])['status'],'UNAVAILABLE')
        newer=deepcopy(v);newer['native_sequence']+=1;self.assertIsNone(apply(newer,p,OPEN+306))

    def test_quote_and_brti_owner_change_and_regression_cannot_renew(self):
        f=frame(offset=305,p=.6,ask=.6);v=view(f);now=[OPEN+306]
        for mutate in (lambda s:s['quote'].update(epoch='restart'),lambda s:s['brti'].update(owner_epoch='restart'),
                       lambda s:s['quote'].update(sequence=1),lambda s:s['brti'].update(cf_ts=OPEN+303)):
            r=Revalidator(Evaluator(),lambda:now[0]);self.assertEqual(r.step(v,source(f,now[0]))['status'],'CONFIRMED')
            s=source(f,now[0]+.1);now[0]+=.1;mutate(s)
            self.assertEqual(r.step(v,s)['status'],'PENDING');now[0]=OPEN+306

    def test_phase_gate_boundary_cannot_be_crossed_on_retained_confirmation(self):
        f=frame(offset=599,p=.6,ask=.6);v=view(f);now=[OPEN+599.5]
        r=Revalidator(Evaluator(),lambda:now[0]);p=r.step(v,source(f,now[0],age=1))
        self.assertEqual(p['expires_at'],OPEN+600)
        now[0]=OPEN+600;self.assertEqual(apply(v,p,now[0])['status'],'UNAVAILABLE')
        self.assertEqual(r.step(v,source(f,now[0]))['status'],'PENDING')


if __name__=='__main__':unittest.main()
