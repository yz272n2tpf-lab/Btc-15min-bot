"""Offline acceptance of integrated finish-line authority and lifecycle contracts."""
import ast
from copy import deepcopy
import hashlib
import itertools
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from btc15_v2_product import directional as d
from btc15_v2_product.scalp import Scalp
from btc15_v2_product.scalp_policy import proposal_for
from btc15_v2_product.journal import ProcessorEnvelope,public_view
from btc15_v2_product.revalidation import Revalidator,apply
from btc15_v2_product.revalidation_transport import ConfirmationTransport
from test_btc15_ladder_completion_v1 import frame,OPEN
from test_btc15_scalp_journal_v1 import state,ENTRY
from test_btc15_read_only_revalidation import source,Evaluator

ROOT=Path(__file__).parent

def directional():
    e=ProcessorEnvelope(d.Directional(),'main');e.restore({});return e

def step(e,f):return e.process((f,'offline-test'),f['captured_ts']+.001)

def scalp_frame(at=ENTRY,bid=.59,seq=1,side='UP',momentum=15):
    f=state(at,bid,seq,side);row=f['row']
    for p in f['proposals'].values():
        p['history']['30']['btc']=row['btc']-(momentum if side=='UP' else -momentum)
    return f


class ProtectedBaselines(unittest.TestCase):
    def test_numerical_gates_and_qualifier_ast_identical(self):
        def nodes(name):
            t=ast.parse((ROOT/name).read_text())
            return {n.name:ast.dump(n,include_attributes=False) for n in t.body if isinstance(n,ast.FunctionDef)}
        old=nodes('btc15_ladder_product_v1.py');new=nodes('btc15_v2_product/directional.py')
        for name in ('qualify','protected_frame','native_frame'):
            self.assertEqual(old[name],new[name],name)

    def test_early_exact_boundaries_no_side_or_persistence_gate(self):
        for ask,p,left,gap in itertools.product([.35,.45,.450001,.50],[.749999,.75,.90],[119.999,120,360,600,600.001],[-25,24.999,25]):
            f=frame(900-left,p=p,ask=ask);f['btc_price']=f['target']+gap
            f['fair']['edge']=p-ask
            raw,_=d.protected_frame(f,f['captured_ts'])
            expected=ask<=.45 and p>=.75 and 120<=left<=600 and abs(gap)>=25
            self.assertEqual(raw['early']['ready'],expected,(ask,p,left,gap))
            if expected:self.assertGreaterEqual(f['fair']['edge'],.08)

    def test_final_exact_boundaries(self):
        for p,left,gap,ratio,brti in itertools.product([.899999,.90],[360,360.01,480,480.01],[49.99,50,74.99,75],[.99999,1],[10,12,-80]):
            f=frame(900-left,p=p,ask=.8);f['btc_price']=f['target']+gap
            f['brti']['value']=f['target']+brti;f['fair']['dist_over_range5']=ratio
            raw,_=d.protected_frame(f,f['captured_ts'])
            self.assertEqual(raw['final']['ready'],p>=.9 and left<=480 and gap>=(75 if left>360 else 50) and ratio>=1 and brti>11)

    def test_challenger_frozen_report_only_no_import_path(self):
        p=ROOT/'btc15_v2_product/coverage_challenger_a.json';c=json.loads(p.read_text())
        self.assertEqual(c['status'],'REPORT_ONLY');self.assertFalse(c['production_authority'])
        self.assertEqual([c[k] for k in ('fair_min','max_time_left_minutes','early_boundary_minutes','early_gap_usd','late_gap_usd','min_support','min_dist_range')],[.9,8,7,150,50,0,0])
        for f in (ROOT/'btc15_v2_product').glob('*.py'):
            self.assertNotIn('coverage_challenger_a',f.read_text())


