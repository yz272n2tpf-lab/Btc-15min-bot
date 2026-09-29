"""Detached authenticated journal admission; OFFLINE ONLY, not wired to services.

An approved acquisition principal signs completed original gzip members AFTER
copying them to independent storage. This code does not acquire live artifacts,
make HTTP requests, sign publisher claims, or assert that a live mirror exists.
HMAC authenticates the acquisition principal, not a missing native/V2 witness.
"""
from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
import threading
import zlib
import fcntl

from btc15_directional_signal_authority_v1 import (
    Authority, decode_state, pack, snapshot_identity, unavailable, utc)
from btc15_directional_signal_publication_v1 import signal_view
from btc15_qualified_forward_observer_v1 import observation
from btc15_protected_publication_handoff_v1 import strict_json
from btc15_external_clock_guard_v1 import Bound, admit, micros

SCHEMA='BTC15_DETACHED_COMMON_MEMBER_V1'
MAX_COMPRESSED=1_048_576
MAX_DECOMPRESSED=2_097_152
MAX_MANIFEST=65_536


@dataclass(frozen=True)
class Policy:
    endpoint: str
    service_id: str
    run_id: str
    observer_epoch: str
    collector_commit: str
    run_manifest_sha256: str
    fingerprints: tuple
    signer_id: str
    stream_id: str
    clock_domains: tuple = (('native','native'),('collector','collector'),('parity','native'))
    start_offset: int=0
    start_sequence: int=1


@dataclass(frozen=True)
class Sample:
    utc: str
    boot_ns: int
    epoch: str
    bound: Bound | None
    healthy: bool=True


def signature(manifest,key):
    if type(key) is not bytes or len(key)<32:raise ValueError('WEAK_ACQUISITION_KEY')
    return hmac.new(key,pack(manifest).encode(),hashlib.sha256).hexdigest()


def seal_member(data, policy, *, offset, sequence, clock_refs, key):
    """Offline acquisition helper; caller attests origin, never producer code.
    Has no I/O and cannot retrieve a live journal. Original bytes are not encoded
    as HTTP bytes. This key must differ from the reader authorization credential.
    """
    manifest=dict(schema=SCHEMA, acquisition='DETACHED_IMMUTABLE_MEMBER',
        endpoint=policy.endpoint,service_id=policy.service_id,run_id=policy.run_id,
        observer_epoch=policy.observer_epoch,collector_commit=policy.collector_commit,
        run_manifest_sha256=policy.run_manifest_sha256,fingerprints=dict(policy.fingerprints),
        signer_id=policy.signer_id,stream_id=policy.stream_id,offset=offset,
        end_offset=offset+len(data),sequence=sequence,byte_count=len(data),
        sha256=hashlib.sha256(data).hexdigest(),clock_refs=clock_refs,
        original_http_bytes_available=False,native_epoch=None,native_decision_id=None,
        v2_admitted=False,orders=False)
    return pack(dict(manifest=manifest,mac=signature(manifest,key))).encode()


def read_member(path):
    # A local, consumer-owned detached file only. No URLs/symlinks/devices.
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0<before.st_size<=MAX_COMPRESSED:
            raise ValueError('MEMBER_SIZE_OR_TYPE')
        with os.fdopen(fd,'rb',closefd=False) as stream:data=stream.read(MAX_COMPRESSED+1)
        after=os.fstat(fd)
        identity=[before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns]
        if identity!=[after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns] or len(data)!=before.st_size:
            raise ValueError('MEMBER_CHANGED_DURING_READ')
        return data,identity
    finally:os.close(fd)


def parsed_member(data):
    d=zlib.decompressobj(16+zlib.MAX_WBITS)
    raw=d.decompress(data,MAX_DECOMPRESSED+1)
    if len(raw)>MAX_DECOMPRESSED or d.unconsumed_tail:
        raise ValueError('DECOMPRESSION_LIMIT')
    if not d.eof:raise ValueError('PARTIAL_GZIP_MEMBER')
    if d.unused_data:raise ValueError('EXTRA_MEMBER_OR_TRAILING_BYTES')
    if not raw.endswith(b'\n'):raise ValueError('MISSING_RECORD_TERMINATOR')
    record=strict_json(raw.decode('utf-8'))
    # Bound JSON depth/node count after parsing; recursion itself is caught by
    # admission, and total input size is bounded before parsing.
    def walk(value,depth=0):
        if depth>32:raise ValueError('JSON_DEPTH_LIMIT')
        if type(value) is float and not math.isfinite(value):raise ValueError('NONFINITE_JSON_NUMBER')
        if isinstance(value,dict):
            for item in value.values():walk(item,depth+1)
        elif isinstance(value,list):
            for item in value:walk(item,depth+1)
    walk(record)
    return record


