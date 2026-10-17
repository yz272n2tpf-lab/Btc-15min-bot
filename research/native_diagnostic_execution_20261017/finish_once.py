"""Authorized health preservation and ONE invocation of the existing finisher."""
import base64,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from research.native_operational_20261017 import probe

RUN='DIAG_20261017_e2294683_f7c32d04'
CONFIG=Path('/research-evidence/approved')/RUN/'campaign.json'
OUT=Path('/research-evidence')/(RUN+'-reader')
RECEIPTS=Path('/research-evidence')/('native-diagnostic-execution-'+RUN)
DEPLOYMENTS={'main':'9fb6061a-7ed3-4ed6-a18a-32c4b74edc9c','v81':'1b5183a4-fca3-411f-9846-0a6ab860d283'}
REMOTE=r'''
import hashlib,json,os,pathlib,sys,time
p=json.load(sys.stdin);c=p['config'];lane=p['lane'];r=c['roles'][lane]
expected={'RAILWAY_PROJECT_ID':'baea4e22-d004-4434-b2c5-81a7fbc05086','RAILWAY_ENVIRONMENT_ID':'61775c5d-c583-4dfc-af41-f25578856fd9','RAILWAY_SERVICE_ID':r['service'],'RAILWAY_VOLUME_ID':r['volume'],'RAILWAY_VOLUME_MOUNT_PATH':'/data','RAILWAY_GIT_COMMIT_SHA':r['build'],'RAILWAY_DEPLOYMENT_ID':p['deployment']}
assert all(os.environ.get(k)==v for k,v in expected.items()),'CANDIDATE_IDENTITY'
v=os.statvfs('/data');answer={'identity':expected,'at':time.time(),'available_bytes':v.f_bavail*v.f_frsize,'roles':{},'recording_enabled':os.environ.get('BTC15_RECORDING_ENABLED')}
for role in (['main','information'] if lane=='main' else ['v81']):
 root=pathlib.Path(c['root'])/role;assert not root.is_symlink(),'ROLE_SYMLINK';files={}
 for name in ('identity.json','health.json','terminal-status.json','seal.json'):
  f=root/name
  if not f.exists():files[name]={'missing':True};continue
  assert not f.is_symlink() and f.stat().st_size<=1048576,'RECEIPT_PATH_OR_SIZE'
  b=f.read_bytes();files[name]={'sha256':hashlib.sha256(b).hexdigest(),'value':json.loads(b)}
 answer['roles'][role]=files
print('BTC15_DIAG_NATIVE_HEALTH '+json.dumps(answer,sort_keys=True))
'''

def emit(path):
    if not path.is_file() or path.is_symlink():return
    data=path.read_bytes()
    if len(data)>524288:raise RuntimeError('REPORT_OUTPUT_BOUND:'+path.name)
    parts=[data[i:i+3072] for i in range(0,len(data),3072)]
    for i,part in enumerate(parts):
        print('BTC15_DIAG_ARTIFACT '+json.dumps(dict(path=str(path),sha256=hashlib.sha256(data).hexdigest(),part=i,parts=len(parts),data=base64.b64encode(part).decode()),sort_keys=True),flush=True)

def main():
    probe.check_local();assert os.environ.get('RAILWAY_GIT_COMMIT_SHA')=='950e4b5e401d501bb26b5a66473e06500e8c08ac'
    raw=CONFIG.read_bytes();assert hashlib.sha256(raw).hexdigest()=='12b17ac651578d3325fadbc39fd340e9e6dc700d769c9ff5d6678e004d191949'
    c=json.loads(raw);plan=json.loads(Path('/app/research/native_operational_20261017/NATIVE_READ_PLAN.json').read_bytes())
    assert not OUT.exists(),'FINISH_ALREADY_ATTEMPTED'
    os.umask(0o077);marker=RECEIPTS/'finish-invocation.json'
    with marker.open('x') as f:json.dump(dict(at=time.time(),run_id=RUN,finisher_invocations=1),f);f.flush();os.fsync(f.fileno())
    probe.REMOTE=REMOTE
    for lane in ('main','v81'):
        r=subprocess.run(probe.command(plan[lane]['domain']),input=json.dumps(dict(config=c,lane=lane,deployment=DEPLOYMENTS[lane])),text=True,capture_output=True,timeout=30)
        if r.returncode:raise RuntimeError(lane+':HEALTH_IDENTITY_OR_ACCESS:'+r.stderr[-1500:])
        assert len(r.stdout.encode())<=2*1024**2,'HEALTH_BOUND'
        rows=[s.split(' ',1)[1] for s in r.stdout.splitlines() if s.startswith('BTC15_DIAG_NATIVE_HEALTH ')];assert len(rows)==1
        answer=json.loads(rows[0]);target=RECEIPTS/(lane+'-native-health.json')
        with target.open('x') as f:json.dump(answer,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        emit(target)
    # Existing implementation owns stop, bounded drain/transfer and serial reader.
    r=subprocess.run([sys.executable,'-B','-m','ops.live_recording.finish','--config',str(CONFIG),'--output',str(OUT)],capture_output=True,text=True,timeout=420)
    for name,text in [('finisher-stdout.txt',r.stdout),('finisher-stderr.txt',r.stderr)]:
        with (RECEIPTS/name).open('x') as f:f.write(text);f.flush();os.fsync(f.fileno())
    print('BTC15_DIAG_FINISH_PROCESS '+json.dumps(dict(returncode=r.returncode,stdout=r.stdout[-4000:],stderr=r.stderr[-2000:]),sort_keys=True),flush=True)
    for name in ('attempt-1.json','quality.json','DELIVERY.json','native-preflight-measurements.json','reader-1/verification/summary.json'):
        emit(OUT/name)
    assert r.returncode==0,'FINISH_PROCESS_FAILED'

try:main()
except Exception as e:
    print('BTC15_DIAG_EXECUTION_FAILURE '+json.dumps(dict(type=type(e).__name__,reason=str(e)[:2000],run_id=RUN)),flush=True)
    raise