class DirectionalLifecycle(unittest.TestCase):
    def test_preentry_context_cannot_create_or_veto(self):
        for ask,p in [( .35,.8),(.6,.95),(.35,.7)]:
            e=directional();f=frame(offset=425,ask=ask,p=p)
            # BRTI opposition forbids FINAL but must not veto protected EARLY.
            f['brti']['value']=f['target']-80
            r,_,v=step(e,f)
            self.assertEqual(r.get('event')=='BUY',ask<=.45 and p>=.75)
            if r.get('event')!='BUY':self.assertEqual(v['final']['helper']['state'],'CONTEXT_ONLY')

    def test_weak_opposition_watch_caution_not_protect(self):
        e=directional();step(e,frame())
        r,_,v=step(e,frame(offset=310,sequence=2,p=.55,ask=.7,side='DOWN'))
        self.assertNotEqual(v['early']['guidance'],'PROTECT');self.assertIn(v['early']['guidance'],('WATCH','CAUTION'))
        self.assertFalse(e.processor.state.position.saw_strong_final)

    def test_healthy_improving_and_deteriorating_same_side(self):
        e=directional();step(e,frame())
        _,_,v=step(e,frame(offset=310,sequence=2,p=.85,ask=.7))
        self.assertEqual(v['early']['guidance'],'HOLD');self.assertEqual(v['final']['helper']['relation'],'STRENGTHENING')
        _,_,v=step(e,frame(offset=315,sequence=3,p=.8,ask=.7))
        self.assertEqual(v['early']['guidance'],'WATCH');self.assertEqual(v['final']['helper']['relation'],'WEAKENING')

    def test_confirmation_loss_latches_even_after_recovery(self):
        e=directional();_,_,entry=step(e,frame())
        step(e,frame(offset=425,sequence=2,p=.95,ask=.7))
        _,_,v=step(e,frame(offset=430,sequence=3,p=.85,ask=.7))
        self.assertEqual(v['early']['guidance'],'PROTECT');self.assertTrue(v['final']['helper']['material_deterioration'])
        _,_,v=step(e,frame(offset=435,sequence=4,p=.95,ask=.7))
        self.assertEqual(v['early']['guidance'],'PROTECT');self.assertEqual(v['origin'],entry['origin'])
        self.assertIsNone(v['exit_guidance']);self.assertFalse(v['final']['helper']['exit_authority'])

    def test_qualified_opposition_flip_alert(self):
        e=directional();step(e,frame())
        _,_,v=step(e,frame(offset=425,sequence=2,p=.95,ask=.7,side='DOWN'))
        self.assertEqual(v['early']['guidance'],'PROTECT');self.assertEqual(v['final']['helper']['relation'],'FLIP_ALERT')

    def test_missing_stale_sources_never_deterioration(self):
        for change in (lambda f:f.update(fair=None),lambda f:f['brti'].update(ready=False),lambda f:f['quote'].update(ticker='OTHER'),lambda f:f.update(btc_source=OPEN)):
            e=directional();step(e,frame());before=deepcopy(e.processor.state)
            f=frame(offset=310,sequence=2);change(f);r,_,v=step(e,f)
            self.assertEqual(v['status'],'UNAVAILABLE');self.assertNotIn('event',r);self.assertEqual(e.processor.state,before)
            self.assertNotIn('warning',v)


