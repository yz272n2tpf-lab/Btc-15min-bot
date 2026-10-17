"""One authorized control-file provisioning operation; not a capture or probe."""
import hashlib, json, os, shlex, subprocess, sys, time
from pathlib import Path
from research.native_operational_20261017 import probe

EXPECTED = 'e5cfbed6bfe35dc43ab45bc2db2530bd00f1c69dd582f7dea8cd5904f6514ccb'
RUN = 'CORRECTED_DIAG_20261017_8847c61b_510da93a'
REMOTE = r'''
import hashlib,importlib.metadata,json,os,pathlib,sys,time
p=json.load(sys.stdin); plan=p['plan']; raw=p['config'].encode()
assert hashlib.sha256(raw).hexdigest()=='e5cfbed6bfe35dc43ab45bc2db2530bd00f1c69dd582f7dea8cd5904f6514ccb','CONFIG_HASH'
assert all(os.environ.get(k)==v for k,v in plan['identity'].items()),'NATIVE_IDENTITY'
mount=pathlib.Path('/data'); assert mount.is_mount() and not mount.is_symlink(),'DATA_MOUNT'
v=os.statvfs('/data'); available=v.f_bavail*v.f_frsize
assert available>=2449473536,'FREE_SPACE_BELOW_APPROVAL_FLOOR'
c=json.loads(raw); root=pathlib.Path(c['root']); target=pathlib.Path('/data/btc15_recordings-control')/c['run_id']
assert not root.exists() and not root.is_symlink() and not target.exists() and not target.is_symlink(),'RUN_ALREADY_EXISTS'
assert not target.parent.is_symlink(),'CONTROL_PARENT_SYMLINK'
if p['operation']=='read':
 for name,expected in plan['files'].items():
  f=pathlib.Path('/app')/name; assert not f.is_symlink() and hashlib.sha256(f.read_bytes()).hexdigest()==expected,'SOURCE_HASH:'+name
 assert all(importlib.metadata.version(k)==v for k,v in plan['dependencies'].items()),'DEPENDENCIES'
elif p['operation']=='provision':
 os.umask(0o077)
 target.parent.mkdir(mode=0o700,exist_ok=True)
 target.mkdir(mode=0o700)
 fd=os.open(target/'campaign.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f: f.write(raw);f.flush();os.fsync(f.fileno())
 for directory in (target,target.parent):
  fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
 assert hashlib.sha256((target/'campaign.json').read_bytes()).hexdigest()==hashlib.sha256(raw).hexdigest(),'WRITTEN_HASH'
else: raise ValueError('OPERATION')
print('BTC15_AUTHORIZED_CONTROL '+json.dumps(dict(operation=p['operation'],available_bytes=available,at=time.time(),identity={k:os.environ.get(k) for k in plan['identity']},config_sha256=hashlib.sha256(raw).hexdigest(),capture_started=False,orders=False),sort_keys=True))
'''

def run():
    available=probe.check_local()
    assert os.environ.get('RAILWAY_GIT_COMMIT_SHA')==os.environ.get('BTC15_APPROVED_RESEARCH_SHA') and len(os.environ.get('BTC15_APPROVED_RESEARCH_SHA',''))==40,'RESEARCH_SOURCE'
    raw=Path('/app/research/targeted_native_telemetry_20261017/campaign.approval-draft.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==EXPECTED
    plan=json.loads(Path('/app/research/targeted_native_telemetry_20261017/NATIVE_READ_PLAN.json').read_bytes())
    out=Path('/research-evidence')/('native-diagnostic-execution-'+RUN)
    os.umask(0o077);out.mkdir(mode=0o700)
    receipt=dict(run_id=RUN,status='INCOMPLETE',at=time.time(),research_free_bytes=available,operations=[],capture_started=False,orders=False)
    def save():
        blob=(json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode()
        fd=os.open(out/'provision.json',os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
    try:
        probe.REMOTE=REMOTE
        # Both reads pass before either producer config write.
        for operation in ('read','provision'):
            for role in ('main','v81'):
                payload=json.dumps(dict(operation=operation,plan=plan[role],config=raw.decode()))
                r=subprocess.run(probe.command(plan[role]['domain']),input=payload,text=True,capture_output=True,timeout=30)
                assert len(r.stdout.encode())<=131072 and len(r.stderr.encode())<=65536,'SSH_OUTPUT_BOUND'
                rows=[x.split(' ',1)[1] for x in r.stdout.splitlines() if x.startswith('BTC15_AUTHORIZED_CONTROL ')]
                if r.returncode or len(rows)!=1:
                    receipt['failed_operation']=dict(role=role,operation=operation,returncode=r.returncode,stderr=r.stderr[-2000:]);save()
                    raise RuntimeError(role+':'+operation+':SSH_OPERATION_FAILED')
                answer=json.loads(rows[0]);receipt['operations'].append(dict(role=role,**answer));save()
                print('BTC15_AUTHORIZED_CONTROL '+json.dumps(dict(role=role,**answer),sort_keys=True),flush=True)
        approved=Path('/research-evidence/approved');assert not approved.is_symlink()
        approved.mkdir(mode=0o700,exist_ok=True);dest=approved/RUN;dest.mkdir(mode=0o700)
        fd=os.open(dest/'campaign.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        for d in (dest,approved):
            fd=os.open(d,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
        receipt['status']='CONTROL_CONFIG_PROVISIONED';save()
    except Exception as e:
        receipt['failure']=type(e).__name__+':'+str(e)[:200];save();raise
    finally:
        print('BTC15_AUTHORIZED_PROVISION_RECEIPT '+json.dumps(receipt,sort_keys=True),flush=True)

if __name__=='__main__':
    assert sys.argv[1:]==['--separately-authorized-once'],'SEPARATE_AUTHORIZATION_REQUIRED'
    run()
