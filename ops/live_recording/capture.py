"""Recorder-owned admission, queue, quotas and filesystem stop/seal protocol.

No signal handler, service restart, HTTP endpoint, source poll or native queue.
Stopping never restores an older function over a later cadence wrapper.
"""
import atexit,base64,json,os,shutil,threading,time
from collections import Counter
from itertools import count
from pathlib import Path
from .burst_journal_research import BufferedCaptureArchive,BufferedProofWriter
from candidates.early_recording_20261012.archive import BUDGET
from candidates.early_recording_20261012.seams import Observer
from .policy import canonical,sha,file_sha,atomic,need,validate,runtime_identity,PROFILES,MiB
from .telemetry import bounded

RAW_KINDS={'ORIGINAL_RESPONSE','CANDLE_ACCEPTANCE','V81_INPUT','BRTI_READ','OUTCOME_ACCEPTANCE','CLOSEOUT_ACCEPTANCE','NATIVE_FRAME'}
class RoleArchive(BufferedCaptureArchive):
 def observe(self,kind,fields):
  if kind=='INFORMATION_INPUT' and 'outcome_parts' in fields:
   from .telemetry import OUTCOME_BYTES
   n=fields.pop('outcome_parts');need(type(n) is int and 1<=n<=16,'PUBLICATION_PART_BOUND')
   parts=[fields.pop('outcome_%02d'%i) for i in range(n)]
   need(all(type(x) is bytes and 0<len(x)<=1024 for x in parts),'PUBLICATION_PART_BYTES')
   raw=b''.join(parts);need(len(raw)<=OUTCOME_BYTES,'PUBLICATION_TELEMETRY_BYTES')
   self._publication_outcome=json.loads(raw);self._outcome_written=False
   try:
    result=super().observe(kind,fields)
    need(self._outcome_written,'PUBLICATION_TELEMETRY_NOT_RETAINED')
    return result
   finally:self._publication_outcome=None
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
  if kind=='RECORDING_HEALTH' and 'raw' in fields:
   self.write(kind,json.loads(fields['raw']));return
  if kind in {'RECORDING_BOUNDARY','RECORDING_HEALTH'}:self.write(kind,fields);return
  return super().observe(kind,fields)
 def write(self,kind,payload):
  outcome=getattr(self,'_publication_outcome',None)
  if outcome is not None and kind in ('INFORMATION_INPUT','INFORMATION_FAILURE') and 'input_sha256' in payload:
   from .telemetry import check_outcome
   check_outcome(outcome,payload['input_sha256'],payload['published'],payload.get('frame_id'))
   payload=dict(payload,publication_outcome=outcome);self._outcome_written=True
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
  self.local=threading.local();self.hook_ids=count(1);self.inflight=set();self.overruns=[];self.overrun_overflow=0
 def submit_observation(self,kind,**fields):
  self.local.outcome='GATE_CLOSED'
  if not self.active:return False
  if not self.lock.acquire(False):
   self.local.outcome='GATE_MUTEX_BUSY'
   self.writer.gap('ADMISSION_BUSY');self.active=False;self.reason='RECORDER_ADMISSION_BUSY';return False
  try:
   if not self.active:return False
   if kind=='NATIVE_RECORD':
    key=fields['original_journal'];seq=fields['sequence'];z=self.journals.setdefault(key,dict(first=seq,last=seq-1,attempted=0,accepted=0,lane=fields.get('lane'),basis=fields['record_basis']))
    if seq!=z['last']+1:self.gap('CAPTURE_ERROR');return False
    z['last']=seq;z['attempted']+=1
   ok=self.writer.submit_observation(kind,**fields)
   self.local.outcome=getattr(getattr(self.writer,'admission_local',None),'outcome','ADMITTED' if ok else 'REJECTED')
   if kind=='NATIVE_RECORD' and ok:z['accepted']+=1
   if not ok:
    # Stop capture admission immediately after the first loss. Native owners
    # continue unchanged; the control thread drains accepted work and seals
    # INCOMPLETE. Never keep collecting a deceptively usable suffix.
    self.active=False;self.reason='RECORDER_ADMISSION_REJECTED:'+str(kind)[:64]
   return ok
  finally:self.lock.release()
 def gap(self,reason):
  if self.active:
   self.writer.gap(reason);self.active=False;self.reason='RECORDER_EVIDENCE_GAP:'+str(reason)[:64]
 def overhead(self,started,label,thread_started=None,event=None,admitted=None):
  elapsed=time.perf_counter_ns()-started;self.metrics['calls']+=1;self.metrics['total_ns']+=elapsed;self.metrics['max_ns']=max(self.metrics['max_ns'],elapsed)
  self.metrics['under_1ms' if elapsed<=1000000 else 'over_1ms']+=1
  self.metrics[label+':calls']+=1
  if elapsed>1000000:self.metrics[label+':over_1ms']+=1
  cpu=time.thread_time_ns()-thread_started if thread_started is not None and (elapsed>1000000 or event is not None and admitted is not True) else None
  if cpu is not None and elapsed>1000000:
   self.metrics[label+':slow_max_thread_cpu_ns']=max(self.metrics[label+':slow_max_thread_cpu_ns'],cpu)
   self.metrics[label+':slow_max_off_cpu_ns']=max(self.metrics[label+':slow_max_off_cpu_ns'],max(0,elapsed-cpu))
  if event is not None and (elapsed>5000000 or admitted is not True):
   if len(self.overruns)<8:
    try:event=bounded(event)
    except Exception:
     event=dict(identity_capture_failed=True);self.gap('CAPTURE_ERROR')
    self.overruns.append(dict(event,hook=label,wall_ns=elapsed,thread_cpu_ns=cpu,
      admission=getattr(self.local,'outcome','UNKNOWN'),admitted=admitted))
    z=self.overruns[-1];z['off_cpu_ns']=max(0,elapsed-cpu) if cpu is not None else None
   else:self.overrun_overflow+=1;self.gap('CAPTURE_ERROR')
  if elapsed>5000000:
   self.active=False
   self.reason=self.reason or 'HOOK_OVER_5MS:'+label
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
   need(shutil.disk_usage(self.root.parent).free>=sum(self.profile['compressed'][r] for r in roles)+self.profile.get('producer_reserve',1024*MiB),'INITIAL_VOLUME_RESERVE_AND_NATIVE_GROWTH')
  self.root.mkdir(mode=0o700) # No restart append into an earlier campaign role.
  os.chmod(self.root.parent,0o700)
  self.started=time.time();self.begin=time.monotonic();self.failure=None;self.stopped=False;self.stop_event=threading.Event();self.stop_lock=threading.Lock();self.bound=[];self.enabled=True
  self.peaks={'warmup':Counter(),'steady':Counter()};self.last_rate=(self.begin,0,0,0);self.providers=[];self.next_health=self.begin
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
  self.archive.decoded_cap=self.profile.get('decoded_by_role',{}).get(role,self.profile['decoded']//share)
  self.archive.record_cap=self.profile.get('records_by_role',{}).get(role,self.profile['records']//share)
  self.archive.reserve=self.profile.get('producer_reserve',512*MiB) # independent of configured volume size
  self.writer=BufferedProofWriter(self.root/'unused',lambda p,w:w.identity,2*MiB,queue_size=16384,queue_bytes=32*MiB,admission_limits=dict(queue_size=16384,queue_bytes=32*MiB),archive=self.archive)
  self.gate=Gate(self.writer)
  self.observer=Observer(self.gate,btc_feed='Coinbase:existing:'+role,btc_epoch=self.archive.session,brti_feed='BRTI:existing-owner:'+role)
  self.observer.capture_requests=True
  emit=self.observer.emit
  def measured(kind,**fields):
   if not self.gate.active:return False
   begun=time.perf_counter_ns();thread_begun=time.thread_time_ns();id=next(self.gate.hook_ids)
   if len(self.gate.inflight)>=64:self.gate.gap('CAPTURE_ERROR');return False
   self.gate.inflight.add(id);result=None;event=None
   if (role,kind) in (('main','QUOTE_ACCEPT'),('v81','QUOTE_RECEIVE')):
    fields['recorder_hook_id']=id
    event={k:fields.get(k) for k in ('recorder_hook_id','ticker','epoch','received_at','accepted_at','monotonic_ns')}
    event.update(role=role,session=self.archive.session)
   try:
    result=emit(kind,**fields);return result
   finally:
    try:self.gate.overhead(begun,kind,thread_begun,event,result)
    finally:self.gate.inflight.discard(id)
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
  return dict(run_id=self.config['run_id'],role=self.role,session=self.archive.session,admission=self.gate.active,stopped=self.stopped,failure=self.failure or self.gate.reason,writer=self.writer.status(),hooks=dict(self.gate.metrics),hook_overruns=list(self.gate.overruns),hook_overrun_overflow=self.gate.overrun_overflow,hooks_inflight=len(self.gate.inflight),raw_bytes=self.archive.journal.raw_bytes,compressed_bytes=self.archive.journal.stored_bytes,records=self.archive.journal.records,elapsed=time.monotonic()-self.begin,peak_rates={k:dict(v) for k,v in self.peaks.items()},original_proof_queues=[dict(writer_id=id(p.proof_writer),queue_id=id(p.proof_writer.queue),unfinished=p.proof_writer.queue.unfinished_tasks,dropped=p.proof_writer.dropped,rejected=p.proof_writer.rejected,published=p.proof_writer.published) for p in self.providers])
 def watch(self):
  while not self.stop_event.wait(.5):
   try:
    now=time.monotonic();j=self.archive.journal;before,raw,stored,n=self.last_rate;dt=now-before;peak=self.peaks['warmup' if now-self.begin<120 else 'steady']
    for k,v in [('decoded',(j.raw_bytes-raw)/dt),('compressed',(j.stored_bytes-stored)/dt),('envelopes',(j.records-n)/dt)]:peak[k]=max(peak[k],v)
    self.last_rate=(now,j.raw_bytes,j.stored_bytes,j.records)
    s=self.status();atomic(self.root/'health.json',s)
    reason=None
    if (self.root/'stop-request.json').exists():
     request=json.loads((self.root/'stop-request.json').read_bytes());need(request['run_id']==self.config['run_id'] and request['role']==self.role,'STOP_IDENTITY');reason='OPERATOR_FINISH'
    if time.monotonic()-self.begin>=self.config['duration_seconds']:reason='DURATION_LIMIT'
    if s['writer']['archive_failed'] or s['writer']['losses']:reason='RECORDER_LOSS_OR_FAILURE';self.failure=reason
    if self.gate.reason:reason=self.gate.reason;self.failure=reason
    for key,n in list(self.gate.metrics.items()):
     if key.endswith(':calls') and n>=100 and self.gate.metrics[key[:-6]+':over_1ms']/n>.01:reason='HOOK_P99_OVER_1MS';self.failure=reason
    if reason:self.stop(reason);return
    if now>=self.next_health:
     # Control-thread serialization only; bounded 1 Hz cumulative counters in
     # the existing archive permit measured arrival/drain deficit analysis.
     self.next_health=now+1
     telemetry=dict(schema='BTC15_CAPTURE_FLOW_V1',elapsed=now-self.begin,
                    observed_at=time.time(),phase='warmup' if now-self.begin<120 else 'steady',
                    writer=s['writer'],hooks=s['hooks'],records=s['records'],
                    raw_bytes=s['raw_bytes'],compressed_bytes=s['compressed_bytes'])
     raw=canonical(telemetry);need(len(raw)<=65536,'HEALTH_TELEMETRY_BOUND')
     self.emit('RECORDING_HEALTH',raw=raw)
   except Exception as e:
    self.failure='CONTROL_FAILURE:'+type(e).__name__;self.stop(self.failure);return
 def stop(self,reason='OPERATOR_FINISH',timeout=5):
  with self.stop_lock:
   if self.stopped:return self.status()
   if not hasattr(self,'stop_reason'):self.stop_reason=reason
   admitted=self.gate.disable();self.stop_event.set()
   if not admitted:
    self.failure='ADMISSION_STOP_TIMEOUT';atomic(self.root/'terminal-status.json',self.status())
    if not getattr(self,'admission_recovery',None):
     def retry_admission():
      if self.gate.lock.acquire(timeout=30):self.gate.lock.release();self.stop('LATE_ADMISSION_STOP',timeout=5)
     self.admission_recovery=threading.Thread(target=retry_admission,daemon=True,name='recorder-bounded-admission-recovery');self.admission_recovery.start()
    return self.status()
   # Gate closed before writer close. Native wrappers, queues and caches stay installed.
   hook_deadline=time.monotonic()+.25
   while self.gate.inflight and time.monotonic()<hook_deadline:time.sleep(.001)
   if self.gate.inflight:self.failure=self.failure or 'HOOK_DRAIN_TIMEOUT'
   if not self.writer._closing:
    if self.gate.overruns:
     self.writer.submit_observation('RECORDING_HEALTH',raw=canonical(dict(schema='BTC15_HOOK_OVERRUN_V1',samples=list(self.gate.overruns),overflow=self.gate.overrun_overflow,inflight=len(self.gate.inflight))))
    self.writer.submit_observation('RECORDING_BOUNDARY',reason=self.stop_reason,observed_at=time.time(),native_owners_continue=True)
   # All producer admission has ended. Atomic CPython flag avoids an unbounded
   # acquisition of the original writer's accounting lock during live stop.
   self.writer._closing=True;self.writer._thread.join(timeout);done=not self.writer._thread.is_alive()
   if not done:
    # Preserve the initiating failure (e.g. OVERSIZE/queue loss); a timeout
    # is additional evidence, never a replacement diagnosis or a clean seal.
    self.failure=self.failure or 'DRAIN_TIMEOUT';self.drain_timed_out=True
    atomic(self.root/'terminal-status.json',dict(self.status(),reason=self.stop_reason,drain_timed_out=True))
    if not getattr(self,'late_sealer',None):
     def recover():
      self.writer._thread.join(30)
      if not self.writer._thread.is_alive():self.stop('LATE_INCOMPLETE_SEAL',timeout=.1)
     self.late_sealer=threading.Thread(target=recover,daemon=True,name='recorder-bounded-late-seal');self.late_sealer.start()
    return self.status()
   self.stopped=True
   if self.control is not threading.current_thread():self.control.join(1)
   if not self.writer.status()['terminal_accounting_complete']:
    self.failure=self.failure or 'DURABILITY_ACCOUNTING_INCOMPLETE'
   s=self.status();s['status']='INCOMPLETE' if s['failure'] or s['writer']['archive_failed'] or s['writer']['losses'] else 'SEALED'
   s['reason']=self.stop_reason;s['drain_timed_out']=getattr(self,'drain_timed_out',False);s['journals']=self.gate.journals;s['stopped_at']=time.time();atomic(self.root/'terminal-status.json',s)
   files=[]
   for p in sorted(self.root.rglob('*')):
    if p.is_file() and (p.name.endswith('.jsonl.gz') or p.name in ('identity.json','terminal-status.json')):
     files.append(dict(path=str(p.relative_to(self.root)),size=p.stat().st_size,sha256=file_sha(p)))
   atomic(self.root/'seal.json',dict(schema='BTC15_ROLE_SEAL_V1',run_id=self.config['run_id'],role=self.role,identity=json.loads((self.root/'identity.json').read_bytes()),session=self.archive.session,last_sequence=self.archive.seq,last_sha256=self.archive.previous,status=s['status'],files=files,journals=self.gate.journals))
   return s
