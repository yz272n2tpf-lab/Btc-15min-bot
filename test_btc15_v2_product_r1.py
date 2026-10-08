"""Coordinated offline qualification. All quotes, sources and settlements are FIXTURES."""
import ast
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from btc15_v2_product import REVISION,ENVELOPE
from btc15_v2_product.admin import Admin,LOCAL
from btc15_v2_product.bootstrap import Pool,Preparation,PreparedProvider,identity
from btc15_v2_product.quote_view import QuoteProjection
from btc15_v2_product.journal import RevisionJournal,ProcessorEnvelope,public_view,unavailable
from btc15_v2_product.runtime import instrument
from btc15_ladder_product_v1 import Directional
from btc15_scalp_journal_v1 import Scalp
from btc15_ladder_journal_v1 import Journal,atomic_json
from btc15_kalshi_quote_provenance_v1 import Book,Provider
from btc15_v81_qualified_inputs_v1 import QuoteProvider,require_qualified
from test_btc15_ladder_completion_v1 import frame,OPEN
from test_btc15_scalp_journal_v1 import state
from test_btc15_isolated_decision_v2 import completed,fixture
from completion_audit.isolated_decision_v2 import FrozenRuntime,STATE_NAMES,FUNCTION_NAMES,stable
from ops.btc15_v2_scoring import bridge
from ops.btc15_v2_scoring.product_cohort import configured
from btc15_v2_product.release import SERVICES,VOLUMES,PROJECT,ENVIRONMENT,MANIFEST,verify_environment,read_receipt

ROOT=Path(__file__).parent
OUT=ROOT/'qualification/v2_product_20261004'

def market(opened=OPEN,target=80000):
    return dict(ticker=bridge.ticker(opened),open_time=bridge.utc(opened),close_time=bridge.utc(opened+900),floor_strike=target)

class InertProvider(PreparedProvider):
    def __init__(self):
        self.lock=threading.Lock();self.ticker=None;self.close_ms=None;self.book=None;self.events=[];self.epoch=None

