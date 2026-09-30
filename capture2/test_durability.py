"""Narrow capture transport qualification, never a strategy/event proof."""
import argparse
from collections import Counter
import gzip
import hashlib
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

from capture2.runtime import CaptureProducer,SenderPopulation
from capture2.writer import Accounting
from capture2.test_repairs import HeldSocket,identity,wait_for,ROOT,NATIVE_SHA


class PollableHeld(HeldSocket):
    def connect(self,address):pass


class DurabilityTests(unittest.TestCase):
    def test_readiness_retry_retirement_and_durable_rejection_reason(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pop=SenderPopulation(root,time.clock_gettime_ns(time.CLOCK_BOOTTIME)+10_000_000_000)
            sink=PollableHeld();seen=[]
            def poll(r,w,e,timeout):time.sleep(.001);return [],w if sink.ready else [],[]
            with patch('capture2.runtime.select.select',side_effect=poll):
                def offer():
                    p=CaptureProducer('x',identity('short'),b'a'*32,sock=sink,population=pop,
                        end_boot_ns=pop.end_boot_ns,status_path=root/'transport-short.json',max_packets=2)
                    seen.append(p)
                    assert p.offer('OBSERVED',{'index':0})
                    assert p.offer('OBSERVED',{'index':1})
                    assert not p.offer('OBSERVED',{'index':2})
                t=threading.Thread(target=offer);t.start();t.join();p=seen[0]
                wait_for(lambda:p.sock.retries>0);sink.ready=True
                wait_for(lambda:pop.retired==1)
            pop.close();pop.thread.join(3)
            s=p.sock.snapshot();self.assertEqual(s['rejected_full'],1);self.assertEqual(s['first_rejection']['sequence'],3)
            self.assertEqual(s['pending_packets'],0);self.assertGreater(s['backpressure_wait_ns'],0)
            self.assertEqual([json.loads(r)['event']['sequence'] for r in sink.raw],[1,2])
            a=Accounting(root).capture({'short':2});self.assertEqual((a['created'],a['total'],a['retired']),(1,1,1))
            self.assertFalse(a['complete']);self.assertIn('STREAM_LOSS_OR_TRANSPORT_ERROR',a['errors'])

    def test_atomic_census_excludes_later_files_and_marks_new_receiver_streams(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            s=dict(producer_id='one',process_id=1,finished=False,complete=False,offered=1,delivered=1,
                   producer_dropped=0,rejected=0,last_transport_error=None,retry_eagain=0,pending_packets=0)
            p=dict(process_id=1,created=1,active=1,retired=0,retired_flushed=0,retired_incomplete=0,
                   fault=None,admission_rejected=0,census_version=1,active_records=[s],retired_reports=[])
            (root/'population-1.json').write_text(json.dumps(p))
            (root/'transport-newer.json').write_text(json.dumps(dict(s,producer_id='newer')))
            a=Accounting(root);cut=a.capture({'one':1})
            self.assertTrue(cut['complete'],cut['errors']);self.assertEqual((cut['created'],cut['total']),(1,1))
            ahead=a.capture({'one':1,'newer':1});self.assertFalse(ahead['complete'])
            self.assertEqual(ahead['missing_streams'],['newer']);self.assertEqual((ahead['created'],ahead['total']),(1,1))
            s['producer_dropped']=1;p['active_records']=[s];(root/'population-1.json').write_text(json.dumps(p))
            loss=a.capture({'one':1});self.assertFalse(loss['complete']);self.assertEqual(loss['lossy_streams'],['one'])


def sustained(side,count=1500000,rate=9000,churn=5000):
    """1.5M authentic envelopes, 9k/s target versus retained 8,757/s peak.

    2,250-record bursts every .25s exceed retained 2,156/100ms where CPU allows.
    If generator is slower, measured rates are emitted, not claimed. A separate
    producer churns 5k streams. Receiver is suspended twice for 0.25s to exercise
    bounded pending data; capture accounting/chunk reads compete with recording.
    """
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);address=str(root/'events.sock');port_sock=socket.socket();port_sock.bind(('127.0.0.1',0));port=port_sock.getsockname()[1];port_sock.close()
        config=dict(directory=d,socket=address,key=(b'a'*32).hex(),run_id='run',build='build',
                    source_hashes=[NATIVE_SHA],max_seconds=900,quota_bytes=1024*1024*1024,port=port)
        cp=root/'config.json';cp.write_text(json.dumps(config));proc=subprocess.Popen([sys.executable,'-B','-m','capture2.writer','--config',str(cp)],cwd=ROOT)
        end=time.clock_gettime_ns(time.CLOCK_BOOTTIME)+850_000_000_000
        pop=SenderPopulation(root,end);errors=[];stop=threading.Event();poll_counts=Counter();stalls=[]
        fixture=json.loads((ROOT/'capture_durability/transport_fixture.json').read_text())
        from urllib.request import urlopen
        def poller():
            while not stop.wait(.5):
                try:
                    with urlopen(f'http://127.0.0.1:{port}/ground-zero/manifest',timeout=20) as r:h=json.load(r)['health']
                    a=h['transport_accounting'];poll_counts['snapshots']+=1
                    if a['created']!=a['total']:errors.append('AGGREGATE_MISMATCH')
                    if a['errors']:poll_counts.update(a['errors'])
                    if h['gap_count'] or h['invalid'] or a['dropped']:errors.append('LIVE_LOSS')
                except Exception as exc:errors.append('POLL:'+repr(exc))
        def churner():
            for i in range(churn):
                if stop.is_set():return
                def one():
                    try:
                        p=CaptureProducer(address,identity(f'{side}-short-{i}'),b'a'*32,end_boot_ns=end,
                                          population=pop,status_path=root/f'transport-short-{i}.json')
                        for n in range(2):
                            if not p.offer('CHURN',{'index':n}):raise AssertionError(p.last_error)
                    except Exception as exc:errors.append('CHURN:'+repr(exc))
                t=threading.Thread(target=one);t.start();t.join()
                time.sleep(.02)
        def pause_receiver():
            for delay in (5,15):
                if stop.wait(delay):return
                before=time.monotonic();os.kill(proc.pid,signal.SIGSTOP);time.sleep(.25);os.kill(proc.pid,signal.SIGCONT);stalls.append(time.monotonic()-before)
        p=None;threads=[];started=time.monotonic();bins=Counter()
        try:
            wait_for(lambda:Path(address).exists() or proc.poll() is not None,10)
            if not Path(address).exists():raise AssertionError('WRITER_START')
            p=CaptureProducer(address,identity(f'{side}-quote'),b'a'*32,end_boot_ns=end,population=pop,status_path=root/'transport-quote.json')
            for fn in (poller,churner,pause_receiver):
                t=threading.Thread(target=fn,daemon=True);t.start();threads.append(t)
            started=time.monotonic();batch=2250
            for i in range(count):
                if not p.offer('LIFECYCLE_EMISSION',fixture[i%len(fixture)]):raise AssertionError('QUOTE_OFFER:'+str(p.last_error))
                bins[int((time.monotonic()-started)*10)]+=1
                if (i+1)%batch==0:
                    due=started+(i+1)/rate;delay=due-time.monotonic()
                    if delay>0:time.sleep(delay)
                if i%100000==0 and errors:raise AssertionError(errors[:5])
            emitted=time.monotonic()-started;p.close();threads[1].join(180)
            if threads[1].is_alive():raise AssertionError('CHURN_TIMEOUT')
            wait_for(lambda:pop.snapshot()['active']==0,30);pop.close();pop.thread.join(3)
            wait_for(lambda:p.sock.snapshot()['pending_packets']==0,30)
            expected=count+2*churn
            deadline=time.monotonic()+30
            while True:
                with urlopen(f'http://127.0.0.1:{port}/ground-zero/manifest',timeout=20) as r:m=json.load(r)
                h=m['health'];a=h['transport_accounting']
                if h['packets']==expected and a['complete']:break
                if time.monotonic()>=deadline:raise AssertionError({'health':h,'errors':errors})
                time.sleep(.1)
            stop.set()
            for t in threads:t.join(3)
            if errors:raise AssertionError(errors[:10])
            heads={};rows=0;archive_hash=hashlib.sha256();compressed=root/'packets.jsonl.gz'
            # Sender population is closed; archive byte cut contains complete gzip members.
            with compressed.open('rb') as f:
                for raw in iter(lambda:f.read(1024*1024),b''):archive_hash.update(raw)
            for raw in gzip.open(compressed,'rb'):
                event=json.loads(raw)['event'];pid=event['identity']['producer_id'];seq=event['sequence']
                if seq!=heads.get(pid,0)+1 or event['prior_dropped']:raise AssertionError('ARCHIVE_CONTINUITY')
                heads[pid]=seq;rows+=1
            assert rows==expected and len(heads)==churn+1,(rows,len(heads))
            assert (a['created'],a['total'],a['active'],a['retired'])==(churn+1,churn+1,0,churn+1),a
            assert a['dropped']==a['pending']==h['gap_count']==h['invalid']==0
            quote=p.sock.snapshot();assert quote['retry_eagain']>0 and quote['backpressure_wait_ns']>0
            assert quote['high_water_bytes']<=quote['max_bytes'] and pop.high_water<=16
            result=dict(side=side,status='PASS',quote_packets=count,all_packets=rows,emission_seconds=emitted,
                        elapsed_seconds=time.monotonic()-started,mean_pps=count/emitted,max_100ms=max(bins.values()),
                        max_dgram_qlen=Path('/proc/sys/net/unix/max_dgram_qlen').read_text().strip(),
                        quote_transport=quote,accounting=a,polls=dict(poll_counts),receiver_stall_seconds=stalls,
                        sender_high_water=pop.high_water,python_maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                        archive_bytes=compressed.stat().st_size,archive_sha256=archive_hash.hexdigest())
            (ROOT/f'capture_durability/results/stress-{side}.json').write_text(json.dumps(result,indent=2))
            print('SUSTAINED_RESULT',json.dumps(result),flush=True)
        except Exception as exc:
            result=dict(side=side,status='FAIL',error=repr(exc),elapsed_seconds=time.monotonic()-started,
                        quote_transport=p.sock.snapshot() if p else None,population=pop.snapshot(),errors=errors[:20])
            (ROOT/f'capture_durability/results/stress-{side}.json').write_text(json.dumps(result,indent=2))
            print('SUSTAINED_RESULT',json.dumps(result),flush=True);raise
        finally:
            stop.set()
            try:os.kill(proc.pid,signal.SIGCONT)
            except ProcessLookupError:pass
            if p:p.close()
            pop.close();pop.thread.join(3);proc.terminate();proc.wait(timeout=10)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--sustained',choices=['main','v81']);args=parser.parse_args()
    if args.sustained:sustained(args.sustained)
    else:unittest.main(argv=[sys.argv[0]],verbosity=2)
