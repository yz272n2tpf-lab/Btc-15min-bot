"""Actual native loop/model/reducer + local durable writers; SYNTHETIC inputs.

No source API, live process, order, credential or production volume is accessed.
Virtual source clocks measure scheduling; real perf_counter measures execution.
"""
import ast
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from completion_audit.isolated_decision_v2 import FrozenRuntime, FUNCTION_NAMES
from test_btc15_isolated_decision_v2 import completed, fixture, OPEN
from btc15_v2_product import main_timing as timing, runtime as product_runtime
from btc15_v2_product import journal as journal_module, directional
from btc15_v2_product.admin import Admin
from btc15_v2_product.bootstrap import Pool, PreparedProvider
from btc15_quote_proof_offpath_v1 import OffPathProofWriter
import btc15_kalshi_quote_provenance_v1 as quotes
import btc15_information_native_offpath_candidate as native
import btc15_ladder_journal_v1 as frozen_journal

BASE = '1bd5b44d9e11a4f0dc572cd74b7ba513e61f9844'
RESULTS = {'input_class':'SYNTHETIC_CAUSAL_RECEIPTS_NOT_HISTORICAL_REPLAY',
           'live_source_tests':0, 'external_requests':0, 'comparisons':{}, 'checks':[]}
EVIDENCE = Path(__file__).parent


def baseline_instrument():
    raw = subprocess.check_output(['git','show',BASE+':btc15_v2_product/runtime.py'], cwd=ROOT)
    fn = next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name=='instrument')
    ns = dict(ast=ast,deepcopy=deepcopy,CALLS=product_runtime.CALLS)
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'<protected-instrument>','exec'),ns)
    return ns['instrument']