def book_for(p,at,yes='.34',no='.65'):
    p.book=Book(p.ticker)
    p.book.apply(dict(type='orderbook_snapshot',sid=1,seq=1,msg=dict(market_ticker=p.ticker,market_id='m',
        yes_dollars_fp=[[yes,'10']],no_dollars_fp=[[no,'10']])))
    p.book.apply(dict(type='orderbook_delta',sid=1,seq=2,msg=dict(market_ticker=p.ticker,market_id='m',
        side='yes',price_dollars=yes,delta_fp='1',ts_ms=int((at-.1)*1000))))
    p.epoch='book-epoch';p.accepted_ts=at-.05
    p.accepted_key=(p.epoch,p.book.market_id,p.book.sid,p.book.seq,p.book.ts_ms)
    with patch('btc15_v2_product.bootstrap.time.time',return_value=at):p._accepted_clock(p.book,p.epoch)
    return p.book

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.at=OPEN-10;self.pool=Pool(InertProvider,lambda:self.at)
    def test_prepare_has_no_preopen_frame_or_strategy_side_effect(self):
        p=self.pool.prepare(market());book_for(p,self.at)
        self.assertIsNone(self.pool.current)
        with self.assertRaisesRegex(ValueError,'NO_PREOPEN'):self.pool.select(market(),80000)
        with patch('btc15_v81_qualified_inputs_v1.time.time',return_value=self.at):
            self.assertIsNone(p.frame(p.ticker,p.close_ms))
        self.at=OPEN+.3;self.pool.select(market(),80000)
        # Pre-open book remains unusable after open; receipt time cannot qualify it.
        with patch('btc15_v81_qualified_inputs_v1.time.time',return_value=self.at):
            self.assertIsNone(self.pool.frame(p.ticker,p.close_ms))
        book_for(p,self.at)
        with patch('btc15_v81_qualified_inputs_v1.time.time',return_value=self.at):
            got=self.pool.frame(p.ticker,p.close_ms)
            expected=QuoteProvider.frame(p,p.ticker,p.close_ms)
        self.assertEqual(got,expected);self.assertEqual(got['source_ts_ms'],int((self.at-.1)*1000))
    def test_future_preparation_never_resets_active_book_and_pool_is_bounded(self):
        self.at=OPEN+875;self.pool.select(market(),80000);active=self.pool.current;book_for(active,self.at)
        b=active.book;self.pool.prepare(market(OPEN+900));self.pool.prepare(market(OPEN+1800))
        self.assertIs(active.book,b);self.assertIs(self.pool.current,active);self.assertEqual(len(self.pool.providers),2)
        self.at=OPEN+900.2;self.pool.select(market(OPEN+900),80000)
        self.assertIsNot(self.pool.current,active);self.at=OPEN+1775;self.pool.prepare(market(OPEN+1800));self.assertEqual(len(self.pool.providers),2)
    def test_official_exact_handoff_precedes_canonical_list_and_target_is_not_staged(self):
        calls=[];current={'value':market(target=None)}
        def get(path,params=None):
            calls.append((path,params));return {'markets':[market()]} if params else {'market':current['value']}
        prep=Preparation(get,lambda m:m['floor_strike'],self.pool,lambda:self.at)
        prep.scan();self.at=OPEN+.2
        selected=prep.select(lambda:self.fail('canonical list must not run before staged exact lookup'))
        self.assertIsNone(selected['floor_strike']);self.assertIsNone(self.pool.current)
        current['value']=market(target=80001)
        selected=prep.select(lambda:self.fail('canonical fallback unexpected'))
        self.assertEqual(selected['floor_strike'],80001);self.assertEqual(self.pool.official['target'],80001)
        current['value']=market(target=80002)
        with self.assertRaisesRegex(ValueError,'FIXED_OFFICIAL'):prep.select(lambda:None)
    def test_scan_does_not_discard_opening_handoff_when_staging_next(self):
        selected=[market()]
        prep=Preparation(lambda path,params=None:{'markets':selected} if params else {'market':market()},lambda m:m['floor_strike'],self.pool,lambda:self.at)
        prep.scan();self.at=OPEN+.2;selected[:]=[market(OPEN+900)];prep.scan()
        self.assertEqual(prep.select(lambda:None)['ticker'],market()['ticker'])
    def test_wrong_ticker_window_target_and_discovery_failure_fail_closed(self):
        self.at=OPEN+1
        for m in [dict(market(),ticker='OTHER'),dict(market(),close_time=bridge.utc(OPEN+901)),dict(market(),open_time=bridge.utc(OPEN+1))]:
            with self.subTest(m=m),self.assertRaises(ValueError):self.pool.select(m,80000)
        for t in [None,float('nan'),-1]:
            with self.subTest(target=t),self.assertRaises(ValueError):self.pool.select(market(),t)
        prep=Preparation(lambda *a,**k:(_ for _ in ()).throw(TimeoutError()),lambda m:m['floor_strike'],self.pool,lambda:self.at)
        self.assertIsNone(prep.select(lambda:None));self.assertIsNone(self.pool.current)
    def test_quote_projection_matches_actual_book_and_cannot_renew_expiry(self):
        self.at=OPEN+300;self.pool.select(market(),80000);p=self.pool.current;book_for(p,self.at)
        before=(p.book.seq,p.book.ts_ms,deepcopy(p.book.levels));q=QuoteProjection(self.pool,lambda:self.at)
        a=q.capture();self.assertEqual(a['status'],'AVAILABLE');self.assertEqual(a['up_ask'],.35)
        self.at+=.4;b=q.capture();self.assertEqual(a['expires_at'],b['expires_at'])
        self.assertEqual(before,(p.book.seq,p.book.ts_ms,p.book.levels))
        self.at+=6;self.assertEqual(q.capture()['status'],'UNAVAILABLE')
        self.at=OPEN+300;book_for(p,self.at);p.book.levels['no'].clear()
        with patch('btc15_v2_product.bootstrap.time.time',return_value=self.at):p._accepted_clock(p.book,p.epoch)
        self.assertEqual(q.capture()['status'],'UNAVAILABLE')
        self.at=OPEN+900;self.assertEqual(q.capture()['reason'],'OUTSIDE_OFFICIAL_WINDOW')
    def test_native_consume_exact_return_and_provenance_no_extra_processing(self):
        self.at=OPEN+300;self.pool.select(market(),80000);p=self.pool.current;book_for(p,self.at)
        # Inert providers bypass __init__; supply its existing off-path seam.
        p.proof_writer=SimpleNamespace(submit=lambda witness,events:True)
        p.events=[]
        with tempfile.TemporaryDirectory() as td,patch('btc15_kalshi_quote_provenance_v1.proof_path',return_value=Path(td)/'proof.json'),patch('btc15_kalshi_quote_provenance_v1.time.time',return_value=self.at):
            expected=Provider.consume(p,p.ticker,bridge.utc(self.at),p.close_ms)
            first=deepcopy(p.last_product_quote)
            actual=self.pool.consume(p.ticker,bridge.utc(self.at),p.close_ms)
        self.assertEqual(actual,expected);self.assertEqual(self.pool.last_product_quote,first)

