"""Producer-only wiring. Original functions execute once, with unchanged inputs."""
import ast
from collections import deque
from dataclasses import asdict
from itertools import islice
import errno
import hashlib
import json
import os
from pathlib import Path
import sys
import socket
import select
import threading
import time
import types
import uuid
import weakref
from urllib.request import urlopen

from sprint_evidence.passive_capture import Producer, Identity, digest, observed_copy, SCHEMA, GATE_FIELDS, MAX_MEMBER
from capture2.wire import freeze,owned_size,envelope,frame,MAX_FRAME,MAX_BATCH,MAX_BATCH_RAW
from sprint_evidence.quote_receive_capture import QuoteReceiveCapture, instrument as quote_tree, SOURCE_SHA256
from sprint_evidence.source_witness_capture import SourceWitnessCapture, NATIVE_SHA

ROOT = Path(__file__).resolve().parents[1]
_local = threading.local()
_config = None
_expired = False
_population = None


class SenderPopulation:
    """Fixed sender slots; terminal metadata survives sender/thread retirement.

    Admission never waits. The single accountant does all reaping, status I/O,
    and counter aggregation. A slot is released only after its thread has exited.
    Exhaustion/contended admission disables qualification explicitly.
    """
    def __init__(self,directory,end_boot_ns,*,max_active=16,max_created=16384):
        self.directory=Path(directory);self.end_boot_ns=end_boot_ns
        self.max_active=max_active;self.max_created=max_created
        self.lock=threading.Lock();self.active={};self.created=0;self.high_water=0
        self.retired=self.flushed=self.incomplete=0
        self.retired_reports=[]
        self.offered=self.accepted=self.delivered=self.dropped=self.retried=0
        self.rejections=deque(maxlen=1024);self.rejected=0;self.fault=None;self.stopping=False
        self.path=self.directory/('population-'+str(os.getpid())+'.json')
        self.thread=threading.Thread(target=self._run,name='capture-population',daemon=True)
        self.thread.start()

    def admit(self,transport):
        if not self.lock.acquire(False):
            self.rejections.append(dict(producer_id=transport.owner.identity.producer_id,reason='ADMISSION_CONTENTION'))
            self.rejected+=1;self.fault='ADMISSION_CONTENTION'
            raise RuntimeError('CAPTURE_ADMISSION_CONTENTION')
        try:
            reason=('POPULATION_STOPPED' if self.stopping or self.fault else
                    'SENDER_LIMIT' if len(self.active)>=self.max_active else
                    'STREAM_LIMIT' if self.created>=self.max_created else None)
            if reason:
                self.rejections.append(dict(producer_id=transport.owner.identity.producer_id,reason=reason))
                self.rejected+=1;self.fault=reason
                raise RuntimeError('CAPTURE_'+reason)
            self.active[transport.owner.identity.producer_id]=transport
            self.created+=1;self.high_water=max(self.high_water,len(self.active))
        finally:self.lock.release()

    def snapshot(self):
        with self.lock:
            live=list(self.active.values())
            return dict(process_id=os.getpid(),observed_boot_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),
                        created=self.created,active=len(live),retired=self.retired,
                        census_version=1,active_records=[t.snapshot() for t in live],
                        retired_reports=list(self.retired_reports),
                        retired_flushed=self.flushed,retired_incomplete=self.incomplete,
                        active_ids=[t.owner.identity.producer_id for t in live],
                        active_sender_high_water=self.high_water,max_active_senders=self.max_active,
                        max_created_streams=self.max_created,accountant_threads=1,
                        max_buffer_bytes_per_sender=16*1024*1024,
                        max_aggregate_buffer_bytes=self.max_active*16*1024*1024,
                        active_buffer_bytes=sum(t.enqueued_bytes-t.delivered_bytes for t in live),
                        retired_offered=self.offered,retired_accepted=self.accepted,
                        retired_delivered=self.delivered,retired_dropped=self.dropped,
                        retired_retried=self.retried,admission_rejected=self.rejected,
                        rejected_attempts=list(self.rejections),rejected_details_omitted=self.rejected-len(self.rejections),
                        fault=self.fault,stopping=self.stopping)

    def _reap(self):
        with self.lock:live=list(self.active.items())
        for pid,t in live:
            if not t.finished or t.thread.is_alive():continue
            origin=t.origin()
            if origin is not None and origin.is_alive() and not self.stopping:
                if t.last_transport_error:self.fault='TRANSPORT_FINISHED_EARLY'
                continue
            # Final status includes any offers after a terminal transport error.
            # Disk I/O must not hold the admission lock.
            t._report();s=t.snapshot()
            with self.lock:
                self.retired+=1
                self.flushed+=int(s['flushed']);self.incomplete+=int(not s['complete'])
                for target,key in [('offered','offered'),('accepted','accepted'),('delivered','delivered'),
                                   ('dropped','producer_dropped'),('retried','retry_eagain')]:
                    setattr(self,target,getattr(self,target)+s[key])
                if not s['complete']:self.fault='RETIRED_INCOMPLETE'
                self.retired_reports.append(dict(producer_id=pid,path=Path(t.status_path).name if t.status_path else None))
                del self.active[pid]
                t._terminal=s;t.owner=None;t.origin=None;t.queue.clear()

    def _run(self):
        next_report=0
        while True:
            self._reap()
            if time.clock_gettime_ns(time.CLOCK_BOOTTIME)>=self.end_boot_ns:self.stopping=True
            if time.monotonic()>=next_report or self.stopping:
                try:
                    tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.snapshot()));os.replace(tmp,self.path)
                except Exception:self.fault='POPULATION_STATUS_WRITE'
                next_report=time.monotonic()+1
            if self.stopping and not self.active:return
            time.sleep(.01)

    def close(self):
        self.stopping=True
        for t in list(self.active.values()):t.close()


