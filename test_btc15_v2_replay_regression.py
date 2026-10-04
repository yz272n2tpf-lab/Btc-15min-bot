"""Replay/publication integration regressions. Synthetic inputs; NO live acceptance."""
import ast
from contextlib import ExitStack
import csv
from copy import deepcopy
from datetime import datetime
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
import zlib

import btc15_ladder_journal_v1 as frozen
import btc15_ladder_product_v1 as product
import btc15_information_native_offpath_candidate as native
import btc15_kalshi_quote_provenance_v1 as quotes
from btc15_v2_product.admin import Admin
from btc15_v2_product.journal import ADMINS,RevisionJournal,RevisionWorker,public_view
from btc15_v2_product.routes import serve
from btc15_v2_product.runtime import instrument
from completion_audit.isolated_decision_v2 import FrozenRuntime
from test_btc15_isolated_decision_v2 import completed,fixture
from test_btc15_ladder_completion_v1 import frame,OPEN
from test_btc15_v2_product_r1 import shifted

OUT=Path(__file__).parent/'qualification/v2_product_20261004'

def parity_file(path,count):
    with path.open('w',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=['contract','timestamp_utc','target','final60_count',
            'final60_average','final60_side','final60_complete'])
        writer.writeheader()
        for i in range(count):
            writer.writerow(dict(contract='historical-'+str(i),timestamp_utc='2026-10-02T00:00:00Z',
                target=80000,final60_count=60,final60_average=80080+i/100,final60_side='UP',final60_complete=True))

def wait_for(predicate,timeout=10):
    end=time.monotonic()+timeout
    while not predicate():
        if time.monotonic()>end:raise AssertionError('timed out waiting for durable progress')
        threading.Event().wait(.002)

class OneScan(threading.Event):
    def wait(self,timeout=None):
        self.set()
        return True

def copier(path):
    thread=threading.Thread(target=native._cohort_closeout_worker,args=({'BRTI_PARITY_LOG':path},OneScan()),daemon=True)
    thread.start()
    return thread

def records(path):
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        return [(seq,json.loads(zlib.decompress(raw))) for seq,raw in db.execute('SELECT seq,body FROM events ORDER BY seq')]

def native_namespace(f):
    return dict(market=dict(ticker=f['contract'],open_time=product.iso(f['official_open']),close_time=product.iso(f['official_close'])),
        parse_dt=datetime.fromisoformat,_ec_live=f['fair'],_brti_contract=f['brti'],
        _btc_spot_provenance=dict(source_utc=datetime.fromisoformat(product.iso(f['btc_source'])),
            observed_utc=datetime.fromisoformat(product.iso(f['btc_received']))),
        now_ts=f['feature_cutoff'],target=f['target'],btc=f['btc_price'],
        _fair_model_artifact_sha256=f['artifact'],_fair_model_weights_sha256=f['weights'],
        **{k:f[k] for k in ('up_bid','up_ask','down_bid','down_ask')})

