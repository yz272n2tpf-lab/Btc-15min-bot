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
    for directory, _, names in os.walk(root):
        for name in names:
            path=Path(directory)/name
            try: files.append((path.stat().st_size,str(path.relative_to(root))))
            except OSError: pass
    disk=shutil.disk_usage(root)
    return dict(schema='BTC15_PRODUCTION_STORAGE_R1',at=time.time(),
                used_bytes=disk.used,free_bytes=disk.free,total_bytes=disk.total,
                file_bytes=sum(size for size,_ in files),file_count=len(files),
                largest=sorted(files,reverse=True)[:12],signal_only=True,orders=False)


def supervise(directory):
    from .release import ROOT
    from btc15_information_install_v1 import terminate_group
    env=os.environ.copy()
    env['PYTHONPATH']=str(ROOT)+os.pathsep+env.get('PYTHONPATH','')
    reader={k:v for k,v in env.items() if not k.startswith(('KALSHI_','BTC15_BRTI_'))}
    commands={
        'native':([sys.executable,'-u',str(ROOT/'btc15_v2_native.py')],env),
        'dashboard':([sys.executable,'-u',str(directory/'BTC15_DASHBOARD_LIVE_SERVER_V1.py')],reader),
        'information':([sys.executable,'-u','-m','btc15_v2_product.worker'],reader),
    }
    processes={}
    stopping=threading.Event()
    previous={s:signal.signal(s,lambda *_:stopping.set()) for s in (signal.SIGINT,signal.SIGTERM)}
    def inventory():
        while not stopping.is_set():
            try: print('BTC15 PRODUCTION STORAGE | '+json.dumps(storage_snapshot(),separators=(',',':')),flush=True)
            except OSError as exc: print('BTC15 STORAGE INSPECTION | '+type(exc).__name__,flush=True)
            stopping.wait(300)
    threading.Thread(target=inventory,daemon=True,name='storage-inventory').start()
    try:
        for name,(argv,child_env) in commands.items():
            processes[name]=subprocess.Popen(argv,cwd=ROOT,env=child_env,start_new_session=True)
        print('BTC15 PRODUCTION OWNERS | native,dashboard,information | legacy collectors disabled | NO ORDERS',flush=True)
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
        for process in processes.values():
            try: os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError: pass
        for process in processes.values(): terminate_group(process)
        for sig,handler in previous.items(): signal.signal(sig,handler)
