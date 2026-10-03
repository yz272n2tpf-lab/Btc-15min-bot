    root=Path('/data' if mode=='main' else tempfile.gettempdir())/'btc15_ground_zero'/run_id
    root.mkdir(parents=True,exist_ok=False)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    ns=os.readlink('/proc/self/ns/time')
    c=dict(mode=mode,build=build,run_id=run_id,directory=str(root),socket=str(Path(tempfile.gettempdir())/('gz-'+uuid.uuid4().hex[:16]+'.sock')),
           key=os.urandom(32).hex(),boot_id=boot,time_namespace_id=ns,clock_domain=boot+'/'+ns,
           source_hashes=[NATIVE_SHA,PROTECTED_SHA,QUOTE_SHA,V81_SHA,WRAPPER_SHA,PROTECTION_SHA],max_seconds=min(2100,remaining),
           capture_files={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted((ROOT/'capture2').glob('*.py'))},
           end_boot_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME)+int(min(2100,remaining)*1000000000),
           quota_bytes=1024*1024*1024,port=8769,signal_only=True,orders=False,
           native_strategy_commit='abe212b513827c8cec28a2f64e0161e79296bd82' if mode=='main' else 'b05723ec622f901a05402ecf27f4d33505753ef1')
    config=root/'config.json';config.write_text(json.dumps(c));config.chmod(0o600)
    os.environ['BTC15_CAPTURE_CONFIG']=str(config)
    child=subprocess.Popen([sys.executable,'-B','-m','capture2.writer','--config',str(config)],cwd=ROOT)
    deadline=time.monotonic()+5
    while not Path(c['socket']).exists() and child.poll() is None and time.monotonic()<deadline:time.sleep(.02)
    if not Path(c['socket']).exists():
        child.terminate();child.wait(timeout=5)
        raise RuntimeError('CAPTURE_WRITER_NOT_READY')
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
    try:child=begin(args.mode)
    except Exception as exc:
        print('GROUND_ZERO_CAPTURE_UNAVAILABLE | '+type(exc).__name__+': '+str(exc)+' | original strategy launcher retained',flush=True)
        if args.mode=='v81':return runpy.run_path(str(ROOT/'v81_30_45_live_feed.py'),run_name='__main__')
        import btc15_information_install_v1 as original
        return original.supervise(original.assemble())
    try:
        if args.mode=='v81':return v81()
        import btc15_information_install_v1 as original
        return original.supervise(d)
    finally:
        child.terminate();child.wait(timeout=5)


if __name__=='__main__':raise SystemExit(main())