class BufferedDatagram:
    """Single producer, single sender. Native offer never retries or waits.

    A finite byte/record FIFO absorbs receiver scheduling/compression/fsync
    stalls. Only the daemon sender retries EAGAIN. Full/expired buffers reject
    explicitly through the existing Producer drop counter. CPython deque append
    and popleft are atomic; each byte counter has exactly one writing thread.
    No lock, disk operation, network wait or ACK is added to the native offer.
    """
    def __init__(self,address,*,end_boot_ns,status_path=None,sock=None,
                 max_bytes=16*1024*1024,max_packets=16384,population=None):
        if not 0<max_bytes<=16*1024*1024 or not 0<max_packets<=16384:raise ValueError('BUFFER_BOUND')
        self.address=address;self.end_boot_ns=end_boot_ns;self.status_path=status_path
        self.population=population;self.origin=None;self._terminal=None;self.retirement_reason=None
        self.max_bytes=max_bytes;self.max_packets=max_packets;self.queue=deque();self.inflight=[]
        self.enqueued_bytes=self.delivered_bytes=self.accepted=self.delivered=0
        self.retries=self.rejected=self.high_water_bytes=self.high_water_packets=0
        self.rejected_full=self.rejected_ended=self.backpressure_wait_ns=0
        self.first_rejection=self.last_rejection=None
        self.last_delivered_sequence=0;self.last_transport_error=None
        self.serialized=self.frames=self.wire_bytes=self.serialization_ns=0
        self.stopping=False;self.finished=False;self.owner=None;self.terminal_report_written=False
        self.sock=sock

    def start(self,owner):
        self.owner=owner;self.origin=weakref.ref(threading.current_thread())
        self.thread=threading.Thread(target=self._run,name='capture-datagram-drain',daemon=True)
        if self.population is not None:self.population.admit(self)
        try:self.thread.start()
        except Exception:
            self.last_transport_error='SENDER_START_FAILED';self.finished=True
            raise

    def handoff(self,event,charge):
        pending=self.enqueued_bytes-self.delivered_bytes
        if self.stopping or self.finished or time.clock_gettime_ns(time.CLOCK_BOOTTIME)>=self.end_boot_ns:
            self._reject('CAPTURE_BUFFER_ENDED');self.rejected_ended+=1;raise BufferError('CAPTURE_BUFFER_ENDED')
        if len(self.queue)+len(self.inflight)>=self.max_packets or pending+charge>self.max_bytes:
            self._reject('CAPTURE_BUFFER_FULL');self.rejected_full+=1;raise BufferError('CAPTURE_BUFFER_FULL')
        self.enqueued_bytes+=charge;self.accepted+=1
        self.queue.append((event,charge))
        self.high_water_bytes=max(self.high_water_bytes,pending+charge)
        self.high_water_packets=max(self.high_water_packets,len(self.queue)+len(self.inflight))

    def _reject(self,reason):
        self.rejected+=1
        value=dict(reason=reason,sequence=self.owner.sequence,boot_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME))
        if self.first_rejection is None:self.first_rejection=value
        self.last_rejection=value

    def snapshot(self):
        if self._terminal is not None:return dict(self._terminal)
        flushed=self.accepted==self.delivered and not self.queue and not self.inflight
        complete=flushed and self.owner.offered==self.delivered and not self.owner.dropped and not self.last_transport_error
        return dict(producer_id=self.owner.identity.producer_id,process_id=os.getpid(),
                    observed_boot_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),
                    offered=self.owner.offered,producer_dropped=self.owner.dropped,
                    producer_last_error=self.owner.last_error,accepted=self.accepted,
                    delivered=self.delivered,last_delivered_sequence=self.last_delivered_sequence,
                    pending_packets=len(self.queue)+len(self.inflight),pending_bytes=self.enqueued_bytes-self.delivered_bytes,
                    retry_eagain=self.retries,rejected=self.rejected,
                    rejected_full=self.rejected_full,rejected_ended=self.rejected_ended,
                    first_rejection=self.first_rejection,last_rejection=self.last_rejection,
                    backpressure_wait_ns=self.backpressure_wait_ns,
                    serialized=self.serialized,frames=self.frames,wire_bytes=self.wire_bytes,serialization_ns=self.serialization_ns,
                    buffer_basis="CONSERVATIVE_OWNED_SNAPSHOT_HEAP; SERIALIZED_BATCH_WORKING_SET_SEPARATE",
                    max_serialized_working_bytes=8*1024*1024,
                    high_water_bytes=self.high_water_bytes,high_water_packets=self.high_water_packets,
                    max_bytes=self.max_bytes,max_packets=self.max_packets,
                    finished=self.finished,last_transport_error=self.last_transport_error,
                    retirement_reason=self.retirement_reason,flushed=flushed,complete=complete,
                    state=('RETIRED_FLUSHED' if complete else 'RETIRED_INCOMPLETE') if self.finished else 'ACTIVE',
                    basis='OFF_PATH_COUNTER_SNAPSHOT; concurrent offer may be in progress')

    def _report(self):
        if self.status_path is None:return
        try:
            path=Path(self.status_path);tmp=path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.snapshot()));os.replace(tmp,path)
            if self.finished:self.terminal_report_written=True
        except Exception as exc:self.last_transport_error='STATUS_WRITE_'+type(exc).__name__

    def _run(self):
        next_report=0
        try:
            if self.sock is None:self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
            self.sock.setblocking(False);self.sock.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,MAX_FRAME)
            # Connected AF_UNIX poll tracks the receiver queue. An unconnected
            # socket is spuriously writable; fixed 1 ms sleeps throttle bursts.
            self.sock.connect(self.address)
            while time.clock_gettime_ns(time.CLOCK_BOOTTIME)<self.end_boot_ns+5_000_000_000:
                if time.clock_gettime_ns(time.CLOCK_BOOTTIME)>=self.end_boot_ns:
                    self.stopping=True
                if time.monotonic()>=next_report:
                    self._report();next_report=time.monotonic()+1
                if not self.queue:
                    origin=self.origin()
                    if self.stopping or origin is None or not origin.is_alive():
                        self.retirement_reason='EXPLICIT_CLOSE' if self.stopping else 'ORIGIN_THREAD_EXITED'
                        break
                    time.sleep(.001);continue
                # One immutable snapshot FIFO; encoding and gzip live only here.
                # Queue entries remain charged until the complete frame is sent.
                before=time.monotonic_ns();rows=[];charges=[];size=0
                # Sender owns a private in-flight batch. The native producer only
                # appends to the shared deque and never waits on sender work.
                while self.queue and len(self.inflight)<MAX_BATCH:
                    event,charge=self.queue.popleft()
                    encoded=envelope(event,self.owner.key)
                    if self.inflight and size+len(encoded)+1>MAX_BATCH_RAW:
                        self.queue.appendleft((event,charge));break
                    self.inflight.append((event,charge,encoded));size+=len(encoded)+1
                rows=[(event,encoded) for event,charge,encoded in self.inflight]
                charges=[charge for event,charge,encoded in self.inflight]
                raw=frame(rows,self.owner.identity_record,self.owner.key)
                self.serialized+=len(rows);self.serialization_ns+=time.monotonic_ns()-before
                while True:
                    try:
                        if self.sock.sendto(raw,socket.MSG_DONTWAIT,self.address)!=len(raw):raise OSError('SHORT_DATAGRAM')
                        break
                    except OSError as exc:
                        if exc.errno not in (errno.EAGAIN,errno.EWOULDBLOCK,errno.ENOBUFS):raise
                        self.retries+=1;before=time.monotonic_ns()
                        select.select([],[self.sock],[],.05)
                        self.backpressure_wait_ns+=time.monotonic_ns()-before
                        if time.clock_gettime_ns(time.CLOCK_BOOTTIME)>=self.end_boot_ns+5_000_000_000:
                            raise TimeoutError('CAPTURE_FLUSH_DEADLINE')
                for (event,encoded),charge in zip(rows,charges):
                    self.delivered_bytes+=charge;self.delivered+=1
                    self.last_delivered_sequence=event['sequence']
                self.inflight.clear()
                self.frames+=1;self.wire_bytes+=len(raw)
        except Exception as exc:self.last_transport_error=type(exc).__name__+':'+str(exc)[:120]
        finally:
            if self.retirement_reason is None:self.retirement_reason='TRANSPORT_ERROR' if self.last_transport_error else 'CAPTURE_DEADLINE'
            self.finished=True;self._report()
            if self.sock is not None:self.sock.close()

    def close(self):
        self.stopping=True


