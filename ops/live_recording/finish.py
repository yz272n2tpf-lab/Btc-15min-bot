"""FINISH_CAMPAIGN: bounded private retrieval, existing reader, PDF and recovery.

Runs only in the existing authorized Codespace. SSH access, host key and exact
new deployment identities must already be approved/provisioned. No cloud setup.
"""
import argparse,json,os,selectors,shlex,shutil,subprocess,sys,time,zipfile
from pathlib import Path
from .policy import PROFILES,PROJECT,ENVIRONMENT,canonical,sha,file_sha,need,atomic,safe_path,MiB,GiB

class SSH:
 def __init__(self,c,deadline):self.c=c;self.deadline=deadline
 def call(self,role,args,limit):
  r=self.c['roles'][role];target=r['ssh_target'];need(__import__('re').fullmatch(r'[A-Za-z0-9._-]+@ssh\.railway\.com',target),'REVIEWED_SSH_TARGET')
  key=safe_path(self.c['ssh_key']);hosts=safe_path(self.c['known_hosts'])
  need(key.is_file() and hosts.is_file() and key.stat().st_mode&0o077==0,'PRIVATE_SSH_KEY_AND_PINNED_HOST_KEY_REQUIRED')
  cmd=['ssh','-T','-oBatchMode=yes','-oStrictHostKeyChecking=yes','-oIdentitiesOnly=yes','-oConnectTimeout=8','-oServerAliveInterval=5','-oServerAliveCountMax=2','-i',str(key),'-oUserKnownHostsFile='+str(hosts),target,'cd /app && exec '+shlex.join(['python','-B','-m','ops.live_recording.remote',*args])]
  proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  out=bytearray();err=bytearray();sel=selectors.DefaultSelector()
  try:
   proc.stdin.write(canonical(self.c));proc.stdin.close();sel.register(proc.stdout,selectors.EVENT_READ,'out');sel.register(proc.stderr,selectors.EVENT_READ,'err')
   deadline=min(self.deadline,time.monotonic()+45)
   while sel.get_map():
    need(time.monotonic()<deadline,'SSH_DEADLINE')
    for key_event,_ in sel.select(.1):
     data=os.read(key_event.fileobj.fileno(),65536)
     if not data:sel.unregister(key_event.fileobj);continue
     buf=out if key_event.data=='out' else err;buf.extend(data)
     need(len(buf)<=(limit if key_event.data=='out' else MiB),'SSH_OUTPUT_BOUND')
   need(proc.wait(timeout=2)==0,'SSH_REMOTE_OPERATION_FAILED')
   return bytes(out)
  finally:
   sel.close()
   if proc.poll() is None:proc.kill();proc.wait(timeout=2)
   proc.stdout.close();proc.stderr.close()
 def seals(self):
  out={};errors=[];self.partial_seals=out
  for role,roles in (('main',['main','information']),('v81',['v81'])):
   try:
    r=json.loads(self.call(role,['finish','--roles',','.join(roles)],2*MiB));need(r['run_id']==self.c['run_id'],'REMOTE_RUN_ID');out.update(r['seals'])
   except Exception as e:errors.append(role+':'+type(e).__name__+':'+str(e)[:160])
  need(not errors,'STOP_OR_SEAL_INCOMPLETE:'+';'.join(errors))
  return out
 def object(self,role,seal,name,size):return self.call(role,['object','--role',role,'--seal',seal,'--path',name],size)