class Replay:
    def __init__(self, candidate, length=40, start=415, age=2.4, outage=None, processing_delay=0.,
                 between_tick_opportunity=False, btc=100080.):
        self.candidate,self.start,self.length,self.age,self.outage=candidate,start,length,age,outage
        self.processing_delay=processing_delay
        self.between_tick_opportunity,self.btc=between_tick_opportunity,btc
        self.r=FrozenRuntime(completed());self.r.at=OPEN+start
        self.end=OPEN+start+length;self.tick=None;self.inputs=None
        self.publications=[];self.latencies=[];self.request_counts=Counter();self.last_bytes={}
        self.scope=ExitStack();self.root=Path(self.scope.enter_context(tempfile.TemporaryDirectory()))
        self.scope.enter_context(patch.dict(os.environ,{'BTC15_KALSHI_QUOTE_PROVENANCE_CANARY':'1'}))
        self.admin=Admin(self.root,'main',clock=lambda:self.r.at)
        self.scope.enter_context(patch.object(journal_module,'ADMINS',{'main':self.admin}))
        self.scope.enter_context(patch.object(journal_module,'time',SimpleNamespace(time=lambda:self.r.at)))
        self.scope.enter_context(patch.object(frozen_journal,'Journal',journal_module.RevisionJournal))
        self.worker=journal_module.RevisionWorker(self.root,'main',directional.Directional(),clock=lambda:self.r.at)
        # Preserve real off-path validation and writes; only transport is synthetic.
        root=self.root
        class Provider(PreparedProvider):
            def __init__(p):
                p.lock=threading.Lock();p.ticker=None;p.close_ms=None;p.book=None;p.epoch=None;p.events=[]
                def validate(proof,w):
                    quotes.replay(proof,w.source_time,w.ticker,w.close_ms,w.consumed_ms)
                    return proof['identity']
                p.proof_writer=OffPathProofWriter(root/'proofs',validate,quotes.MAX_BYTES)
        self.pool=Pool(Provider,lambda:self.r.at)
        self.scope.enter_context(patch.object(quotes,'_provider',self.pool))
        self.scope.enter_context(patch.object(directional,'_worker',self.worker))
        self.scope.enter_context(patch.object(directional,'_sequence',0))
        self.scope.enter_context(patch.object(directional,'time',SimpleNamespace(time=lambda:self.r.at)))
        import btc15_v2_product.bootstrap as bootstrap
        self.scope.enter_context(patch.object(bootstrap,'time',SimpleNamespace(time=lambda:self.r.at)))
        self.scope.enter_context(patch.object(native,'COHORT_PATH',self.root/'cohort.jsonl'))
        exporter=native.NativeExport(clock=lambda:self.r.at,provider_reader=lambda:self.pool.current)
        self.r.ns.update(_v2_admin=self.admin,_v2_prepare=lambda _:None,
            _btc15_information_offer=exporter.offer,_btc15_cohort_offer=native.cohort_offer,
            # The existing closeout worker is separately regression-tested. No
            # historical disk scan or settlement HTTP is launched by this tape.
            _btc15_cohort_closeout_offer=lambda _:None,
            _btc15_ladder_offer=self.publish,
            get_active_market=self.market,get_btc_spot=self.spot)
        self.r.ns['time']=SimpleNamespace(time=lambda:self.r.at,sleep=self.sleep)
        self.r.ns['_btc15_data_path']=lambda name:self.root/name
        # Actual native CSV rows are retained for workload accounting. The
        # in-memory sink is the existing offline harness's external-effect seam.
        if candidate:
            self.scheduler=timing.install(self.r.ns,self.pool,self.worker,self.admin,
                clock=lambda:self.r.at,monotonic=lambda:self.r.at-OPEN,sleep=self.sleep)
        transform=product_runtime.instrument if candidate else baseline_instrument()
        tree=transform(native.instrument(self.r.tree),'main')
        functions=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in FUNCTION_NAMES]
        exec(compile(ast.Module(body=functions,type_ignores=[]),'<native-functions>','exec'),self.r.ns)
        loop=next(n for n in tree.body if isinstance(n,ast.While) and isinstance(n.test,ast.Name) and n.test.id=='running')
        self.loop=compile(ast.Module(body=[loop],type_ignores=[]),'<native-loop>','exec')
        self.feed()

    def feed(self):
        second=int(round((self.r.at-OPEN)*1000))//1000
        if second==self.tick:return
        self.tick=second
        ask=(.31 if second==self.start+2 else .72) if self.between_tick_opportunity else (.41 if second%10<5 else .72)
        self.inputs=fixture(second,ask=ask,btc=self.btc,brti_delay=self.age)
        at=OPEN+second
        if self.outage and self.outage[0]<=second<self.outage[1]:
            self.r.ns['_brti_delivery'].fail(at)
        else:
            receipt=(self.btc,at-self.age,at,'synthetic-owner')
            self.r.ns['_brti_delivery'].accept(*receipt)
            self.r.ns['_store_brti_publications']([(receipt[1],receipt[0])])
        if self.pool.current:self.book()

    def book(self):
        p=self.pool.current;proof=self.inputs['proof']
        if p.ticker!=self.inputs['market']['ticker']:return
        p.book=quotes.Book(p.ticker);p.events=deepcopy(proof['events']);p.epoch=proof['epoch']
        for event in p.events:p.book.apply(event)

    def market(self):
        self.request_counts['kalshi_exact_market']+=1
        m=deepcopy(self.inputs['market'])
        self.pool.select(m,m['floor_strike']);self.book()
        return m

    def spot(self):
        self.request_counts['coinbase_ticker']+=1
        self.r.ns['_btc_spot_provenance']=dict(source_utc=self.inputs['btc_source'],
                                             observed_utc=self.inputs['btc_received'])
        return self.inputs['btc']

    def sleep(self,seconds):
        # Virtual clocks must not outrun actual filesystem worker threads.
        # This barrier is a test transport adapter, not candidate runtime code;
        # injected backpressure is tested independently below.
        self.worker.queue.join();self.admin.queue.join()
        for p in self.pool.providers:p.proof_writer.queue.join()
        # Deliver each original synthetic receipt even during a baseline sleep.
        destination=min(self.end,round(self.r.at+seconds,6))
        while self.r.at<destination:
            self.r.at=min(destination,round(self.r.at+.05,6));self.feed()
        if self.r.at>=self.end:self.r.ns['running']=False

    def publish(self,ns):
        self.r.at=round(self.r.at+self.processing_delay,6)
        start=time.perf_counter();directional.offer(ns)
        self.worker.queue.join()
        if self.worker.failed:raise AssertionError(self.worker.failed)
        view=json.loads((self.root/'main.json').read_text())
        self.publications.append(view)
        self.latencies.append((time.perf_counter()-start)*1000)

    def run(self):
        try:
            started=time.perf_counter();exec(self.loop,self.r.ns)
            runtime_seconds=time.perf_counter()-started
            self.worker.queue.join();self.admin.queue.join()
            for p in self.pool.providers:p.proof_writer.queue.join()
            assert not self.worker.failed and not self.admin.failed
            assert not self.worker.dropped and not self.admin.dropped
            warnings=[m for m in self.r.messages if 'WARNING' in m]
            assert not warnings,warnings
            with sqlite3.connect(self.root/'main.admin.sqlite3') as db:
                adminrows=[json.loads(x[0]) for x in db.execute('SELECT body FROM evidence')]
            attempts=[x for x in adminrows if x['schema']=='BTC15_NATIVE_ATTEMPT_R1']
            if self.candidate:
                assert all(a.get('scheduling',{}).get('policy')=='FRESH_BRTI_MAX_1HZ_HTTP_5S' for a in attempts)
            stages={}
            for attempt in attempts:
                for s in attempt['stages']:stages.setdefault(s['stage'],[]).append(s['elapsed_ms'])
            with sqlite3.connect(self.root/'main.sqlite3') as db:
                records=[json.loads(zlib.decompress(x[0])) for x in db.execute('SELECT body FROM events')]
            qualified=[v for v in self.publications if v['status']!='UNAVAILABLE']
            # Exact union of actual producer publication leases, clipped to the
            # declared tape. Zero added logical CPU delay; wall latency below.
            intervals=[]
            for index,v in enumerate(self.publications):
                if v['status']=='UNAVAILABLE':continue
                next_at=self.publications[index+1]['journal_committed_ts'] if index+1<len(self.publications) else self.end
                left=max(OPEN+self.start,v['journal_committed_ts']);right=min(self.end,v['expires_at'],next_at)
                if right<=left:continue
                if intervals and left<=intervals[-1][1]:intervals[-1][1]=max(intervals[-1][1],right)
                else:intervals.append([left,right])
            covered=sum(b-a for a,b in intervals)
            gaps=[];cursor=OPEN+self.start
            for a,b in intervals:
                if a>cursor:gaps.append(a-cursor)
                cursor=b
            if cursor<self.end:gaps.append(self.end-cursor)
            sample=dict(attempts=len(attempts),publications=len(self.publications),qualified=len(qualified),
                qualified_seconds=round(covered,6),gap_seconds=round(self.length-covered,6),
                gap_count=len(gaps),maximum_gap_seconds=round(max(gaps,default=0),6),
                http_requests=dict(self.request_counts),native_csv_rows=len(self.r.records),
                cohort_rows=len((self.root/'cohort.jsonl').read_text().splitlines()),
                decision_rows=len(records),admin_rows=len(adminrows),
                source_btc_observations=len(self.r.ns['_ec_btc_ticks']),
                journal_drops=self.worker.dropped,admin_drops=self.admin.dropped,
                proof_published=sum(p.proof_writer.published for p in self.pool.providers),
                proof_dropped=sum(p.proof_writer.dropped for p in self.pool.providers),
                proof_rejected=sum(p.proof_writer.rejected for p in self.pool.providers),
                native_and_writers_wall_seconds=runtime_seconds,
                synthetic_processing_delay_seconds=self.processing_delay,
                scheduling_counters=attempts[-1].get('scheduling'),
                periodic_state_saves=len(self.r.saves),
                publication_durable_latency_ms=dict(median=statistics.median(self.latencies),maximum=max(self.latencies)),
                stage_latency_ms={k:dict(count=len(v),median=statistics.median(v),maximum=max(v)) for k,v in stages.items()},
                bytes_by_file={str(p.relative_to(self.root)):p.stat().st_size for p in self.root.rglob('*') if p.is_file() and p.suffix not in ('.json',)},
                signals=[dict(at=v['published_ts']-OPEN,status=v['status'],expiry=v.get('expires_at'),
                    final=v.get('final',{}).get('state'),confidence=v.get('final',{}).get('confidence'),
                    early=v.get('early',{}).get('guidance'),reason=v.get('reason')) for v in self.publications],
                events=[dict(at=r['published_ts']-OPEN,event=r.get('event')) for r in records if r.get('event')],
                scheduler='FRESH_BRTI_MAX_1HZ' if self.candidate else 'PROTECTED_5S')
            assert sample['proof_dropped']==sample['proof_rejected']==0,sample
            for r in records:
                f=r['evidence'];v=next(v for v in self.publications if v['published_ts']==r['published_ts'])
                assert r['signal_only'] is True and r['orders'] is False
                if v['status']!='UNAVAILABLE':
                    assert v['expires_at']==min(f['official_close'],f['brti']['cf_ts']+5,f['btc_source']+10,
                                               f['quote']['exchange_ts_ms']/1000+6,f['captured_ts']+15)
            return sample
        finally:
            self.worker.queue.put(None);self.worker.thread.join(2)
            self.admin.queue.put(None);self.admin.thread.join(2)
            self.scope.close()


