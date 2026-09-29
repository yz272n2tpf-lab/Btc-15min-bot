"""Short hosted NONPRODUCTION socket/storage/timing smoke. Synthetic evidence.

No feed/network/source polls or strategy actions. Requires real local Unix IPC
and exact frozen runtime tests separately. It never qualifies the host's clocks.
"""
import argparse
from dataclasses import asdict
import json
import multiprocessing
import os
from pathlib import Path
import socket
import sqlite3
import statistics
import tempfile
import time

from .passive_capture import Producer,Receiver,Identity,add_event_store,MAX_PACKET
from round2_evidence.capture import initialize,DetachedRecorder
from round2_evidence.test_round2 import artifact
from test_btc15_external_evidence_admission_v1 import POLICY,KEY
from test_btc15_directional_signal_authority_v1 import fixture

IDENTITY=Identity('HOSTED_SYNTHETIC_PRODUCER','HOSTED_SYNTHETIC_BUILD','a'*64,'HOSTED_SYNTHETIC_RUN','UNQUALIFIED_HOST_CLOCK','UNQUALIFIED_BOOT')

class Discard:
    def sendto(self,data,*args):return len(data)
    def close(self):pass


def worker(address,path,ready,stop):
    receiver=Receiver(path,[IDENTITY],{(IDENTITY.producer_id,IDENTITY.run_id):KEY},common_recorder=DetachedRecorder(path,POLICY,acquisition_key=KEY))
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);sock.bind(address);sock.settimeout(.1)
    ready.set()
    try:
        while not stop.is_set():
            try:raw,_,flags,_=sock.recvmsg(MAX_PACKET)
            except socket.timeout:continue
            if not flags & socket.MSG_TRUNC:receiver.accept(raw)
    finally:sock.close()


def summary(values):
    values=sorted(values)
    return dict(n=len(values),minimum_us=values[0]/1000,median_us=statistics.median(values)/1000,
                p99_us=values[min(len(values)-1,int(len(values)*.99))]/1000,maximum_us=values[-1]/1000)


def benchmark():
    p=Producer('discard',IDENTITY,KEY,sock=Discard())
    runs={}
    for name,body in [('small',{'synthetic':True}),('near_text_cap',{'payload':'x'*130000}),
                      ('near_node_cap',{'values':[1]*4000})]:
        vals=[]
        for _ in range(200):
            start=time.perf_counter_ns();ok=p.offer('NATIVE_CYCLE',body);vals.append(time.perf_counter_ns()-start)
            if not ok:raise AssertionError(p.last_error)
        runs[name]=summary(vals)
    protected=[];state=fixture(300)
    for _ in range(100):
        start=time.perf_counter_ns();assert p.protected(state,{});assert p.published(state)
        protected.append(time.perf_counter_ns()-start)
    runs['protected_generation_plus_write_link']=summary(protected)
    return dict(encoding_hmac_copy_only_no_kernel_delivery=runs,
        hard_real_time_bound_proven=False,native_scheduler_modified=False,
        scheduler_475_boundary='KNOWN_NEGATIVE: any positive added hook time can displace next cycle at min sleep',
        added_upstream_requests=0,added_native_fsync=0,producer_send_attempts_per_event=1)


def smoke():
    result=dict(schema='BTC15_SPRINT_CAPTURE_SMOKE_V1',mode='NONPRODUCTION_SYNTHETIC',clock_admission='UNAVAILABLE_NOT_CERTIFIED',
                performance_claim=False,benchmark=benchmark())
    try:
        probe=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);probe.close()
    except PermissionError as exc:
        result.update(status='UNAVAILABLE_SOCKET_PERMISSION',reason=str(exc),separate_process_exercised=False)
        return result
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);path=root/'unified.sqlite';address=str(root/'events.sock')
        initialize(path,POLICY);add_event_store(path)
        ready=multiprocessing.Event();stop=multiprocessing.Event()
        worker_process=multiprocessing.Process(target=worker,args=(address,str(path),ready,stop));worker_process.start()
        if not ready.wait(5):raise RuntimeError('RECEIVER_NOT_READY')
        p=Producer(address,IDENTITY,KEY);timings=[];states=[]
        for i in range(12):
            state=fixture(300+i*5,final_ready=i%2==0,final_side='UP' if i<6 else 'DOWN');states.append(state)
            at=time.perf_counter_ns();assert p.protected(state,{});assert p.published(state);timings.append(time.perf_counter_ns()-at)
            # Test driver pacing only; never inside producer/hook and no ACK.
            time.sleep(.01)
        member=artifact()[0];assert p.common_member(member,0)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            with sqlite3.connect(path) as db:
                count=db.execute('SELECT COUNT(*) FROM producer_events').fetchone()[0]
                members=db.execute('SELECT COUNT(*) FROM members').fetchone()[0]
            if count==25 and members==1:break
            time.sleep(.01)
        stop.set();worker_process.join(5)
        if worker_process.is_alive():worker_process.terminate();worker_process.join();raise RuntimeError('RECEIVER_DID_NOT_STOP')
        with sqlite3.connect(path) as db:
            original=db.execute('SELECT original FROM members').fetchone()[0]
            rows=db.execute('SELECT raw FROM producer_events ORDER BY seq').fetchall()
        events=[json.loads(r[0])['event'] for r in rows]
        assert len(events)==25 and original==member and p.dropped==0
        assert all(events[2*i]['body']['state']==states[i] for i in range(12))
        assert all(events[2*i]['body']['generation_id']==events[2*i+1]['body']['generation_id'] for i in range(12))
        result.update(status='PASS_ACQUISITION_SMOKE_ONLY',separate_process_exercised=True,
                      producer_pid=os.getpid(),consumer_pid=worker_process.pid,events=25,exact_original_members=1,
                      reconstructed_protected_generations=12,explicit_generation_file_write_links=12,
                      dropped=p.dropped,actual_send_plus_encode_pair=summary(timings),immutable_archive_bytes=path.stat().st_size)
        p.close()
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--require-socket',action='store_true')
    args=parser.parse_args();result=smoke();Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))
    if args.require_socket and result['status']!='PASS_ACQUISITION_SMOKE_ONLY':raise SystemExit(1)

if __name__=='__main__':main()
