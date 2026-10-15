"""Recorder-owned admission, queue, quotas and filesystem stop/seal protocol.

No signal handler, service restart, HTTP endpoint, source poll or native queue.
Stopping never restores an older function over a later cadence wrapper.
"""
import atexit,base64,json,os,shutil,threading,time
from collections import Counter
from pathlib import Path
from .recorder_queue import RecorderOffPathProofWriter
from candidates.early_recording_20261012.archive import Archive,BUDGET
from .batched_journal import BatchedCompressedJournal
from candidates.early_recording_20261012.seams import Observer
from .policy import canonical,sha,file_sha,atomic,need,validate,runtime_identity,PROFILES,MiB

RAW_KINDS={'ORIGINAL_RESPONSE','CANDLE_ACCEPTANCE','V81_INPUT','BRTI_READ','OUTCOME_ACCEPTANCE','CLOSEOUT_ACCEPTANCE','NATIVE_FRAME'}
class RoleArchive(Archive):
 def __init__(self,*args,**kwargs):
  role=kwargs.get('role')
  super().__init__(*args,**kwargs)
  # Only the isolated V81 recorder opts into batched evidence durability.
  # MAIN, Information, and every native journal retain their original writer.
  if role=='v81':self.journal=BatchedCompressedJournal(self.path,**self.budget)
 def close(self):
  try:
   if isinstance(self.journal,BatchedCompressedJournal):self.journal.flush()
  finally:super().close()
 def observe(self,kind,fields):
  if kind=='ORIGINAL_RESPONSE':
   raw=fields['raw'];self.write(kind,dict({k:v for k,v in fields.items() if k!='raw'},raw_base64=base64.b64encode(raw).decode(),sha256=sha(raw)));return
  if kind=='HTTP_RESPONSE':
   try:json.loads(fields['raw'])
   except (ValueError,UnicodeDecodeError):
    raw=fields['raw'];h=sha(raw)
    self.write('HTTP_BYTES',dict(raw_base64=base64.b64encode(raw).decode(),sha256=h))
    self.write('SOURCE_GAP',dict(reason='ORIGINAL_HTTP_NOT_JSON',endpoint=fields['endpoint'],observed_at=fields['received_at'],raw_sha256=h));return
  if kind in RAW_KINDS:
   raw=fields['raw'];self.write(kind,dict(fields,raw=raw.decode(),sha256=sha(raw)));return
  if kind in {'RECORDING_BOUNDARY','RECORDING_HEALTH'}:self.write(kind,fields);return
  return super().observe(kind,fields)
 def write(self,kind,payload):
  if hasattr(self,'profile'):
   j=self.journal
   if kind not in ('STOP','EVIDENCE_GAP','RECORDING_BOUNDARY'):
    need(j.raw_bytes<self.decoded_cap-5*MiB and j.records<self.record_cap-4,'ROLE_DECODED_OR_RECORD_CAP')
    need((j.total_bytes or 0)<j.max_total_bytes-6*MiB,'ROLE_SEAL_RESERVE')
    if j.records%100==0:need(shutil.disk_usage(self.path.parent).free>self.reserve,'VOLUME_RESERVE')
  return super().write(kind,payload)