def config():
    global _config
    if _config is None:
        _config = json.loads(Path(os.environ['BTC15_CAPTURE_CONFIG']).read_text())
    return _config


class CaptureProducer(Producer):
    def __init__(self,address,identity,key,*,end_boot_ns,status_path=None,**kwargs):
        transport=BufferedDatagram(address,end_boot_ns=end_boot_ns,status_path=status_path,**kwargs)
        super().__init__(address,identity,key,sock=transport)
        self.identity_record=asdict(identity)
        template=dict(schema=SCHEMA,identity=self.identity_record,sequence=0,kind="",
            hook_read=dict(wall_ns=0,before_boot_ns=0,after_boot_ns=0,clock_qualified=False),prior_dropped=0,signal_only=True,orders=False,body=None)
        self.fixed_charge=owned_size(template)+512
        transport.start(self)

    def offer(self,kind,body,*,raw_quote=None,origin_sequence=None,common_member=None):
        if not self.enabled:return False
        self.sequence+=1;self.offered+=1
        try:
            before=time.clock_gettime_ns(time.CLOCK_BOOTTIME);wall=time.time_ns();after=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
            copied,body_charge=freeze(body)
            event=dict(schema=SCHEMA,identity=self.identity_record,sequence=self.sequence,kind=kind,
                hook_read=dict(wall_ns=wall,before_boot_ns=before,after_boot_ns=after,clock_qualified=False),
                prior_dropped=self.dropped,signal_only=True,orders=False,body=copied)
            if raw_quote is not None:event['_capture_raw_quote']=raw_quote
            if origin_sequence is not None:event['_capture_origin_sequence']=origin_sequence
            if common_member is not None:event['_capture_common_member']=common_member
            self.sock.handoff(event,self.fixed_charge+body_charge+sys.getsizeof(kind)+sys.getsizeof(raw_quote)+sys.getsizeof(common_member));self.sent+=1;self.last_error=None;return True
        except Exception as exc:
            self.dropped+=1;self.last_error=type(exc).__name__+':'+str(exc)[:120];return False

    def protected(self,state,local_values):
        try:
            copied=observed_copy(state);sequence=self.sequence+1
            okay=self.offer('PROTECTED_GENERATION',dict(state=copied,
                gate_values={k:local_values.get(k) for k in GATE_FIELDS},generation_id=None,state_sha256=None,
                completed_delivery_utc=None,accepted_origin_id=None,basis='EXISTING_build_state_RETURN_NO_REEVALUATION'),
                origin_sequence=sequence)
            self.last_generation=(state,copied,sequence) if okay else None
            return okay
        except Exception:self.last_generation=None;return False

    def published(self,state):
        try:
            copied=observed_copy(state);prior=self.last_generation
            linked=prior is not None and prior[0] is state and prior[1]==copied
            return self.offer('PROTECTED_FILE_WRITE_COMPLETED',dict(state=copied,browser_delivery_utc=None,
                state_sha256=None,generation_id=None,
                linkage_status='OBSERVED_SAME_OBJECT_UNCHANGED' if linked else 'UNAVAILABLE_GENERATION_LINK',
                basis='EXISTING_LOCAL_FILE_WRITE_RETURNED_NOT_BROWSER_DELIVERY'),origin_sequence=prior[2] if linked else None)
        except Exception:return False

    def common_member(self,member,offset):
        if type(member) is not bytes or not 0<len(member)<=MAX_MEMBER:
            self.sequence+=1;self.offered+=1;self.dropped+=1;self.last_error='COMMON_MEMBER_BUDGET';return False
        return self.offer('COMMON_MEMBER',dict(member_base64=None,original_offset=offset,byte_count=len(member),sha256=None,
            basis='EXISTING_APPEND_FSYNC_COMPLETED_MEMBER_UNCHANGED'),common_member=member)


