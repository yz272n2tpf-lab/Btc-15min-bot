"""Explicit opt-in composition. Existing source files and strategy expressions stay fixed."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

from sprint_evidence.passive_capture import instrument_native, instrument_protected, digest
from sprint_evidence.source_witness_capture import instrument_native as source_tree, NATIVE_SHA
from sprint_evidence.v81_capture import instrument as v81_tree, SOURCE_SHA256 as V81_SHA, DIRECT_SOURCE_PINS
from sprint_evidence.quote_receive_capture import SOURCE_SHA256 as QUOTE_SHA

ROOT=Path(__file__).resolve().parents[1]
PROTECTED_SHA='66cdbaa21daa848f261e87e1528dce5a0cadd700fe3be22567f664f968f6d1b7'


def add_imports(tree, text):
    pos=1 if tree.body and isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant) else 0
    tree.body[pos:pos]=ast.parse(text).body
    return ast.fix_missing_locations(tree)


def main_tree(raw):
    tree=instrument_native(raw,NATIVE_SHA)
    witnesses=source_tree(raw)
    selected=next(n for n in witnesses.body if isinstance(n,ast.FunctionDef) and n.name=='_latest_brti')
    for i,n in enumerate(tree.body):
        if isinstance(n,ast.FunctionDef) and n.name=='_latest_brti':tree.body[i]=selected
    return add_imports(tree,'from capture2.runtime import native_producer as _sprint_producer, sources_tap as _sprint_sources')


def native():
    from capture2.runtime import install_quotes
    install_quotes()
    import btc15_information_native_offpath_candidate as original
    base=original.instrument
    def composed(tree):
        raw=original.BOT.read_bytes()
        if ast.dump(tree)!=ast.dump(ast.parse(raw)):raise ValueError('NATIVE_INPUT_TREE_CHANGED')
        return base(main_tree(raw))
    original.instrument=composed
    sys.argv=[sys.argv[0]]
    return original.main()


def route(tree):
    found=0
    for n in ast.walk(tree):
        if isinstance(n,ast.FunctionDef) and n.name=='do_GET':
            n.body[:0]=ast.parse('from capture2.runtime import serve\nif serve(self):\n    return').body;found+=1
    if found!=1:raise ValueError('HTTP_SEAM')
    return ast.fix_missing_locations(tree)


def assemble_main(directory):
    import btc15_information_install_v1 as original
    d=original.assemble(directory)
    protected=d/'BTC15_DASHBOARD_STATE_V2.py';raw=protected.read_bytes()
    tree=instrument_protected(raw,PROTECTED_SHA)
    add_imports(tree,'from capture2.runtime import Proxy\n_sprint_producer = Proxy('+repr(PROTECTED_SHA)+')')
    protected.write_text(ast.unparse(tree)+'\n')
    server=d/'BTC15_DASHBOARD_LIVE_SERVER_V1.py';server.write_text(ast.unparse(route(ast.parse(server.read_bytes())))+'\n')
    wrapper=d/'btc15_run_with_rescue_v2_shadow_v1.py'
    old=repr(str(ROOT/'btc15_information_native_offpath_candidate.py'))
    text=wrapper.read_text()
    if text.count(old)!=1:raise ValueError('NATIVE_LAUNCH_PATH')
    wrapper.write_text(text.replace(old,repr(str(ROOT/'capture2/native_entry.py'))))
    return d


def begin(mode):
    build=os.environ.get('RAILWAY_GIT_COMMIT_SHA')
    if not build:raise ValueError('EXACT_BUILD_REQUIRED')
    run_id='ground-zero-'+mode+'-'+uuid.uuid4().hex
    root=Path('/data' if mode=='main' else tempfile.gettempdir())/'btc15_ground_zero'/run_id
    root.mkdir(parents=True,exist_ok=False)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    ns=os.readlink('/proc/self/ns/time')
    c=dict(mode=mode,build=build,run_id=run_id,directory=str(root),socket=str(Path(tempfile.gettempdir())/('gz-'+uuid.uuid4().hex[:16]+'.sock')),
           key=os.urandom(32).hex(),boot_id=boot,time_namespace_id=ns,clock_domain=boot+'/'+ns,
           source_hashes=[NATIVE_SHA,PROTECTED_SHA,QUOTE_SHA,V81_SHA],max_seconds=2100,
           end_boot_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME)+2100*1000000000,
           quota_bytes=512*1024*1024,port=8769,signal_only=True,orders=False,
           native_strategy_commit='abe212b513827c8cec28a2f64e0161e79296bd82' if mode=='main' else 'b05723ec622f901a05402ecf27f4d33505753ef1')
    config=root/'config.json';config.write_text(json.dumps(c));config.chmod(0o600)
    os.environ['BTC15_CAPTURE_CONFIG']=str(config)
    child=subprocess.Popen([sys.executable,'-B','-m','capture2.writer','--config',str(config)],cwd=ROOT)
    deadline=time.monotonic()+5
    while not Path(c['socket']).exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.02)
    if not Path(c['socket']).exists():raise RuntimeError('CAPTURE_WRITER_NOT_READY')
    print('GROUND_ZERO_CAPTURE | '+json.dumps({k:v for k,v in c.items() if k!='key'}),flush=True)
    return child


def v81():
    from capture2.runtime import install_quotes,producer
    from sprint_evidence.v81_capture import V81Capture
    for name,expected in DIRECT_SOURCE_PINS.items():
        if digest((ROOT/name).read_bytes())!=expected:raise ValueError('V81_SOURCE_CHANGED:'+name)
    install_quotes()
    class Tap:
        def publication(self,*args):
            try:return V81Capture(producer(V81_SHA)).publication(*args)
            except Exception:return False
        def evaluation(self,*args):
            try:return V81Capture(producer(V81_SHA)).evaluation(*args)
            except Exception:return False
    path=ROOT/'v81_30_45_live_feed.py'
    namespace=dict(__name__='__main__',__file__=str(path),_sprint_v81=Tap())
    exec(compile(route(v81_tree(path.read_bytes())),str(path),'exec'),namespace)


def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['main','v81'],required=True);p.add_argument('--approved-capture-only',action='store_true',required=True)
    args=p.parse_args()
    if Path.cwd()!=ROOT:raise ValueError('ORIGINAL_CWD_REQUIRED')
    if args.mode=='main':
        d=assemble_main(Path(tempfile.gettempdir())/'btc15_ground_zero_assembly')
    child=begin(args.mode)
    try:
        if args.mode=='v81':return v81()
        import btc15_information_install_v1 as original
        return original.supervise(d)
    finally:
        child.terminate();child.wait(timeout=5)


if __name__=='__main__':raise SystemExit(main())
