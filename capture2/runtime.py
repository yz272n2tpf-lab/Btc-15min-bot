"""Producer-only wiring. Original functions execute once, with unchanged inputs."""
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
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


def config():
    global _config
    if _config is None:
        _config = json.loads(Path(os.environ['BTC15_CAPTURE_CONFIG']).read_text())
    return _config


def producer(source):
    if time.clock_gettime_ns(time.CLOCK_BOOTTIME) >= config()['end_boot_ns']:
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
        cache[source] = Producer(c['socket'], ident, bytes.fromhex(c['key']))
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
            return producer(SOURCE_SHA256).lifecycle(dict(schema='BTC15_QUOTE_CONSUMED_V1',
                proof={k:v for k,v in proof.items() if k!='events'}, quotes=quotes,
                basis='ORIGINAL_Provider.consume_RETURN; NO_EXTRA_READ_OR_VALIDATION'))
        except Exception: return False


def install_quotes():
    name='btc15_kalshi_quote_provenance_v1'
    if name in sys.modules: raise ValueError('QUOTE_MODULE_ALREADY_LOADED')
    path=ROOT/(name+'.py');raw=path.read_bytes();tree=quote_tree(raw)
    provider=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Provider')
    fn=next(n for n in provider.body if isinstance(n,ast.FunctionDef) and n.name=='consume')
    class ReturnHook(ast.NodeTransformer):
        count=0
        def visit_Return(self,n):
            if isinstance(n.value,ast.Name) and n.value.id=='quotes':
                self.count+=1
                return [ast.parse('_ground_quote.consumed(proof, quotes)').body[0],n]
            return n
    hook=ReturnHook();hook.visit(fn)
    if hook.count!=1: raise ValueError('QUOTE_CONSUMPTION_SEAM')
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