class DeferredQuoteCapture(QuoteReceiveCapture):
    def _emit(self,raw,error,before,after,ticker,epoch):
        body=dict(schema='BTC15_QUOTE_RECEIVE_OBSERVATION_V1',ticker=ticker,connection_epoch=epoch,
            time_namespace_id=self.time_namespace_id,recv_call_before_boot_ns=before,recv_return_after_boot_ns=after,
            bracket_available=before is not None and after is not None and before<=after,
            source_timestamp=None,native_book_accepted=None,source_clock_qualified=False,
            raw_base64=None,raw_sha256=None,raw_bytes=None,raw_type=None,
            status='RECEIVE_ERROR' if error else 'OBSERVED',error_type=error,guidance=None,manual_fill=None)
        retained=None
        if error is None:
            if type(raw) not in (str,bytes):body['status']='UNAVAILABLE_RAW_TYPE'
            else:
                body['raw_type']='str' if type(raw) is str else 'bytes'
                if len(raw)>96000:body['status']='UNAVAILABLE_OVERSIZE'
                else:retained=raw
        return self.producer.offer('LIFECYCLE_EMISSION',dict(emission=body,
            basis='ALREADY_EMITTED_OBJECT; upstream_ids_REQUIRED_FOR_LINKAGE'),raw_quote=retained)


