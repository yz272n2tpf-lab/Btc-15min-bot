"""Explicit, inert observation seams. Nothing binds or starts at import time.

Install only in an independently authorized runtime. This assignment exercises
these seams solely on offline objects. No source function is replaced on disk.
"""
import ast
from copy import deepcopy
import functools
import inspect
import time
import types


class Observer:
    def __init__(self, writer, *, btc_feed, btc_epoch, brti_feed, clock=time.time):
        self.writer=writer;self.btc_feed=btc_feed;self.btc_epoch=btc_epoch
        self.brti_feed=brti_feed;self.clock=clock

    def emit(self, kind, **fields):
        try:return self.writer.submit_observation(kind,**fields)
        except Exception:
            try:self.writer.gap('CAPTURE_ERROR')
            except Exception:pass
            return False

    def source(self, asset, value, source, receipt, epoch, *, basis='ORIGINAL',accepted=True):
        return self.emit('SOURCE',asset=asset,value=value,source_ts=source,receipt_ts=receipt,
            original_receipt_ts=receipt if basis=='ORIGINAL' else None,available_at=receipt,
            feed=self.btc_feed if asset=='BTC' else self.brti_feed,epoch=epoch,basis=basis,
            accepted_by_owner=accepted,
            epoch_basis='CAPTURE_PROCESS' if asset=='BTC' else 'DELIVERY_OWNER',
            receipt_basis='OWNER_APPLICATION_RECEIPT' if basis=='ORIGINAL' else 'FIRST_RECOVERY_AVAILABILITY')

    def bind_btc(self, ns):
        original=ns['get_btc_spot']
        @functools.wraps(original)
        def observed(*args,**kwargs):
            try:result=original(*args,**kwargs)
            except Exception:
                self.emit('SOURCE_GAP',asset='BTC',reason='OWNER_FETCH_FAILED',observed_at=self.clock())
                raise
            try:
                p=ns['_btc_spot_provenance']
                self.source('BTC',p['price'],p['source_utc'].timestamp(),p['observed_utc'].timestamp(),self.btc_epoch)
            except Exception:self.emit('SOURCE_GAP',asset='BTC',reason='BTC_RECEIPT_UNAVAILABLE')
            return result
        ns['get_btc_spot']=observed

    def bind_btc_tick(self, ns):
        """Alternative pre-gate seam for runtimes that bind their own HTTP adapter.

        Bind this OR bind_btc, not both. Original append/trim remains unchanged.
        """
        original=ns['_ec_append_btc_tick']
        @functools.wraps(original)
        def appended(source,received,value):
            result=original(source,received,value)
            try:self.source('BTC',float(value),source.timestamp(),received.timestamp(),self.btc_epoch)
            except Exception:self.emit('SOURCE_GAP',asset='BTC',reason='BTC_TICK_CAPTURE_FAILED')
            return result
        ns['_ec_append_btc_tick']=appended

    def bind_delivery(self, delivery):
        accept,fail,remember=delivery.accept,delivery.fail,delivery.remember
        @functools.wraps(accept)
        def accepted(value,source,observed,epoch):
            try:result=accept(value,source,observed,epoch)
            except Exception:
                self.source('BRTI',value,source,observed,epoch,accepted=False)
                self.emit('SOURCE_GAP',asset='BRTI',reason='OWNER_REJECTED',observed_at=observed)
                raise
            self.source('BRTI',value,source,observed,epoch)
            return result
        @functools.wraps(fail)
        def failed(observed):
            result=fail(observed)
            self.emit('SOURCE_GAP',asset='BRTI',reason='PRIMARY_UNAVAILABLE',observed_at=observed)
            return result
        @functools.wraps(remember)
        def recovered(points,observed):
            result=remember(points,observed)
            try:
                if not isinstance(points,(list,tuple)) or len(points)>2048:
                    self.writer.gap('OVERSIZE');return result
                for source,value in points:
                    # Existing owner remembers first availability, never source time.
                    receipt=delivery.seen.get((source,value),observed)
                    self.source('BRTI',value,source,receipt,delivery.epoch,basis='RECOVERED')
            except Exception:self.emit('SOURCE_GAP',asset='BRTI',reason='RECOVERY_CAPTURE_FAILED')
            return result
        delivery.accept,delivery.fail,delivery.remember=accepted,failed,recovered

    def http(self, path, raw):
        # Explicit public market/series whitelist. No headers, keys or credentials.
        if path=='/trade-api/v2/markets' or path.startswith('/trade-api/v2/markets/') or path=='/trade-api/v2/series/KXBTC15M':
            self.emit('HTTP_RESPONSE',endpoint=path,raw=raw,received_at=self.clock(),
                      receipt_basis='AFTER_RESPONSE_JSON_DECODE',source='EXISTING_KALSHI_HTTP')

    def bind_http(self, ns):
        """Insert only after the existing JSON decode in the already-bound getter."""
        original=ns['kalshi_get']
        tree=ast.parse(inspect.getsource(original))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef))
        count=0
        class Insert(ast.NodeTransformer):
            def visit_Assign(visitor,node):
                nonlocal count
                if (isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute)
                    and node.value.func.attr=='json' and isinstance(node.value.func.value,ast.Name)
                    and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='data'):
                    count+=1;response=node.value.func.value.id
                    return [node,*ast.parse(f'try:\n _evidence_http(path, {response}.content)\nexcept Exception:\n pass').body]
                return node
        fn=Insert().visit(fn)
        if count!=1:raise ValueError('HTTP_RESPONSE_SEAM_MISMATCH')
        scope=dict(original.__globals__);scope['_evidence_http']=self.http
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'<offline-http-evidence>','exec'),scope)
        ns['kalshi_get']=scope[fn.name]

    def quote_receive(self, raw, ticker, epoch, receipt, monotonic_ns):
        return self.emit('QUOTE_RECEIVE',raw=raw,ticker=ticker,epoch=epoch,received_at=receipt,
            monotonic_ns=monotonic_ns,receipt_basis='WS_RECV_RETURN_APPLICATION_TIME',
            original_wire_receipt=None,source='EXISTING_KALSHI_WEBSOCKET')

    def quote_accept(self, raw, ticker, epoch, receipt, at):
        return self.emit('QUOTE_ACCEPT',raw=raw,ticker=ticker,epoch=epoch,received_at=receipt,
                         accepted_at=at,accept_basis='AFTER_EXISTING_EVIDENCE_ACCEPT')

    def send(self,original,raw,ticker,epoch):
        result=original(raw)
        self.emit('QUOTE_REQUEST',raw=raw,ticker=ticker,epoch=epoch,sent_at=self.clock(),
                  receipt_basis='EXISTING_WS_SEND_RETURN')
        return result

    def bind_provider(self, provider, *, preserve_proof_writer=False):
        """Recompile the same session with three append-only observation seams.

        Uses the SAME ws object and decoder, subscription and refresh requests.
        No constructor, socket opening, subscribe call or provider run is invoked.
        """
        # PreparedProvider.session is already AST-generated, so recover its source
        # from the pinned Provider source and apply the existing clock transform.
        from btc15_v2_product.bootstrap import _accepted_session
        from btc15_kalshi_quote_provenance_v1 import Provider
        tree=ast.parse(inspect.getsource(Provider))
        fn=next(n for n in tree.body[0].body if isinstance(n,ast.FunctionDef) and n.name=='session')
        requests=getattr(self,'capture_requests',False)
        counts=dict(receive=0,accept=0,clock=0,start=0,requests=0)
        class Insert(ast.NodeTransformer):
            def visit_Expr(visitor,node):
                if requests and isinstance(node.value,ast.Call) and ast.unparse(node.value.func)=='ws.send':
                    counts['requests']+=1
                    call=node.value
                    return ast.copy_location(ast.Expr(value=ast.Call(func=ast.Attribute(value=ast.Name(id='_evidence',ctx=ast.Load()),attr='send',ctx=ast.Load()),args=[call.func,*call.args,ast.Name(id='ticker',ctx=ast.Load()),ast.parse("locals().get('epoch')",mode='eval').body],keywords=call.keywords)),node)
                return node
            def visit_Assign(visitor,node):
                label=ast.unparse(node.targets[0])
                if label=='event' and ast.unparse(node.value)=='json.loads(ws.recv(timeout=1))':
                    counts['receive']+=1
                    return ast.parse('_ev_raw = ws.recv(timeout=1)\n_ev_received = time.time()\n_ev_mono = time.monotonic_ns()\n_evidence.quote_receive(_ev_raw,ticker,epoch,_ev_received,_ev_mono)\nevent = json.loads(_ev_raw)').body
                if label=='epoch':
                    counts['start']+=1
                    return [node,*ast.parse("_evidence.emit('STREAM_START',ticker=ticker,epoch=epoch,observed_at=time.time())").body]
                if label=='rebased':
                    counts['accept']+=1
                    return [node,*ast.parse('_evidence.quote_accept(_ev_raw,ticker,epoch,_ev_received,time.time())').body]
                if label=='(self.events, self.epoch)':
                    counts['clock']+=1
                    return [node,*ast.parse('self._accepted_clock(evidence.book, epoch)').body]
                return node
        fn=Insert().visit(fn)
        if counts!=dict(receive=1,accept=1,clock=1,start=1,requests=2 if requests else 0):raise ValueError('QUOTE_SEAM_MISMATCH')
        final=ast.parse("_evidence.emit('STREAM_END',ticker=ticker,epoch=locals().get('epoch'),observed_at=time.time(),reason='SESSION_RETURN_OR_DISCONNECT',continuity=False)").body
        fn.body=[ast.Try(body=fn.body,handlers=[],orelse=[],finalbody=final)]
        scope=dict(_accepted_session().__globals__);scope['_evidence']=self
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'<offline-quote-evidence>','exec'),scope)
        observed=scope['session']
        provider.session=types.MethodType(observed,provider)
        if preserve_proof_writer:
            provider.proof_writer.evidence_sink=self.writer
        else:
            provider.proof_writer=self.writer


def available_sources(records, cut, *, asset, include_recovered=False):
    """Offline as-of selector. Later BRTI can never populate an earlier decision."""
    rows=[dict(r['payload'],capture_session=r['session']) for r in records if r['kind']=='SOURCE'
            and r['payload']['asset']==asset and r['payload']['accepted_by_owner']
            and r['payload']['source_ts']<=cut and r['payload']['available_at']<=cut
            and (include_recovered or r['payload']['basis']=='ORIGINAL')]
    return sorted(rows,key=lambda p:(p['receipt_ts'],p['source_ts'],p['observation_id']))
