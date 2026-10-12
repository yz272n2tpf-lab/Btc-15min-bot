"""Explicit recorder-only object wiring, inert until used by local staging.

Reuses OffPathProofWriter for one bounded archive drain. The existing provider
proof writer/cache/queue stays intact, so recorder disk failure cannot become
MAIN publication backpressure. No new source connection or inference loop.
"""
from pathlib import Path
import ast, inspect, json, sys, threading, time, types
from candidates.early_recording_20261012.archive import Archive, BUDGET, canonical,sha
from candidates.early_recording_20261012.seams import Observer
from btc15_quote_proof_offpath_v1 import OffPathProofWriter
from .policy import validate_config,FLAGS

class Capture:
    def __init__(self,c):
        self.config=validate_config(c);self.enabled=c['capture_enabled'];self.bound=[]
        self.publisher=None;self.writer=None;self.stopped=False;self.failure=None
        if not self.enabled:return
        root=Path(c['root']);root.mkdir(parents=True,exist_ok=True)
        identity=dict(run_id=c['run_id'],configuration_sha256=sha(canonical(c)),mode=c['mode'],**FLAGS)
        marker=root/'identity.json'
        if marker.exists() and json.loads(marker.read_text())!=identity:raise ValueError('CROSS_RUN_IDENTITY')
        if not marker.exists():marker.write_bytes(canonical(identity))
        budget=dict(BUDGET,max_total_bytes=c['storage']['per_archive_bytes'])
        self.archive=Archive(root/'source',evidence_class='FIXTURE',source_binding=c['run_id']+':main',
                             budget=budget,storage_policy=c['storage'])
        limits=c.get('ingress',dict(queue_size=64,queue_bytes=8*1024**2))
        self.writer=OffPathProofWriter(root/'unused_archive_cache',lambda p,w:w.identity,2*1024**2,
                                       queue_size=limits['queue_size'],queue_bytes=limits['queue_bytes'],admission_limits=limits,archive=self.archive)
        self.observer=Observer(self.writer,btc_feed='fixture:existing-BTC',btc_epoch=self.archive.session,
                               brti_feed='fixture:existing-BRTI')
        self._health_stop=threading.Event()
        # Health thread reads counters only. No disk, market polling or strategy.
        self._health=threading.Thread(target=self._watch,daemon=True,name='capture-health-stderr')
        self._health.start()

    def _watch(self):
        previous=None
        while not self._health_stop.wait(.25):
            s=self.status();key=(s['status'],str(s.get('losses')))
            if key!=previous:
                print('BTC15_CAPTURE_HEALTH '+json.dumps(s,sort_keys=True),file=sys.stderr,flush=True)
                previous=key

    def status(self):
        if not self.enabled:return dict(status='DISABLED',**FLAGS)
        s=self.writer.status();bad=s['archive_failed'] or bool(s['losses']) or self.failure
        if self.publisher and self.publisher.evidence_gap:bad=True
        return dict(s,status='INCOMPLETE' if bad else ('CLOSED' if self.stopped else 'CAPTURING_FIXTURE'),
            run_id=self.config['run_id'],archive_session=self.archive.session,
            information_gap=self.publisher.evidence_gap if self.publisher else None,
            failure=self.failure,**FLAGS)

    def bind_sources(self,ns,*,tick=False):
        if not self.enabled:return
        if getattr(self,'sources_bound',False):raise ValueError('DUPLICATE_SOURCE_BIND')
        self.sources_bound=True
        for k in (('_ec_append_btc_tick' if tick else 'get_btc_spot'),):self.bound.append((ns,k,ns[k]))
        self.observer.bind_btc_tick(ns) if tick else self.observer.bind_btc(ns)
        delivery=ns['_brti_delivery']
        for k in ('accept','fail','remember'):self.bound.append((delivery,k,getattr(delivery,k)))
        self.observer.bind_delivery(delivery)
        if 'kalshi_get' in ns:
            self.bound.append((ns,'kalshi_get',ns['kalshi_get']));self.observer.bind_http(ns)

    def bind_provider(self,provider):
        if not self.enabled:return provider
        if getattr(provider,'_capture_bound',False):raise ValueError('DUPLICATE_PROVIDER_BIND')
        self.bound.extend([(provider,'session',provider.session),(provider.proof_writer,'evidence_sink',provider.proof_writer.evidence_sink)])
        self.observer.bind_provider(provider,preserve_proof_writer=True)
        self.bound.append((provider,'_capture_bound',getattr(provider,'_capture_bound',False)))
        provider._capture_bound=True
        return provider

    def bind_pool(self,pool):
        if not self.enabled:return
        if pool.providers:raise ValueError('BIND_BEFORE_PROVIDER_CREATION')
        factory=pool.factory;self.bound.append((pool,'factory',factory))
        pool.factory=lambda:self.bind_provider(factory())

    def publisher_kwargs(self):
        if not self.enabled:return {}
        c=self.config
        a=Archive(Path(c['root'])/'information',evidence_class='FIXTURE',source_binding=c['run_id']+':information',
                  budget=dict(BUDGET,max_total_bytes=c['storage']['per_archive_bytes']),storage_policy=c['storage'])
        return dict(evidence_archive=a)

    def attach_publisher(self,publisher):
        self.publisher=publisher
        if self.enabled and publisher.evidence_archive is None:raise ValueError('MISSING_INFORMATION_BINDING')

    def bind_journal(self,journal):
        """Called on existing journal owner worker; serialize AFTER original commit."""
        if not self.enabled:return
        original=journal.commit;self.bound.append((journal,'commit',original))
        def commit(record,state):
            sequence=original(record,state)
            try:self.writer.submit_observation('NATIVE_RECORD',raw=canonical(record),
                original_journal=journal.get('journal_id'),sequence=sequence,
                committed_at=time.time(),record_basis='POST_ORIGINAL_COMMIT',lane=journal.get('lane'))
            except Exception:self.writer.gap('CAPTURE_ERROR')
            return sequence
        journal.commit=commit

    def close(self,timeout=5):
        if not self.enabled or self.stopped:return True
        # Owner must stop calling fixture inputs before graceful shutdown.
        for obj,key,old in reversed(self.bound):
            if isinstance(obj,dict):obj[key]=old
            else:setattr(obj,key,old)
        self.bound.clear()
        if self.publisher:self.publisher.close_evidence()
        ok=self.writer.close(timeout);self.stopped=ok
        if not ok:self.failure='SHUTDOWN_DEADLINE'
        self._health_stop.set();self._health.join(.5)
        terminal=self.status()
        try:(Path(self.config['root'])/'terminal-status.json').write_bytes(canonical(terminal))
        except Exception:pass  # stderr/memory remain the failure channel
        print('BTC15_CAPTURE_FINAL '+json.dumps(terminal,sort_keys=True),file=sys.stderr,flush=True)
        return ok


