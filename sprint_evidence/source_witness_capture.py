"""Passive witnesses at actual owner/receipt/selection completion boundaries.

No network call, acceptance, selection, validation or strategy evaluation is
performed by capture. Existing exact source executes once; only evidence added.
"""
import ast
import base64
from pathlib import Path
import time
import sys
import types
from .passive_capture import digest,pack,observed_copy

OWNER_SHA='34aabd7f068237ff883c0315c2140db5013497d9ec41546e9eb821c62cdbb23a'
DELIVERY_SHA='6231e35afef153e813ba8ad63e5a13f47531d3c82cac51348a23baf4c7ef9b02'
NATIVE_SHA='323f7a38726bab23743a1895a5c743613b9cd0cea37dc80edb69cdbaeed43202'
SCHEMA='BTC15_PASSIVE_SOURCE_WITNESS_V1'
MAX_RESPONSE_BYTES=96_000


class SourceWitnessCapture:
    """One instance/Producer per producing thread; no cross-thread counters."""
    def __init__(self,producer):
        self.producer=producer;self.response=None

    def begin_fetch(self):
        self.response=None

    def _emit(self,kind,observed_ns,body):
        return self.producer.lifecycle(dict(schema=SCHEMA,witness_kind=kind,
            completed_boundary_observed_wall_ns=observed_ns,
            completion_is_not_beginning=True,clock_qualified=False,
            **body))

    def owner_response(self,response):
        """Only already-loaded requests bytes; never access a streaming property."""
        try:
            at=time.time_ns()
            raw=response.__dict__.get('_content')
            status=response.__dict__.get('status_code')
            good=type(raw) is bytes and 0<len(raw)<=MAX_RESPONSE_BYTES
            self.response=dict(response_event_sequence=self.producer.sequence+1,
                response_sha256=digest(raw) if good else None,
                response_byte_count=len(raw) if type(raw) is bytes else None,
                response_status=status,response_received_observed_wall_ns=at,
                payload_basis='EXISTING_REQUESTS_DECODED_BODY_BYTES' if good else 'UNAVAILABLE_BODY_OR_BUDGET')
            return self._emit('OWNER_HTTP_RETURNED',at,dict(**self.response,
                # Error body remains hash-only; no request headers/auth material.
                body_base64=base64.b64encode(raw).decode() if good and status==200 else None,
                owner_epoch=None,source_utc=None,
                boundary='AFTER_EXISTING_GET_RETURN_BEFORE_HTTP_STATUS_OR_PAYLOAD_VALIDATION'))
        except Exception:
            self.response=None;return False

    def owner_completed(self,owner,local_values):
        try:
            at=time.time_ns()
            batch=local_values.get('batch')
            copied=observed_copy(batch)
            return self._emit('OWNER_VALIDATION_COMPLETED',at,dict(
                owner_epoch=owner.owner_epoch,owner_sequence=owner.sequence,
                latest_source_ts_ms=local_values.get('latest_ts') if owner.status=='PRIMARY_OK' else None,
                value=owner.value,status=owner.status,
                batch_received_wall=local_values.get('received_wall'),
                batch_received_basis='EXISTING_POST_FETCH_PARSED_BATCH_RECEIPT; NOT_RAW_HTTP_RECEIPT',
                batch=copied,parsed_batch_sha256=digest(pack(copied)) if batch is not None else None,
                response_reference=self.response,
                error_type=owner.last_error_type,
                boundary='AFTER_EXISTING_SUCCESS_OR_ERROR_STATE_COMMIT_AND_LOCK_RELEASE',
                payload_validation_succeeded=owner.status=='PRIMARY_OK'))
        except Exception:return False

    def delivery_accepted(self,delivery,local_values):
        try:
            at=time.time_ns()
            return self._emit('LOCAL_BRTI_RECEIPT_ACCEPTED',at,dict(
                value=local_values.get('value'),source=local_values.get('source'),
                received=local_values.get('observed'),owner_epoch=local_values.get('epoch'),
                boundary='AFTER_EXISTING_Delivery.accept_BODY_AND_LOCK_RELEASE',
                owner_validation_completed=None,original_owner_payload_sha256=None))
        except Exception:return False

    def delivery_rejected(self,local_values):
        try:
            at=time.time_ns()
            return self._emit('LOCAL_BRTI_RECEIPT_REJECTED',at,dict(
                value=local_values.get('value'),source=local_values.get('source'),
                received=local_values.get('observed'),owner_epoch=local_values.get('epoch'),
                boundary='EXISTING_Delivery.accept_EXCEPTION_RETHROWN_UNCHANGED'))
        except Exception:return False

    def native_consumed(self,selected,cut,checked):
        try:
            at=time.time_ns()
            return self._emit('NATIVE_BRTI_SELECT_RETURNED',at,dict(
                original_cutoff=cut,original_checked_time=checked,selected=selected,
                boundary='AFTER_EXISTING_Delivery.select_RETURN_AND_LOCK_RELEASE',
                downstream_conflict_guard_not_yet_applied=True,
                completed_native_decision_or_publication=None))
        except Exception:return False


