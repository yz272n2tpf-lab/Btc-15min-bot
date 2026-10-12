"""One fresh exact-release local target; exercise installed verifier then rollback.
No native launcher, release-guard bypass, service, subscription or source process.
"""
from pathlib import Path
import json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ops.recording_workflow.staging import make_target,install,rollback,allowlist
from ops.recording_workflow.evidence import file_sha
from ops.recording_workflow.policy import config
from candidates.early_recording_20261012.archive import canonical
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
target=out/'target';baseline=make_target(target);installed=install(target)
plan=json.loads((target/'LOCAL_RECORDING_OVERLAY/plan.json').read_bytes())
(out/'ALLOWLIST.json').write_bytes(canonical(plan))
start=time.time()
def child(name,args):
 result=subprocess.run([sys.executable,'-B',*args],cwd=target,capture_output=True,text=True,timeout=45)
 (out/(name+'.txt')).write_text(result.stdout+result.stderr)
 if result.returncode:raise AssertionError(name+': '+result.stderr[-2000:])
 return result
cfg=out/'disabled.json';cfg.write_bytes(canonical(config(out/'never-created')))
child('INSTALLED_PREFLIGHT',['-m','ops.recording_workflow.operator','preflight','--config',str(cfg)])
# Fixture generator is a test harness; its relative imports resolve to INSTALLED
# modules. Its full source and hash accompany this audit, not a runtime override.
script="""import importlib.util,sys,socket
from unittest.mock import patch
from pathlib import Path
p=Path.cwd()
import ops.recording_workflow.whole_run as v
assert Path(v.__file__).resolve().is_relative_to(p)
spec=importlib.util.spec_from_file_location('ops.recording_workflow.test_whole_run',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with patch('socket.socket.connect',side_effect=AssertionError('NETWORK_FORBIDDEN')):
 m.fixture(sys.argv[2])
"""
child('INSTALLED_FIXTURE',['-c',script,str(ROOT/'ops/recording_workflow/test_whole_run.py'),str(out/'fixture')])
limits=out/'limits.json';limits.write_bytes(canonical(dict(partition_bytes=8192,record_bytes=8192)))
child('INSTALLED_FINALIZE',['-m','ops.recording_workflow.operator','finalize','--root',str(out/'fixture/run'),'--output',str(out/'finalized'),'--limits',str(limits)])
quality=json.loads((out/'finalized/report/quality.json').read_bytes());whole=quality['mechanics']['whole_run']
assert quality['fixture_complete'] and whole['partitions']>1 and whole['metrics']['cross_partition_associations']>0
assert not quality['complete_evidence'] and not quality['cost_verified'] and quality['long_test']=='NO_GO'
child('INSTALLED_PACKAGE',['-m','ops.recording_workflow.operator','package','--root',str(out/'fixture/run'),'--finalized',str(out/'finalized'),'--store',str(out/'private-store')])
pkg=json.loads((out/'INSTALLED_PACKAGE.txt').read_text())
child('SEPARATE_READER',['-m','ops.recording_workflow.operator','restore','--manifest',pkg['manifest'],'--sha256',pkg['sha256'],'--output',str(out/'reader')])
child('SEPARATE_READER_REPORT',['-m','ops.recording_workflow.operator','finalize','--root',str(out/'reader'),'--output',str(out/'reader-finalized'),'--limits',str(limits)])
rq=json.loads((out/'reader-finalized/report/quality.json').read_bytes());assert rq['fixture_complete']
# Overlay and untouched release drift are both rejected before rollback mutation.
for name in ('ops/recording_workflow/whole_run.py','requirements.txt'):
 p=target/name;old=p.read_bytes();p.write_bytes(old+b'\n# LOCAL TEST DRIFT\n')
 try:rollback(target)
 except ValueError as exc:assert 'DRIFT' in str(exc)
 else:raise AssertionError('DRIFT_ACCEPTED')
 p.write_bytes(old)
reverted=rollback(target)
assert reverted['original_files']==878
assert not (out/'never-created').exists()
result=dict(status='VERIFIED',fixture_only=True,release=baseline['release'],original_release_files=878,overlay_files=len(plan),allowlist_sha256=file_sha(out/'ALLOWLIST.json'),
 candidate_modules={r['path']:r['after'] for r in plan},installed_whole_run=whole,
 reader_fixture_complete=rq['fixture_complete'],rollback=reverted,drift_rejections=['overlay','untouched_release'],capture_default_off=True,services_started=0,subscriptions=0,
 fixture_generator_sha256=file_sha(ROOT/'ops/recording_workflow/test_whole_run.py'),seconds=time.time()-start,completed_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat())
(out/'RESULTS.json').write_bytes(canonical(result));print(json.dumps(result))
