"""Append-only seams into pinned owners. No strategy reconstruction or polling."""
import ast,inspect,json,textwrap,time,types
from urllib.parse import urlsplit
from .policy import canonical,sha,need

def compile_function(original,transform,capture):
 tree=ast.parse(textwrap.dedent(inspect.getsource(original)));fn=tree.body[0];fn.decorator_list=[]
 fn=transform.visit(fn);scope=dict(original.__globals__);scope['_rec']=capture
 exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'<btc15-recorder-seam>','exec'),scope)
 return scope[fn.name]

class Adapters:
 def __init__(self,capture):self.c=capture;self.http_receipts={};self.brti_receipts={}
 def http_get(self,original,url,*args,**kwargs):
  # Return the same response/exception. Never copy headers, auth or arbitrary URLs.
  try:result=original(url,*args,**kwargs)
  except Exception:
   self.c.emit('SOURCE_GAP',reason='EXISTING_HTTP_OWNER_EXCEPTION',observed_at=time.time());raise
  if not self.c.gate.active:return result
  at=time.time();beg=time.perf_counter_ns()
  try:
   u=urlsplit(url);allowed=(u.hostname in ('api.exchange.coinbase.com','external-api.kalshi.com','api.elections.kalshi.com') and (u.path.startswith('/products/BTC-USD/') or u.path.startswith('/trade-api/v2/markets') or u.path=='/trade-api/v2/series/KXBTC15M'))
   if allowed:
    raw=result.content
    self.c.emit('ORIGINAL_RESPONSE',raw=raw,endpoint=u.scheme+'://'+u.netloc+u.path,received_at=at,status_code=result.status_code,receipt_basis='HTTP_GET_RETURN_BEFORE_NATIVE_DECODE',source='EXISTING_OWNER_RESPONSE')
    self.http_receipts[__import__('threading').get_ident()]=(sha(raw),at)
    if '/trade-api/' in u.path:self.c.emit('HTTP_RESPONSE',raw=raw,endpoint=u.path,received_at=at,receipt_basis='HTTP_GET_RETURN_BEFORE_NATIVE_DECODE',source='EXISTING_KALSHI_HTTP')
  except Exception:self.c.gate.gap('CAPTURE_ERROR')
  finally:self.c.gate.overhead(beg,'HTTP_RESPONSE')
  return result
 def completed(self,frame,original):
  if not self.c.gate.active:return
  # Startup-only accepted native cache. No later receipt is backdated to candle end.
  at=time.time()
  try:
   from .candle_schema import acceptance_rows,SCHEMA,PRODUCER_SHA256
   batch=[];meta=dict(accepted_at=at,basis='NATIVE_COMPLETED_CACHE_ACCEPTANCE',clock_schema=SCHEMA,producer_sha256=PRODUCER_SHA256)
   for row in acceptance_rows(frame,original):
    if not self.c.gate.active:return
    batch.append(row)
    if len(batch)==256:self.c.emit('CANDLE_ACCEPTANCE',raw=canonical(batch),**meta);batch=[]
   if batch:self.c.emit('CANDLE_ACCEPTANCE',raw=canonical(batch),**meta)
  except Exception:self.c.gate.gap('CAPTURE_ERROR')
 def brti(self,original,*args,**kwargs):
  try:point=original(*args,**kwargs)
  except Exception:
   self.c.emit('SOURCE_GAP',asset='BRTI',reason='EXISTING_SHARED_CONSUMER_EXCEPTION',observed_at=time.time());raise
  if self.c.gate.active:
   at=time.time();beg=time.perf_counter_ns()
   try:
    raw=canonical(point);self.c.emit('BRTI_READ',raw=raw,received_at=at,receipt_basis='EXISTING_SHARED_CONSUMER_RETURN');self.brti_receipts[__import__('threading').get_ident()]=(sha(raw),at)
   except Exception:self.c.gate.gap('CAPTURE_ERROR')
   finally:self.c.gate.overhead(beg,'BRTI_READ')
  return point
 def bind_pool(self,pool):
  need(not pool.providers,'POOL_MUST_BIND_BEFORE_CREATION');original=pool.factory
  def factory():
   p=original();writer=p.proof_writer;queue=writer.queue
   self.c.observer.bind_provider(p,preserve_proof_writer=True)
   p.proof_writer.evidence_sink=self.c.gate
   self.c.providers.append(p)
   need(p.proof_writer is writer and writer.queue is queue,'NATIVE_PROOF_QUEUE_CHANGED')
   return p
  pool.factory=factory
 def prepare_main(self,original,ns,pool):
  self.c.observer.bind_btc(ns);self.c.observer.bind_delivery(ns['_brti_delivery']);self.bind_pool(pool)
  # Original installs ReadCadence AFTER these wrappers. Soft stop never restores them.
  return original(ns,pool)
 def prepare_v81(self,original,ns,pool):
  self.bind_pool(pool);owner=ns['_qualified_inputs'];get=owner.get;brti=owner.brti_read;snapshot=owner.snapshot
  owner.get=lambda *a,**k:self.http_get(get,*a,**k)
  owner.brti_read=lambda:self.brti(brti)
  def observed():
   thread=__import__('threading').get_ident();self.http_receipts.pop(thread,None);self.brti_receipts.pop(thread,None)
   row=snapshot()
   if self.c.gate.active:
    try:
     from btc15_v2_product.admin import LOCAL
     btc,brti=self.http_receipts[thread],self.brti_receipts[thread]
     self.c.document('V81_INPUT',row,accepted_at=time.time(),receipt_basis='AFTER_EXISTING_REQUIRE_QUALIFIED',btc_response_sha256=btc[0],btc_received_at=btc[1],brti_observation_sha256=brti[0],brti_received_at=brti[1],attempt_id=(getattr(LOCAL,'attempt',None) or {}).get('attempt_id'))
    except Exception:self.c.gate.gap('CAPTURE_ERROR')
   return row
  owner.snapshot=observed
  module=ns['requests']
  class Proxy:
   def __getattr__(proxy,key):return getattr(module,key)
   def get(proxy,*a,**k):return self.http_get(module.get,*a,**k)
  ns['requests']=Proxy()
  return original(ns,pool)
 def instrument(self,original,tree,lane):
  tree=original(tree,lane)
  if lane!='main':return tree
  owner=self
  class Insert(ast.NodeTransformer):
   def visit_Call(self,node):
    self.generic_visit(node)
    if ast.unparse(node.func)=='requests.get':return ast.copy_location(ast.Call(func=ast.Attribute(value=ast.Name(id='_recording_adapter',ctx=ast.Load()),attr='http_get',ctx=ast.Load()),args=[node.func,*node.args],keywords=node.keywords),node)
    return node
   def visit_Assign(self,node):
    self.generic_visit(node)
    if any(isinstance(t,ast.Name) and t.id=='_fair_btc' for t in node.targets):
     need(isinstance(node.value,ast.Call) and ast.unparse(node.value.func)=='_fair_completed_candles','EXACT_COMPLETED_CANDLE_SEAM')
     return [node,*ast.parse('_recording_adapter.completed(_fair_btc, _fair_raw_btc)').body]
    return node
  tree=Insert().visit(tree)
  # Entry is a reference only; the capture was created in the correct process.
  tree.body[0:0]=ast.parse('from ops.live_recording.bootstrap import ACTIVE_ADAPTER as _recording_adapter').body
  return ast.fix_missing_locations(tree)

