"""Production process ownership: native MAIN, dashboard and information only.

The retired validation/rescue/parity collectors are not trading authorities.
Their historical files remain untouched. No orders or source-clock changes.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time


def storage_snapshot(root=Path('/data')):
    """Read-only inventory; never prune, truncate, migrate or archive evidence."""
    files=[]
    directories={}
    for directory, _, names in os.walk(root):
        for name in names:
            path=Path(directory)/name
            try:
                relative=path.relative_to(root)
                size=path.stat().st_size
                files.append((size,str(relative)))
                group=relative.parts[0] if len(relative.parts)>1 else '(root files)'
                directories[group]=directories.get(group,0)+size
            except OSError: pass
    disk=shutil.disk_usage(root)
    return dict(schema='BTC15_PRODUCTION_STORAGE_R1',at=time.time(),
                used_bytes=disk.used,free_bytes=disk.free,total_bytes=disk.total,
                file_bytes=sum(size for size,_ in files),file_count=len(files),
                largest=sorted(files,reverse=True)[:24],
                directories=sorted(((v,k) for k,v in directories.items()),reverse=True)[:12],
                capacity_status=('CRITICAL' if disk.free < 512*1024**2 else
                                 'ARCHIVE_APPROVAL_NEEDED' if disk.free < 2*1024**3 else 'OK'),
                retention='PRESERVE_ALL_EXISTING_EVIDENCE; COMPRESS_NEW_INFORMATION_ONLY',
                signal_only=True,orders=False)


def process_snapshot(processes):
    """Only owned process identities and volume write descriptors; no env/argv."""
    out=[]
    for name,process in processes.items():
        paths=[]
        for fd in Path('/proc',str(process.pid),'fd').glob('*'):
            try:
                target=os.readlink(fd)
                if not target.startswith('/data/'):continue
                info=Path('/proc',str(process.pid),'fdinfo',fd.name).read_text()
                flags=next(int(line.split()[1],8) for line in info.splitlines() if line.startswith('flags:'))
                if flags & os.O_ACCMODE in (os.O_WRONLY,os.O_RDWR):paths.append(target)
            except (OSError,StopIteration,ValueError):pass
        out.append(dict(owner=name,pid=process.pid,alive=process.poll() is None,
                        open_volume_writes=sorted(set(paths))))
    return out


def supervise(directory):
    from .release import ROOT
    from btc15_information_install_v1 import terminate_group
    env=os.environ.copy()
    env['PYTHONPATH']=str(ROOT)+os.pathsep+env.get('PYTHONPATH','')
    reader={k:v for k,v in env.items() if not k.startswith(('KALSHI_','BTC15_BRTI_'))}
    # Existing evidence is immutable. Only newly generated information uses
    # lossless segments; native journals, settlement and strategy writes stay put.
    reader['BTC15_INFORMATION_COMPRESS_NEW']='1'
    commands={
        'native':([sys.executable,'-u',str(ROOT/'btc15_v2_native.py')],env),
        'dashboard':([sys.executable,'-u',str(directory/'BTC15_DASHBOARD_LIVE_SERVER_V1.py')],reader),
        'information':([sys.executable,'-u','-m','btc15_v2_product.worker'],reader),
    }
    processes={}
    maintenance=None
    stopping=threading.Event()
    previous={s:signal.signal(s,lambda *_:stopping.set()) for s in (signal.SIGINT,signal.SIGTERM)}
    def inventory():
        while not stopping.is_set():
            try:
                snapshot=storage_snapshot()
                snapshot['processes']=process_snapshot(processes)
                print('BTC15 PRODUCTION STORAGE | '+json.dumps(snapshot,separators=(',',':')),flush=True)
            except OSError as exc: print('BTC15 STORAGE INSPECTION | '+type(exc).__name__,flush=True)
            stopping.wait(300)
    try:
        for name,(argv,child_env) in commands.items():
            processes[name]=subprocess.Popen(argv,cwd=ROOT,env=child_env,start_new_session=True)
        threading.Thread(target=inventory,daemon=True,name='storage-inventory').start()
        print('BTC15 PRODUCTION OWNERS | native,dashboard,information | legacy collectors disabled | NO ORDERS',flush=True)
        # One nonessential, low-priority process; its failure cannot restart MAIN.
        # A durable attempt marker prevents repeats, including after an abort.
        if env.get('BTC15_ARCHIVE_LEGACY_ONCE')=='20261009':
            try:
                reader['BTC15_ARCHIVE_OWNED_PIDS']=','.join(str(p.pid) for p in processes.values())
                maintenance=subprocess.Popen([sys.executable,'-u','-m','btc15_information_archive_once'],
                    cwd=ROOT,env=reader,start_new_session=True)
            except OSError as exc:
                print('BTC15 ARCHIVE | START_ABORTED | '+type(exc).__name__,flush=True)
        while not stopping.wait(.5):
            for name,process in processes.items():
                code=process.poll()
                if code is not None:
                    # Restart as a single owned tree. A dead dashboard cannot
                    # leave Railway reporting a functioning public application.
                    print('BTC15 PRODUCTION CHILD EXIT | '+name+' | '+str(code),flush=True)
                    return code or 1
        return 0
    finally:
        stopping.set()
        if maintenance is not None:
            try: os.killpg(maintenance.pid,signal.SIGTERM)
            except ProcessLookupError: pass
        for process in processes.values():
            try: os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError: pass
        for process in processes.values(): terminate_group(process)
        if maintenance is not None: terminate_group(maintenance)
        for sig,handler in previous.items(): signal.signal(sig,handler)