class EquivalenceTests(unittest.TestCase):
    def test_v81_full_native_loop_call_count_and_frozen_gate_equivalence(self):
        from collections import deque
        import math
        from btc15_v81_qualified_inputs_v1 import InputUnavailable
        class Stop(BaseException):pass
        def stop(_):raise Stop()
        tree=ast.parse((ROOT/'v81_30_45_live_feed.py').read_text())
        native_trees=[ast.parse((ROOT/name).read_text()) for name in ('scalp_lead_shadow_v5.py','scalp_lead_unified_v8.py')]
        at=[OPEN+300];current=[None];results=[[],[]];engines=[Scalp(),Scalp()]
        with tempfile.TemporaryDirectory() as td:
            admin=Admin(td,'v81',clock=lambda:at[0])
            spaces=[]
            for index in (0,1):
                ns=dict(math=math,print=lambda *a,**k:None,hist=deque(),_v2_admin=admin,
                    _qualified_inputs=SimpleNamespace(last_ticker=market()['ticker']),InputUnavailable=InputUnavailable,
                    time=SimpleNamespace(time=lambda:at[0],sleep=stop))
                for native_tree in native_trees:
                    for n in native_tree.body:
                        if isinstance(n,ast.Assign):
                            try:value=ast.literal_eval(n.value)
                            except (ValueError,TypeError):continue
                            for target in n.targets:
                                if isinstance(target,ast.Name):ns[target.id]=deepcopy(value)
                    names={'ago','d','features','_fresh','_floor_ratio','evidence_route'}
                    fns=[n for n in native_tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
                    exec(compile(ast.Module(body=fns,type_ignores=[]),'<frozen-v81-functions>','exec'),ns)
                picked=instrument(tree,'v81') if index else tree
                fns=[n for n in picked.body if isinstance(n,ast.FunctionDef)]
                exec(compile(ast.Module(body=fns,type_ignores=[]),'<native-v81-loop>','exec'),ns)
                def snap():
                    if isinstance(current[0],Exception):raise current[0]
                    return deepcopy(current[0])
                ns['snap']=snap;engines[index].restore({})
                def offer(f,index=index):
                    results[index].append((deepcopy(f),engines[index].process(f,at[0])))
                ns['journal_offer']=offer;spaces.append(ns)
            for i in range(41):
                at[0]=OPEN+300+i
                current[0]=state(at[0],.34,i+1)['row']
                current[0]['btc']+=i*i;current[0]['brti']+=i*i
                current[0]['input_provenance']['brti']['value']=current[0]['brti']
                if i==33:current[0]=InputUnavailable('TIMESTAMPED_QUOTES_UNAVAILABLE')
                for ns in spaces:
                    with self.assertRaises(Stop):ns['loop']()
            self.assertEqual(results[0],results[1]);self.assertEqual(len(results[1]),41)
            self.assertEqual(stable(spaces[0]['hist']),stable(spaces[1]['hist']))
            admin.queue.join();admin.offer(None);admin.thread.join(2)
            with sqlite3.connect(Path(td)/'v81.admin.sqlite3') as db:
                self.assertEqual(db.execute('SELECT count(*) FROM evidence').fetchone()[0],82)

    def test_complete_native_loop_instrumentation_is_observational(self):
        a=FrozenRuntime(completed());b=a.fork();hooks=[]
        with tempfile.TemporaryDirectory() as td:
            admin=Admin(td,'main',clock=lambda:b.at)
            b.ns.update(_v2_admin=admin,_v2_prepare=lambda ns:None)
            tree=instrument(b.tree,'main');loop=next(n for n in tree.body if isinstance(n,ast.While) and isinstance(n.test,ast.Name) and n.test.id=='running')
            functions=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in FUNCTION_NAMES]
            exec(compile(ast.Module(body=functions,type_ignores=[]),'<instrumented-functions>','exec'),b.ns)
            b.loop=compile(ast.Module(body=[loop],type_ignores=[]),'<instrumented-native>','exec')
            bad_brti=fixture(320);bad_brti['brti_receipts']=[];bad_brti['brti_error']=True
            cases=[fixture(300),fixture(305),fixture(310,quote_wait=True),fixture(315),bad_brti,fixture(325)]
            noactive=fixture(330);noactive['market']=None;cases.append(noactive)
            bad=fixture(335);bad['market']['floor_strike']=None;cases.append(bad)
            for inp in cases:
                self.assertEqual(stable(a.step(inp)),stable(b.step(deepcopy(inp))))
                for name in STATE_NAMES:self.assertEqual(stable(a.ns[name]),stable(b.ns[name]),name)
            admin.queue.join();admin.offer(None);admin.thread.join(2)
            with sqlite3.connect(Path(td)/'main.admin.sqlite3') as db:
                rows=[json.loads(r[0]) for r in db.execute('SELECT body FROM evidence')]
            starts=[r for r in rows if r['schema']=='BTC15_NATIVE_ATTEMPT_START_R1']
            rows=[r for r in rows if r['schema']=='BTC15_NATIVE_ATTEMPT_R1']
            self.assertEqual({r['attempt_id'] for r in starts},{r['attempt_id'] for r in rows})
            self.assertEqual(len(rows),len(cases));self.assertEqual(len({r['attempt_id'] for r in rows}),len(cases))
            self.assertIn('QUOTE_WAIT',{r['outcome'] for r in rows});self.assertIn('NO_ACTIVE',{r['outcome'] for r in rows})
            self.assertIn('_fair_rf.predict_proba',{s['stage'] for r in rows for s in r['stages']})
    def test_directional_and_scalp_wrappers_preserve_every_frozen_output_and_state(self):
        for lane,cls in [('main',Directional),('v81',Scalp)]:
            a,b=cls(),cls();a.restore({});wrapped=ProcessorEnvelope(b,lane);wrapped.restore({})
            if lane=='main':
                tape=[frame(offset=300+i*5,sequence=i+1,p=p,ask=ask,side=side) for i,(p,ask,side) in enumerate([(.8,.35,'UP'),(.95,.75,'UP'),(.65,.72,'DOWN'),(.95,.76,'UP')])]
                bad=frame(offset=320,sequence=5);bad['brti']['ready']=False;tape+=[bad,frame(offset=325,sequence=6)]
            else:
                tape=[state(OPEN+299,.34,1),state(OPEN+300,.34,2),state(OPEN+301,.72,3),state(OPEN+302,.70,4),state(OPEN+303,.68,5),state(OPEN+304,.80,6),dict(kind='UNAVAILABLE',reason='FIXTURE',contract=market()['ticker'])]
            for i,f in enumerate(tape):
                now=f.get('captured_ts',OPEN+305)+.001
                r,s,v=a.process(deepcopy(f),now);r2,s2,v2=wrapped.process((deepcopy(f),'attempt'+str(i)),now)
                r2.pop('product');self.assertEqual(r,r2);self.assertEqual(s,s2)
                for k in ('schema','product_revision','lane','official_identity','administrative_journal'):v2.pop(k,None)
                self.assertEqual(v,v2)
    def test_typed_unavailable_has_no_action_or_renewed_source_deadline(self):
        with tempfile.TemporaryDirectory() as td:
            p=ProcessorEnvelope(Directional(),'main');p.restore({});f=frame()
            _,_,v=p.process((f,'attempt'),f['captured_ts']+.01);atomic_json(Path(td)/'main.json',v)
            fresh=public_view(td,'main',f['captured_ts']+.02);self.assertEqual(fresh['status'],'AVAILABLE')
            old=public_view(td,'main',f['captured_ts']+5)
            self.assertEqual(old['reason'],'SOURCE_EXPIRED');self.assertIn('official_identity',old)
            self.assertNotIn('final',old);self.assertNotIn('expires_at',old);self.assertTrue(old['historical_only'])
            ended=public_view(td,'main',OPEN+900);self.assertNotIn('official_identity',ended);self.assertNotIn('origin',ended)
    def test_admin_overflow_is_explicit_and_never_calls_strategy(self):
        a=object.__new__(Admin);import queue
        a.queue=queue.Queue(1);a.failed=None;a.accepted=a.written=a.dropped=0
        self.assertTrue(a.offer({'kind':'NO_ACTIVE'}));self.assertFalse(a.offer({'kind':'QUOTE_WAIT'}))
        self.assertEqual(a.health()['status'],'UNAVAILABLE');self.assertEqual(a.dropped,1)
    def test_admin_disk_failure_is_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'not-a-directory';root.write_text('fixture')
            a=Admin(root,'main');a.thread.join(2)
            self.assertTrue(a.failed.startswith('ADMIN_WRITER_FAILURE'));self.assertFalse(a.offer({'schema':'ATTEMPT'}))


