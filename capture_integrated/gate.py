"""Test-only final gate. Capture candidate and all strategy sources stay fixed."""
from collections import deque
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import urlopen

from capture2.runtime import CaptureProducer, SenderPopulation
from capture2.qualification import LIMITS, admitted_events, qualify, read_state
from capture2.test_writer_pipeline import CONFIG, KEY, SOURCE, end, wait_for, rss
from capture2.writer import packet
from capture_envelope.preflight import rolling_peak
from sprint_evidence.passive_capture import Identity

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = '3685844fcdc5956d8971aa80271ef170ffef30d2'
RESULTS = ROOT/'capture_integrated/results'
PROFILES = {
    # Durations/rates jointly respect ALL five rolling limits, including joins.
    'main': [(0.1,10500),(.15,7500),(.75,2300),(4,1450),(10,1900),(2,1000)],
    'v81': [(.1,3300),(.15,2600),(.75,2200),(4,925),(5,750),(5,950),(2,400)],
}

def run(side, case):
    with tempfile.TemporaryDirectory() as d:
        root=Path(d); address=str(root/'events.sock')
        with socket.socket() as s:
            s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
        config=dict(CONFIG, mode=side, directory=d, socket=address, max_seconds=180,
                    quota_bytes=256*1024*1024, port=port)
        cp=root/'config.json'; cp.write_text(json.dumps(config))
        proc=subprocess.Popen([sys.executable,'-B','-m','capture2.writer','--config',str(cp)],
                              cwd=ROOT,start_new_session=True)
        population=SenderPopulation(root,end(160)); p=None
        stop=threading.Event(); history=[]; monitor_errors=[]; monitor=None
        counters={'offered':0,'quote':0,'churn':0}; children=[]; max_rss=[0,0]
        fixture=json.loads((ROOT/'capture_durability/transport_fixture.json').read_text())
        expected_fault=case!='in-envelope'; injected=False; fault_sequence=None
        started=time.monotonic()
        def health():
            with urlopen(f'http://127.0.0.1:{port}/ground-zero/manifest',timeout=5) as response:
                assert response.status==200
                return json.load(response)['health']
        def observe():
            while not stop.wait(.5):
                try:
                    h=health(); a=h['transport_accounting']
                    assert a['created']==a['total'],'ATOMIC_CENSUS'
                    history.append(dict(seconds=time.monotonic()-started,offered=counters['offered'],
                        committed=h['packets'],pending=p.sock.accepted-p.sock.delivered,aggregate_pending=a['pending'],
                        population_active=a['active'],created=a['created'],retried=a['retried'],
                        accounting_complete_at_cut=a['complete']))
                    max_rss[0]=max(max_rss[0],rss(os.getpid()));max_rss[1]=max(max_rss[1],rss(proc.pid))
                except Exception as exc:monitor_errors.append(repr(exc))
        def churn_pair():
            index=len(children); outcome=[]
            def producer():
                try:
                    q=CaptureProducer(address,Identity(f'{side}-short-{index}','build',SOURCE,'run','domain','boot'),
                        KEY,end_boot_ns=population.end_boot_ns,status_path=root/f'transport-{index}.json',population=population)
                    for n in range(2):
                        assert q.offer('CHURN',dict(index=index,n=n)),q.last_error
                    outcome.append(q)
                except Exception as exc:outcome.append(exc)
            t=threading.Thread(target=producer);t.start();t.join()
            assert len(outcome)==1 and isinstance(outcome[0],CaptureProducer),repr(outcome)
            children.append(outcome[0]);counters['churn']+=2;counters['offered']+=2
        try:
            wait_for(lambda:Path(address).exists(),10)
            p=CaptureProducer(address,Identity(side+'-quote','build',SOURCE,'run','domain','boot'),KEY,
                end_boot_ns=population.end_boot_ns,status_path=root/'transport-quote.json',population=population)
            profiles=(PROFILES[side]*2 if case=='in-envelope' else
                      [(2,6000 if side=='main' else 3500),(1,200)] if case=='over-envelope' else [(2,500),(1,200)])
            monitor=threading.Thread(target=observe,daemon=True);monitor.start();started=time.monotonic()
            # Workload pacing only: never alter candidate timing, queues or sockets.
            # No catch-up burst after a delayed test thread. Offers are in batches
            # of <=10, with a small rolling-budget safety margin for host jitter.
            windows=[(ms,limit-20,deque()) for ms,limit in LIMITS[side]]
            for duration,rate in profiles:
                remaining=round(duration*rate); due=time.monotonic()
                while remaining:
                    n=min(10,remaining)
                    if case=='in-envelope':
                        now=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                        delay=0
                        for ms,limit,queue in windows:
                            while queue and queue[0]<=now-ms*1000000:queue.popleft()
                            if len(queue)+n>limit:
                                delay=max(delay,(queue[len(queue)+n-limit-1]+ms*1000000-now)/1e9+.0001)
                        if delay>0:time.sleep(delay)
                    delay=due-time.monotonic()
                    if delay>0:time.sleep(delay)
                    j=0
                    while j<n:
                        if case=='in-envelope' and n-j>=2 and counters['offered'] and counters['offered']%250==0:
                            churn_pair(); j+=2
                        else:
                            if case=='integrity-failure' and not injected and counters['quote']==500:
                                p.sequence+=1;fault_sequence=p.sequence;injected=True
                            assert p.offer('LIFECYCLE_EMISSION',fixture[counters['quote']%len(fixture)]),p.last_error
                            counters['quote']+=1;counters['offered']+=1;j+=1
                    if case=='in-envelope':
                        # Timestamp AFTER each test batch makes the safety limiter
                        # conservative; archive timestamps independently validate it.
                        stamp=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                        for _,_,queue in windows:queue.extend([stamp]*n)
                    remaining-=n; due=max(due+n/rate,time.monotonic())
            emission_seconds=time.monotonic()-started
            p.close();population.close();wait_for(lambda:population.snapshot()['active']==0,15)
            population.thread.join(3)
            wait_for(lambda:health()['packets']==counters['offered'],15)
            (root/'drain.stop').touch()
            wait_for(lambda:health().get('qualification',{}).get('closed') is True,30)
            stop.set();monitor.join(6)
            assert not monitor_errors,monitor_errors
            h=health();a=h['transport_accounting'];q=h['qualification']
            individuals=[];offset=0
            while offset is not None:
                with urlopen(f"http://127.0.0.1:{port}/ground-zero/transports?snapshot={a['snapshot_id']}&offset={offset}",timeout=5) as response:
                    page=json.load(response)
                assert page['snapshot_id']==a['snapshot_id'] and page['total']==a['total']
                individuals.extend(page['records']);offset=page['next_offset']
            assert a['created']==a['total']==len({r['producer_id'] for r in individuals})==len(children)+1
            assert a['active']==a['pending']==a['dropped']==a['retired_incomplete']==0
            assert a['retired']==a['retired_flushed']==a['created']
            assert all(r['flushed'] and r['complete'] and r['finished'] and r['pending_packets']==0 for r in individuals)
            assert sum(r['retry_eagain'] for r in individuals)==a['retried']
            assert sum(r['offered'] for r in individuals)==sum(r['accepted'] for r in individuals)==sum(r['delivered'] for r in individuals)==counters['offered']
            assert all(r['high_water_bytes']<=r['max_bytes'] and r['high_water_packets']<=r['max_packets'] for r in individuals)
            assert population.high_water<=16
            assert h['final_fsync_completed'] and not h['uncommitted_valid'] and not h['invalid']
            heads={};times=[];events={};gaps=[];rows=0
            for raw in gzip.open(root/'packets.jsonl.gz','rb'):
                e=packet(raw,config);pid=e['identity']['producer_id'];seq=e['sequence']
                if seq!=heads.get(pid,0)+1:gaps.append(dict(stream_id=pid,expected=heads.get(pid,0)+1,received=seq))
                heads[pid]=seq;rows+=1
                assert e['prior_dropped']==0
                t=e['hook_read']['before_boot_ns'];times.append(t)
                events[(pid,seq)]=(t,e['hook_read']['wall_ns'],e['identity']['source_sha256'])
            assert rows==counters['offered']==h['packets']==h['received_valid']
            assert heads==h['streams']
            times.sort();peaks=[dict(window_ms=ms,limit=limit,measured=rolling_peak(times,ms*1000000)) for ms,limit in LIMITS[side]]
            expected_state='UNQUALIFIED' if expected_fault else 'QUALIFIED'
            assert q['qualification_state']==expected_state,q
            if case=='integrity-failure':
                assert injected and len(gaps)==h['gap_count']==1 and h['missing_packets']==1
                assert gaps[0]['expected']==fault_sequence
                assert 'SEQUENCE_GAP' in q['reason_codes'],q
            else:
                assert not gaps and h['gap_count']==h['missing_packets']==0
                assert a['complete'] and not a['errors']
            if case=='over-envelope':
                assert any(x['measured']>x['limit'] for x in peaks)
                reason=next(r for r in q['reasons'] if r['code']=='RATE_ENVELOPE_EXCEEDED')
                t,wall,source=events[(reason['stream_id'],reason['detail']['sequence'])]
                assert (reason['boot_ns'],reason['wall_ns'],reason['source'])==(t,wall,source)
                assert reason['measured']==reason['limit']+1
                actual=sum(t-reason['window_ms']*1000000<x<=t for x in times)
                assert actual==reason['measured']
                assert times[-1]-reason['boot_ns']>1_000_000_000,'CLEAN_TAIL_MISSING'
            else:assert all(x['measured']<=x['limit'] for x in peaks),peaks
            before=(root/'packets.jsonl.gz').read_bytes();admission={}
            first_reasons=json.loads(json.dumps(q['reasons']))
            if expected_fault:
                assert qualify(root,config)['qualification_state']=='UNQUALIFIED'
                assert read_state(root,config)['reasons']==first_reasons,'LATCH_WITNESS_CHANGED'
            for ladder in ('EARLY','FINAL','SCALP'):
                if expected_fault:
                    try:list(admitted_events(root,config,ladder))
                    except ValueError as exc:
                        assert str(exc)=='EVIDENCE_NOT_QUALIFIED:UNQUALIFIED'
                        admission[ladder]='REFUSED_UNQUALIFIED'
                    else:raise AssertionError('UNQUALIFIED_ADMISSION')
                else:
                    assert sum(1 for _ in admitted_events(root,config,ladder))==rows
                    admission[ladder]='ADMITTED_INTEGRITY_ONLY'
            assert (root/'packets.jsonl.gz').read_bytes()==before
            # Observe recovery during the run as well as at final shutdown.
            recovery=[x for x in history if x['seconds']>5 and x['pending']==0]
            if case=='in-envelope':
                assert len(children)>64 and len(recovery)>=3,'CHURN_OR_RECOVERY_NOT_EXERCISED'
                assert max(max_rss)<512*1024,'RESOURCE_RSS_BOUND'
            result=dict(status='PASS',case=case,side=side,counters=counters,emission_seconds=emission_seconds,
                offered_pps=counters['offered']/emission_seconds,peak_windows=peaks,packet_rows=rows,gaps=gaps,
                qualification=q,scoring_admission=admission,archive_sha256=hashlib.sha256(before).hexdigest(),
                diagnostics_unchanged=True,clean_tail_and_sticky_requalification=expected_fault,
                aggregate={k:v for k,v in a.items() if k!='populations'},individual_records=individuals,
                sender_high_water=population.high_water,maximum_sender_backlog_packets=max(r['high_water_packets'] for r in individuals),
                maximum_sender_backlog_bytes=max(r['high_water_bytes'] for r in individuals),
                maximum_sampled_aggregate_pending=max((x['aggregate_pending'] for x in history),default=0),
                ending_backlog_packets=a['pending'],backpressure_wait_ns=sum(r['backpressure_wait_ns'] for r in individuals),
                maximum_rss_kib=max_rss,history=history,recovery_zero_backlog_observations=len(recovery),
                final_fsync=h['final_fsync_completed'],writer_elapsed_seconds=h['elapsed_seconds'],
                writer_average_with_startup_flush_pps=rows/h['elapsed_seconds'],
                writer_batch_high_water_packets=h['pending_batch_high_water_packets'])
            return result
        except Exception as exc:
            result=dict(status='FAIL',case=case,side=side,error=repr(exc),counters=counters,
                history=history,transport=p.sock.snapshot() if p else None,population=population.snapshot())
            try:result['health']=health()
            except Exception:pass
            (RESULTS/f'failure-{side}-{case}.json').write_text(json.dumps(result,indent=2))
            raise
        finally:
            stop.set()
            if monitor:monitor.join(6)
            if p:p.close()
            population.close();population.thread.join(3)
            os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=10)

