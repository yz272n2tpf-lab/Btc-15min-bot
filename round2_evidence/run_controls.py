"""Run preserved test modules in separate processes; no test/policy rewrites."""
import argparse,hashlib,json,os,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--python',required=True);p.add_argument('--output',required=True);p.add_argument('--support');p.add_argument('--only',nargs='*');p.add_argument('--timeout',type=int,default=180);a=p.parse_args()
root=Path(__file__).resolve().parents[1];out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
base=Path(a.support).resolve() if a.support else root
files=sorted((base/'completion_audit').glob('test_*.py')) if a.support else sorted(root.glob('test_*.py'))
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
if a.support:env['PYTHONPATH']=str(base/'completion_audit')+os.pathsep+str(base)
if a.only:files=[f for f in files if f.stem in a.only]
results=[]
for f in files:
    module=f.stem;cmd=([a.python,'-B','-m','unittest',module,'-v'] if 'import unittest' in f.read_text() else [a.python,'-B',str(f)]);start=time.monotonic()
    try:
        r=subprocess.run(cmd,cwd=base,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=a.timeout)
        data=r.stdout;code=r.returncode;status='PASS' if code==0 else 'FAIL'
    except subprocess.TimeoutExpired as exc:data=exc.stdout or b'';code=None;status='TIMEOUT'
    name=module+'.log';(out/name).write_bytes(data)
    results.append(dict(module=module,command=cmd,cwd=str(base),returncode=code,status=status,elapsed_seconds=round(time.monotonic()-start,3),log=name,log_sha256=hashlib.sha256(data).hexdigest()))
    (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(module,status,flush=True)
raise SystemExit(any(r['status']!='PASS' for r in results))