class Gate:
 """Closed callbacks become inert; a nonblocking lock bounds admission races."""
 def __init__(self,writer):
  self.writer=writer;self.active=True;self.lock=threading.Lock();self.metrics=Counter();self.journals={};self.reason=None
 def submit_observation(self,kind,**fields):
  if not self.active:return False
  if not self.lock.acquire(False):self.writer.gap('ADMISSION_BUSY');return False
  try:
   if not self.active:return False
   if kind=='NATIVE_RECORD':
    key=fields['original_journal'];seq=fields['sequence'];z=self.journals.setdefault(key,dict(first=seq,last=seq-1,attempted=0,accepted=0,lane=fields.get('lane'),basis=fields['record_basis']))
    if seq!=z['last']+1:self.writer.gap('CAPTURE_ERROR')
    z['last']=seq;z['attempted']+=1
   ok=self.writer.submit_observation(kind,**fields)
   if kind=='NATIVE_RECORD' and ok:z['accepted']+=1
   return ok
  finally:self.lock.release()
 def gap(self,reason):
  if self.active:self.writer.gap(reason)
 def overhead(self,started,label):
  elapsed=time.perf_counter_ns()-started;self.metrics['calls']+=1;self.metrics['total_ns']+=elapsed;self.metrics['max_ns']=max(self.metrics['max_ns'],elapsed)
  self.metrics['under_1ms' if elapsed<=1000000 else 'over_1ms']+=1
  self.metrics[label+':calls']+=1
  if elapsed>1000000:self.metrics[label+':over_1ms']+=1
  if elapsed>5000000:self.active=False;self.reason='HOOK_OVER_5MS:'+label
 def disable(self):
  if not self.lock.acquire(timeout=.25):self.active=False;self.reason='ADMISSION_STOP_TIMEOUT';return False
  try:self.active=False
  finally:self.lock.release()
  return True

class AsyncInformationArchive:
 """Existing information publisher callback, routed to recorder's own drain."""
 def __init__(self,gate):self.gate=gate
 def start(self):pass
 def close(self):pass
 def observe(self,kind,fields):return self.gate.submit_observation(kind,**fields)
 def write(self,kind,fields):
  if kind!='STOP':return self.gate.submit_observation(kind,**fields)

