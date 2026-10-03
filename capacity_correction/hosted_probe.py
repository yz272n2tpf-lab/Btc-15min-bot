"""Focused real-socket bursts above every measured Oct 3 V8.1 rolling peak."""
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
import time
from urllib.request import urlopen

from capture2.runtime import CaptureProducer,SenderPopulation
from capture2.test_writer_pipeline import CONFIG,KEY,SOURCE,end,wait_for
from capture2.qualification import admitted_events,LIMITS
from capture2.writer import packet
from sprint_evidence.passive_capture import Identity

ROOT=Path(__file__).resolve().parents[1]
MEASURED={100:1773,250:3417,1000:5232,5000:11492,10000:17420}

def peak(times,width):
    left=value=0
    for right,t in enumerate(times):
        while times[left]<=t-width:left+=1
        value=max(value,right-left+1)
    return value

def run(side):
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);address=str(root/'events.sock')
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        c=dict(CONFIG,mode=side,directory=d,socket=address,max_seconds=60,quota_bytes=3*1024**3,port=port)
        cp=root/'config.json';cp.write_text(json.dumps(c))
        child=subprocess.Popen([sys.executable,'-B','-m','capture2.writer','--config',str(cp)],cwd=ROOT,start_new_session=True)
        population=SenderPopulation(root,end(55));producer=None
        def health():
            with urlopen(f'http://127.0.0.1:{port}/ground-zero/manifest',timeout=5) as r:return json.load(r)['health']
        try:
            wait_for(lambda:Path(address).exists(),10)
            producer=CaptureProducer(address,Identity(side+'-quote','build',SOURCE,'run','domain','boot'),KEY,
                end_boot_ns=population.end_boot_ns,status_path=root/'transport.json',population=population)
            fixture=json.loads((ROOT/'capacity_correction/fixture.json').read_text())
            start=time.monotonic();count=0
            # 3 x 6,000-packet episodes: 2,000/100 ms; 4,000/250 ms;
            # 6,000/1 s; 12,000/5 s; 18,000/10 s. No sampled evidence.
            for cycle in (0,4,8):
                for burst in (0,.12,.60):
                    for index in range(2000):
                        target=start+cycle+burst+index*.000045
                        delay=target-time.monotonic()
                        if delay>0:time.sleep(delay)
                        assert producer.offer('LIFECYCLE_EMISSION',fixture[count%len(fixture)]),producer.last_error
                        count+=1
            producer.close();population.close();population.thread.join(5)
            wait_for(lambda:health()['packets']==count,15)
            (root/'drain.stop').touch()
            wait_for(lambda:health().get('qualification',{}).get('closed'),20)
            h=health();a=h['transport_accounting'];q=h['qualification']
            assert q['qualification_state']=='QUALIFIED',q
            assert a['complete'] and not a['errors'] and not a['dropped'],a
            assert h['invalid']==h['gap_count']==h['uncommitted_valid']==0 and h['final_fsync_completed'],h
            times=[]
            with gzip.open(root/'packets.jsonl.gz','rb') as stream:
                for raw in stream:
                    e=packet(raw,c);assert e['sequence']==len(times)+1 and e['prior_dropped']==0
                    times.append(e['hook_read']['before_boot_ns'])
            observed={ms:peak(times,ms*1000000) for ms,_ in LIMITS[side]}
            assert all(observed[ms]>=n for ms,n in MEASURED.items()),('MEASURED_PEAK_NOT_EXERCISED',observed)
            assert all(observed[ms]<=n for ms,n in LIMITS[side]),('NEW_LIMIT_EXCEEDED',observed)
            for ladder in ('EARLY','FINAL','SCALP'):assert sum(1 for _ in admitted_events(root,c,ladder))==count
            return dict(side=side,records=count,qualification=q['qualification_state'],observed_peaks=observed,
                terminal_transport=producer.sock.snapshot(),archive_bytes=h['bytes'],
                gaps=h['gap_count'],invalid=h['invalid'],pending=a['pending'],dropped=a['dropped'])
        finally:
            if producer:producer.close()
            population.close();population.thread.join(3)
            os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=10)

if __name__=='__main__':
    results=[run(side) for side in ('main','v81')]
    result=dict(status='PASS',commit=os.environ.get('GITHUB_SHA'),sides=results,signal_only=True,orders=False)
    (ROOT/'capacity_correction/hosted_result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
