"""Bounded recorder-only observations of pinned native calls; no evaluation.

The two function clones add observation statements only. Removing those seams
must reconstruct the exact original AST before either clone can be installed.
"""
import ast
import copy
import hashlib
import inspect
import json
import math
import textwrap
import threading

OUTCOME_BYTES=16384
OUTCOME_TOTAL=2*1024*1024
OUTCOME_COUNT=2048
PINS=('c40c714d28ec74884a95732a5bc5d8a24e03bb3a0fd4806240a9f37c4e910214',
      'd415e0ddcb99b1776822c2e5852c519507701fd2fe657a2ffa32cccb6724830d')

def bounded(value, budget=None, depth=0):
    """Snapshot plain native JSON values only; never call user conversion hooks."""
    budget=[4096] if budget is None else budget
    if depth>4:raise ValueError('TELEMETRY_DEPTH')
    t=type(value)
    if t is str:
        if len(value)>512:raise ValueError('TELEMETRY_STRING')
        budget[0]-=len(value)*4
    elif value is None or t in (bool,int,float):
        if t is float and not math.isfinite(value):raise ValueError('TELEMETRY_NONFINITE')
        budget[0]-=32
    elif t in (list,tuple):
        if len(value)>16:raise ValueError('TELEMETRY_LIST')
        return [bounded(v,budget,depth+1) for v in value]
    elif t is dict:
        if len(value)>16 or any(type(k) is not str for k in value):raise ValueError('TELEMETRY_DICT')
        return {bounded(k,budget,depth+1):bounded(v,budget,depth+1) for k,v in value.items()}
    else:raise ValueError('TELEMETRY_TYPE')
    if budget[0]<0:raise ValueError('TELEMETRY_BYTES')
    return value

class PublicationTrace:
    def __init__(self,publisher):
        self.stage='ENTER';self.invalid=None;self.owner=publisher
        self.data=dict(schema='BTC15_PUBLICATION_OUTCOME_V1',health=[],clocks=[],
                       evaluation_calls=0,outcome='ENTER',native_frame_id=None,native_rejection_reason=None,
                       native_exception=None,exception=None,return_value=None,
                       prior_native_frame_id=None)
    def note(self,label,*values):
        # Observation faults cannot change the native return, exception or calls.
        try:
            if label=='stage':self.stage=values[0]
            elif label=='prior':
                self.data['prior_latest_frame_id'],self.data['prior_source_key']=map(bounded,values)
                self.data['prior_native_frame_id']=self.owner._recording_prior_native
            elif label=='health':self.data['health'].append(dict(stage=self.stage,value=bounded(values[0])))
            elif label=='clock':self.data['clocks'].append(dict(stage=self.stage,value=bounded(values[0])))
            elif label=='evaluate':self.stage='EVALUATION';self.data['evaluation_calls']+=1
            elif label=='no_progress':self.data['outcome']='NO_PROGRESS'
            elif label=='commit':
                self.data['native_frame_id']=bounded(values[0]);self.data['outcome']='NATIVE_PUBLISHED'
                self.owner._recording_prior_native=values[0]
            elif label=='exception':self.data['exception']=self.exception(values[0]);self.data['outcome']='EXCEPTION'
            if len(self.data['health'])>2 or len(self.data['clocks'])>2:raise ValueError('TELEMETRY_CALL_BOUND')
        except Exception as exc:self.invalid=type(exc).__name__+':TELEMETRY_BOUND_OR_SNAPSHOT'
    @staticmethod
    def exception(exc):
        return dict(type=type(exc).__module__+'.'+type(exc).__name__,args=bounded(exc.args))
    def rejection(self,reason,exc):
        try:
            self.data['native_rejection_reason']=bounded(reason)
            self.data['native_exception']=self.exception(exc)
            self.data['outcome']='REJECTED'
        except Exception:self.invalid='REJECTION_TELEMETRY_BOUND'
        return reason
    def encode(self,raw,published):
        from .policy import canonical,sha,need
        need(self.invalid is None,'PUBLICATION_TELEMETRY_INCOMPLETE')
        result=dict(self.data,input_sha256=sha(raw),published=published,stage=self.stage)
        encoded=canonical(result);need(len(encoded)<=OUTCOME_BYTES,'PUBLICATION_TELEMETRY_BYTES')
        return encoded

def _note(code):
    n=ast.parse('self._recording_trace.'+code).body[0];n._recording_added=True;return n

def _stage(name):return _note('note("stage",'+repr(name)+')')

class _Native(ast.NodeTransformer):
    def __init__(self):self.health=0
    def visit_With(self,n):
        self.generic_visit(n)
        if ast.unparse(n.items[0].context_expr)=='self.worker_lock':
            n.body.insert(0,_note('note("prior",self.latest,self.key)'))
        return n
    def visit_Assign(self,n):
        self.generic_visit(n);target=ast.unparse(n.targets[0]);value=ast.unparse(n.value)
        if value=='health_reader()':
            self.health+=1;label='PRE_HEALTH' if self.health==1 else 'POST_HEALTH'
            return [_stage(label),n,_note('note("health",h)')]
        if value=='clock()':
            label='PRE_CLOCK' if target=='start' else 'POST_CLOCK'
            return [_stage(label),n,_note('note("clock",'+target+')')]
        if value=='validate(raw, h, start)':return [_stage('PRE_VALIDATION'),n]
        if target=='key':return [_stage('SOURCE_PROGRESS'),n]
        if target=='values':return [_note('note("evaluate")'),n,_stage('ASSESSMENT_SCHEMA')]
        if target=='a':return [_stage('FRAME_BUILD'),n]
        if target=='(self.latest, self.key, self.reason)':return [n,_note('note("commit",frame_id)')]
        return n
    def visit_Expr(self,n):
        self.generic_visit(n)
        if ast.unparse(n.value)=='validate(raw, h, published)':return [_stage('POST_VALIDATION'),n]
        return n
    def visit_If(self,n):
        self.generic_visit(n)
        if ast.unparse(n.test)=='not progress(self.key, key)':n.body.insert(0,_note('note("no_progress")'))
        return n
    def visit_Call(self,n):
        self.generic_visit(n)
        if ast.unparse(n.func)=='self.unavailable':
            before=n.args[0];wrapped=ast.Call(func=ast.parse('self._recording_trace.rejection',mode='eval').body,args=[before,ast.Name(id='exc',ctx=ast.Load())],keywords=[])
            wrapped._recording_original=copy.deepcopy(before);n.args[0]=wrapped
        return n