def producer(source):
    global _expired,_population
    if _expired:raise RuntimeError('BOUNDED_CAPTURE_ENDED')
    if time.clock_gettime_ns(time.CLOCK_BOOTTIME) >= config()['end_boot_ns']:
        _expired=True
        raise RuntimeError('BOUNDED_CAPTURE_ENDED')
    cache = getattr(_local, 'producers', None)
    if cache is None:
        cache = {}; _local.producers = cache
    if source not in cache:
        c = config()
        if source not in c['source_hashes']:
            raise ValueError('UNREGISTERED_SOURCE')
        if _population is None:raise RuntimeError('CAPTURE_POPULATION_UNAVAILABLE')
        if _population.fault:raise RuntimeError('CAPTURE_POPULATION_'+_population.fault)
        ident = Identity(c['mode']+':'+str(os.getpid())+':'+str(threading.get_native_id())+':'+uuid.uuid4().hex,
                         c['build'], source, c['run_id'], c['clock_domain'], c['boot_id'])
        status_path=Path(c['directory'])/('transport-'+digest(ident.producer_id.encode())+'.json')
        cache[source] = CaptureProducer(c['socket'], ident, bytes.fromhex(c['key']),
                                       end_boot_ns=c['end_boot_ns'],status_path=status_path,population=_population)
    return cache[source]