def shifted(value,delta):
    if isinstance(value,dict):return {k:shifted(v,delta) for k,v in value.items()}
    if isinstance(value,list):return [shifted(v,delta) for v in value]
    if type(value) in (int,float):
        if OPEN-4000<=value<=OPEN+4000:return value+delta
        if (OPEN-4000)*1000<=value<=(OPEN+4000)*1000:return value+delta*1000
    if isinstance(value,str):
        if value==market()['ticker']:return bridge.ticker(OPEN+delta)
        if value.startswith('2026-10-03T'):
            try:return bridge.utc(datetime.fromisoformat(value).timestamp()+delta)
            except ValueError:pass
    return value

def release_fixture(path,opened=OPEN):
    r=dict(schema='BTC15_V2_RELEASE_RECEIPT_R1',revision=REVISION,strategy=bridge.CANDIDATE,
        signal_only=True,orders=False,evidence_class='FIXTURE',project=PROJECT,environment=ENVIRONMENT,
        manifest_sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        lanes={lane:dict(build=('a' if lane=='main' else 'b')*40,service=SERVICES[lane],volume=VOLUMES[lane],
            deployment=('1' if lane=='main' else '2')*8+'-1234-1234-1234-123456789abc',started_at=opened-10) for lane in ('main','v81')})
    path.write_text(json.dumps(r,indent=2)+'\n');return r,hashlib.sha256(path.read_bytes()).hexdigest()