class ReplayRegression(unittest.TestCase):
    def context(self,root,clock,journal=RevisionJournal,worker_type=RevisionWorker,admin=True,scope=None):
        stack=scope
        stack.enter_context(patch.object(frozen,'Journal',journal))
        stack.enter_context(patch.object(native,'COHORT_PATH',root/'native-cohort.jsonl'))
        stack.enter_context(patch.object(native,'_COHORT_CLOSEOUT_SEEN',set()))
        a=Admin(root,'main',clock=clock) if admin else None
        stack.enter_context(patch.dict(ADMINS,{'main':a},clear=True))
        worker=worker_type(root,'main',product.Directional(),clock=clock)
        stack.enter_context(patch.object(product,'_worker',worker))
        def stop():
            if worker.thread.is_alive():worker.queue.put(None);worker.thread.join(3)
            if a and a.thread.is_alive():a.queue.put(None);a.thread.join(3)
        stack.callback(stop)
        return worker,a

    def test_rejected_candidate_negative_control_reproduces_exact_latch(self):
        class RejectedWorker(RevisionWorker):
            def offer(self,value):
                # Exact rejected admission: every closeout uses frozen put_nowait.
                return frozen.Worker.offer(self,(value,None) if value is not None else None)
        entered,release=threading.Event(),threading.Event()
        class HeldJournal(RevisionJournal):
            def commit(self,record,state):
                if record['kind']=='BRTI_CLOSEOUT':entered.set();release.wait(5)
                return super().commit(record,state)
        with ExitStack() as scope:
            td=scope.enter_context(tempfile.TemporaryDirectory())
            root=Path(td);at=frame()['captured_ts']+.01
            worker,_=self.context(root,lambda:at,HeldJournal,RejectedWorker,admin=False,scope=scope)
            worker.offer(frame());worker.queue.join();before=(root/'main.json').read_bytes()
            parity_file(root/'parity.csv',800);thread=copier(root/'parity.csv')
            self.assertTrue(entered.wait(2));thread.join(3);self.assertFalse(thread.is_alive())
            self.assertEqual(worker.failed,'JOURNAL_QUEUE_FULL');self.assertEqual(worker.dropped,1)
            self.assertFalse(worker.offer(frame(offset=305,sequence=2)))
            release.set();worker.queue.join()
            self.assertTrue(worker.thread.is_alive());self.assertEqual((root/'main.json').read_bytes(),before)
            self.assertEqual(public_view(root,'main',at+6)['reason'],'SOURCE_EXPIRED')
            worker.queue.put(None);worker.thread.join(2)

    def test_800_closeouts_four_bursts_with_current_observer_journals_routes_and_rollover(self):
        class SlowJournal(RevisionJournal):
            def commit(self,record,state):
                if record['kind']=='BRTI_CLOSEOUT':threading.Event().wait(.004)
                return super().commit(record,state)
        with ExitStack() as scope:
            td=scope.enter_context(tempfile.TemporaryDirectory())
            root=Path(td);at=[OPEN+300.01]
            worker,admin=self.context(root,lambda:at[0],SlowJournal,scope=scope)
            provider=SimpleNamespace(last_product_quote=None)
            views=[];n=0;overlapping=0
            with patch.object(quotes,'_provider',provider),patch.object(product,'time',SimpleNamespace(time=lambda:at[0]-.01)):
                for wave in range(4):
                    parity_file(root/'parity.csv',(wave+1)*200);thread=copier(root/'parity.csv')
                    wave_iterations=0
                    while thread.is_alive() or wave_iterations<50:
                        n+=1;wave_iterations+=1;overlapping+=int(thread.is_alive())
                        offset=300.25+(n-1)*5;delta=int(offset//900)*900
                        f=shifted(frame(offset=offset%900,sequence=n,p=.95 if n%3 else .8),delta)
                        at[0]=f['captured_ts']+.01;provider.last_product_quote=f['quote']
                        admin.begin();admin.call('_btc15_ladder_offer',product.offer,native_namespace(f));admin.finish()
                        wait_for(lambda:worker.failed or (root/'main.json').exists() and json.loads((root/'main.json').read_text()).get('published_ts')==at[0])
                        self.assertIsNone(worker.failed)
                        class Handler:
                            path='/ladders'
                            def _send(self,code,kind,body):self.code,self.value=code,json.loads(body)
                        handler=Handler()
                        with patch.dict(os.environ,BTC15_LADDER_DATA_ROOT=td),patch('btc15_v2_product.journal.time.time',return_value=at[0]):
                            self.assertTrue(serve(handler))
                        v=handler.value;self.assertEqual(handler.code,200)
                        self.assertNotEqual(v['status'],'UNAVAILABLE',v)
                        self.assertEqual(v['contract'],f['contract']);self.assertAlmostEqual(v['final']['probability_up'],f['fair']['up_fair'])
                        if views:
                            self.assertGreater(v['published_ts'],views[-1]['published_ts'])
                            self.assertGreater(v['journal']['sequence'],views[-1]['journal']['sequence'])
                            if v['contract']!=views[-1]['contract']:self.assertIsNone(v['origin'])
                        views.append(v)
                        self.assertLess(n,3000)
                    thread.join(2);self.assertFalse(thread.is_alive())
            worker.queue.join();admin.queue.join()
            self.assertEqual(worker.replay_committed,800);self.assertEqual(worker.dropped,0)
            self.assertTrue(worker.thread.is_alive());self.assertIsNone(worker.failed)
            self.assertEqual(worker.accepted,worker.written);self.assertGreater(overlapping,16)
            rows=records(root/'main.sqlite3');closeouts=[r for _,r in rows if r['kind']=='BRTI_CLOSEOUT']
            cohort=[json.loads(s) for s in (root/'native-cohort.jsonl').read_text().splitlines()]
            self.assertEqual(len(closeouts),800);self.assertEqual(len(cohort),800)
            self.assertEqual({r['contract']:r['brti_closeout'] for r in closeouts},{r['contract']:r['brti'] for r in cohort})
            self.assertEqual(len([r for _,r in rows if r['kind']=='NATIVE_DECISION']),n)
            self.assertEqual([seq for seq,_ in rows],list(range(1,n+801)))
            # A copier restart reads the retained cohort and does not duplicate rows.
            native._COHORT_CLOSEOUT_SEEN.clear();again=copier(root/'parity.csv');again.join(3)
            self.assertFalse(again.is_alive());self.assertEqual(worker.replay_committed,800)
            with sqlite3.connect(root/'main.admin.sqlite3') as db:
                attempts=[json.loads(r[0]) for r in db.execute('SELECT body FROM evidence')]
            done=[r for r in attempts if r['schema']=='BTC15_NATIVE_ATTEMPT_R1']
            self.assertEqual(len(done),n);self.assertTrue(all(r['outcome']=='PUBLICATION_QUEUED' for r in done))
            self.assertTrue(all('_btc15_ladder_offer' in {s['stage'] for s in r['stages']} for r in done))
            self.assertEqual(len([r for r in attempts if r['schema']=='BTC15_PUBLICATION_TIMING_R1']),n+800)
            self.assertIsNone(admin.failed);self.assertEqual(admin.dropped,0)
            self.assertGreater(len({v['contract'] for v in views}),1)
            self.assertIn('ENTER',{v['early']['guidance'] for v in views})
            self.assertIn('HOLD',{v['early']['guidance'] for v in views})
            self.assertIn('PASS',{v['early']['guidance'] for v in views})
            self.assertEqual(public_view(root,'main',at[0]+6)['reason'],'SOURCE_EXPIRED')
            OUT.mkdir(parents=True,exist_ok=True)
            (OUT/'replay_regression_results.json').write_text(json.dumps(dict(evidence_class='FIXTURE',
                status='PASS',closeouts=800,bursts=4,native_publications=n,concurrent_publications=overlapping,
                accepted=worker.accepted,written=worker.written,dropped=worker.dropped,replay_waits=worker.replay_waits,
                contracts=sorted({v['contract'] for v in views}),native_rejections=0,admin_drops=admin.dropped,
                first_publication=views[0]['published_ts'],last_publication=views[-1]['published_ts'],
                signal_only=True,orders=False),indent=2)+'\n')
            worker.queue.put(None);worker.thread.join(2);admin.queue.put(None);admin.thread.join(2)

    def test_full_frozen_native_loop_calls_real_observer_during_replay(self):
        runtime=FrozenRuntime(completed());tree=instrument(native.instrument(runtime.tree),'main')
        loop=next(n for n in tree.body if isinstance(n,ast.While) and isinstance(n.test,ast.Name) and n.test.id=='running')
        runtime.loop=compile(ast.Module(body=[loop],type_ignores=[]),'<repaired-full-native-loop>','exec')
        with ExitStack() as scope:
            td=scope.enter_context(tempfile.TemporaryDirectory())
            root=Path(td);worker,admin=self.context(root,lambda:runtime.at+.001,scope=scope)
            runtime.ns.update(_v2_admin=admin,_btc15_information_offer=lambda ns:None,
                _btc15_cohort_offer=native.cohort_offer,_btc15_cohort_closeout_offer=native.cohort_closeout_offer,
                _btc15_ladder_offer=product.offer,BRTI_PARITY_LOG=root/'parity.csv')
            parity_file(root/'parity.csv',128);provider=SimpleNamespace(last_product_quote=None)
            with patch.object(quotes,'_provider',provider),patch.object(product,'time',SimpleNamespace(time=lambda:runtime.at)),patch.object(native,'_COHORT_CLOSEOUT_STARTED',False):
                try:
                    for n in range(24):
                        inp=fixture(300+n*5);p=inp['proof'];m=inp['market'];prices=quotes.replay(p,p['source_time'],m['ticker'],int(datetime.fromisoformat(m['close_time']).timestamp()*1000),int(inp['decision']*1000))[0]
                        provider.last_product_quote=dict(ticker=m['ticker'],source_time=p['source_time'],epoch=p['epoch'],
                            consumed_ms=p['consumed_ms'],market_id=p['identity'][0],sid=p['identity'][1],seq=p['identity'][2],
                            exchange_ts_ms=p['identity'][3],close_ms=int(datetime.fromisoformat(m['close_time']).timestamp()*1000),quotes=prices)
                        runtime.step(inp)
                        wait_for(lambda:(root/'main.json').exists() and json.loads((root/'main.json').read_text()).get('published_ts')==runtime.at+.001)
                        self.assertNotEqual(public_view(root,'main',runtime.at+.002)['status'],'UNAVAILABLE')
                    wait_for(lambda:worker.replay_committed==128)
                finally:native._stop_cohort_closeout_worker()
            worker.queue.join();admin.queue.join()
            self.assertEqual(len([r for _,r in records(root/'main.sqlite3') if r['kind']=='NATIVE_DECISION']),24)
            self.assertEqual(worker.dropped,0);self.assertIsNone(worker.failed)
            worker.queue.put(None);worker.thread.join(2);admin.queue.put(None);admin.thread.join(2)

    def test_disk_failure_is_explicit_and_retains_closeout_source(self):
        class BrokenJournal(RevisionJournal):
            def commit(self,record,state):raise OSError('injected disk failure')
        with ExitStack() as scope:
            td=scope.enter_context(tempfile.TemporaryDirectory())
            root=Path(td);worker,_=self.context(root,lambda:OPEN+300,BrokenJournal,admin=False,scope=scope)
            parity_file(root/'parity.csv',1);thread=copier(root/'parity.csv');thread.join(3)
            self.assertFalse(thread.is_alive());self.assertEqual(worker.replay_committed,0)
            self.assertEqual(worker.replay_failures,1);self.assertEqual(worker.failed,'JOURNAL_FAILURE:OSError')
            self.assertEqual(len((root/'native-cohort.jsonl').read_text().splitlines()),1)
            self.assertFalse(worker.offer(frame()))

if __name__=='__main__':unittest.main()