_population_init_lock=threading.Lock()
def population():
    global _population
    if _population is not None:return _population
    if not _population_init_lock.acquire(False):raise RuntimeError('CAPTURE_POPULATION_STARTING')
    try:
        if _population is None:
            c=config();_population=SenderPopulation(c['directory'],c['end_boot_ns'])
        return _population
    finally:_population_init_lock.release()


class Proxy:
    """Each original producing thread owns its own bounded producer state."""
    def __init__(self, source): self.source = source; self.local = threading.local()
    def native(self, ns, kind='NATIVE_CYCLE'):
        try: return producer(self.source).native(ns, kind)
        except Exception: return False
    def fair_input(self, loc, glob):
        try: return producer(self.source).fair_input(loc, glob)
        except Exception: return False
    def protected(self, state, loc):
        try:
            # Chart history is not a decision input. Preserve every decision/source
            # field and the existing gate values without traversing display history.
            selected = {k:v for k,v in state.items() if k != 'chart'}
            self.local.last = (state, selected)
            return producer(self.source).protected(selected, loc)
        except Exception: return False
    def published(self, state):
        try:
            previous = getattr(self.local, 'last', None)
            selected = previous[1] if previous and previous[0] is state else {k:v for k,v in state.items() if k != 'chart'}
            return producer(self.source).published(selected)
        except Exception: return False
    def lifecycle(self, result):
        try: return producer(self.source).lifecycle(result)
        except Exception: return False


native_producer = Proxy(NATIVE_SHA)


class SourceProxy:
    def native_consumed(self, selected, cut, checked):
        try: return SourceWitnessCapture(producer(NATIVE_SHA)).native_consumed(selected, cut, checked)
        except Exception: return False


sources_tap = SourceProxy()


class Quotes:
    def recv(self, ws, ticker, epoch, *args, **kwargs):
        # Setup failure cannot prevent the original single receive.
        try:
            tap = DeferredQuoteCapture(producer(SOURCE_SHA256), time_namespace_id=config()['time_namespace_id'])
        except Exception:
            return ws.recv(*args, **kwargs)
        return tap.recv(ws, ticker, epoch, *args, **kwargs)
    def consumed(self, proof, quotes):
        try:
            if proof is None or quotes is None:return False
            return producer(SOURCE_SHA256).lifecycle(dict(schema='BTC15_QUOTE_CONSUMED_V1',
                proof={k:v for k,v in proof.items() if k!='events'}, quotes=quotes,
                basis='ORIGINAL_Provider.consume_RETURN; NO_EXTRA_READ_OR_VALIDATION'))
        except Exception: return False

    def tick(self):
        try:return time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        except Exception:return None
    def book(self, evidence, ticker, epoch, before):
        if _expired:return False
        try:
            after=self.tick();book=evidence.book
            best={}
            for side in ('yes','no'):
                level=max(book.levels[side]) if book.levels[side] else None
                best[side]=None if level is None else dict(price=str(level),quantity=str(book.levels[side][level]))
            return producer(SOURCE_SHA256).lifecycle(dict(schema='BTC15_QUOTE_APPLIED_V1',
                ticker=ticker,epoch=epoch,time_namespace_id=config()['time_namespace_id'],
                before_boot_ns=before,after_boot_ns=after,
                market_id=book.market_id,sid=book.sid,sequence=book.seq,exchange_ts_ms=book.ts_ms,
                valid=book.valid,overflow=evidence.overflow,best_bids=best,
                basis='ORIGINAL_Evidence.accept_RETURN_AND_LOCK_RELEASE; NOT_A_FILL'))
        except Exception:return False