def instrument_owner(raw,*,enabled=True):
    if digest(raw)!=OWNER_SHA:raise ValueError('OWNER_SOURCE_CHANGED')
    tree=ast.parse(raw)
    if not enabled:return tree
    classes={n.name:n for n in tree.body if isinstance(n,ast.ClassDef)}
    fetch=next(n for n in classes['KalshiBrtiFetcher'].body if isinstance(n,ast.FunctionDef) and n.name=='fetch_once')
    if not isinstance(fetch.body[0],ast.Assign):raise ValueError('OWNER_HTTP_SEAM')
    fetch.body.insert(1,ast.parse('_sprint_sources.owner_response(r)').body[0])
    poll=next(n for n in classes['SharedBrtiPoller'].body if isinstance(n,ast.FunctionDef) and n.name=='poll_once')
    block=next(n for n in poll.body if isinstance(n,ast.Try))
    block.body.insert(0,ast.parse('_sprint_sources.begin_fetch()').body[0])
    found=0
    class Returns(ast.NodeTransformer):
        def visit_Return(self,n):
            nonlocal found
            if isinstance(n.value,ast.Constant) and n.value.value is True:
                found+=1;return [ast.parse('_sprint_sources.owner_completed(self, locals())').body[0],n]
            return n
    Returns().visit(poll)
    if found!=2:raise ValueError('OWNER_COMPLETION_SEAM')
    return ast.fix_missing_locations(tree)


def instrument_delivery(raw,*,enabled=True):
    if digest(raw)!=DELIVERY_SHA:raise ValueError('DELIVERY_SOURCE_CHANGED')
    tree=ast.parse(raw)
    if not enabled:return tree
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Delivery')
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='accept')
    original=fn.body
    # Original body executes once. The existing exception is rethrown; no
    # capture-dependent accept result, lock ownership, or source mutation.
    wrapper=ast.parse('try:\n    pass\nexcept Exception:\n    _sprint_sources.delivery_rejected(locals())\n    raise').body[0]
    wrapper.body=original
    fn.body=[wrapper,ast.parse('_sprint_sources.delivery_accepted(self, locals())').body[0]]
    return ast.fix_missing_locations(tree)


def instrument_native(raw,*,enabled=True):
    if digest(raw)!=NATIVE_SHA:raise ValueError('NATIVE_SOURCE_CHANGED')
    tree=ast.parse(raw)
    if not enabled:return tree
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_latest_brti')
    matches=[i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and
             isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='select']
    if len(matches)!=1:raise ValueError('NATIVE_SELECT_RETURN_SEAM')
    fn.body.insert(matches[0]+1,ast.parse('_sprint_sources.native_consumed(latest, cut, checked)').body[0])
    return ast.fix_missing_locations(tree)


def compile_source(path,kind,tap):
    transforms={'owner':instrument_owner,'delivery':instrument_delivery,'native':instrument_native}
    expected={'owner':OWNER_SHA,'delivery':DELIVERY_SHA,'native':NATIVE_SHA}[kind]
    if tap.producer.identity.source_sha256!=expected:raise ValueError('SOURCE_PRODUCER_BINDING')
    raw=Path(path).read_bytes();tree=transforms[kind](raw)
    name='sprint_evidence._source_candidate_'+kind+'_'+digest(tap.producer.identity.run_id.encode())[:12]
    module=types.ModuleType(name);module.__file__=str(path);module._sprint_sources=tap
    sys.modules[name]=module
    return compile(tree,str(path),'exec'),module.__dict__