class CohortTests(unittest.TestCase):
    def test_actual_worker_commits_once_and_links_only_administrative_attempt(self):
        import btc15_ladder_journal_v1 as frozen_journal
        from btc15_v2_product.journal import RevisionWorker,ADMINS
        at=OPEN+300.01
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);admin=Admin(root,'main',clock=lambda:at)
            with patch.object(frozen_journal,'Journal',RevisionJournal),patch.dict(ADMINS,{'main':admin}),patch('btc15_v2_product.journal.time.time',return_value=at):
                worker=RevisionWorker(root,'main',Directional(),clock=lambda:at)
                admin.begin();attempt_id=LOCAL.attempt['attempt_id']
                self.assertTrue(worker.offer(frame()));admin.finish()
                worker.offer(None);worker.thread.join(5)
                self.assertFalse(worker.thread.is_alive());self.assertIsNone(worker.failed)
                self.assertEqual(worker.written,1)
                admin.offer(None);admin.thread.join(5)
                self.assertFalse(admin.thread.is_alive());self.assertIsNone(admin.failed)
                with sqlite3.connect(root/'main.sqlite3') as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0],1)
                    latest=json.loads(db.execute("SELECT v FROM meta WHERE k='latest'").fetchone()[0])
                    self.assertEqual(latest['product']['attempt_id'],attempt_id)
                with sqlite3.connect(root/'main.admin.sqlite3') as db:
                    rows=[json.loads(r[0]) for r in db.execute('SELECT body FROM evidence ORDER BY seq')]
                self.assertEqual(len(rows),3)
                self.assertEqual({r['attempt_id'] for r in rows},{attempt_id})
                timings=[r for r in rows if r['schema']=='BTC15_PUBLICATION_TIMING_R1']
                self.assertEqual(timings[0]['journal_sequence'],1)
                v=public_view(root,'main',at)
                self.assertEqual(v['product_revision'],REVISION);self.assertEqual(v['journal']['written'],1)

    def test_unreviewed_deployment_volume_service_and_manifest_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'receipt.json';original,_=release_fixture(path)
            for key,val in [('deployment','unknown'),('volume','wrong-volume'),('service','wrong-service'),('build',bridge.IDENTITIES['main']['build'])]:
                r=deepcopy(original);r['lanes']['main'][key]=val;path.write_text(json.dumps(r));sha=hashlib.sha256(path.read_bytes()).hexdigest()
                with self.subTest(key=key),self.assertRaisesRegex(ValueError,'RELEASE_LANE_IDENTITY'):read_receipt(path,sha)
            r=deepcopy(original);r['manifest_sha256']='0'*64;path.write_text(json.dumps(r));sha=hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,'RELEASE_MANIFEST_RECEIPT'):read_receipt(path,sha)

    def test_foreign_root_is_rejected_without_touching_original_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'main.sqlite3';j=Journal(path,'main');j.close();before=hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,'FOREIGN_COHORT'):RevisionJournal(path,'main')
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)
    def test_real_processors_journals_snapshot_bridge_and_later_fixture_accumulation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);receipt_path=root/'release.json';receipt,sha=release_fixture(receipt_path)
            writers={};engines={};envs={};checkpoints=[]
            for lane,cls in [('main',Directional),('v81',Scalp)]:
                ids=receipt['lanes'][lane];envs[lane]=dict(RAILWAY_GIT_COMMIT_SHA=ids['build'],RAILWAY_DEPLOYMENT_ID=ids['deployment'])
                with patch.dict(os.environ,envs[lane]),patch('btc15_v2_product.journal.time.time',return_value=OPEN-10):
                    writers[lane]=RevisionJournal(root/'live'/lane/(lane+'.sqlite3'),lane)
                engines[lane]=ProcessorEnvelope(cls(),lane);engines[lane].restore({})
            try:
                for window in (0,1):
                    delta=window*900;opened=OPEN+delta
                    for lane,w in writers.items():
                        step=5 if lane=='main' else 1
                        with patch.dict(os.environ,envs[lane]):
                            for n,offset in enumerate(range(0,900,step)):
                                at=OPEN+offset+.2
                                f=frame(offset=offset+.2,sequence=window*1000+n+1,p=.6,ask=.6) if lane=='main' else state(at,.49,window*1000+n+1,eligible=False)
                                f=shifted(f,delta)
                                r,s,_=engines[lane].process((f,f'fixture-{window}-{n}'),at+delta+.001)
                                self.assertNotIn('unavailable_reason',r)
                                w.commit(r,s)
                            settlement=dict(source='OFFICIAL_KALSHI_GET_MARKET',endpoint='https://external-api.kalshi.com/trade-api/v2/markets/'+bridge.ticker(opened),
                                ticker=bridge.ticker(opened),open_ts=opened,close_ts=opened+900,target=80000.,received_ts=opened+902,
                                status='AUTHORITATIVE',market_status='finalized',result='yes',side='UP',settlement_ts=bridge.utc(opened+901))
                            r,s,_=engines[lane].process((dict(kind='SETTLEMENT',contract=bridge.ticker(opened),settlement=settlement),None),opened+902)
                            w.commit(r,s)
                    paths={}
                    with configured(bridge,receipt_path,sha,allow_fixture=True):
                        for lane,w in writers.items():
                            paths[lane]=root/f'{lane}-{window}.sqlite3'
                            bridge.snapshot(w.path,paths[lane],lane,bridge.IDENTITIES[lane],evidence_class='FIXTURE')
                        report=bridge.score(paths['main'],paths['v81'],root/f'score-{window}',allow_fixture=True)
                    self.assertEqual(report['counts']['fully_scoreable_settled'],window+1)
                    self.assertEqual(report['scoring_status'],'BLOCKED');self.assertIn('SYNTHETIC_FIXTURE_ONLY',report['blockers'])
                    checkpoints.append(report['counts'])
                with self.assertRaisesRegex(ValueError,'NEW_PRODUCT_REQUIRES_REVIEWED_RECEIPT'):
                    bridge.load_snapshot(paths['main'],'main',allow_fixture=True)
                with self.assertRaisesRegex(ValueError,'REVIEWED_RECEIPT_HASH_REQUIRED'):
                    with configured(bridge,receipt_path,'0'*64,allow_fixture=True):pass
                OUT.mkdir(parents=True,exist_ok=True)
                (OUT/'fixture_bridge_progression.json').write_text(json.dumps(dict(evidence_class='FIXTURE',production_claim=False,checkpoints=checkpoints),indent=2)+'\n')
            finally:
                for w in writers.values():w.close()
    def test_restart_startup_slot_is_excluded_and_old_build_cannot_mix(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'main.sqlite3'
            env=dict(RAILWAY_GIT_COMMIT_SHA='a'*40,RAILWAY_DEPLOYMENT_ID='one')
            with patch.dict(os.environ,env),patch('btc15_v2_product.journal.time.time',return_value=OPEN+300):
                j=RevisionJournal(path,'main');p=ProcessorEnvelope(Directional(),'main');p.restore({});f=frame()
                r,s,v=p.process((f,'id'),OPEN+300.01);j.commit(r,s);j.close()
                j=RevisionJournal(path,'main');self.assertEqual(j.get('startup_slots'),[OPEN]);self.assertEqual(j.db.execute('SELECT missing FROM contracts').fetchone()[0],1);j.close()
            with patch.dict(os.environ,dict(env,RAILWAY_GIT_COMMIT_SHA='b'*40)),self.assertRaisesRegex(ValueError,'COHORT_IDENTITY_CHANGED'):
                RevisionJournal(path,'main')
    def test_production_launcher_is_locked_without_reviewed_receipt(self):
        with patch.dict(os.environ,{},clear=True),self.assertRaisesRegex(ValueError,'DEPLOYMENT_NOT_AUTHORIZED'):
            verify_environment('main')

if __name__=='__main__':unittest.main()