class _Durable(ast.NodeTransformer):
    def visit_With(self,n):
        self.generic_visit(n)
        if ast.unparse(n.items[0].context_expr)=='self.lock':return [_stage('DURABLE_FRAME_LOOKUP'),n]
        return n
    def visit_Assign(self,n):
        self.generic_visit(n)
        if ast.unparse(n.targets[0])=='record':return [_stage('DURABLE_JOURNAL'),n]
        return n
    def visit_Call(self,n):
        self.generic_visit(n)
        if ast.unparse(n.func)=='super().offer':
            original=copy.deepcopy(n)
            n.func=ast.Name(id='_recording_native_offer',ctx=ast.Load());n.args.insert(0,ast.Name(id='self',ctx=ast.Load()))
            n._recording_original=original
        return n

class _Remove(ast.NodeTransformer):
    def visit(self,n):
        if getattr(n,'_recording_added',False):return None
        if hasattr(n,'_recording_original'):return n._recording_original
        return super().visit(n)

def clone(original,transform,pin,extra=None):
    raw=inspect.getsource(original)
    if hashlib.sha256(raw.encode()).hexdigest()!=pin:raise ValueError('PINNED_PUBLICATION_SOURCE')
    tree=ast.parse(textwrap.dedent(raw));before=ast.dump(tree,include_attributes=False)
    changed=transform.visit(copy.deepcopy(tree))
    if ast.dump(_Remove().visit(copy.deepcopy(changed)),include_attributes=False)!=before:
        raise ValueError('PUBLICATION_SEAM_CHANGED_NATIVE_AST')
    scope=dict(original.__globals__);scope.update(extra or {})
    exec(compile(ast.fix_missing_locations(changed),'<recorder-publication-seam>','exec'),scope)
    return scope[tree.body[0].name]

def publisher_class(original,gate):
    from btc15_information_v1 import InformationPublisher
    from .capture import AsyncInformationArchive
    native=clone(InformationPublisher.offer,_Native(),PINS[0])
    durable=clone(original._offer_original,_Durable(),PINS[1],dict(_recording_native_offer=native))
    class OutcomeArchive(AsyncInformationArchive):
        def __init__(self):super().__init__(gate);self.count=0;self.total=0;self.owner=None
        def observe(self,kind,fields):
            if not gate.active:return False
            if kind=='INFORMATION_INPUT':
                try:
                    encoded=self.owner._recording_trace.encode(fields['raw'],fields['published'])
                    if self.count>=OUTCOME_COUNT or self.total+len(encoded)>OUTCOME_TOTAL:raise ValueError('PUBLICATION_TOTAL_BOUND')
                    # Respect the unchanged native writer's 1 KiB non-raw field
                    # limit. Reassemble only on the existing archive worker.
                    parts=[encoded[i:i+1024] for i in range(0,len(encoded),1024)]
                    self.count+=1;self.total+=len(encoded)
                    fields=dict(fields,outcome_parts=len(parts),**{'outcome_%02d'%i:v for i,v in enumerate(parts)})
                except Exception:gate.gap('CAPTURE_ERROR');return False
            return super().observe(kind,fields)
    class RecordedPublisher(original):
        def __init__(self,*args,**kwargs):
            archive=OutcomeArchive();kwargs['evidence_archive']=archive
            super().__init__(*args,**kwargs)
            archive.owner=self;self._recording_prior_native=None;self._recording_local=threading.local()
        @property
        def _recording_trace(self):return self._recording_local.trace
        def _offer_original(self,raw,health_reader,clock):
            if not gate.active:return original._offer_original(self,raw,health_reader,clock)
            trace=PublicationTrace(self);self._recording_local.trace=trace
            try:
                result=durable(self,raw,health_reader,clock)
                trace.data['return_value']=result
                if result:trace.stage='DURABLE_PUBLISHED'
                return result
            except BaseException as exc:
                trace.note('exception',exc);raise
    return RecordedPublisher

def check_outcome(value,input_sha,published,frame_id):
    from .policy import canonical,need
    need(isinstance(value,dict) and len(canonical(value))<=OUTCOME_BYTES,'PUBLICATION_TELEMETRY_SCHEMA')
    need(value['schema']=='BTC15_PUBLICATION_OUTCOME_V1' and value['input_sha256']==input_sha,'PUBLICATION_INPUT_LINK')
    need(type(value['published']) is bool and value['published']==published,'PUBLICATION_RETURN_LINK')
    need(len(value['health'])<=2 and len(value['clocks'])<=2 and value['evaluation_calls'] in (0,1),'PUBLICATION_CALL_BOUND')
    need(value['return_value'] is published if value['exception'] is None else value['return_value'] is None and published is False,'PUBLICATION_EXCEPTION_LINK')
    if frame_id is not None:need(value['native_frame_id']==frame_id and published,'PUBLICATION_FRAME_LINK')