class GeneralizedScalp(unittest.TestCase):
    def setUp(self):self.e=Scalp();self.e.restore({})
    def step(self,**kw):
        f=scalp_frame(**kw);return self.e.process(f,f['captured_ts']+.001)
    def test_both_sides_price_independent_exact_btc30_and_time(self):
        for side,bid,momentum,left in itertools.product(('UP','DOWN'),(.09,.29,.44,.59,.89),(14.999,15),(119,120,600)):
            f=scalp_frame(OPEN+900-left,bid,1,side,momentum)
            got=proposal_for(f['row'],side,f['proposals'][side]['history'])
            self.assertEqual(got['ok'],momentum>=15 and left>=120,(side,bid,momentum,left))

    def test_first_qualified_native_sample_enters_no_band_no_confirmation(self):
        for side in ('UP','DOWN'):
            self.setUp();r,_,v=self.step(side=side)
            self.assertEqual(r['event'],'SCALP_SIGNAL');self.assertEqual(v['origin']['original_ask'],.60)
            self.assertEqual(v['origin']['route'],'GENERALIZED');self.assertIsNone(v['executable_current_bid'])
            self.assertTrue(v['signal_only']);self.assertFalse(v['orders'])

    def test_arm_exact_giveback_both_sides_and_immutable_ask(self):
        for side in ('UP','DOWN'):
            self.setUp();_,_,entry=self.step(side=side)
            _,_,v=self.step(at=ENTRY+1,bid=.65,seq=2,side=side)
            self.assertEqual(v['guidance'],'PROTECT');self.assertTrue(self.e.engine.armed)
            _,_,v=self.step(at=ENTRY+2,bid=.69,seq=3,side=side)
            _,_,v=self.step(at=ENTRY+3,bid=.650001,seq=4,side=side);self.assertEqual(v['guidance'],'PROTECT')
            r,_,v=self.step(at=ENTRY+4,bid=.65,seq=5,side=side)
            self.assertEqual(r['event'],'SCALP_EXIT');self.assertEqual(v['guidance'],'EXIT')
            self.assertEqual(v['terminal']['executable_exit_bid'],.65);self.assertEqual(v['origin'],entry['origin'])
            self.assertIsNone(v['terminal']['manual_fill']);self.assertIsNone(v['terminal']['realized_profit'])

    def test_ended_unarmed_nonactionable_and_serial_reentry_reversal(self):
        for side,lane in [('UP','REENTRY_CONTINUATION'),('DOWN','REVERSAL_RECROSS')]:
            self.setUp();self.step()
            r,_,v=self.step(at=ENTRY+181,bid=.59,seq=2)
            self.assertEqual(r['event'],'SCALP_ENDED_UNARMED');self.assertEqual(v['guidance'],'PASS')
            self.assertEqual(v['terminal']['state'],'ENDED_UNARMED');self.assertFalse(v['terminal']['actionable_exit']);self.assertIsNone(v['exit_guidance'])
            r,_,v=self.step(at=ENTRY+182,bid=.59,seq=3,side=side)
            self.assertEqual(v['guidance'],'ENTER');self.assertEqual(v['origin']['serial_index'],2);self.assertEqual(v['origin']['lane'],lane)

    def test_armed_horizon_blocks_and_eventual_giveback_exits(self):
        self.step();self.step(at=ENTRY+1,bid=.70,seq=2)
        r,saved,v=self.step(at=ENTRY+181,bid=.69,seq=3)
        self.assertEqual(v['guidance'],'PROTECT');self.assertIsNone(v['terminal']);self.assertNotIn('event',r)
        self.e=Scalp();self.e.restore(saved)
        r,_,v=self.step(at=ENTRY+182,bid=.66,seq=4)
        self.assertEqual(v['guidance'],'EXIT');self.assertEqual(v['terminal']['reason'],'ARM5_GIVEBACK4')

    def test_no_artificial_count_cap(self):
        self.step()
        for n in range(1,8):
            self.step(at=ENTRY+n*3-2,bid=.70,seq=n*3)
            self.step(at=ENTRY+n*3-1,bid=.66,seq=n*3+1)
            _,_,v=self.step(at=ENTRY+n*3,bid=.59,seq=n*3+2)
            self.assertEqual(v['origin']['serial_index'],n+1)

    def test_repeated_or_stale_quote_cannot_arm_exit_or_free_lane(self):
        self.step();f=scalp_frame(ENTRY+1,.70,2)
        f['row']['input_provenance']['quote']['source_ts_ms']=int((ENTRY-.01)*1000)
        r,_,v=self.e.process(f,ENTRY+1.001)
        self.assertEqual(v['guidance'],'HOLD');self.assertFalse(self.e.engine.armed)
        f=scalp_frame(ENTRY+181,.59,3);f['row']['input_provenance']['brti']['source_ts_ms']=int((ENTRY+174)*1000)
        r,_,v=self.e.process(f,ENTRY+181.001)
        self.assertEqual(v['status'],'UNAVAILABLE');self.assertIsNone(self.e.terminal);self.assertNotIn('event',r)


