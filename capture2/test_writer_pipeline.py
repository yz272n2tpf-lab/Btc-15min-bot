"""Focused correctness plus decisive real-kernel sustained pipeline gate."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import gzip
import hashlib
import hmac
import json
import os
from pathlib import Path
import resource
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import urlopen

from capture2.runtime import CaptureProducer,SenderPopulation,DeferredQuoteCapture
from capture2.wire import freeze,owned_size,envelope,frame,unframe,MAX_FRAME
from sprint_evidence.passive_capture import Identity,observed_copy,pack,digest,SCHEMA
from sprint_evidence.quote_receive_capture import SOURCE_SHA256
from capture2.writer import Accounting,packet

ROOT=Path(__file__).resolve().parents[1];KEY=b'a'*32;SOURCE=SOURCE_SHA256
IDENT=Identity('test','build',SOURCE,'run','domain','boot')
CONFIG=dict(key=KEY.hex(),run_id='run',build='build',source_hashes=[SOURCE])

def end(seconds=15):return time.clock_gettime_ns(time.CLOCK_BOOTTIME)+int(seconds*1e9)
def wait_for(fn,timeout=5):
    limit=time.monotonic()+timeout
    while not fn() and time.monotonic()<limit:time.sleep(.005)
    if not fn():raise AssertionError('WAIT_TIMEOUT')

class Held:
    def __init__(self):self.ready=False;self.raw=[];self.threads=[]
    def setblocking(self,*a):pass
    def setsockopt(self,*a):pass
    def connect(self,*a):pass
    def close(self):pass
    def sendto(self,raw,*args):
        if not self.ready:raise BlockingIOError(11,'held')
        self.raw.append(raw);self.threads.append(threading.get_ident());return len(raw)

def poll(r,w,e,timeout):time.sleep(.001);return [],w if w[0].ready else [],[]

def unpack_all(frames):
    rows=[]
    for f in frames:
        header,payload=unframe(f,CONFIG);decoded=[packet(r,CONFIG) for r in gzip.decompress(payload).splitlines()]
        assert [r['sequence'] for r in decoded]==header['sequences']
        rows+=decoded
    return rows

class PipelineTests(unittest.TestCase):
    def test_snapshot_shape_bound_and_no_later_mutation(self):
        original={'n':[1,2.0,float('nan'),True,None,{'nested':'value'}],'at':datetime(2026,9,30,tzinfo=timezone.utc)}
        copied,charge=freeze(original);self.assertEqual(copied,observed_copy(original));self.assertEqual(charge,owned_size(copied))
        original['n'][-1]['nested']='changed';self.assertEqual(copied['n'][-1]['nested'],'value')
        for invalid in [{1:'bad'},'x'*140001,[None]*4097]:
            with self.assertRaises(ValueError):freeze(invalid)

    def test_offer_never_serializes_and_worker_preserves_exact_origin_link(self):
        sink=Held();p=CaptureProducer('x',IDENT,KEY,sock=sink,end_boot_ns=end())
        origin=threading.get_ident();serializers=[]
        import capture2.runtime as runtime
        original_encoder=runtime.envelope
        def encode(*args):serializers.append(threading.get_ident());return original_encoder(*args)
        state={'early':{'ready':True},'generated_utc':'observed','source_timestamp_utc':'source','price':31}
        with patch('capture2.runtime.select.select',side_effect=poll),patch('capture2.runtime.envelope',side_effect=encode):
            try:
                self.assertTrue(p.protected(state,{}));self.assertTrue(p.published(state))
                state['price']=77
                self.assertTrue(p.published(state));sink.ready=True;p.close();p.sock.thread.join(3)
                rows=unpack_all(sink.raw);self.assertEqual([r['sequence'] for r in rows],[1,2,3])
                first=rows[0];state_hash=digest(pack(first['body']['state']))
                gid=digest(pack([first['identity'],1,state_hash]))
                self.assertEqual(first['body']['generation_id'],gid);self.assertEqual(first['body']['state']['price'],31)
                self.assertEqual(rows[1]['body']['generation_id'],gid);self.assertIsNone(rows[2]['body']['generation_id'])
                self.assertEqual(rows[2]['body']['linkage_status'],'UNAVAILABLE_GENERATION_LINK')
                self.assertNotIn(origin,serializers);self.assertNotIn(origin,sink.threads);self.assertTrue(p.sock.snapshot()['complete'])
            finally:p.close();p.sock.thread.join(3)

    def test_raw_quote_and_body_immutable_and_authenticated_wire(self):
        sink=Held();p=CaptureProducer('x',IDENT,KEY,sock=sink,end_boot_ns=end());tap=DeferredQuoteCapture(p,time_namespace_id='ns')
        with patch('capture2.runtime.select.select',side_effect=poll):
            try:
                tap._emit('{"quote":31}',None,1,2,'ticker','epoch')
                body={'mutable':[31]};self.assertTrue(p.offer('TEST',body));body['mutable'][0]=99
                sink.ready=True;p.close();p.sock.thread.join(3);rows=unpack_all(sink.raw)
                self.assertEqual(rows[0]['body']['emission']['raw_sha256'],digest(b'{"quote":31}'))
                self.assertEqual(rows[1]['body']['mutable'],[31])
                broken=bytearray(sink.raw[0]);broken[-1]^=1
                with self.assertRaises(ValueError):unframe(bytes(broken),CONFIG)
                wrong=dict(CONFIG,build='wrong')
                with self.assertRaises(ValueError):unframe(sink.raw[0],wrong)
            finally:p.close();p.sock.thread.join(3)

    def test_deadline_drains_accepted_and_overflow_stays_explicit(self):
        for overflow in [False,True]:
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);sink=Held();population=SenderPopulation(root,end(.15));p=CaptureProducer('x',IDENT,KEY,sock=sink,end_boot_ns=population.end_boot_ns,
                    status_path=root/'transport.json',population=population,max_packets=2)
                with patch('capture2.runtime.select.select',side_effect=poll):
                    try:
                        self.assertTrue(p.offer('TEST',{'n':1}));self.assertTrue(p.offer('TEST',{'n':2}))
                        if overflow:self.assertFalse(p.offer('TEST',{'n':3}))
                        time.sleep(.25);sink.ready=True;wait_for(lambda:population.retired==1)
                        population.thread.join(3);rows=unpack_all(sink.raw);self.assertEqual(len(rows),2)
                        self.assertEqual(p.sock.snapshot()['pending_packets'],0)
                        a=Accounting(root).capture({'test':2});self.assertEqual((a['created'],a['total'],a['retired']),(1,1,1))
                        self.assertEqual(a['complete'],not overflow)
                    finally:sink.ready=True;p.close();population.close();population.thread.join(3)


def rss(pid):
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith('VmRSS:'):return int(line.split()[1])
    except FileNotFoundError:pass
    return 0

def sustained(side,count=1500000,rate=12000,churn=5000):
    results=ROOT/'capture_writer/results';results.mkdir(exist_ok=True,parents=True)
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);address=str(root/'events.sock');port_sock=socket.socket();port_sock.bind(('127.0.0.1',0));port=port_sock.getsockname()[1];port_sock.close()
        config=dict(CONFIG,directory=d,socket=address,max_seconds=900,quota_bytes=1024*1024*1024,port=port)
        cp=root/'config.json';cp.write_text(json.dumps(config));proc=subprocess.Popen([sys.executable,'-B','-m','capture2.writer','--config',str(cp)],cwd=ROOT,start_new_session=True)
        deadline=end(850);population=SenderPopulation(root,deadline);stop=threading.Event();errors=[];history=[];stalls=[];p=None;threads=[]
        fixture=json.loads((ROOT/'capture_durability/transport_fixture.json').read_text())
        started=time.monotonic();churn_offered=[0];census_checks=[0];after_cut=[0];max_rss=[0,0]
        def health():
            with urlopen(f'http://127.0.0.1:{port}/ground-zero/manifest',timeout=15) as response:return json.load(response)['health']
        def monitor():
            while not stop.wait(.5):
                try:
                    h=health();a=h['transport_accounting'];census_checks[0]+=1
                    if a['created']!=a['total']:errors.append('CENSUS_MISMATCH')
                    if a['missing_streams']:after_cut[0]+=1
                    if h['invalid'] or h['gap_count'] or a['dropped'] or a['retired_incomplete']:errors.append('CONTINUITY')
                    offered=p.offered+churn_offered[0]
                    history.append(dict(seconds=time.monotonic()-started,offered=offered,committed=h['packets'],
                        commit_boot_ns=h['observed_boot_ns'],pending=p.sock.accepted-p.sock.delivered,pending_bytes=p.sock.enqueued_bytes-p.sock.delivered_bytes,
                        writer_uncommitted=h['uncommitted_valid'],writer_cpu_ns=h['writer_cpu_ns'],frames=h['received_frames'],
                        archive_lag=offered-h['packets']))
                    max_rss[0]=max(max_rss[0],rss(os.getpid()));max_rss[1]=max(max_rss[1],rss(proc.pid))
                except Exception as exc:errors.append('MONITOR:'+repr(exc))
        def churner():
            for i in range(churn):
                if stop.is_set():return
                def one():
                    try:
                        q=CaptureProducer(address,Identity(f'{side}-short-{i}','build',SOURCE,'run','domain','boot'),KEY,
                            end_boot_ns=deadline,status_path=root/f'transport-short-{i}.json',population=population)
                        for n in range(2):
                            if not q.offer('CHURN',{'index':n}):raise AssertionError(q.last_error)
                            churn_offered[0]+=1
                    except Exception as exc:errors.append('CHURN:'+repr(exc))
                t=threading.Thread(target=one);t.start();t.join();time.sleep(.02)
        def pause_writer():
            for delay in (5,15):
                if stop.wait(delay):return
                before=time.monotonic();os.kill(proc.pid,signal.SIGSTOP);time.sleep(.25);os.kill(proc.pid,signal.SIGCONT);stalls.append(time.monotonic()-before)
        last_health=None
        try:
            wait_for(lambda:Path(address).exists() or proc.poll() is not None,10)
            assert Path(address).exists(),'WRITER_START'
            p=CaptureProducer(address,Identity(f'{side}-quote','build',SOURCE,'run','domain','boot'),KEY,end_boot_ns=deadline,
                              status_path=root/'transport-quote.json',population=population)
            for fn in (monitor,churner,pause_writer):
                t=threading.Thread(target=fn,daemon=True);t.start();threads.append(t)
            started=time.monotonic();batch=2250
            for i in range(count):
                if not p.offer('LIFECYCLE_EMISSION',fixture[i%len(fixture)]):raise AssertionError('QUOTE_OFFER:'+str(p.last_error))
                if (i+1)%batch==0:
                    delay=started+(i+1)/rate-time.monotonic()
                    if delay>0:time.sleep(delay)
                if i%100000==0 and errors:raise AssertionError(errors[:3])
            emission_seconds=time.monotonic()-started;quote_stop=time.monotonic();p.close();threads[1].join(180)
            assert not threads[1].is_alive(),'CHURN_TIMEOUT'
            population.close();wait_for(lambda:population.snapshot()['active']==0,30);population.thread.join(3)
            expected=count+2*churn;timeout=time.monotonic()+30
            while True:
                last_health=health();a=last_health['transport_accounting']
                if last_health['packets']==expected and a['complete']:break
                if time.monotonic()>timeout:raise AssertionError('FINAL_RECONCILIATION:'+json.dumps({k:a[k] for k in ['created','total','active','retired','pending','dropped','errors']}))
                time.sleep(.1)
            drain_seconds=time.monotonic()-quote_stop
            (root/'drain.stop').touch();wait_for(lambda:(root/'final_health.json').exists(),10)
            last_health=health();a=last_health['transport_accounting'];stop.set()
            for t in threads:t.join(3)
            assert not errors,errors[:3]
            assert last_health['final_fsync_completed'] and last_health['uncommitted_valid']==0
            all_records=[];offset=0
            while offset is not None:
                with urlopen(f"http://127.0.0.1:{port}/ground-zero/transports?snapshot={a['snapshot_id']}&offset={offset}",timeout=15) as response:page=json.load(response)
                all_records.extend(page['records']);offset=page['next_offset']
            assert len({x['producer_id'] for x in all_records})==a['created']==a['total']==churn+1
            assert all(x['complete'] and x['flushed'] and x['pending_packets']==0 for x in all_records)
            assert a['active']==a['dropped']==a['pending']==a['retired_incomplete']==0
            assert a['retired']==a['retired_flushed']==churn+1
            heads={};rows=0;first_wall=last_wall=None
            for raw in gzip.open(root/'packets.jsonl.gz','rb'):
                event=packet(raw,CONFIG);pid=event['identity']['producer_id'];seq=event['sequence']
                assert seq==heads.get(pid,0)+1 and event['prior_dropped']==0,'ARCHIVE_SEQUENCE'
                heads[pid]=seq;rows+=1
                if pid==f'{side}-quote':
                    first_wall=event['hook_read']['wall_ns'] if first_wall is None else first_wall;last_wall=event['hook_read']['wall_ns']
            assert rows==expected and len(heads)==churn+1
            quote=p.sock.snapshot();assert quote['retry_eagain']>0,'BACKPRESSURE_NOT_EXERCISED'
            assert quote['pending_packets']==quote['producer_dropped']==0 and quote['high_water_bytes']<=16*1024*1024
            assert population.high_water<=16 and max(max_rss)<512*1024,'RESOURCE_BOUND'
            measured=count/emission_seconds;assert measured>=9011,('OFFERED_RATE_TOO_LOW',measured)
            # Stability: recurrent near-empty queue observations throughout the
            # second half, not a one-time drain of accumulated throughput debt.
            steady=[r for r in history if 30<r['seconds']<emission_seconds]
            half=[r for r in steady if r['seconds']>=emission_seconds/2]
            buckets={}
            for r in half:buckets.setdefault(int(r['seconds']//10),[]).append(r['pending'])
            minima=[min(v) for v in buckets.values() if len(v)>=3]
            assert len(minima)>=3 and max(minima)<2250,('BACKLOG_NOT_RECOVERING',minima)
            assert max(r['pending_bytes'] for r in half)<16*1024*1024,'BACKLOG_BOUND'
            slope=(sum(r['pending'] for r in half[-10:])/len(half[-10:])-sum(r['pending'] for r in half[:10])/len(half[:10]))/(half[-1]['seconds']-half[0]['seconds'])
            assert slope<10,('THROUGHPUT_DEBT',slope)
            first=steady[0];last=steady[-1];writer_rate=(last['committed']-first['committed'])/(last['commit_boot_ns']-first['commit_boot_ns'])*1e9
            result=dict(status='PASS',side=side,quote_packets=count,all_packets=rows,emission_seconds=emission_seconds,
                offered_quote_pps=measured,measured_writer_wall_pps=writer_rate,writer_cpu_capacity_pps=rows/(last_health['writer_cpu_ns']/1e9),
                writer_cpu_seconds=last_health['writer_cpu_ns']/1e9,history=history,backlog_slope_pps=slope,late_ten_second_pending_minima=minima,
                maximum_pending=max(r['pending'] for r in history),ending_pending=quote['pending_packets'],
                post_quote_stop_drain_seconds=drain_seconds,quote_transport=quote,
                counters={k:a[k] for k in ['created','total','active','retired','retired_flushed','retired_incomplete','offered','delivered','dropped','retried','pending']},
                unique_individuals=len(all_records),census_checks=census_checks[0],receiver_ahead_of_census_snapshots=after_cut[0],
                sender_high_water=population.high_water,maximum_rss_kib=max_rss,writer_health={k:v for k,v in last_health.items() if k not in ['streams','transport_accounting']},
                receiver_stall_seconds=stalls,final_flush_fsync=True,archive_bytes=(root/'packets.jsonl.gz').stat().st_size)
            (results/f'stress-{side}.json').write_text(json.dumps(result,indent=2));print('PIPELINE_RESULT',json.dumps({k:v for k,v in result.items() if k!='history'}),flush=True)
        except Exception as exc:
            try:last_health=health()
            except Exception:pass
            pop=population.snapshot()
            result=dict(status='FAIL',side=side,error=repr(exc),elapsed_seconds=time.monotonic()-started,
                quote_transport=p.sock.snapshot() if p else None,history=history,
                population={k:v for k,v in pop.items() if k not in ['retired_reports','active_records']},
                writer_health={k:v for k,v in (last_health or {}).items() if k not in ['streams','transport_accounting']},errors=errors[:10])
            (results/f'stress-{side}.json').write_text(json.dumps(result,indent=2));print('PIPELINE_RESULT',json.dumps({k:v for k,v in result.items() if k!='history'}),flush=True);raise
        finally:
            stop.set()
            try:os.kill(proc.pid,signal.SIGCONT)
            except ProcessLookupError:pass
            if p:p.close()
            population.close();population.thread.join(3)
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            proc.wait(timeout=10)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--sustained',choices=['main','v81']);args=parser.parse_args()
    if args.sustained:sustained(args.sustained)
    else:unittest.main(argv=[sys.argv[0]],verbosity=2)
