"""Focused hosted recovery gates; never reruns the preserved 257-test suite."""
from pathlib import Path
import hashlib,json,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'hosted_recovery';out.mkdir(exist_ok=True)
sources=json.loads((ROOT/'sprint_evidence/qualification_sources.json').read_text())
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in sources.items())
(out/'identity.json').write_text(json.dumps(dict(git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),sources=sources,prior_pass_run=36621151007,prior_tests_not_rerun=257),indent=2)+'\n')
results=[]
for name,args in [
    ('new_snapshot_tests',['-m','unittest','sprint_evidence.test_monitor_snapshot','-v']),
    ('new_snapshot_transport',['-m','sprint_evidence.recovery_smoke','--output',str(out/'snapshot_transport.json')]),
]:
    result=subprocess.run([sys.executable,'-B',*args],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
    (out/(name+'.log')).write_bytes(result.stdout)
    results.append(dict(name=name,returncode=result.returncode,sha256=hashlib.sha256(result.stdout).hexdigest()))
    print(name,result.returncode,flush=True)
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
raise SystemExit(0 if all(r['returncode']==0 for r in results) else 1)