def initialize_checkpoint(path,policy):
    path=Path(path)
    with path.open('xb'):pass
    with sqlite3.connect(path) as db:
        db.executescript('''PRAGMA synchronous=FULL;
        CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT NOT NULL);
        CREATE TABLE members(offset INTEGER PRIMARY KEY, digest TEXT NOT NULL,
          file_identity TEXT NOT NULL, manifest TEXT NOT NULL, bytes BLOB NOT NULL,
          disposition TEXT);
        CREATE TRIGGER no_member_delete BEFORE DELETE ON members BEGIN
          SELECT RAISE(ABORT,'immutable evidence'); END;
        CREATE TRIGGER no_member_rewrite BEFORE UPDATE OF digest,file_identity,manifest,bytes ON members BEGIN
          SELECT RAISE(ABORT,'immutable evidence'); END;''')
        for k,v in dict(policy=pack(asdict(policy)),offset=policy.start_offset,
                        sequence=policy.start_sequence,pending=None,latest=None,
                        previous=None,status='NO_INPUT').items():
            db.execute('INSERT INTO meta VALUES (?,?)',(k,pack(v)))


class Admission:
    """Single writer. Only consume/view are authorized public operations.
    No automatic initialization/recovery, network transport, service startup or
    production clock provider. Private checkpoint and authority ledger required.
    """
    def __init__(self,ledger,checkpoint,policy,*,acquisition_key,reader_credential,
                 clock_provider,clock_registry,activation_bound,runtime_epoch,artifact_root):
        if (type(acquisition_key) is not bytes or type(reader_credential) is not bytes
                or len(acquisition_key)<32 or len(reader_credential)<32 or acquisition_key==reader_credential):
            raise ValueError('SEPARATE_STRONG_CREDENTIALS_REQUIRED')
        self.ledger,self.checkpoint=Path(ledger),Path(checkpoint)
        if self.ledger.resolve()==self.checkpoint.resolve():raise ValueError('PRIVATE_STORAGE_CONFLICT')
        self.policy=policy;self.key=acquisition_key;self.reader=reader_credential
        self.artifact_root=Path(artifact_root).resolve()
        self.clock_provider=clock_provider;self.registry=dict(clock_registry)
        self.activation_bound=activation_bound;self.epoch=runtime_epoch
        self.authority=Authority(ledger,runtime_epoch=runtime_epoch,build={'external_admission':SCHEMA})
        self.last_sample=None;self.clock_failed=False;self.ready=False
        self.lock=threading.Lock()

    def _authorize(self,credential):
        if type(credential) is not bytes or not hmac.compare_digest(self.reader,credential):
            raise ValueError('READER_UNAUTHORIZED')

    def _db(self):
        db=sqlite3.connect(self.checkpoint.resolve().as_uri()+'?mode=rw',uri=True,timeout=0)
        db.execute('PRAGMA synchronous=FULL');return db

    def _meta(self,db):
        data={k:json.loads(v) for k,v in db.execute('SELECT k,v FROM meta')}
        if data['policy']!=pack(asdict(self.policy)):raise ValueError('PINNED_POLICY_CHANGED')
        return data

    def _save(self,db,**values):
        for k,v in values.items():db.execute('UPDATE meta SET v=? WHERE k=?',(pack(v),k))
        db.commit()

    def _sample(self):
        s=self.clock_provider()
        if (self.clock_failed or not isinstance(s,Sample) or not s.healthy
                or s.epoch!=self.epoch or not isinstance(s.bound,Bound)
                or s.bound.epoch!=self.epoch or type(s.boot_ns) is not int or s.boot_ns<0):
            self.clock_failed=True;raise ValueError('CONSUMER_CLOCK_UNAVAILABLE')
        s.bound.witness(s.utc)
        if self.last_sample:
            old=self.last_sample
            elapsed_ns=s.boot_ns-old.boot_ns
            delta_us=micros(s.utc)-micros(old.utc)
            # BOOTTIME must include suspension. A mismatch is a step/clock fault,
            # never a reason to rewrite UTC. Measurement errors are not tolerance
            # for drift; compare using the configured rate and read uncertainty.
            allowed=(s.bound.read_error_us+old.bound.read_error_us
                     +abs(elapsed_ns)*max(s.bound.rate_ppm,old.bound.rate_ppm)/1_000_000_000)
            if elapsed_ns<0 or abs(delta_us-elapsed_ns/1000)>allowed:
                self.clock_failed=True;raise ValueError('CLOCK_STEP_OR_SUSPEND_MISMATCH')
        self.last_sample=s;return s

    def _unavailable(self,reason):
        origin=None
        try:
            with sqlite3.connect(self.ledger.resolve().as_uri()+'?mode=ro',uri=True,timeout=0) as db:
                origin=json.loads(db.execute("SELECT value FROM meta WHERE key='latest'").fetchone()[0]).get('origin_id')
        except (sqlite3.Error,ValueError,TypeError):pass
        return unavailable(reason,origin=origin)

    def _context(self,manifest,record):
        expected={'schema_version','record_type','run_id','recorded_utc','sequence_in_process',
                  'observer_epoch','sources','sampling_seconds','actual_browser_delivery_verified','signal_only','orders'}
        if (type(record) is not dict or set(record)!=expected
                or type(record.get('schema_version')) is not int or record.get('schema_version')!=1
                or record.get('record_type')!='OBSERVATION'
                or record.get('run_id')!=self.policy.run_id
                or record.get('observer_epoch')!=self.policy.observer_epoch
                or type(record.get('sequence_in_process')) is not int
                or record['sequence_in_process']!=manifest['sequence']
                or type(record.get('sampling_seconds')) not in (int,float) or record['sampling_seconds']!=1
                or record.get('actual_browser_delivery_verified') is not False
                or record.get('orders') is not False or record.get('signal_only') is not True):
            raise ValueError('JOURNAL_IDENTITY_OR_SCHEMA')
        utc(record['recorded_utc'])
        sources=record.get('sources')
        if type(sources) is not list or not 1<=len(sources)<=4 or any(type(x) is not dict for x in sources):
            raise ValueError('SOURCE_SCHEMA')
        if any(x.get('service') not in ('main','owner','v81','serial') for x in sources):
            raise ValueError('UNAPPROVED_SOURCE_LABEL')
        mains=[x for x in sources if x.get('service')=='main']
        if len(mains)!=1:raise ValueError('MAIN_SOURCE_NOT_UNIQUE')
        source=mains[0]
        utc(source['request_started_utc']);utc(source['response_received_utc'])
        raw=source.get('state')
        if source.get('http_status')!=200 or source.get('error_type') or type(raw) is not dict:
            raise ValueError('MAIN_SOURCE_WAIT')
        for key in ('timer','market','health','safety','parity','early'):
            if type(raw.get(key)) is not dict:raise ValueError('PROTECTED_SCHEMA:'+key)
        # FINAL may genuinely be missing; unchanged authority owns its semantics.
        for key in ('final','scalp'):
            if raw.get(key) is not None and type(raw[key]) is not dict:
                raise ValueError('PROTECTED_SCHEMA:'+key)
        if raw.get('early',{}).get('source')!='FROZEN_TIER1':raise ValueError('WRONG_EARLY_PRODUCER')
        if raw.get('final') and raw['final'].get('source')!='FROZEN_V4_6_FINAL':
            raise ValueError('WRONG_FINAL_PRODUCER')
        context=dict(raw=raw,source=source,clock_refs=manifest['clock_refs'])
        context['bound_snapshots']={k:asdict(v) for k,v in self._bounds(context).items()}
        return context

    def _bounds(self,context):
        refs=context['clock_refs']
        if type(refs) is not dict or set(refs)!= {'native','collector','parity'}:
            raise ValueError('CLOCK_ROLES_UNAVAILABLE')
        result={role:self.registry.get(ref) for role,ref in refs.items()}
        if any(not isinstance(b,Bound) for b in result.values()):raise ValueError('CLOCK_BOUND_UNAVAILABLE')
        if any(result[role].clock_id!=dict(self.policy.clock_domains)[role] for role in result):
            raise ValueError('CLOCK_DOMAIN_BINDING_MISMATCH')
        if 'bound_snapshots' in context and context['bound_snapshots']!={k:asdict(v) for k,v in result.items()}:
            raise ValueError('HISTORICAL_CLOCK_CERTIFICATE_CHANGED')
        return result

    def _guard(self,context,sample,previous=None,consumed=None,consumed_bound=None):
        with sqlite3.connect(self.ledger.resolve().as_uri()+'?mode=ro',uri=True,timeout=0) as db:
            meta=dict(db.execute('SELECT key,value FROM meta'))
        if previous:previous={**previous,'bounds':self._bounds(previous)}
        return admit(context['raw'],context['source'],self._bounds(context),sample.utc,sample.bound,
                     meta['activated_utc'],self.activation_bound,previous,consumed,consumed_bound)

    def _verify(self,data,envelope):
        if type(envelope) is not bytes or len(envelope)>MAX_MANIFEST:raise ValueError('MANIFEST_SIZE')
        e=strict_json(envelope.decode())
        if type(e) is not dict or set(e)!={'manifest','mac'} or type(e['manifest']) is not dict or type(e['mac']) is not str:
            raise ValueError('MANIFEST_SCHEMA')
        m=e['manifest']
        if not hmac.compare_digest(signature(m,self.key),e['mac']):raise ValueError('ACQUISITION_AUTHENTICATION_FAILED')
        expected=seal_member(data,self.policy,offset=m['offset'],sequence=m['sequence'],
                             clock_refs=m['clock_refs'],key=self.key)
        if strict_json(expected)['manifest']!=m:raise ValueError('PINNED_MANIFEST_OR_MEMBER_CONFLICT')
        if any(type(m[k]) is not int or m[k]<0 for k in ('offset','end_offset','sequence','byte_count')):
            raise ValueError('INVALID_MEMBER_COORDINATES')
        return m

    def consume(self,path,envelope,*,credential):
        try:self._authorize(credential)
        except ValueError as exc:return unavailable(str(exc))
        if not self.lock.acquire(False):return self._unavailable('ADMISSION_BUSY')
        lockfd=None;db=None
        try:
            self.ready=False
            if Path(path).parent.resolve()!=self.artifact_root:
                raise ValueError('OUTSIDE_APPROVED_DETACHED_ROOT')
            path=self.artifact_root/Path(path).name
            if Path(path).resolve() in (self.ledger.resolve(),self.checkpoint.resolve()):
                raise ValueError('INPUT_STORAGE_CONFLICT')
            lockfd=os.open(self.checkpoint,os.O_RDONLY|os.O_NOFOLLOW)
            fcntl.flock(lockfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            db=self._db();meta=self._meta(db)
            # Revoke previously available projection BEFORE potentially slow I/O.
            self._save(db,status='ADMISSION_IN_PROGRESS')
            data,identity=read_member(path);m=self._verify(data,envelope)
            old=db.execute('SELECT digest,file_identity,disposition FROM members WHERE offset=?',(m['offset'],)).fetchone()
            if old and (old[0]!=m['sha256'] or json.loads(old[1])!=identity):
                raise ValueError('MEMBER_REPLACEMENT_OR_CONFLICT')
            if old and old[2] is not None:raise ValueError('DUPLICATE_MEMBER_NO_TRANSITION')
            if m['offset']!=meta['offset'] or m['sequence']!=meta['sequence']:
                raise ValueError('STREAM_GAP_REPLAY_OR_SWITCH')
            record=parsed_member(data)
            if not old:
                db.execute('INSERT INTO members VALUES (?,?,?,?,?,NULL)',
                    (m['offset'],m['sha256'],pack(identity),pack(m),data))
                self._save(db,pending=m['offset'])
            # Operational WAIT or clock failures advance only the private input
            # cursor. They NEVER call the authority or advance lifecycle state.
            try:
                context=self._context(m,record);sample=self._sample()
                previous=meta['previous']
                # Commit-before-checkpoint crash: authority may already hold this
                # exact source. The pending authenticated bytes supply witnesses.
                with sqlite3.connect(self.ledger.resolve().as_uri()+'?mode=ro',uri=True,timeout=0) as ledger:
                    lm=dict(ledger.execute('SELECT key,value FROM meta'))
                state=decode_state(lm['state'])
                if state.last_source_utc:
                    latest=json.loads(lm['latest'])
                    key,content=snapshot_identity(context['raw'])
                    if latest.get('protected_snapshot_key')==key and latest.get('protected_content_sha256')==content:
                        previous=context
                    elif not previous or utc(previous['raw']['source_timestamp_utc'])!=state.last_source_utc:
                        raise ValueError('PREVIOUS_CLOCK_LINK_UNAVAILABLE')
                proof=self._guard(context,sample,previous)
                raw=context['raw'];receipt=utc(context['source']['response_received_utc'])
                result=self.authority.consume(raw,observation(raw,receipt),now_utc=sample.utc,receipt_utc=receipt)
                context.update(consumed=result['consumed_utc'],consumed_bound=asdict(sample.bound),
                               record_id=result['record_id'],member_offset=m['offset'],member_sha256=m['sha256'])
                status=result['status']
                db.execute('UPDATE members SET disposition=? WHERE offset=?',(status,m['offset']))
                self._save(db,offset=m['end_offset'],sequence=m['sequence']+1,pending=None,
                           latest=context,previous=context if status in ('AVAILABLE','PASS') else meta['previous'],status=status)
                # Historical event only; current guidance is independently checked
                # after ledger/checkpoint work. No BUY event is re-emitted on view.
                self.ready=True
                view=self._view(db)
                return dict(view,accepted_event=result['event'],accepted_record_id=result['record_id'],
                            clock_admission=proof)
            except (ValueError,TypeError,KeyError) as exc:
                self.ready=False
                db.execute('UPDATE members SET disposition=? WHERE offset=?',('UNAVAILABLE:'+str(exc),m['offset']))
                self._save(db,offset=m['end_offset'],sequence=m['sequence']+1,pending=None,status='UNAVAILABLE:'+str(exc))
                return self._unavailable(str(exc))
        except (OSError,sqlite3.Error,ValueError,TypeError,KeyError,UnicodeError,zlib.error,RecursionError) as exc:
            self.ready=False
            if db:
                try:
                    db.rollback()
                    self._save(db,status='UNAVAILABLE:'+type(exc).__name__+':'+str(exc))
                except sqlite3.Error:pass
            return self._unavailable(type(exc).__name__+':'+str(exc))
        finally:
            if db:db.close()
            if lockfd is not None:os.close(lockfd)
            self.lock.release()

    def _view(self,db):
        if not self.ready:return self._unavailable('REVALIDATION_REQUIRED')
        meta=self._meta(db)
        if meta['status'] not in ('AVAILABLE','PASS') or not meta['latest']:
            return self._unavailable(meta['status'])
        c=meta['latest'];cb=Bound(**c['consumed_bound'])
        before=self._sample();self._guard(c,before,consumed=c['consumed'],consumed_bound=cb)
        view=signal_view(c['raw'],self.ledger,utc(before.utc))
        if view.get('status')=='UNAVAILABLE':return view
        # A slow read/projection must not inherit its earlier availability check.
        after=self._sample();after_proof=self._guard(c,after,consumed=c['consumed'],consumed_bound=cb)
        if view.get('record_id')!=c['record_id']:raise ValueError('LEDGER_PROJECTION_CHANGED')
        # Reuse frozen projection once at the actual later clock; no transitions.
        view=signal_view(c['raw'],self.ledger,utc(after.utc))
        if view.get('status')=='UNAVAILABLE':return view
        final=self._sample();final_proof=self._guard(c,final,consumed=c['consumed'],consumed_bound=cb)
        if view.get('record_id')!=c['record_id'] or after_proof['brti_age_predicate']!=final_proof['brti_age_predicate']:
            raise ValueError('PROJECTION_BRANCH_CHANGED')
        return dict(view,external_member_sha256=c['member_sha256'],
                    evidence_basis='PARSED_PROTECTED_STATE_IN_AUTHENTICATED_DETACHED_GZIP_MEMBER',
                    availability_checked_utc=final.utc,publication_completed_utc=None)

    def view(self,*,credential):
        try:self._authorize(credential)
        except ValueError as exc:return unavailable(str(exc))
        try:
            if not self.lock.acquire(False):return self._unavailable('ADMISSION_BUSY')
            lockfd=None
            try:
                lockfd=os.open(self.checkpoint,os.O_RDONLY|os.O_NOFOLLOW)
                fcntl.flock(lockfd,fcntl.LOCK_SH|fcntl.LOCK_NB)
                with self._db() as db:return self._view(db)
            finally:
                if lockfd is not None:os.close(lockfd)
                self.lock.release()
        except (OSError,sqlite3.Error,ValueError,TypeError,KeyError) as exc:
            self.ready=False
            return self._unavailable(type(exc).__name__+':'+str(exc))
