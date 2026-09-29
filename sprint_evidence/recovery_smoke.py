"""Only new monitoring-snapshot transport integration; synthetic, nonproduction."""
import json
import multiprocessing as mp
from pathlib import Path
import socket
import sqlite3
import tempfile
import threading
import time
from .capture_smoke import IDENTITY, summary
from .monitor_snapshot import SnapshotReceiver, read
from .passive_capture import Producer, MAX_PACKET, add_event_store
from round2_evidence.capture import initialize, DetachedRecorder
from round2_evidence.test_round2 import artifact
from test_btc15_external_evidence_admission_v1 import POLICY, KEY
from test_btc15_directional_signal_authority_v1 import fixture


def worker(address, archive, snapshot, receipts, ready, done):
    receiver=SnapshotReceiver(archive,[IDENTITY],{(IDENTITY.producer_id,IDENTITY.run_id):KEY},
        common_recorder=DetachedRecorder(archive,POLICY,acquisition_key=KEY),snapshot_path=snapshot)
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);sock.bind(address);sock.settimeout(5)
    ready.set(); results=[];durations=[]
    try:
        for _ in range(25):
            raw,_,flags,_=sock.recvmsg(MAX_PACKET)
            assert not flags & socket.MSG_TRUNC
            start=time.perf_counter_ns();results.append(receiver.accept(raw));durations.append(time.perf_counter_ns()-start)
        Path(receipts).write_text(json.dumps(dict(receipts=results,consumer_work=summary(durations))))
        done.set()
    finally:sock.close()


def smoke():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);archive=root/'archive.sqlite';snapshot=root/'monitor.json'
        address=str(root/'socket');receipts=root/'receipts.json'
        initialize(archive,POLICY);add_event_store(archive)
        ready=mp.Event();done=mp.Event()
        process=mp.Process(target=worker,args=(address,str(archive),str(snapshot),str(receipts),ready,done));process.start()
        stop=threading.Event();monitor=dict(reads=0,errors=[])
        def inspect_snapshot():
            while not stop.is_set():
                try:read(snapshot);monitor['reads']+=1
                except FileNotFoundError:pass
                except Exception as exc:
                    if len(monitor['errors'])<10:monitor['errors'].append(str(exc))
                stop.wait(.001)
        thread=threading.Thread(target=inspect_snapshot)
        producer=None
        try:
            assert ready.wait(5),'RECEIVER_NOT_READY'
            thread.start();producer=Producer(address,IDENTITY,KEY)
            states=[]
            for i in range(12):
                state=fixture(300+i*5,final_ready=i%2==0);states.append(state)
                assert producer.protected(state,{});assert producer.published(state)
                time.sleep(.01) # synthetic driver pacing; no producer ACK
            member=artifact()[0];assert producer.common_member(member,0)
            assert done.wait(5),'RECEIVER_INCOMPLETE'
            process.join(5);assert process.exitcode==0
            evidence=json.loads(receipts.read_text())
            assert len(evidence['receipts'])==25
            assert all(r['status']=='RECORDED_UNQUALIFIED_CLOCK' for r in evidence['receipts']),evidence
            assert monitor['reads']>0 and not monitor['errors'],monitor
            assert producer.dropped==0
            with sqlite3.connect(archive) as db:
                rows=db.execute('SELECT raw FROM producer_events ORDER BY seq').fetchall()
                assert db.execute('SELECT original FROM members').fetchone()[0]==member
            events=[json.loads(row[0])['event'] for row in rows]
            assert len(events)==25
            for i in range(12):
                assert events[2*i]['body']['state']==states[i]
                assert events[2*i]['body']['generation_id']==events[2*i+1]['body']['generation_id']
            return dict(status='PASS_NEW_SNAPSHOT_TRANSPORT_ONLY',events=25,
                generations=12,exact_members=1,drops=0,concurrent_monitor=monitor,
                **evidence,clock_admission='UNAVAILABLE',production_deployed=False)
        finally:
            stop.set()
            if thread.ident is not None:thread.join(5)
            if producer is not None:producer.close()
            if process.is_alive():process.terminate();process.join(5)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    result=smoke();Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='receipts'}))
