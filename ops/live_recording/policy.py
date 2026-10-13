"""Finite reviewed profiles. No capacity allocation, pruning or trading flags."""
import hashlib, importlib.metadata, json, os, re, shutil, sys
from pathlib import Path

MiB=1024**2; GiB=1024**3
BASES={'main':'4f9ffe51ff9af6adf3f1eb0bd4a77f91dc2caa7c','v81':'6e04aced0f718b29f8ed805abcc0f76b01ed5096'}
MANIFESTS={'main':'e8d8a1b54ff9ea3850296567ee8921149e5ea07697144b7bbeb41ea382045949','v81':'9e9c59b061b51486db6b1cdbc4a1b8096634eb09d9f4cfd1894362d75828660f'}
SERVICES={'main':'ab28dca6-7bea-4956-bdb9-dbb7b4c74635','v81':'6025e83e-a41c-4e0a-8c16-f71120bd501b'}
VOLUMES={'main':'6ced6b1a-3755-4518-a240-c895e936d443','v81':'d5eeafca-e0fc-42f0-b7d1-4705907720c6'}
PROJECT='baea4e22-d004-4434-b2c5-81a7fbc05086'
ENVIRONMENT='61775c5d-c583-4dfc-af41-f25578856fd9'
ROLES=('main','v81','information')
PROFILES={
 'preflight':dict(seconds=1200,compressed={'main':64*MiB,'v81':64*MiB,'information':32*MiB},decoded=768*MiB,records=300000,db=4*GiB,index=256*MiB,reader_seconds=240),
 'day':dict(seconds=86940,compressed={'main':GiB,'v81':512*MiB,'information':512*MiB},decoded=12*GiB,records=6000000,db=48*GiB,index=3*GiB,reader_seconds=3600)}

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def file_sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(MiB),b''):h.update(b)
 return h.hexdigest()
def need(ok,reason):
 if not ok:raise ValueError(reason)
def safe_path(p):
 p=Path(p).absolute()
 need(not any(x.is_symlink() for x in [p,*p.parents]),'SYMLINK_PATH')
 return p.resolve()
def atomic(path,value):
 path=Path(path);raw=canonical(value);tmp=path.with_suffix(path.suffix+'.tmp')
 fd=os.open(tmp,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def runtime_identity(c,role):
 """Pin source before rollout; retain the platform-assigned deployment at start."""
 r=c['roles'][role]
 expected=dict(project=PROJECT,environment=ENVIRONMENT,service=r['service'],volume=r['volume'],build=r['build'])
 names=dict(project='RAILWAY_PROJECT_ID',environment='RAILWAY_ENVIRONMENT_ID',service='RAILWAY_SERVICE_ID',volume='RAILWAY_VOLUME_ID',build='RAILWAY_GIT_COMMIT_SHA')
 need(all(os.getenv(names[k])==v for k,v in expected.items()),'RUNTIME_IDENTITY_DRIFT')
 deployment=os.getenv('RAILWAY_DEPLOYMENT_ID','')
 need(re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',deployment) is not None,'RUNTIME_DEPLOYMENT_ID')
 need(r['deployment']=='ATTEST_AT_START' or r['deployment']==deployment,'RUNTIME_DEPLOYMENT_DRIFT')
 need(os.getenv('RAILWAY_VOLUME_MOUNT_PATH')=='/data','RUNTIME_VOLUME_MOUNT')
 return dict(expected,deployment=deployment)
def validate(c,role,*,offline=False):
 need(c.get('schema')=='BTC15_LIVE_CAMPAIGN_V1','CAMPAIGN_SCHEMA')
 need(role in ROLES and role in c['roles'],'ROLE')
 need(re.fullmatch('[A-Za-z0-9_-]{1,64}',c['run_id']) is not None,'RUN_ID')
 need(c['profile'] in PROFILES and c.get('orders') is False and c.get('signal_only') is True,'PROFILE_OR_SAFETY')
 need(c.get('capture_enabled') is True,'EXPLICIT_CAPTURE_OPT_IN')
 need(0<c['duration_seconds']<=PROFILES[c['profile']]['seconds'],'DURATION')
 lane='main' if role=='information' else role
 r=c['roles'][role];need(r['service']==SERVICES[lane] and r['volume']==VOLUMES[lane],'ROLE_IDENTITY')
 need(r['base_release']==BASES[lane] and re.fullmatch('[0-9a-f]{40}',r['build']) is not None,'BUILD_PIN')
 root=safe_path(c['root'])
 if offline:need(not root.is_relative_to('/data') and not root.is_relative_to('/app'),'OFFLINE_PATH')
 else:
  need(root==Path('/data/btc15_recordings')/c['run_id'],'CAMPAIGN_ROOT')
  runtime_identity(c,role)
 return root/role
def attest(root,c,role):
 from btc15_v2_product.release import verify_files
 lane='main' if role=='information' else role
 verify_files(lane,root)
 install=json.loads((Path(root)/'BTC15_RECORDER_INSTALL.json').read_bytes())
 need(install['lane']==lane and install['base_release']==BASES[lane],'INSTALL_BASE')
 need(file_sha(Path(root)/'BTC15_RECORDER_ORIGINAL_RELEASE.json')==MANIFESTS[lane],'ORIGINAL_RELEASE_HASH')
 need(file_sha(Path(root)/'BTC15_V2_PRODUCT_RELEASE_R1.json')==c['roles'][role]['manifest_sha256'],'CANDIDATE_MANIFEST_HASH')
 for name,h in install['candidate_files'].items():need(file_sha(Path(root)/name)==h,'INSTALLED_SOURCE_HASH:'+name)
 deps={}
 for line in (Path(root)/'requirements.txt').read_text().splitlines():
  name,want=line.split('==');got=importlib.metadata.version(name);need(got==want,'DEPENDENCY:'+name);deps[name]=got
 need(sys.implementation.name=='cpython','CPYTHON_COUNTER_ATOMICITY')
 return dict(python=sys.version,dependencies=deps,install_sha256=file_sha(Path(root)/'BTC15_RECORDER_INSTALL.json'))
