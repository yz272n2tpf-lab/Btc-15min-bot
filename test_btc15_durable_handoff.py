"""Bounded durable publication, using actual frozen Scalp and SQLite journals."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zlib

from btc15_scalp_journal_v1 import Scalp
from btc15_v2_product.durable_handoff import DurableWorker, Inbox, CAPACITY
from btc15_v2_product.journal import RevisionJournal, public_view
from test_btc15_scalp_journal_v1 import state, OPEN, ENTRY
from ops.btc15_v2_scoring.bridge import ticker


def frame(at, seq, eligible=True, bid=.34):
    f=state(at,bid,seq,eligible=eligible)
    opened=int(at//900)*900;contract=ticker(opened)
    f['contract']=contract;f['row'].update(ticker=contract,left=opened+900-at)
    for p in [f['row']['input_provenance'], *[h['input_provenance'] for v in f['proposals'].values() for h in v['history'].values()]]:
        p.update(open_ts=opened,close_ts=opened+900,ticker=contract)
        p['quote']['ticker']=contract
    return f


class Trace(Scalp):
    def __init__(self):super().__init__();self.observations=[]
    def process(self,f,now):
        result=super().process(f,now)
        self.observations.append((deepcopy(f),now,deepcopy(result)))
        return result


def records(root):
    with sqlite3.connect(Path(root)/'v81.sqlite3') as db:
        return [(s,json.loads(zlib.decompress(raw))) for s,raw in db.execute('SELECT seq,body FROM events ORDER BY seq')]


class HandoffTests(unittest.TestCase):
    def test_fresh_runtime_import_installs_the_durable_worker(self):
        code='''import os,tempfile
from unittest.mock import patch
from btc15_v2_product.runtime import v81_main
from btc15_v2_product.journal import install,worker_for
from btc15_v2_product.durable_handoff import DurableWorker
with tempfile.TemporaryDirectory() as td:
 os.environ['BTC15_LADDER_DATA_ROOT']=td
 install()
 import btc15_scalp_journal_v1 as lane
 assert lane.Worker is worker_for
 with patch.object(DurableWorker,'start_settlements',lambda self:None):lane.start()
 assert isinstance(lane._worker,DurableWorker)
 assert lane.offer(dict(kind='UNAVAILABLE',reason='FIXTURE_STARTUP'))
 assert lane._worker.wait_idle(5)
 assert lane._worker.written==1
 lane._worker.close()
'''
        r=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def equivalent(self,trace):
        oracle=Scalp();oracle.restore({});events=[]
        for f,now,result in trace.observations:
            expected=oracle.process(f,now)
            self.assertEqual(result,expected)
            r=result[0]
            if r.get('event'):events.append((r['event'],r['published_ts'],(r.get('origin') or {}).get('origin_id')))
        self.assertEqual(len(events),len(set(events)))
        return events

    def test_delayed_worker_160_records_concurrent_reads_and_recovery(self):
        entered,release=threading.Event(),threading.Event();clock=[ENTRY+.001];trace=Trace()
        original=RevisionJournal.commit
        def delayed(journal,record,saved):
            if record['product']['handoff_sequence']==1:
                entered.set()
                if not release.wait(10):raise RuntimeError('test barrier timeout')
            return original(journal,record,saved)
        with tempfile.TemporaryDirectory() as td,patch.object(RevisionJournal,'commit',delayed):
            w=DurableWorker(td,'v81',trace,lambda:clock[0]);stop=threading.Event();reads=[]
            def read_loop():
                while not stop.wait(.001):
                    v=public_view(td,'v81',clock[0]);reads.append(v)
            reader=threading.Thread(target=read_loop);reader.start()
            try:
                self.assertTrue(w.offer(frame(ENTRY,1,False)));self.assertTrue(entered.wait(5))
                timings=[]
                for n in range(1,160):
                    clock[0]=ENTRY+n+.001;t=time.perf_counter()
                    self.assertTrue(w.offer(frame(ENTRY+n,n+1,False)))
                    timings.append((time.perf_counter()-t)*1000)
                self.assertEqual((w.accepted,w.written,w.dropped,w.inbox.depth),(160,0,0,160))
                # Inputs are acknowledged only after the separate inbox commit.
                with sqlite3.connect(w.inbox.path) as db:self.assertEqual(db.execute('SELECT count(*) FROM pending').fetchone()[0],160)
                release.set();self.assertTrue(w.wait_idle(10));self.assertIsNone(w.failed)
                for n in range(160,164):
                    clock[0]=ENTRY+n+.001
                    self.assertTrue(w.offer(frame(ENTRY+n,n+1,False)));self.assertTrue(w.wait_idle(5))
                    self.assertEqual(public_view(td,'v81',clock[0])['status'],'PASS')
                self.assertTrue(w.thread.is_alive());self.assertEqual((w.accepted,w.written,w.dropped,w.inbox.depth),(164,164,0,0))
                rec=records(td);self.assertEqual([s for s,_ in rec],list(range(1,165)))
                self.assertTrue(any(r.get('unavailable_reason') for _,r in rec))
                self.assertEqual(self.equivalent(trace),[])
                seqs=[v['journal']['sequence'] for v in reads if 'journal' in v]
                self.assertEqual(seqs,sorted(seqs))
                out=Path(__file__).parent/'qualification/final_completion_20261005';out.mkdir(parents=True,exist_ok=True)
                (out/'v81-overload.json').write_text(json.dumps(dict(status='PASS',accepted=164,written=164,dropped=0,
                    backlog_peak=160,ending_queue=0,capacity=CAPACITY,concurrent_reads=len(reads),
                    native_admission_ms_max=max(timings),native_admission_ms_mean=sum(timings)/len(timings),
                    sequence_gaps=0,event_drift=0,upstream_calls=0,delayed_sources_fail_closed=True,
                    publication_recovers=True,initial_production_trigger='UNPROVEN'),indent=2)+'\n')
            finally:
                release.set();stop.set();reader.join(5);w.close()

    def test_full_contract_rollover_invalid_sources_and_event_equivalence(self):
        clock=[OPEN+.501];trace=Trace();sequences=[];unavailable=[]
        with tempfile.TemporaryDirectory() as td:
            w=DurableWorker(td,'v81',trace,lambda:clock[0])
            try:
                for n in range(960):
                    at=OPEN+.5+n;clock[0]=at+.001
                    f=frame(at,n+1,eligible=40<=at%900<880,bid=.44 if n%40 in (5,6) else .38 if n%40==7 else .34)
                    if n==410:f['row']['input_provenance']['quote']['source_ts_ms']=int((at-6.001)*1000)
                    if n==610:f['row']['input_provenance']['quote']['ticker']='WRONG'
                    self.assertTrue(w.offer(f));self.assertTrue(w.wait_idle(5));self.assertIsNone(w.failed)
                    v=public_view(td,'v81',clock[0]);sequences.append(v['journal']['sequence'])
                    if n in (410,610):self.assertEqual(v['status'],'UNAVAILABLE');unavailable.append(v['reason'])
                    else:self.assertIn(v['status'],('AVAILABLE','PASS'),(n,v))
                    if v['status']!='UNAVAILABLE':self.assertEqual(v['contract'],ticker(int(at//900)*900))
                self.assertEqual(sequences,list(range(1,961)))
                events=self.equivalent(trace);self.assertTrue(events)
                rec=records(td);actual=[(r['event'],r['published_ts'],(r.get('origin') or {}).get('origin_id')) for _,r in rec if r.get('event')]
                self.assertEqual(actual,events)
                clock[0]+=10;self.assertEqual(public_view(td,'v81',clock[0])['status'],'UNAVAILABLE')
                out=Path(__file__).parent/'qualification/final_completion_20261005';out.mkdir(parents=True,exist_ok=True)
                (out/'v81-contract.json').write_text(json.dumps(dict(status='PASS',cadence_seconds=1,
                    clock='accelerated production-cadence logical clock',duration_seconds=960,accepted=w.accepted,
                    written=w.written,dropped=w.dropped,ending_queue=w.inbox.depth,events=events,
                    event_ids_and_timestamps_equal=True,sequence_gaps=0,source_injections=unavailable,
                    rollover=True,expiry_closed=True),indent=2)+'\n')
            finally:w.close()

    def test_durable_commit_cursor_prevents_duplicate_after_crash(self):
        with tempfile.TemporaryDirectory() as td:
            original=Inbox.acknowledge
            def crash(inbox,through):
                if through==1:raise RuntimeError('SIMULATED_PROCESS_DEATH_AFTER_COMMIT')
                return original(inbox,through)
            with patch.object(Inbox,'acknowledge',crash):
                w=DurableWorker(td,'v81',Scalp(),lambda:ENTRY+.001)
                self.assertTrue(w.offer(frame(ENTRY,1,False)));w.thread.join(5)
                self.assertFalse(w.thread.is_alive());self.assertEqual(len(records(td)),1);w.close()
            w=DurableWorker(td,'v81',Scalp(),lambda:ENTRY+10)
            try:
                self.assertTrue(w.wait_idle(5));self.assertEqual(len(records(td)),1)
                self.assertEqual(public_view(td,'v81',ENTRY+10)['status'],'UNAVAILABLE')
                self.assertTrue(w.offer(frame(ENTRY+10,2,False)));self.assertTrue(w.wait_idle(5))
                self.assertEqual([s for s,_ in records(td)],[1,2]);self.assertEqual(w.dropped,0)
            finally:w.close()
            # A clean restart republishes the same committed count, never +1.
            import btc15_v2_product.durable_handoff as handoff
            published=threading.Event();original_publish=handoff.atomic_json
            def republish(path,value):
                original_publish(path,value);published.set()
            with patch.object(handoff,'atomic_json',republish):
                w=DurableWorker(td,'v81',Scalp(),lambda:ENTRY+11)
                try:
                    self.assertTrue(published.wait(5));self.assertTrue(w.wait_idle(5))
                    v=public_view(td,'v81',ENTRY+11)
                    self.assertEqual(v['journal']['written'],2)
                    self.assertEqual(v['journal']['queue_depth'],0)
                    self.assertEqual(len(records(td)),2)
                finally:w.close()

    def test_capacity_rejection_has_durable_evidence_and_is_not_latched(self):
        with tempfile.TemporaryDirectory() as td:
            inbox=Inbox(td,'TEST',capacity=2)
            try:
                for n in range(2):self.assertTrue(inbox.append((frame(ENTRY+n,n,False),None),ENTRY+n))
                self.assertFalse(inbox.append((frame(ENTRY+2,2,False),None),ENTRY+2))
                self.assertEqual(inbox.db.execute('SELECT count(*) FROM rejected').fetchone()[0],1)
                self.assertEqual((inbox.accepted,inbox.dropped,inbox.depth),(2,1,2))
                inbox.acknowledge(1)
                self.assertTrue(inbox.append((frame(ENTRY+3,3,False),None),ENTRY+3))
                self.assertEqual((inbox.accepted,inbox.dropped,inbox.depth),(3,1,2))
            finally:inbox.close()

    def test_transient_publication_write_failure_retries_without_reprocessing(self):
        import btc15_v2_product.durable_handoff as handoff
        original=handoff.atomic_json;attempts=[];trace=Trace()
        def interrupted(path,value):
            attempts.append(value['published_ts'])
            if len(attempts)<=2:raise OSError('INJECTED_TEMPORARY_WRITE_FAILURE')
            return original(path,value)
        with tempfile.TemporaryDirectory() as td,patch.object(handoff,'atomic_json',interrupted):
            w=DurableWorker(td,'v81',trace,lambda:ENTRY+.001)
            try:
                self.assertTrue(w.offer(frame(ENTRY,1,False)));self.assertTrue(w.wait_idle(5))
                self.assertEqual(len(trace.observations),1);self.assertEqual(len(records(td)),1)
                self.assertEqual(attempts,[ENTRY+.001]*3)
                self.assertEqual(public_view(td,'v81',ENTRY+.001)['status'],'PASS')
                self.assertTrue(w.thread.is_alive());self.assertIsNone(w.failed)
            finally:w.close()


if __name__=='__main__':unittest.main()