def quote_composed_tree(raw):
    tree=quote_tree(raw)
    provider=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Provider')
    fn=next(n for n in provider.body if isinstance(n,ast.FunctionDef) and n.name=='consume')
    # finally runs after every original with-lock exit, including return quotes.
    # The original local proof is used; no additional book read/validation occurs.
    wrapper=ast.parse("try:\n    pass\nfinally:\n    _ground_quote.consumed(locals().get('proof'), locals().get('_capture_returned_quotes'))").body[0]
    class Returned(ast.NodeTransformer):
        count=0
        def visit_Return(self,node):
            if isinstance(node.value,ast.Name) and node.value.id=='quotes':
                self.count+=1
                return [ast.parse('_capture_returned_quotes = quotes').body[0],node]
            return node
    returned=Returned();returned.visit(fn)
    if returned.count!=1:raise ValueError('QUOTE_RETURN_SEAM')
    wrapper.body=fn.body;fn.body=[wrapper]
    session=next(n for n in provider.body if isinstance(n,ast.FunctionDef) and n.name=='session')
    class AppliedHook(ast.NodeTransformer):
        count=0
        def visit_With(self,node):
            if any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='accept' for n in ast.walk(node)):
                self.count+=1
                before=ast.parse('_capture_apply_before = _ground_quote.tick()').body[0]
                after=ast.parse('_ground_quote.book(evidence, ticker, epoch, _capture_apply_before)').body[0]
                return [before,node,after]
            return node
    hook=AppliedHook();hook.visit(session)
    if hook.count!=1:raise ValueError('QUOTE_APPLY_SEAM')
    return ast.fix_missing_locations(tree)


def install_quotes():
    name='btc15_kalshi_quote_provenance_v1'
    if name in sys.modules:raise ValueError('QUOTE_MODULE_ALREADY_LOADED')
    path=ROOT/(name+'.py');tree=quote_composed_tree(path.read_bytes())
    module=types.ModuleType(name);module.__file__=str(path);module._ground_quote=Quotes()
    sys.modules[name]=module
    try: exec(compile(ast.fix_missing_locations(tree),str(path),'exec'),module.__dict__)
    except BaseException:
        sys.modules.pop(name,None);raise


def serve(handler):
    """Bounded read-only proxy to the detached writer; no native evaluation."""
    if not handler.path.startswith('/ground-zero/'):
        return False
    try:
        if len(handler.path)>200: raise ValueError('PATH_BUDGET')
        with urlopen('http://127.0.0.1:8769'+handler.path, timeout=2) as r:
            body=r.read(2*1024*1024+1);code=r.status;headers=dict(r.headers)
        if len(body)>2*1024*1024: raise ValueError('BODY_BUDGET')
    except Exception:
        code=503;body=b'{"status":"UNAVAILABLE_CAPTURE_READER"}';headers={}
    handler.send_response(code)
    handler.send_header('Content-Type',headers.get('Content-Type','application/json'))
    handler.send_header('Content-Length',str(len(body)))
    handler.send_header('Cache-Control','no-store')
    for key,value in headers.items():
        if key.lower().startswith('x-capture-'): handler.send_header(key,value)
    handler.end_headers();handler.wfile.write(body)
    return True


# Initialize off the strategy execution path, under Python's module import lock.
# A failed passive accountant leaves hooks unavailable; it never blocks launch.
if os.environ.get('BTC15_CAPTURE_CONFIG'):
    try:population()
    except Exception:pass
