"""Assembled process-tree qualification, synthetic sources, no upstream access."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from btc15_information_install_v1 import assemble,replace_once,terminate_group


def proc_stats():
    records={}
    for d in Path('/proc').iterdir():
        if not d.name.isdigit():continue
        try:
            raw=(d/'stat').read_text();parts=raw[raw.rfind(')')+2:].split()
            command=(d/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            records[int(d.name)]=dict(ppid=int(parts[1]),cpu=(int(parts[11])+int(parts[12]))/os.sysconf('SC_CLK_TCK'),
                                     rss=int(parts[21])*os.sysconf('SC_PAGE_SIZE'),command=command,state=parts[0])
        except (OSError,ValueError,IndexError):pass
    return records


def descendants(records,pid):
    selected={pid}
    while True:
        more={p for p,r in records.items() if r['ppid'] in selected}
        if more<=selected:return selected
        selected|=more


def scenario(name,enabled,events,clients,duration=35,cpus=1):
    with tempfile.TemporaryDirectory(prefix='btc15-topology-') as temp:
        d=Path(temp);build=assemble(d/'build');data=d/'data';data.mkdir()
        output=d/'native.json';log=d/'process.log'
        # External effects only: dedicated synthetic clock/data root, and native
        # network/file adapters. Production modules contain no test switch.
        (d/'sitecustomize.py').write_text(
            'import os,time\nfrom pathlib import Path\n'
            'base=float(os.environ["BTC15_TEST_MONO"])\n'
            'time.time=lambda:1577837100.+time.monotonic()-base\n'
            'import btc15_data_paths_v1 as paths\n'
            'paths._btc15_data_root=lambda **kwargs:Path(os.environ["BTC15_TEST_DATA"])\n')
        for name2 in ('btc15_final_position_protection_shadow_v3.py','btc15_qualified_forward_observer_v1.py',
                      'btc15_kalshi_parity_shadow_v1.py'):
            (d/name2).symlink_to(ROOT/name2)
        replace_once(build/'btc15_run_with_rescue_v2_shadow_v1.py',
            repr(str(ROOT/'btc15_information_native_v1.py')),repr(str(ROOT/'completion_audit/information_runtime_fixture.py')))
        runner=d/'run.py'
        runner.write_text('from pathlib import Path\nimport btc15_information_install_v1 as install\n'
                          f'install.ROOT=Path({str(d)!r})\n'
                          f'raise SystemExit(install.supervise(Path({str(build)!r}),Path({str(ROOT/"btc15_information_worker_v1.py")!r})))\n'
                          if enabled else
                          f'import os,sys\nos.execv(sys.executable,[sys.executable,"-u",{str(build/"BTC15_RUN_FULL_VALIDATION_WITH_DASHBOARD_V1.py")!r}])\n')
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        env=dict(os.environ,PYTHONPATH=str(d)+os.pathsep+str(ROOT),PORT=str(port),
                 BTC15_TEST_MONO=str(time.monotonic()),BTC15_TEST_DATA=str(data),BTC15_TEST_OUTPUT=str(output),
                 BTC15_TEST_INFORMATION='1' if enabled else '0',BTC15_TEST_PROOF_EVENTS=str(events),
                 OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        affinity=sorted(os.sched_getaffinity(0))[:cpus]
        stream=log.open('w')
        p=subprocess.Popen([sys.executable,'-u',str(runner)],cwd=d,env=env,start_new_session=True,
                           stdout=stream,stderr=stream,preexec_fn=lambda:os.sched_setaffinity(0,set(affinity)))
        halt=threading.Event();counts={};latencies=[];samples=[];peak=0;seen={};cpu_first={};cpu_last={};native=None
        display_events=[]
        def client(i):
            while not halt.is_set():
                start=time.monotonic()
                try:
                    path='/information' if i%4 else '/dashboard_state.json'
                    with urlopen(f'http://127.0.0.1:{port}'+path,timeout=1) as r:value=json.loads(r.read())
                    status=value.get('status','NATIVE')
                    if path=='/information' and status=='AVAILABLE':
                        assert value['authority']=='INFORMATIONAL_READ_ONLY' and value['orders'] is False
                        assert 0<=value['checked_ts']-value['brti_source_ts']<=5
                    counts[status]=counts.get(status,0)+1
                    latencies.append(time.monotonic()-start)
                    if i==1:
                        received=time.monotonic();until=received
                        if status=='AVAILABLE':
                            remaining=min(value['display_until'],value['expires_at'],value['brti_source_ts']+5)-value['checked_ts']-(received-start)
                            until=received+max(0,remaining)
                        display_events.append((received,until))
                except Exception:
                    counts['unavailable_transport']=counts.get('unavailable_transport',0)+1
                    if i==1:display_events.append((time.monotonic(),0))
                halt.wait(.1 if clients>4 else .5)
        threads=[threading.Thread(target=client,args=(i,),daemon=True) for i in range(clients)]
        try:
            deadline=time.monotonic()+20
            while not output.exists() and time.monotonic()<deadline:
                if p.poll() is not None:raise RuntimeError(log.read_text()[-8000:])
                time.sleep(.1)
            if not output.exists():raise RuntimeError('Native startup failed: '+log.read_text()[-8000:])
            for t in threads:t.start()
            begin=time.monotonic();deadline=begin+duration
            while time.monotonic()<deadline:
                allp=proc_stats();ids=descendants(allp,p.pid)
                # Child process groups are still descendants while root is alive.
                records={i:allp[i] for i in ids if i in allp}
                peak=max(peak,sum(v['rss'] for v in records.values()))
                for i,v in records.items():
                    seen[i]=v['command'];cpu_first.setdefault(i,v['cpu']);cpu_last[i]=v['cpu']
                samples.append(len(records));time.sleep(.1)
            native=json.loads(output.read_text())
            # 10ms time grid for ONE actual viewer, charging full HTTP RTT and
            # clearing on errors; request-success counts are not availability.
            info_available=action_available=0
            for n in range(int(duration*100)):
                at=begin+n*.01
                reads=[event for event in display_events if event[0]<=at]
                if reads and at<reads[-1][1]:info_available+=1
                ticks=[t for t in native['ticks'] if t['published_monotonic']<=at]
                if ticks:
                    t=ticks[-1];until=t['source_qualified_until']
                    if until and t['published_clock']+(at-t['published_monotonic'])<=until:action_available+=1
            # Worker restart must not terminate/restart the native process tree.
            if enabled:
                workers=[pid for pid,cmd in seen.items() if 'btc15_information_worker_v1.py' in cmd]
                assert len(workers)==1,(workers,seen)
                os.kill(workers[0],signal.SIGKILL)
                restart_deadline=time.monotonic()+8;new_worker=None
                while time.monotonic()<restart_deadline:
                    allp=proc_stats();ids=descendants(allp,p.pid)
                    new_worker=next((i for i in ids if i!=workers[0] and 'btc15_information_worker_v1.py' in allp.get(i,{}).get('command','')),None)
                    if new_worker:break
                    time.sleep(.1)
                assert new_worker is not None,'Worker did not restart'
                assert json.loads(output.read_text())['pid']==native['pid'],'Native owner restarted'
            authority=sorted({Path(cmd.split()[-1]).name for cmd in seen.values()})
            result=dict(name=name,duration_s=duration,cpus=affinity,clients=clients,proof_events=events,
                        peak_tree_rss_mib=peak/1024**2,mean_cpu_cores=sum(cpu_last[i]-v for i,v in cpu_first.items())/duration,
                        max_processes=max(samples),processes=authority,http_counts=counts,
                        information_display_availability_pct=info_available/int(duration*100)*100,
                        native_source_qualified_availability_pct=action_available/int(duration*100)*100,
                        availability_grid_s=.01,availability_viewer=1,
                        http_p95_s=sorted(latencies)[int(.95*(len(latencies)-1))] if latencies else None,
                        native=native,worker_restart_pass=enabled)
        finally:
            halt.set()
            for t in threads:
                if t.ident:t.join(2)
            terminate_group(p,8);stream.close()
            # The installed root creates distinct worker/core process groups.
            orphans=[]
            for pid,cmd in seen.items():
                if pid==p.pid:continue
                try:
                    if proc_stats().get(pid,{}).get('state') not in (None,'Z'):
                        orphans.append(pid)
                        os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:pass
        result['shutdown_clean']=not orphans
        result['process_log_tail']=log.read_text()[-3000:]
        return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--duration',type=float,default=35);args=parser.parse_args()
    scenarios=[]
    for name,on,events,clients,cpus in [('baseline',False,2,4,1),('normal',True,2,4,1),
                                     ('single_cpu_stress',True,2000,24,1),('two_cpu_stress',True,2000,24,2),
                                     ('near_bound_proof_stress',True,7000,24,2)]:
        result=scenario(name,on,events,clients,args.duration,cpus);scenarios.append(result)
        args.output.write_text(json.dumps(dict(schema='BTC15_INFORMATION_TOPOLOGY_QUALIFICATION_V1',
            scope='Offline assembled production tree; native network and disk effects adapted; synthetic January 2020 sources',
            scenarios=scenarios),indent=2)+'\n')
        print(name,json.dumps({k:v for k,v in result.items() if k not in ('native','process_log_tail','processes')}),flush=True)
    assert all(s['shutdown_clean'] for s in scenarios),'Orphan process after shutdown'
    assert all(not s['native']['errors'] for s in scenarios),'Source fixture failed'
    assert all(s['native']['native_inputs'] and s['native']['native_records'] for s in scenarios),'Native assessment never executed'
    assert all(len(s['native']['ticks'])>=6 for s in scenarios),'Native loop starved'
    assert all(max(t['lateness_s'] for t in s['native']['ticks'])<.5 for s in scenarios),'Native scheduling gate >500ms'
    assert all(s['peak_tree_rss_mib']<2048 for s in scenarios),'Tree exceeds 2GiB stress budget'
    assert scenarios[1]['http_counts'].get('AVAILABLE',0)>0,'No qualified information through installed topology'


if __name__=='__main__':main()