def bind_journal(c):
 from btc15_v2_product.journal import ORIGINAL_JOURNAL
 class Insert(ast.NodeTransformer):
  count=0
  def visit_Return(self,n):
   if isinstance(n.value,ast.Name) and n.value.id=='seq':
    self.count+=1
    return [*ast.parse("try:\n _rec.mirror_commit(self, raw, seq)\nexcept Exception:\n _rec.gate.gap('CAPTURE_ERROR')").body,n]
   return n
 t=Insert();new=compile_function(ORIGINAL_JOURNAL.commit,t,c);need(t.count==1,'EXACT_JOURNAL_COMMIT_SEAM');ORIGINAL_JOURNAL.commit=new
 def mirror(journal,raw,seq):
  if not c.gate.active:return
  beg=time.perf_counter_ns()
  try:c.emit('NATIVE_RECORD',raw=raw,original_journal=journal.get('journal_id'),sequence=seq,committed_at=time.time(),record_basis='POST_ORIGINAL_COMMIT',lane=journal.get('lane'))
  finally:c.gate.overhead(beg,'NATIVE_COMMIT')
 c.mirror_commit=mirror
 # Existing tested Admin insertion uses already serialized original bytes.
 from ops.recording_workflow.integration import bind_admin_class
 from btc15_v2_product.admin import Admin
 # Minimal facade preserves existing insertion without routing around admission.
 facade=types.SimpleNamespace(enabled=True,bound=[],writer=c.gate)
 bind_admin_class(facade,Admin)

