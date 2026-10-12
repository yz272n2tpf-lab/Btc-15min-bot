"""Hermetic wrapper for focused tests/replay. Denies network and production paths."""
import os,sys,socket,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ALLOWED=(ROOT,Path('/tmp'))

def guard(event,args):
    if event in ('socket.connect','socket.bind','socket.getaddrinfo','subprocess.Popen','os.system'):
        raise RuntimeError('OFFLINE_NETWORK_OR_PROCESS_DENIED:'+event)
    if event=='open':
        name,mode,flags=args
        if isinstance(name,(str,bytes,os.PathLike)):
            p=Path(os.fsdecode(name)).resolve()
            if str(p).startswith('/data/') or p==Path('/data'):
                raise RuntimeError('PRODUCTION_PATH_DENIED')
            writing=bool((isinstance(mode,str) and any(v in mode for v in 'wax+')) or
                         (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)))
            if writing and not any(p.is_relative_to(a) for a in ALLOWED):
                raise RuntimeError('WRITE_OUTSIDE_ISOLATED_WORKSPACE_DENIED:'+str(p))

sys.addaudithook(guard)
if __name__=='__main__':
    command=sys.argv[1:];sys.argv=command
    if not command:raise SystemExit('Specify module and arguments')
    runpy.run_module(command[0],run_name='__main__',alter_sys=True)