class Capture:
 def __init__(self,c,role,*,offline=False,attestation=None):
  self.config=c;self.role=role;self.root=validate(c,role,offline=offline);self.profile=PROFILES[c['profile']]
  self.root.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
  if not offline:
   roles=('main','information') if role!='v81' else ('v81',)
   need(shutil.disk_usage(self.root.parent).free>=sum(self.profile['compressed'][r] for r in roles)+1024*MiB,'INITIAL_VOLUME_RESERVE_AND_NATIVE_GROWTH')
  self.root.mkdir(mode=0o700) # No restart append into an earlier campaign role.
  os.chmod(self.root.parent,0o700)
  self.started=time.time();self.begin=time.monotonic();self.failure=None;self.stopped=False;self.stop_event=threading.Event();self.stop_lock=threading.Lock();self.bound=[];self.enabled=True
  self.peaks={'warmup':Counter(),'steady':Counter()};self.last_rate=(self.begin,0,0,0);self.providers=[]
  identity=dict(schema='BTC15_CAPTURE_IDENTITY_V1',run_id=c['run_id'],role=role,configuration_sha256=sha(canonical(c)),identity=c['roles'][role],started=self.started,mode='OFFLINE_FIXTURE' if offline else 'NATIVE_CAPTURE',attestation=attestation,signal_only=True,orders=False)
  identity['runtime']=None if offline else runtime_identity(c,role)
  atomic(self.root/'identity.json',identity)
  cap=self.profile['compressed'][role];kw={}
  if offline:
   from ops.recording_workflow.policy import local_policy
   policy=local_policy();policy.update(per_archive_bytes=cap,total_bytes=2*cap+128*MiB+512*MiB+512*MiB+128*MiB);kw['storage_policy']=policy
  else:kw.update(live_config=c,role=role)
  self.archive=RoleArchive(self.root/('information' if role=='information' else 'source'),evidence_class='FIXTURE' if offline else 'NATIVE_CAPTURE',source_binding=c['run_id']+':'+role,budget=dict(BUDGET,max_total_bytes=cap),**kw)
  self.archive.profile=self.profile;share=2 if role=='main' else 4
  self.archive.decoded_cap=self.profile['decoded']//share;self.archive.record_cap=self.profile['records']//share
  self.archive.reserve=512*MiB # independent of configured volume size
  self.writer=RecorderOffPathProofWriter(self.root/'unused',lambda p,w:w.identity,2*MiB,queue_size=16384,queue_bytes=32*MiB,admission_limits=dict(queue_size=16384,queue_bytes=32*MiB),archive=self.archive)
  self.gate=Gate(self.writer)
  self.observer=Observer(self.gate,btc_feed='Coinbase:existing:'+role,btc_epoch=self.archive.session,brti_feed='BRTI:existing-owner:'+role)
  self.observer.capture_requests=True
  emit=self.observer.emit
  def measured(kind,**fields):
   if not self.gate.active:return False
   begun=time.perf_counter_ns()
   try:return emit(kind,**fields)
   finally:self.gate.overhead(begun,kind)
  self.observer.emit=measured
  self.control=threading.Thread(target=self.watch,name='recorder-control-'+role,daemon=True);self.control.start()
 def emit(self,kind,**fields):return self.gate.submit_observation(kind,**fields)
 def document(self,kind,value,**fields):
  if not self.gate.active:return
  started=time.perf_counter_ns()
  try:self.emit(kind,raw=canonical(value),**fields)
  except Exception:self.gate.gap('CAPTURE_ERROR')
  finally:self.gate.overhead(started,kind)
 def status(self):
  return dict(run_id=self.config['run_id'],role=self.role,session=self.archive.session,admission=self.gate.active,stopped=self.stopped,failure=self.failure or self.gate.reason,drain_timeout_observed=getattr(self,'drain_timeout_observed',False),writer=self.writer.status(),hooks=dict(self.gate.metrics),raw_bytes=self.archive.journal.raw_bytes,compressed_bytes=self.archive.journal.stored_bytes,records=self.archive.journal.records,durable_records=getattr(self.archive.journal,'durable_records',self.archive.journal.records),pending_raw_bytes=getattr(self.archive.journal,'pending_raw_bytes',0),pending_records=getattr(self.archive.journal,'pending_records',0),journal_failed=getattr(self.archive.journal,'failed',False),elapsed=time.monotonic()-self.begin,peak_rates={k:dict(v) for k,v in self.peaks.items()},original_proof_queues=[dict(writer_id=id(p.proof_writer),queue_id=id(p.proof_writer.queue),unfinished=p.proof_writer.queue.unfinished_tasks,dropped=p.proof_writer.dropped,rejected=p.proof_writer.rejected,published=p.proof_writer.published) for p in self.providers])
 def watch(self):
  while not self.stop_event.wait(.5):
   try:
    now=time.monotonic();j=self.archive.journal
    if isinstance(j,BatchedCompressedJournal):j.flush_due()
    before,raw,stored,n=self.last_rate;dt=now-before;peak=self.peaks['warmup' if now-self.begin<120 else 'steady']
    for k,v in [('decoded',(j.raw_bytes-raw)/dt),('compressed',(j.stored_bytes-stored)/dt),('envelopes',(j.records-n)/dt)]:peak[k]=max(peak[k],v)
    self.last_rate=(now,j.raw_bytes,j.stored_bytes,j.records)
    s=self.status();atomic(self.root/'health.json',s)
    reason=None
    if (self.root/'stop-request.json').exists():
     request=json.loads((self.root/'stop-request.json').read_bytes());need(request['run_id']==self.config['run_id'] and request['role']==self.role,'STOP_IDENTITY');reason='OPERATOR_FINISH'
    if time.monotonic()-self.begin>=self.config['duration_seconds']:reason='DURATION_LIMIT'
    if s['writer']['archive_failed'] or s['writer']['losses'] or s['journal_failed']:reason='RECORDER_LOSS_OR_FAILURE';self.failure=reason
    if self.gate.reason:reason=self.gate.reason;self.failure=reason
    for key,n in list(self.gate.metrics.items()):
     if key.endswith(':calls') and n>=100 and self.gate.metrics[key[:-6]+':over_1ms']/n>.01:reason='HOOK_P99_OVER_1MS';self.failure=reason
    if reason:self.stop(reason);return
   except Exception as e:
    self.failure='CONTROL_FAILURE:'+type(e).__name__;self.stop(self.failure);return
 def stop(self,reason='OPERATOR_FINISH',timeout=5):
  with self.stop_lock:
   if self.stopped:return json.loads((self.root/'terminal-status.json').read_bytes())
   # Disable source admission only once. Recovery must never insert a second
   # boundary or reopen a writer that is already draining its first shutdown.
   if not getattr(self,'_admission_closed',False):
    admitted=self.gate.disable();self.stop_event.set()
    if not admitted:
     self.failure=self.failure or 'ADMISSION_STOP_TIMEOUT'
     s=self.status();s['status']='INCOMPLETE';s['reason']=reason
     atomic(self.root/'terminal-status.json',s)
     if not getattr(self,'admission_recovery',None):
      def retry_admission():
       if self.gate.lock.acquire(timeout=30):
        self.gate.lock.release();self.stop('LATE_ADMISSION_STOP',timeout=5)
      self.admission_recovery=threading.Thread(target=retry_admission,daemon=True,name='recorder-bounded-admission-recovery')
      self.admission_recovery.start()
     return s
    self._admission_closed=True;self._stop_reason=reason
    self.writer.submit_observation('RECORDING_BOUNDARY',reason=reason,observed_at=time.time(),native_owners_continue=True)
    self.writer._closing=True
   reason=self._stop_reason
   self.writer._thread.join(timeout)
   if self.writer._thread.is_alive():
    # Persist an explicit incomplete receipt. Do not forge a seal while the
    # worker still owns an open gzip member or has uncommitted queued records.
    self.drain_timeout_observed=True
    self.failure=self.failure or 'DRAIN_TIMEOUT'
    s=self.status();s['status']='INCOMPLETE';s['reason']=reason
    atomic(self.root/'terminal-status.json',s)
    if not getattr(self,'late_sealer',None):
     def await_drain():
      # An arbitrary second 30-second deadline previously abandoned sealing
      # permanently even if the evidence writer exited just afterward.
      # This daemon never blocks the native owner and never deletes raw data.
      while self.writer._thread.is_alive():
       self.writer._thread.join(30)
      self.stop(reason,timeout=0)
     self.late_sealer=threading.Thread(target=await_drain,daemon=True,name='recorder-incomplete-drain-recovery')
     self.late_sealer.start()
    return s
   if getattr(self.archive.journal,'failed',False):
    self.failure=self.failure or 'JOURNAL_FLUSH_FAILURE'
    s=self.status();s['status']='INCOMPLETE';s['reason']=reason
    atomic(self.root/'terminal-status.json',s)
    # A potentially torn gzip member is never presented as a sealed archive.
    return s
   self.stopped=True
   if self.control is not threading.current_thread():self.control.join(1)
   s=self.status();s['status']='INCOMPLETE' if s['failure'] or s['writer']['archive_failed'] or s['writer']['losses'] else 'SEALED'
   s['reason']=reason;s['journals']=self.gate.journals;s['stopped_at']=time.time()
   atomic(self.root/'terminal-status.json',s)
   files=[]
   for p in sorted(self.root.rglob('*')):
    if p.is_file() and (p.name.endswith('.jsonl.gz') or p.name in ('identity.json','terminal-status.json')):
     files.append(dict(path=str(p.relative_to(self.root)),size=p.stat().st_size,sha256=file_sha(p)))
   atomic(self.root/'seal.json',dict(schema='BTC15_ROLE_SEAL_V1',run_id=self.config['run_id'],role=self.role,identity=json.loads((self.root/'identity.json').read_bytes()),session=self.archive.session,last_sequence=self.archive.seq,last_sha256=self.archive.previous,status=s['status'],files=files,journals=self.gate.journals))
   return s