def bind_outcomes(c,adapter):
 import btc15_ladder_settlement_v2 as settlement
 original=settlement.SettlementReader.__init__
 def init(instance,*a,**k):
  original(instance,*a,**k);get=instance.get;instance.get=lambda *a,**k:adapter.http_get(get,*a,**k)
 settlement.SettlementReader.__init__=init
 class Insert(ast.NodeTransformer):
  count=0
  def visit_Assign(self,n):
   if ast.unparse(n.targets[0])=='value' and isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=='receipt':
    self.count+=1
    return [n,*ast.parse("try:\n _rec.document('OUTCOME_ACCEPTANCE',value,response_sha256=__import__('hashlib').sha256(r.content).hexdigest(),accepted_at=__import__('time').time())\nexcept Exception:\n _rec.gate.gap('CAPTURE_ERROR')").body]
   return n
 t=Insert();new=compile_function(settlement.SettlementReader.once,t,c);need(t.count==1,'OUTCOME_RECEIPT_SEAM');settlement.SettlementReader.once=new
 if c.role=='main':
  import btc15_information_native_offpath_candidate as native
  class Closeout(ast.NodeTransformer):
   count=0
   def visit_Expr(self,n):
    if isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=='settlement':
     self.count+=1
     return [*ast.parse("_rec.document('CLOSEOUT_ACCEPTANCE',dict(cohort=row,original_parity=r),accepted_at=time.time(),basis='EXISTING_CLOSEOUT_PRODUCER_AFTER_COHORT_FSYNC')").body,n]
    return n
  t=Closeout();new=compile_function(native._cohort_closeout_worker,t,c);need(t.count==1,'CLOSEOUT_PRODUCER_SEAM');native._cohort_closeout_worker=new

def _install(c):
 adapter=Adapters(c)
 if c.role=='information':
  import btc15_information_service_v1 as service
  from .capture import AsyncInformationArchive
  original=service.DurablePublisher
  def publisher(*a,**k):k['evidence_archive']=AsyncInformationArchive(c.gate);return original(*a,**k)
  service.DurablePublisher=publisher
 else:
  import btc15_v2_product.runtime as runtime
  bind_journal(c);bind_outcomes(c,adapter)
  prepare=runtime.prepare_main if c.role=='main' else runtime.prepare_v81
  if c.role=='main':runtime.prepare_main=lambda ns,pool:adapter.prepare_main(prepare,ns,pool)
  else:runtime.prepare_v81=lambda ns,pool:adapter.prepare_v81(prepare,ns,pool)
  original=runtime.instrument;runtime.instrument=lambda tree,lane:adapter.instrument(original,tree,lane)
 return adapter

def install(c):
 # Bootstrap rollback happens before native owners start. A running recorder
 # never restores functions and cannot remove subsequently installed wrappers.
 bindings=[]
 def save(obj,*names):
  for n in names:bindings.append((obj,n,getattr(obj,n)))
 if c.role=='information':
  import btc15_information_service_v1 as service
  save(service,'DurablePublisher')
 else:
  import btc15_v2_product.runtime as runtime
  from btc15_v2_product.journal import ORIGINAL_JOURNAL
  from btc15_v2_product.admin import Admin
  import btc15_ladder_settlement_v2 as settlement
  save(runtime,'prepare_main','prepare_v81','instrument');save(ORIGINAL_JOURNAL,'commit');save(Admin,'run');save(settlement.SettlementReader,'__init__','once')
  if c.role=='main':
   import btc15_information_native_offpath_candidate as native
   import btc15_brti_shared_consumer_v1 as brti
   save(native,'_cohort_closeout_worker');save(brti,'read_shared_brti')
 try:
  adapter=_install(c)
  if c.role=='main':
   original=brti.read_shared_brti;brti.read_shared_brti=lambda *a,**k:adapter.brti(original,*a,**k)
  return adapter
 except Exception:
  for obj,n,old in reversed(bindings):setattr(obj,n,old)
  raise