def validate_seals(c,seals):
 need(set(seals)=={'main','v81','information'},'MISSING_ROLE_SEAL')
 for role,item in seals.items():
  e=item['seal'];need(item['sha256']==sha(canonical(e)),'SEAL_HASH')
  need(e['schema']=='BTC15_ROLE_SEAL_V1' and e['role']==role and e['run_id']==c['run_id'],'SEAL_IDENTITY')
  i=e['identity'];need(i['identity']==c['roles'][role] and i['configuration_sha256']==sha(canonical(c)) and i['role']==role and i['run_id']==c['run_id'],'EXACT_CONFIG_OR_DEPLOYMENT')
  if i['mode']=='NATIVE_CAPTURE':
   runtime=i.get('runtime',{});r=c['roles'][role]
   need(all(runtime.get(k)==v for k,v in dict(project=PROJECT,environment=ENVIRONMENT,service=r['service'],volume=r['volume'],build=r['build']).items()),'ATTESTED_RUNTIME_IDENTITY')
   deployment=runtime.get('deployment','')
   need(__import__('re').fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',deployment) is not None and (r['deployment']=='ATTEST_AT_START' or deployment==r['deployment']),'ATTESTED_DEPLOYMENT_ID')
  names=set();total=0
  for f in e['files']:
   n=Path(f['path']);need(not n.is_absolute() and '..' not in n.parts and f['path'] not in names and 0<=f['size']<=8*MiB,'OBJECT_INVENTORY')
   need(n.name in ('identity.json','terminal-status.json') or (len(n.parts)==2 and n.parts[0] in ('source.segments','information.segments') and n.name.endswith('.jsonl.gz')),'OBJECT_ALLOWLIST')
   need(__import__('re').fullmatch('[0-9a-f]{64}',f['sha256']),'OBJECT_HASH_FORMAT');names.add(f['path']);total+=f['size']
  need(total<=PROFILES[c['profile']]['compressed'][role]+2*MiB and len(names)<=4096,'ROLE_TRANSFER_QUOTA')
  need({'identity.json','terminal-status.json'}<=names,'ROLE_RECEIPTS_REQUIRED')
 if seals['main']['seal']['identity']['mode']=='NATIVE_CAPTURE':
  need(seals['main']['seal']['identity']['runtime']==seals['information']['seal']['identity'].get('runtime'),'MAIN_INFORMATION_DEPLOYMENT_MISMATCH')
 return seals

def report_quality(summary,seals):
 counts=summary.get('counts',{});matrix=[]
 for label,kind in [('Original BTC/BRTI','SOURCE'),('Original HTTP responses','ORIGINAL_RESPONSE'),('Completed candle acceptance','CANDLE_ACCEPTANCE'),('Quote receive/depth','QUOTE_ACCEPT'),('Proof chains','QUOTE_PROOF'),('Original native/Admin journals','NATIVE_RECORD'),('V81 input acceptance','V81_INPUT'),('Independent information','INFORMATION_INPUT'),('Outcome acceptance','OUTCOME_ACCEPTANCE'),('BRTI closeout acceptance','CLOSEOUT_ACCEPTANCE')]:
  n=counts.get(kind,0);optional=kind in ('OUTCOME_ACCEPTANCE','CLOSEOUT_ACCEPTANCE')
  matrix.append(dict(requirement=label,records=n,status=('VERIFIED_SCOPE' if summary.get('complete_supplied_scope') else 'RECORDED_UNRESOLVED') if n else ('NOT_EMITTED_OR_PENDING' if optional and summary.get('complete_supplied_scope') else 'MISSING_OR_UNRESOLVED')))
 unresolved_origins=sum(summary.get('metrics',{}).get(k,0) for k in ('origins_outside_recorded_journal_interval','terminals_outside_recorded_interval'))
 return dict(fixture_only=summary.get('evidence_classes')==['FIXTURE'],fixture_complete=summary.get('fixture_complete',False),complete_supplied_scope=summary.get('complete_supplied_scope',False),complete_evidence=summary.get('complete_supplied_scope',False) and not unresolved_origins,cost_verified=False,recording_readiness=summary.get('status','INCOMPLETE'),economic_evidence_readiness='NOT_EVALUATED; no fills or fee applicability assumed',production_approval='SEPARATE_AUTHORIZATION_REQUIRED',coverage=summary.get('coverage',{}),counts=counts,matrix=matrix,gaps=[dict(reason=k,count=v) for k,v in summary.get('issue_counts',{}).items()],lifecycle_emitted=summary.get('lifecycle_emitted',{}),pending_outcomes=summary.get('pending_outcomes',{}),absent_lifecycle_basis=summary.get('absent_lifecycle_basis','UNKNOWN'),contract_boundaries=summary.get('contract_boundaries',{}),unresolved_origin_or_terminal_links=unresolved_origins,upstream_candle_receipts_not_captured=summary.get('metrics',{}).get('completed_cache_rows_upstream_receipt_unknown',0))

def finish(c,output,transport=None):
 started=time.monotonic();profile=PROFILES[c['profile']];deadline=started+(300 if c['profile']=='preflight' else 5400)
 output=safe_path(output);need(not output.is_relative_to('/data') and not output.is_relative_to('/app'),'CODESPACE_PRIVATE_DESTINATION')
 os.umask(0o077);output.mkdir(parents=True,exist_ok=True,mode=0o700);need(output.stat().st_mode&0o077==0,'PRIVATE_OUTPUT_PERMISSIONS')
 identity=sha(canonical(c));marker=output/'campaign-config.json'
 if marker.exists():need(file_sha(marker)==identity,'RESUME_CONFIG_DRIFT')
 else:atomic(marker,c)
 # Work DB + index + raw + ZIP + receiver/verification overhead, finite.
 reserve=profile['db']+profile['index']+3*sum(profile['compressed'].values())+2*GiB
 attempts=sorted(output.glob('attempt-*.json'));need(len(attempts)<3,'BOUNDED_RECOVERY_ATTEMPTS_EXHAUSTED');attempt=len(attempts)+1
 receipt=dict(schema='BTC15_FINISH_RECEIPT_V1',run_id=c['run_id'],configuration_sha256=identity,status='INCOMPLETE',attempt=attempt,scope='CAMPAIGN',live_retrieval=False,verified_objects=0,bytes=0,live_blockers=[],signal_only=True,orders=False)
 summary={};seals={};transport=transport or SSH(c,deadline)
 try:
  need(shutil.disk_usage(output).free>=reserve,'CODESPACE_CAPACITY_RESERVE')
  seals=validate_seals(c,transport.seals());pin=output/'seals.json'
  if isinstance(transport,SSH):need(all(x['seal']['identity']['mode']=='NATIVE_CAPTURE' for x in seals.values()),'LIVE_TRANSFER_FIXTURE_CLASS_FORBIDDEN')
  if pin.exists():need(json.loads(pin.read_bytes())==seals,'SEALED_MANIFEST_DRIFT')
  else:atomic(pin,seals)
  rawroot=output/'raw';rawroot.mkdir(exist_ok=True)
  for role,item in seals.items():
   root=rawroot/role;root.mkdir(exist_ok=True);atomic(root/'seal.json',item['seal'])
   for e in item['seal']['files']:
    need(time.monotonic()<deadline,'FINISH_DEADLINE');p=root/e['path'];need(not p.is_symlink() and p.resolve().is_relative_to(root),'DESTINATION_PATH');p.parent.mkdir(parents=True,exist_ok=True)
    if not (p.exists() and p.stat().st_size==e['size'] and file_sha(p)==e['sha256']):
     for retry in range(2):
      data=transport.object(role,item['sha256'],e['path'],e['size'])
      if len(data)==e['size'] and sha(data)==e['sha256']:break
     else:raise ValueError('TRANSFER_HASH_OR_SIZE:'+role+':'+e['path'])
     tmp=p.with_suffix(p.suffix+'.partial')
     with tmp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
     tmp.replace(p)
    receipt['verified_objects']+=1;receipt['bytes']+=e['size']
  receipt['transfer_seconds']=time.monotonic()-started;receipt['live_retrieval']=isinstance(transport,SSH)
  from .capacity import project
  health={r:json.loads((rawroot/r/'terminal-status.json').read_bytes()) for r in seals}
  atomic(output/'24h-projection.json',project(health))
  work=output/('reader-'+str(attempt));work.mkdir();merged=work/'run';merged.mkdir()
  for role,item in seals.items():
   for e in item['seal']['files']:
    if e['path'].endswith('.jsonl.gz'):
     stream='information' if role=='information' else 'source';p=merged/(stream+'.segments')/(role+'-'+Path(e['path']).name);p.parent.mkdir(exist_ok=True);os.link(rawroot/role/e['path'],p)
  atomic(merged/'campaign-scope.json',dict(schema='BTC15_CAMPAIGN_SCOPE_V1',run_id=c['run_id'],seals=[x['seal'] for x in seals.values()]))
  # Fresh interpreter; no source execution, recorder globals or network required.
  cmd=[sys.executable,'-B','-m','ops.live_recording.finish','--read-only',str(work),'--profile',c['profile']]
  completed=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=max(1,deadline-time.monotonic()-5))
  (work/'reader-stdout.txt').write_bytes(completed.stdout);(work/'reader-stderr.txt').write_bytes(completed.stderr)
  need(completed.returncode==0,'INDEPENDENT_READER_FAILED');summary=json.loads((work/'verification/summary.json').read_bytes())
  receipt['status']='VERIFIED_SUPPLIED_SCOPE' if summary['complete_supplied_scope'] else 'INCOMPLETE'
  receipt['source_inventory_sha256']=file_sha(pin);receipt['package_sha256']=file_sha(pin)
 except Exception as e:
  receipt['failure']=type(e).__name__+': '+str(e)[:500]
  receipt['live_blockers'].append('Failure retained. Retry the identical config/output at most three times; verified immutable objects are reused. No raw evidence is deleted.')
 finally:
  if getattr(transport,'partial_seals',None):atomic(output/('partial-seals-'+str(attempt)+'.json'),transport.partial_seals)
  receipt['elapsed_seconds']=time.monotonic()-started
  quality=report_quality(summary,seals)
  quality['health']={r:json.loads((output/'raw'/r/'terminal-status.json').read_bytes()) for r in seals if (output/'raw'/r/'terminal-status.json').is_file()}
  projection=output/'24h-projection.json'
  if projection.is_file():quality['24h_projection']=json.loads(projection.read_bytes())
  if receipt.get('failure'):quality['gaps'].append(dict(reason=receipt['failure']))
  quality['receipt']=receipt;atomic(output/('attempt-'+str(attempt)+'.json'),receipt);atomic(output/'quality.json',quality)
  from .offline_report import render_pdf
  render_pdf(output/'BTC15_Findings.pdf',quality,receipt)
  # Reuse ZIP recovery convention. SQLite work files/hardlinked working copies
  # are reproducible; preserve raw, receipts, ledgers, report and reader logs.
  recovery=output/'recovery.zip';tmp=output/'recovery.partial'
  with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
   for p in sorted(output.rglob('*')):
    if p.is_file() and p not in (recovery,tmp) and p.name!='DELIVERY.json' and not p.name.endswith('.sqlite3') and '/run/' not in str(p.relative_to(output)):
     z.write(p,str(p.relative_to(output)))
  tmp.replace(recovery)
  atomic(output/'DELIVERY.json',dict(status=receipt['status'],pdf='BTC15_Findings.pdf',pdf_sha256=file_sha(output/'BTC15_Findings.pdf'),recovery='recovery.zip',recovery_sha256=file_sha(recovery),complete_evidence=quality['complete_evidence'],live_retrieval_demonstrated=receipt['live_retrieval']))
 return receipt
def read_only(work,profile):
 import socket
 def deny(*a,**k):raise RuntimeError('INDEPENDENT_READER_NETWORK_FORBIDDEN')
 socket.socket.connect=deny;socket.create_connection=deny
 from ops.recording_workflow.evidence import index_run
 from .reader import run
 root=Path(work);index_run(root/'run',root/'index',profile=profile);run(root/'run',root/'index',root/'verification',profile)
def main():
 p=argparse.ArgumentParser();p.add_argument('--config');p.add_argument('--output');p.add_argument('--read-only');p.add_argument('--profile',choices=list(PROFILES));a=p.parse_args()
 if a.read_only:read_only(a.read_only,a.profile)
 else:
  need(a.config and a.output,'CONFIG_AND_OUTPUT_REQUIRED');print(json.dumps(finish(json.loads(Path(a.config).read_bytes()),a.output),sort_keys=True))
if __name__=='__main__':main()
