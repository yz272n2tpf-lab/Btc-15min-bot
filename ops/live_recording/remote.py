"""Private SSH command: recorder stop requests and sealed-object reads only.

No production DB reads, historical export, process signals, deletion or endpoint.
This module is prepared offline; executing it against Railway requires approval.
"""
import argparse,json,os,sys,time
from pathlib import Path
from .policy import validate,runtime_identity,need,sha,canonical,file_sha,atomic,MiB

def identity(c,role):
 root=validate(c,role);p=root/'identity.json';need(p.stat().st_size<65536,'IDENTITY_SIZE');i=json.loads(p.read_bytes())
 need(i['run_id']==c['run_id'] and i['role']==role and i['identity']==c['roles'][role] and i['configuration_sha256']==sha(canonical(c)),'RUN_IDENTITY')
 need(i.get('runtime')==runtime_identity(c,role),'CAPTURE_DEPLOYMENT_CHANGED')
 return root
def finish(c,roles):
 roots={r:identity(c,r) for r in roles}
 for role,root in roots.items():atomic(root/'stop-request.json',dict(run_id=c['run_id'],role=role,requested_at=time.time()))
 deadline=time.monotonic()+8
 while time.monotonic()<deadline:
  if all((p/'seal.json').exists() for p in roots.values()):break
  time.sleep(.1)
 seals={}
 for r,p in roots.items():
  need((p/'seal.json').is_file(),'RECORDER_SEAL_TIMEOUT:'+r)
  raw=(p/'seal.json').read_bytes();need(len(raw)<=MiB,'SEAL_BYTES');seals[r]=dict(sha256=sha(raw),seal=json.loads(raw))
 return dict(schema='BTC15_PRIVATE_FINISH_RECEIPT_V1',run_id=c['run_id'],seals=seals)
def object_path(c,role,seal_sha,name):
 root=identity(c,role);raw=(root/'seal.json').read_bytes();need(sha(raw)==seal_sha,'PINNED_SEAL_CHANGED');seal=json.loads(raw)
 matching=[e for e in seal['files'] if e['path']==name];need(len(matching)==1,'OBJECT_NOT_IN_SEAL');e=matching[0]
 p=root/name;need(not p.is_symlink() and p.resolve().is_relative_to(root) and e['size']<=8*MiB,'SEALED_OBJECT_PATH_OR_SIZE')
 need(p.stat().st_size==e['size'] and file_sha(p)==e['sha256'],'SEALED_OBJECT_CHANGED')
 return p
def main():
 p=argparse.ArgumentParser();p.add_argument('operation',choices=['finish','object']);p.add_argument('--roles');p.add_argument('--role');p.add_argument('--seal');p.add_argument('--path');a=p.parse_args()
 raw=sys.stdin.buffer.read(65537);need(len(raw)<=65536,'CONFIG_SIZE');c=json.loads(raw)
 if a.operation=='finish':sys.stdout.buffer.write(canonical(finish(c,a.roles.split(','))))
 else:
  path=object_path(c,a.role,a.seal,a.path)
  with path.open('rb') as f:
   for chunk in iter(lambda:f.read(MiB),b''):sys.stdout.buffer.write(chunk)
if __name__=='__main__':main()