if __name__=='__main__':
    RESULTS.mkdir(parents=True,exist_ok=True)
    result=dict(candidate=CANDIDATE,test_commit=os.environ.get('GITHUB_SHA'),status='PASS',runs=[],live=False)
    try:
        payload=(ROOT/'capture2_payload.json').read_bytes()
        assert hashlib.sha256(payload).hexdigest()=='aa69df06d0d0a2c8b441ca1b4bd2d647906acd6d3737e44d1d65bc845cdae359'
        for name,source in json.loads(payload).items():assert (ROOT/name).read_bytes()==source.encode(),name
        result['exact_payload_preserved']=True
        for side,case in [('main','in-envelope'),('v81','in-envelope'),('main','over-envelope'),('v81','over-envelope'),('main','integrity-failure')]:
            value=run(side,case)
            (RESULTS/f'{side}-{case}.json').write_text(json.dumps(value,indent=2))
            compact={k:v for k,v in value.items() if k not in ('individual_records','history')}
            result['runs'].append(compact)
            print('CASE_RESULT',json.dumps(compact),flush=True)
    except Exception as exc:result.update(status='FAIL',error=repr(exc))
    (RESULTS/'summary.json').write_text(json.dumps(result,indent=2))
    print('FINAL_RESULT',json.dumps(result),flush=True)
    sys.exit(0 if result['status']=='PASS' else 1)