class NativeAuthority(unittest.TestCase):
    def test_disagreement_informational_no_latch_no_renewal(self):
        f=frame(offset=425,p=.6,ask=.6);e=directional();_,_,v=step(e,f)
        now=f['captured_ts']+1;ev=Evaluator(.9);r=Revalidator(ev,lambda:now)
        before=deepcopy(e.processor.checkpoint());p=r.step(v,source(f,now,age=1))
        self.assertEqual(p['status'],'CHANGED');out=apply(v,p,now)
        self.assertEqual(out['early'],v['early']);self.assertEqual(out['expires_at'],v['expires_at'])
        ev.p=.6;p=r.step(v,source(f,now,age=1));self.assertEqual(p['status'],'AGREES')
        self.assertEqual(before,e.processor.checkpoint())
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'main.json').write_text(json.dumps(v))
            for c in (p,None,{'binding':'bad','status':'CHANGED'}):
                self.assertEqual(public_view(tmp,'main',now=now,confirmation=c)['status'],'PASS')
            self.assertEqual(public_view(tmp,'main',now=v['expires_at'],confirmation=p)['status'],'UNAVAILABLE')
            bad=deepcopy(v);bad['official_identity']['target']+=1;Path(tmp,'main.json').write_text(json.dumps(bad))
            self.assertEqual(public_view(tmp,'main',now=now,confirmation=p)['status'],'UNAVAILABLE')
            bad=deepcopy(v);bad['status']='UNAVAILABLE';bad['reason']='INVALID_EXECUTABLE_BOOK';Path(tmp,'main.json').write_text(json.dumps(bad))
            self.assertEqual(public_view(tmp,'main',now=now,confirmation=p)['status'],'UNAVAILABLE')

    def test_confirmation_transport_never_waits_for_inference(self):
        gate=threading.Event();started=threading.Event()
        def read(key):started.set();gate.wait(1);return {'binding':key}
        t=ConfirmationTransport(read);self.assertIsNone(t.capture({'native':'fixture'}));self.assertTrue(started.wait(.1));gate.set()

    def test_native_consume_offpath_and_incomplete_book_closed(self):
        from btc15_v2_product.bootstrap import PreparedProvider
        class Book:
            market_id='m';sid=1;seq=3;ts_ms=int((ENTRY-.1)*1000)
            def quotes(self,*a):return [.5,.6,.4,.5]
        class Writer:
            def submit(self,*a):return False  # Evidence overflow cannot revoke accepted quotes.
        p=object.__new__(PreparedProvider);p.lock=threading.Lock();p.ticker='KXBTC15M-26OCT031615-15'
        p.close_ms=int((OPEN+900)*1000);p.epoch='q';p.book=Book();p.events=[];p.proof_writer=Writer()
        with patch('btc15_v2_product.bootstrap.time.time',return_value=ENTRY):
            self.assertEqual(p.consume(p.ticker,'cut',p.close_ms),[.5,.6,.4,.5])
            self.assertEqual(p.last_product_quote['seq'],3)
            p.book=None;self.assertIsNone(p.consume(p.ticker,'cut',p.close_ms));self.assertIsNone(p.last_product_quote)

    def test_actual_native_generalized_feed_scans_both_sides_without_old_gate(self):
        from collections import deque
        from types import SimpleNamespace
        from btc15_v2_product.runtime import instrument
        from btc15_v81_qualified_inputs_v1 import InputUnavailable
        class Stop(BaseException):pass
        def stop(_):raise Stop()
        class Admin:
            def begin(self):pass
            def finish(self,ns):pass
            def exception(self,e):pass
            def call(self,name,fn,*a,**kw):return fn(*a,**kw)
        clock=[ENTRY];current=[None];frames=[];engine=Scalp();engine.restore({});views=[]
        ns=dict(hist=deque(),KEEP=240,POLL=1,print=lambda *a,**k:None,
            InputUnavailable=InputUnavailable,_qualified_inputs=SimpleNamespace(last_ticker='fixture'),
            _v2_admin=Admin(),time=SimpleNamespace(time=lambda:clock[0],sleep=stop))
        native=ast.parse((ROOT/'scalp_lead_shadow_v5.py').read_text())
        ago=next(n for n in native.body if isinstance(n,ast.FunctionDef) and n.name=='ago')
        tree=instrument(ast.parse((ROOT/'btc15_v2_product/scalp_feed.py').read_text()),'v81')
        loop=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='loop')
        exec(compile(ast.Module(body=[ago,loop],type_ignores=[]),'<offline-native-scalp>','exec'),ns)
        ns['snap']=lambda:deepcopy(current[0])
        def offer(f):
            frames.append(f);views.append(engine.process(f,clock[0])[2])
        ns['journal_offer']=offer
        for i in range(33):
            clock[0]=ENTRY+i;current[0]=scalp_frame(clock[0],.89,i+1)['row']
            current[0]['btc']+=i
            with self.assertRaises(Stop):ns['loop']()
        self.assertEqual(len(frames),33)
        self.assertTrue(all(set(f['proposals'])=={'UP','DOWN'} for f in frames))
        self.assertEqual(views[30]['guidance'],'ENTER');self.assertEqual(views[30]['origin']['original_ask'],.90)
        self.assertEqual(views[30]['origin']['entry_features']['btc30'],30)

    def test_runtime_wiring_and_no_order_routes(self):
        runtime=(ROOT/'btc15_v2_product/runtime.py').read_text()
        self.assertIn('from .directional import start,offer',runtime);self.assertIn('btc15_v2_product/scalp_feed.py',runtime)
        for name in ('directional.py','directional_authority.py','scalp.py','scalp_policy.py','scalp_feed.py','runtime.py','routes.py'):
            s=(ROOT/'btc15_v2_product'/name).read_text();tree=ast.parse(s)
            self.assertNotIn('/portfolio/orders',s);self.assertNotIn('/trade-api/v2/orders',s)
            for n in ast.walk(tree):
                if isinstance(n,ast.FunctionDef):self.assertNotIn(n.name,('do_POST','do_PUT','do_DELETE'))
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute):self.assertNotIn(n.func.attr,('post','put','delete','place_order','create_order','submit_order'))