class ProducerTests(unittest.TestCase):
    def test_01_actual_producer_continuity(self):
        for name,kw in [('normal',{}),('aged_4s',{'age':4.,'length':20}),
                        ('normal_with_100ms_work',{'processing_delay':.1}),
                        ('aged_4s_with_100ms_work',{'age':4.,'length':20,'processing_delay':.1}),
                        ('source_outage_recovery',{'outage':(425,435),'length':30})]:
            a=Replay(False,**kw).run();b=Replay(True,**kw).run()
            RESULTS['comparisons'][name]=dict(baseline=a,candidate=b)
            self.assertLess(b['gap_seconds'],a['gap_seconds'])
            self.assertEqual(a['http_requests'],b['http_requests'])
            self.assertEqual(a['source_btc_observations'],b['source_btc_observations'])
            self.assertLessEqual(b['attempts'],kw.get('length',40))
            if name=='normal':self.assertEqual(b['gap_seconds'],0)
            if name=='source_outage_recovery':
                self.assertGreater(b['gap_seconds'],0)
                self.assertTrue(any(s['reason']=='BRTI_SOURCE_UNAVAILABLE' for s in b['signals']))
        RESULTS['checks'].append('actual native loop, fitted model, decoder, reducer, proof/admin/decision writers')
        a=Replay(False,start=417,length=12,between_tick_opportunity=True,btc=100450.).run()
        b=Replay(True,start=417,length=12,between_tick_opportunity=True,btc=100450.).run()
        RESULTS['comparisons']['between_tick_early_and_final_boundary']=dict(baseline=a,candidate=b)
        self.assertFalse(any(e['event']=='BUY' for e in a['events']))
        self.assertTrue(any(e['event']=='BUY' and e['at']==419 for e in b['events']))
        self.assertEqual(next(s['at'] for s in a['signals'] if s['final']=='FINAL_CALL'),422)
        self.assertEqual(next(s['at'] for s in b['signals'] if s['final']=='FINAL_CALL'),420)
        for values in RESULTS['comparisons'].values():
            baseline={s['at']:s for s in values['baseline']['signals']}
            common=[(baseline[s['at']],s) for s in values['candidate']['signals'] if s['at'] in baseline]
            values['common_cutoff_comparison']=dict(count=len(common),
                probability_differences=sum(x['confidence']!=y['confidence'] for x,y in common),
                final_state_differences=sum(x['final']!=y['final'] for x,y in common),
                early_guidance_differences=sum(x['early']!=y['early'] for x,y in common))

    def test_02_source_cache_expiry_failure_and_no_restamp(self):
        at=[0.];calls=[]
        def validate(v):
            if v is None or at[0]>=v['expires']:raise ValueError('expired')
        def read():
            calls.append(at[0]);return dict(received=at[0],expires=at[0]+3)
        cache=timing.ReadCadence(read,validate,lambda:at[0])
        original=cache();at[0]=2;self.assertEqual(cache(),original)
        at[0]=3
        with self.assertRaises(ValueError):cache()
        self.assertEqual(len(calls),1)
        at[0]=5;self.assertEqual(cache()['received'],5)
        at[0]=10;cache.read=lambda:(_ for _ in ()).throw(TimeoutError())
        with self.assertRaises(TimeoutError):cache()
        at[0]=11
        with self.assertRaises(ValueError):cache()
        self.assertIsNone(cache.value)
        at[0]=898;slot_cache=timing.ReadCadence(read,lambda v:None,lambda:at[0],lambda:int(at[0]//900))
        slot_cache();at[0]=900;self.assertEqual(slot_cache()['received'],900)
        at[0]=901;self.assertEqual(slot_cache()['received'],900)
        RESULTS['checks'].append('cached source expiry and failed refresh revoke; receipt unchanged on reuse')

    def test_03_scheduler_duplicates_epochs_pressure_and_shutdown(self):
        from btc15_brti_delivery_v1 import Delivery
        at=[100.];healthy=[True];ns=dict(running=True,_brti_delivery=Delivery())
        s=timing.Scheduler(ns,lambda:healthy[0],lambda:at[0],lambda:at[0])
        ns['_brti_delivery'].accept(80000,99,100,'a');self.assertTrue(s.ready())
        for t in (100.1,101,102):at[0]=t;self.assertFalse(s.ready())
        at[0]=103;ns['_brti_delivery'].accept(80000,102,103,'a')
        healthy[0]=False;self.assertFalse(s.ready());self.assertEqual(s.attempts,1)
        healthy[0]=True;self.assertTrue(s.ready())
        at[0]=104;ns['_brti_delivery'].accept(80000,103,104,'b');self.assertTrue(s.ready())
        with self.assertRaises(ValueError):ns['_brti_delivery'].accept(80000,102,104,'b')
        ns['running']=False;self.assertFalse(s.wait())
        RESULTS['checks'].append('duplicate/regressed BRTI, epoch recovery, bounded admission and shutdown')

    def test_04_delayed_processing_rollover_sequence_and_order_guards(self):
        from test_btc15_ladder_completion_v1 import frame,OPEN as FOPEN
        for mutate in (lambda f:None,lambda f:f['brti'].update(ready=False)):
            e=directional.Directional();e.restore({});f=frame();mutate(f)
            r,_,v=e.process(f,f['captured_ts']+6)
            self.assertEqual(v['status'],'UNAVAILABLE');self.assertNotIn('event',r)
        e=directional.Directional();e.restore({});f=frame(offset=899.5,sequence=2,p=.95,ask=.8)
        _,_,v=e.process(f,f['captured_ts']);self.assertEqual(v['expires_at'],FOPEN+900)
        for sequence in (2,1):
            f['native_sequence']=sequence;r,_,v=e.process(f,f['captured_ts'])
            self.assertEqual(v['reason'],'DUPLICATE_OR_OUT_OF_ORDER_DECISION')
            self.assertIs(r['signal_only'],True);self.assertIs(r['orders'],False)
        f=frame(offset=1205,sequence=3,p=.6);f.update(official_open=FOPEN+900,official_close=FOPEN+1800,contract='KXBTC15M-26OCT031630-30')
        f['quote'].update(ticker=f['contract'],close_ms=int(f['official_close']*1000))
        _,_,v=e.process(f,f['captured_ts']);self.assertEqual(v['status'],'PASS');self.assertIsNone(v['origin'])
        RESULTS['checks'].append('late processing rejects expiry; rollover and duplicate/out-of-order native sequence fail closed')

    def test_05_background_cadence_and_strategy_bytes(self):
        before=ast.parse(native.BOT.read_bytes());after=timing.instrument(before)
        old=[n for n in before.body if not isinstance(n,ast.While)]
        new=[n for n in after.body if not isinstance(n,ast.While)]
        self.assertEqual(ast.dump(ast.Module(body=old,type_ignores=[])),ast.dump(ast.Module(body=new,type_ignores=[])))
        for name in ['bot_two_output_build_v4_13_profit_protection_shadow.py','btc15_v2_product/directional.py',
                     'btc15_v2_product/directional_authority.py','btc15_v2_product/scalp.py',
                     'btc15_brti_delivery_v1.py','btc15_v2_product/journal.py','completion_audit/fair_input_candidate.py',
                     'completion_audit/model_artifact/frozen_fair_candidate.joblib']:
            old=subprocess.check_output(['git','show',BASE+':'+name],cwd=ROOT)
            self.assertEqual((ROOT/name).read_bytes(),old,name)
        RESULTS['checks'].append('model, source qualifiers, strategy/reducer, journal and all background loop bytes preserved')

    def test_06_actual_busy_writer_admission(self):
        from test_btc15_ladder_completion_v1 import frame
        entered,release=threading.Event(),threading.Event()
        engine=directional.Directional();engine.restore({})
        class Blocked:
            def restore(self,state):engine.restore(state)
            def process(self,f,now):
                entered.set()
                if not release.wait(3):raise TimeoutError('bounded test writer')
                return engine.process(f,now)
        with tempfile.TemporaryDirectory() as td:
            f=frame();at=[f['captured_ts']]
            w=frozen_journal.Worker(td,'main',Blocked(),clock=lambda:at[0])
            a=Admin(td,'main',clock=lambda:at[0])
            from btc15_brti_delivery_v1 import Delivery
            ns=dict(running=True,_brti_delivery=Delivery(),get_active_market=lambda:None,
                    get_btc_spot=lambda:None,extract_target=lambda m:None)
            pool=SimpleNamespace(current=None,official=None)
            try:
                s=timing.install(ns,pool,w,a,clock=lambda:at[0],monotonic=lambda:at[0])
                self.assertTrue(w.offer(f));self.assertTrue(entered.wait(2))
                for n in range(20):
                    at[0]+=1;ns['_brti_delivery'].accept(80080,at[0]-1,at[0],'test')
                    self.assertFalse(s.ready())
                self.assertEqual(w.accepted,1);self.assertEqual(w.dropped,0)
                release.set();w.queue.join()
                self.assertEqual(frozen_journal.view(td,'main',at[0])['status'],'UNAVAILABLE')
                self.assertTrue(s.ready());self.assertFalse(s.ready())
                self.assertIsNone(w.failed)
            finally:
                release.set();w.queue.put(None);w.thread.join(2);a.queue.put(None);a.thread.join(2)
        RESULTS['checks'].append('actual blocked durable writer admits no extra work, does not overflow, expired view stays unavailable, resumes without burst')


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ProducerTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    RESULTS.update(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=result.wasSuccessful(),
                   failure_details=[detail for _,detail in result.failures+result.errors])
    import importlib.metadata
    RESULTS['local_dependencies']={name:importlib.metadata.version(name) for name in ('numpy','pandas','scikit-learn','scipy','joblib')}
    RESULTS['limitations']=['Synthetic source receipts, not live market or historical native replay.',
        'Virtual source/scheduler clock; 100ms processing cases are injected, not measured live latency.',
        'Real fitted model, native loop and local SQLite/fsync/proof writers; local storage is not Railway storage.',
        'CSV sink uses the existing in-memory test adapter; fair-input/cohort/admin/decision/proof writes are real local files.',
        'Writer barriers keep deterministic virtual time from outrunning OS threads; separate blocked-writer test covers admission.',
        'Production pins scikit-learn 1.9.0; local 1.8.0 emits version warnings. Pinned install attempt timed out.',
        'Existing native closeout background worker and separate SCALP process are not started by this tape.']
    (EVIDENCE/'producer_results.json').write_text(json.dumps(RESULTS,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