def install_hooks(c,runtime_module,service_module):
    """In-memory staging bootstrap. Never launches native_main or service.main.

    Two roles share explicit run/config identity; each owns distinct archive paths.
    Exercise in a local target only. Live mode is rejected by validate_config.
    """
    capture=Capture(c)
    if not capture.enabled:return capture
    prepare=runtime_module.prepare_main
    def prepared(ns,pool):
        capture.bind_sources(ns);capture.bind_pool(pool)
        return prepare(ns,pool)
    capture.bound.append((runtime_module,'prepare_main',prepare));runtime_module.prepare_main=prepared
    from btc15_v2_product.journal import RevisionJournal
    from btc15_v2_product.admin import Admin
    bind_native_journal_class(capture,RevisionJournal);bind_admin_class(capture,Admin)
    publisher=service_module.DurablePublisher
    def observed_publisher(*a,**kw):
        kw.update(capture.publisher_kwargs());p=publisher(*a,**kw);capture.attach_publisher(p);return p
    capture.bound.append((service_module,'DurablePublisher',publisher));service_module.DurablePublisher=observed_publisher
    return capture

class InformationCapture:
    """Independent information-process role; no second source/proof writer."""
    def __init__(self,c):
        self.config=validate_config(c);self.enabled=c['capture_enabled'];self.publisher=None
        if not self.enabled:return
        root=Path(c['root']);root.mkdir(parents=True,exist_ok=True)
        self.identity=dict(run_id=c['run_id'],configuration_sha256=sha(canonical(c)),mode=c['mode'],**FLAGS)
        marker=root/'identity.json'
        try:
            with marker.open('xb') as f:f.write(canonical(self.identity))
        except FileExistsError:
            if json.loads(marker.read_bytes())!=self.identity:raise ValueError('CROSS_PROCESS_RUN_IDENTITY')

    def publisher_kwargs(self):
        if not self.enabled:return {}
        c=self.config
        return dict(evidence_archive=Archive(Path(c['root'])/'information',evidence_class='FIXTURE',
            source_binding=c['run_id']+':information',budget=dict(BUDGET,max_total_bytes=c['storage']['per_archive_bytes']),
            storage_policy=c['storage']))

    def attach_publisher(self,p):self.publisher=p
    def status(self):
        return dict(status='DISABLED' if not self.enabled else ('INCOMPLETE' if self.publisher and self.publisher.evidence_gap else 'INFORMATION_ROLE'),
            run_id=self.config['run_id'],gap=self.publisher.evidence_gap if self.publisher else 'NOT_ATTACHED',**FLAGS)
    def close(self):
        if self.publisher:self.publisher.close_evidence()
        print('BTC15_INFORMATION_CAPTURE_FINAL '+json.dumps(self.status()),file=sys.stderr,flush=True)


def bind_native_journal_class(capture,journal_class):
    """Explicit offline bootstrap before original journal worker construction."""
    if not capture.enabled:return
    original=journal_class.__init__
    def observed(instance,*args,**kwargs):
        original(instance,*args,**kwargs)
        capture.bind_journal(instance)
    capture.bound.append((journal_class,'__init__',original));journal_class.__init__=observed


def bind_admin_class(capture,admin_class):
    """Append-only seam after original Admin SQLite commit, on its existing worker.

    Preserves raw original JSON/sequence/receipt and all rejected attempts; no
    mutable data copy or serialization is added to Admin.offer/decision path.
    """
    if not capture.enabled:return
    original=admin_class.run;tree=ast.parse(__import__('textwrap').dedent(inspect.getsource(original)))
    fn=tree.body[0];found=0
    class Insert(ast.NodeTransformer):
        def visit_AugAssign(self,node):
            nonlocal found
            if ast.unparse(node.target)=='self.written':
                found+=1
                return [node,*ast.parse("try:\n _capture.writer.submit_observation('NATIVE_RECORD',raw=raw.encode(),original_journal=self.epoch,sequence=cur.lastrowid,committed_at=at,record_basis='POST_ADMIN_COMMIT_APPLICATION_CLOCK',lane=self.lane)\nexcept Exception:\n _capture.writer.gap('CAPTURE_ERROR')").body]
            return node
    fn=Insert().visit(fn)
    if found!=1:raise ValueError('PINNED_ADMIN_COMMIT_SEAM')
    scope=dict(original.__globals__);scope['_capture']=capture
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'<local-admin-evidence>','exec'),scope)
    capture.bound.append((admin_class,'run',original));admin_class.run=scope['run']
