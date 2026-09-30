"""Producer-only wiring. Original functions execute once, with unchanged inputs."""
import ast
from collections import deque
import errno
import hashlib
import json
import os
from pathlib import Path
import sys
import socket
import threading
import time
import types
import uuid
from urllib.request import urlopen

from sprint_evidence.passive_capture import Producer, Identity, digest
from sprint_evidence.quote_receive_capture import QuoteReceiveCapture, instrument as quote_tree, SOURCE_SHA256
from sprint_evidence.source_witness_capture import SourceWitnessCapture, NATIVE_SHA

ROOT = Path(__file__).resolve().parents[1]
_local = threading.local()
_config = None
_expired = False


class BufferedDatagram:
    """Single producer, single sender. Native offer never retries or waits.

    A finite byte/record FIFO absorbs receiver scheduling/compression/fsync
    stalls. Only the daemon sender retries EAGAIN. Full/expired buffers reject
    explicitly through the existing Producer drop counter. CPython deque append
    and popleft are atomic; each byte counter has exactly one writing thread.
    No lock, disk operation, network wait or ACK is added to the native offer.
    """
    def __init__(self,address,*,end_boot_ns,status_path=None,sock=None,
                 max_bytes=16*1024*1024,max_packets=16384):
        self.address=address;self.end_boot_ns=end_boot_ns;self.status_path=status_path
        self.max_bytes=max_bytes;self.max_packets=max_packets;self.queue=deque()
        self.enqueued_bytes=self.delivered_bytes=self.accepted=self.delivered=0
        self.retries=self.rejected=self.high_water_bytes=self.high_water_packets=0
        self.last_delivered_sequence=0;self.last_transport_error=None
        self.stopping=False;self.finished=False;self.owner=None
        self.sock=sock if sock is not None else socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.sock.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,196608)

    def start(self,owner):
        self.owner=owner
        self.thread=threading.Thread(target=self._run,name='capture-datagram-drain',daemon=True)
        self.thread.start()

    def sendto(self,raw,flags,address):
        if address!=self.address:raise ValueError('CAPTURE_ADDRESS')
        pending=self.enqueued_bytes-self.delivered_bytes
        if self.stopping or self.finished or time.clock_gettime_ns(time.CLOCK_BOOTTIME)>=self.end_boot_ns:
            self.rejected+=1;raise BufferError('CAPTURE_BUFFER_ENDED')
        if len(self.queue)>=self.max_packets or pending+len(raw)>self.max_bytes:
            self.rejected+=1;raise BufferError('CAPTURE_BUFFER_FULL')
        self.enqueued_bytes+=len(raw);self.accepted+=1
        self.queue.append((raw,self.owner.sequence))
        self.high_water_bytes=max(self.high_water_bytes,pending+len(raw))
        self.high_water_packets=max(self.high_water_packets,len(self.queue))
        return len(raw)

    def snapshot(self):
        return dict(producer_id=self.owner.identity.producer_id,
                    observed_boot_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),
                    offered=self.owner.offered,producer_dropped=self.owner.dropped,
                    producer_last_error=self.owner.last_error,accepted=self.accepted,
                    delivered=self.delivered,last_delivered_sequence=self.last_delivered_sequence,
                    pending_packets=len(self.queue),pending_bytes=self.enqueued_bytes-self.delivered_bytes,
                    retry_eagain=self.retries,rejected=self.rejected,
                    high_water_bytes=self.high_water_bytes,high_water_packets=self.high_water_packets,
                    max_bytes=self.max_bytes,max_packets=self.max_packets,
                    finished=self.finished,last_transport_error=self.last_transport_error,
                    basis='OFF_PATH_COUNTER_SNAPSHOT; concurrent offer may be in progress')

    def _report(self):
        if self.status_path is None:return
        try:
            path=Path(self.status_path);tmp=path.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.snapshot()));os.replace(tmp,path)
        except Exception as exc:self.last_transport_error='STATUS_WRITE_'+type(exc).__name__

    def _run(self):
        next_report=0
        try:
            while time.clock_gettime_ns(time.CLOCK_BOOTTIME)<self.end_boot_ns:
                if time.monotonic()>=next_report:
                    self._report();next_report=time.monotonic()+1
                if not self.queue:
                    if self.stopping:break
                    time.sleep(.001);continue
                raw,sequence=self.queue[0]
                try:
                    if self.sock.sendto(raw,socket.MSG_DONTWAIT,self.address)!=len(raw):raise OSError('SHORT_DATAGRAM')
                except OSError as exc:
                    if exc.errno in (errno.EAGAIN,errno.EWOULDBLOCK,errno.ENOBUFS):
                        self.retries+=1;time.sleep(.001);continue
                    self.last_transport_error=type(exc).__name__+':'+str(exc)[:120];break
                self.queue.popleft();self.delivered_bytes+=len(raw);self.delivered+=1
                self.last_delivered_sequence=sequence
        finally:
            self.finished=True;self._report();self.sock.close()

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
        transport.start(self)

    def offer(self,kind,body):
        if kind=='PROTECTED_GENERATION':
            # An observed eligibility event has an immutable capture identity.
            # It is not promoted to a position, fill or native accepted origin.
            state=body.get('state') or {};early=state.get('early') or {}
            body=dict(body,eligible_opportunity_id=body['generation_id'] if early.get('ready') is True else None,
                opportunity_basis='ACTUAL_PROTECTED_ELIGIBILITY_OBSERVATION',
                opportunity_generated_utc=state.get('generated_utc'),
                original_source_utc=state.get('source_timestamp_utc'),
                upstream_final_origin_id=None,upstream_final_origin_status='NOT_EMITTED_BY_THIS_PRODUCER')
        return super().offer(kind,body)


def producer(source):
    global _expired
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
        ident = Identity(c['mode']+':'+str(os.getpid())+':'+str(threading.get_native_id())+':'+uuid.uuid4().hex,
                         c['build'], source, c['run_id'], c['clock_domain'], c['boot_id'])
        status_path=Path(c['directory'])/('transport-'+digest(ident.producer_id.encode())+'.json')
        cache[source] = CaptureProducer(c['socket'], ident, bytes.fromhex(c['key']),
                                       end_boot_ns=c['end_boot_ns'],status_path=status_path)
    return cache[source]


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
            tap = QuoteReceiveCapture(producer(SOURCE_SHA256), time_namespace_id=config()['time_namespace_id'])
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