class V81QualificationSeam(unittest.TestCase):
    def test_prepared_target_matches_main_label_and_snapshot_reads_fixed_identity(self):
        from btc15_v2_product.runtime import _v81_prepared_target,_v81_selected_target
        from btc15_v2_product.bootstrap import identity
        market=dict(
            ticker='KXBTC15M-26OCT061600-00',
            open_time='2026-10-06T19:45:00+00:00',
            close_time='2026-10-06T20:00:00+00:00',
            title='Bitcoin price — $85,490.48 target',
        )
        calls=[]
        def get(path,params=None):
            calls.append(path)
            return {'market':deepcopy(market)}
        self.assertEqual(_v81_prepared_target(market,get,lambda _:None),85490.48)
        self.assertEqual(calls,[])
        pool=type('PoolFixture',(),{'official':identity(market,85490.48)})()
        self.assertEqual(_v81_selected_target(market,pool),85490.48)

    def test_missing_or_mismatched_prepared_identity_fails_closed(self):
        from btc15_v2_product.runtime import _v81_prepared_target,_v81_selected_target
        from btc15_v2_product.bootstrap import identity
        market=dict(
            ticker='KXBTC15M-26OCT061600-00',
            open_time='2026-10-06T19:45:00+00:00',
            close_time='2026-10-06T20:00:00+00:00',
            title='Bitcoin 15 minute market',
        )
        self.assertIsNone(_v81_prepared_target(market,lambda *a,**k:(_ for _ in ()).throw(OSError()),lambda _:None))
        self.assertIsNone(_v81_selected_target(market,type('PoolFixture',(),{'official':None})()))
        wrong=identity(market,85490.48);wrong['contract']='KXBTC15M-OTHER'
        self.assertIsNone(_v81_selected_target(market,type('PoolFixture',(),{'official':wrong})()))


if __name__=='__main__':unittest.main()
