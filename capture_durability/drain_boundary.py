"""Isolate only the demonstrated AF_UNIX backpressure boundary, no strategy."""
import json,multiprocessing as mp,os,socket,select,tempfile,time
from pathlib import Path

def receiver(address,count,ready):
    s=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);s.bind(address);ready.set()
    for _ in range(count):s.recv(196609)
    s.close()

def bench(mode,count=100000):
    with tempfile.TemporaryDirectory() as d:
        address=d+'/s';ready=mp.Event();p=mp.Process(target=receiver,args=(address,count,ready));p.start();assert ready.wait(3)
        s=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);s.setblocking(False);s.connect(address)
        raw=b'x'*1665;sent=retries=0;start=time.monotonic()
        while sent<count:
            try:s.send(raw);sent+=1
            except BlockingIOError:
                retries+=1
                if mode=='fixed_1ms':time.sleep(.001)
                else:select.select([],[s],[],.05)
        elapsed=time.monotonic()-start;s.close();p.join(5);assert p.exitcode==0
        return dict(mode=mode,packets=sent,bytes_per_packet=len(raw),seconds=elapsed,pps=sent/elapsed,retries=retries)
if __name__=='__main__':
    results=[bench('fixed_1ms'),bench('receiver_readiness')]
    Path('capture_durability/results/drain-boundary.json').write_text(json.dumps(results,indent=2))
    print('DRAIN_BOUNDARY',json.dumps(results),flush=True)
