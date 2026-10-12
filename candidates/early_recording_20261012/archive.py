"""Schema/codec for the existing off-path worker and compressed information journal.

No collector, polling, thread, model or strategy. One explicit exclusive archive,
no pruning; closed and interrupted sessions never silently form continuous history.
"""
from collections import OrderedDict, defaultdict
from copy import deepcopy
import base64
import fcntl
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path
import uuid

from btc15_information_journal_v1 import CompressedJournal

SCHEMA = 'BTC15_OBSERVATION_EVIDENCE_V1'
SAFETY = dict(signal_only=True, orders=False, production_enabled=False, actionable=False)
BUDGET = dict(segment_bytes=8*1024*1024, max_total_bytes=256*1024*1024,
              max_record_bytes=5*1024*1024)
CACHE_BYTES=32*1024*1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def bounded_size(value, limit=CACHE_BYTES):
    pending=[value];seen=set();total=0
    while pending:
        item=pending.pop();identity=id(item)
        if identity in seen:continue
        seen.add(identity);total+=sys.getsizeof(item)
        if total>limit:raise ValueError('CACHE_MEMORY_BUDGET')
        if isinstance(item,dict):pending.extend(item.keys());pending.extend(item.values())
        elif isinstance(item,(list,tuple)):pending.extend(item)
    return total


class Archive:
    def __init__(self, path, *, evidence_class, source_binding, budget=None, storage_policy=None):
        if evidence_class not in {'FIXTURE','NATIVE_CAPTURE'}:
            raise ValueError('Explicit evidence class required')
        if not isinstance(source_binding,str) or not source_binding:
            raise ValueError('Source binding required')
        self.path = Path(path).resolve()
        if self.path.is_relative_to(Path('/data')):
            raise ValueError('Protected production storage forbidden')
        self.evidence_class, self.source_binding = evidence_class, source_binding
        self.session = uuid.uuid4().hex
        self.seq, self.previous = 0, None
        self.budget=dict(budget or BUDGET)
        limits=dict(BUDGET)
        if storage_policy is not None:
            from ops.recording_workflow.policy import validate_policy
            validate_policy(storage_policy)
            limits['max_total_bytes']=storage_policy['per_archive_bytes']
        if set(self.budget)!=set(BUDGET) or any(type(v) is not int or not 0<v<=limits[k] for k,v in self.budget.items()):
            raise ValueError('ARCHIVE_BUDGET')
        self.journal = CompressedJournal(self.path, **self.budget)
        self._lock_file = None
        self._vectors = {}
        self._seen = OrderedDict()
        self._sources = {}

    def start(self):
        self.journal.directory.mkdir(parents=True,exist_ok=True)
        self._lock_file = (self.journal.directory/'writer.lock').open('a+b')
        fcntl.flock(self._lock_file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        # Every start is a new causality boundary. Never append behind torn bytes.
        self.write('START',dict(reason='CAPTURE_START_OR_RESTART',
            continuous_with_prior_session=False,source_binding=self.source_binding,
            retention='STOP_AT_QUOTA_NO_PRUNING',budgets=self.budget))

    def close(self):
        if self._lock_file is not None:
            self._lock_file.close();self._lock_file=None

    def write(self, kind, payload):
        body = dict(schema=SCHEMA,session=self.session,sequence=self.seq+1,
                    previous_sha256=self.previous,kind=kind,payload=payload,
                    evidence_class=self.evidence_class,**SAFETY)
        digest=sha(canonical(body))
        self.journal.append(canonical(dict(body,sha256=digest))+b'\n')
        self.seq += 1; self.previous = digest
        return digest

    def _unique(self, key):
        if key in self._seen:
            self._seen.move_to_end(key);return False
        self._seen[key]=True
        if len(self._seen)>4096:self._seen.popitem(last=False)
        return True

    def vector(self, name, rows):
        """Persist overlapping buffers as trim/append deltas, never repeat buffers.

        All work is off-path. Each vector contains at most 8192 rows and 3 MiB.
        An epoch/name change is a new base; no clocks or observations are invented.
        """
        raw=canonical(rows)
        if len(rows)>8192 or len(raw)>3*1024*1024:raise ValueError('VECTOR_BUDGET')
        digest=sha(raw)
        old_id,old=self._vectors.get(name,(None,[]))
        if digest==old_id:return digest
        prospective=dict(self._vectors);prospective[name]=(digest,rows)
        bounded_size(prospective)
        # Linear prefix-function over row hashes: bounded even after a full reset.
        keys=[sha(canonical(row)) for row in rows]+[None]+[sha(canonical(row)) for row in old]
        prefix=[0]*len(keys)
        for i in range(1,len(keys)):
            n=prefix[i-1]
            while n and keys[i]!=keys[n]:n=prefix[n-1]
            if keys[i]==keys[n]:n+=1
            prefix[i]=n
        overlap=prefix[-1] if keys else 0
        self.write('VECTOR',dict(name=name,id=digest,base=old_id if overlap else None,
            drop=len(old)-overlap if overlap else 0,append=rows[overlap:]))
        self._vectors[name]=(digest,rows)
        return digest

    def input(self, raw, frame_id=None, published=False):
        value=json.loads(raw)
        if canonical(value)!=raw:raise ValueError('INPUT_NOT_CANONICAL')
        skeleton=deepcopy(value)
        for parent,key,name in [(skeleton['anchor'],'ticks','btc_ticks'),
                                (skeleton['anchor'],'completed','btc_completed'),
                                (skeleton['proof'],'events','quote_events')]:
            parent[key]={'vector_ref':self.vector(name,parent[key])}
        self.write('INFORMATION_INPUT',dict(input_sha256=sha(raw),skeleton=skeleton,
            frame_id=frame_id,published=published,decision_cutoff=value['anchor']['decision'],
            capture_cutoff=value['cut'],history_basis='INPUT_COPY_NOT_ORIGINAL_RECEIPT_EVENT'))

    def proof(self, proof, witness, raw, digest):
        # Preserve the exact non-sorted serialization used by the original writer.
        skeleton=dict(proof)
        # Store exact per-event JSON text to preserve original member order too.
        event_text=[json.dumps(e,separators=(',', ':'),allow_nan=False) for e in proof['events']]
        skeleton['events']={'proof_event_vector_ref':self.vector('proof_events',event_text)}
        self.write('QUOTE_PROOF',dict(proof_sha256=digest,skeleton=skeleton,witness=witness,
            encoding='json-insertion-order-compact',displayed_depth_only=True,
            fill_evidence=False))

    def observe(self, kind, fields):
        if kind=='PROOF_BYTES':
            raw=fields['raw'];proof=json.loads(raw)
            self.proof(proof,json.loads(fields['witness_json']),raw,sha(raw));return
        if kind=='NATIVE_RECORD':
            raw=fields['raw']
            self.write(kind,dict(fields,raw=raw.decode(),sha256=sha(raw)))
            return
        if kind=='INFORMATION_INPUT':
            if not isinstance(fields.get('raw'),bytes) or len(fields['raw'])>3*1024*1024:
                self.write('INFORMATION_FAILURE',dict(reason='INPUT_BYTES_BUDGET',raw_retained=False));return
            try:self.input(fields['raw'],fields.get('frame_id'),fields.get('published',False))
            except (ValueError,KeyError,TypeError) as exc:
                raw=fields['raw']
                self.write('INFORMATION_FAILURE',dict(reason='UNREPLAYABLE_INPUT',
                    input_sha256=sha(raw),raw_base64=base64.b64encode(raw).decode(),
                    error=type(exc).__name__,published=fields.get('published',False)))
            return
        if kind=='SOURCE':
            self.source(fields);return
        if kind in {'QUOTE_RECEIVE','QUOTE_ACCEPT'}:
            raw=fields.pop('raw')
            if isinstance(raw,str):raw=raw.encode()
            digest=sha(raw)
            if self._unique(('wire',digest)):
                self.write('QUOTE_BYTES',dict(raw_base64=base64.b64encode(raw).decode(),sha256=digest))
            fields['raw_sha256']=digest
            fields.update(price_unit='USD_per_contract',quantity_unit='contracts_fixed_point',
                          displayed_depth_only=True,fill_evidence=False)
            self.write(kind,fields);return
        if kind=='HTTP_RESPONSE':
            raw=fields.pop('raw')
            if isinstance(raw,str):raw=raw.encode()
            digest=sha(raw)
            if self._unique(('http',digest)):
                self.write('HTTP_BYTES',dict(raw_base64=base64.b64encode(raw).decode(),sha256=digest))
            fields.update(raw_sha256=digest,effective_from=None,effective_to=None,
                          fee_rounding=None,fee_formula=None,applicable_scope=None,
                          missing='Applicability/formula/rounding require explicit official evidence')
            data=json.loads(raw)
            if isinstance(data,dict) and isinstance(data.get('market'),dict):
                m=data['market']
                fields['official_fields']={k:m.get(k) for k in
                    ('ticker','event_ticker','open_time','close_time','floor_strike','strike_type','rules_primary','rules_secondary')}
                fields['target_binding']='RAW_FLOOR_STRIKE_ONLY; validate against original native target/window offline'
            elif isinstance(data,dict) and isinstance(data.get('series'),dict):
                s=data['series']
                fields['observed_series_fields']={k:s.get(k) for k in
                    ('ticker','fee_type','fee_multiplier','last_updated_ts')}
            self.write(kind,fields);return
        if kind not in {'SOURCE_GAP','STREAM_START','STREAM_END','INFORMATION_FAILURE'}:
            raise ValueError('UNKNOWN_OBSERVATION_KIND')
        self.write(kind,fields)

    def source(self, f):
        f=dict(f)
        if f['basis'] not in {'ORIGINAL','RECOVERED'}:raise ValueError('SOURCE_BASIS')
        if not all(finite(f.get(k)) for k in ('value','source_ts','receipt_ts','available_at')):
            self.write('SOURCE_GAP',dict(reason='INVALID_CLOCK_OR_VALUE',source=f.get('feed')));return
        if not f['source_ts']<=f['receipt_ts']<=f['available_at'] or not f.get('epoch') or not f.get('feed'):
            self.write('SOURCE_GAP',dict(reason='SOURCE_CHRONOLOGY_OR_IDENTITY',source=f.get('feed')));return
        publication=sha(canonical([f['feed'],f['epoch'],f['source_ts']]))
        f['publication_id']=publication
        f['observation_id']=sha(canonical(f))
        if not self._unique(('source',f['observation_id'])):return
        key=(f['asset'],f['feed'],f['epoch'],f['basis'])
        previous=self._sources.get(key)
        # Sources are fixed BTC/BRTI bindings; bound restarts/feed identities too.
        if len(self._sources)>=64 and key not in self._sources:self._sources.clear()
        if previous:
            if f['source_ts']==previous['source_ts'] and f['value']==previous['value']:
                # Preserve the new observation receipt compactly while retaining
                # the publication's first receipt. Native BTC may cite this repeat.
                self.write('SOURCE_REPEAT',dict(publication_id=publication,
                    observation_id=f['observation_id'],original_observation_id=previous['observation_id'],
                    receipt_ts=f['receipt_ts'],first_receipt_ts=previous['receipt_ts'],
                    available_at=f['available_at'],accepted_by_owner=f['accepted_by_owner']))
                return
            reasons=[]
            if f['receipt_ts']<previous['receipt_ts']:reasons.append('RECEIPT_REGRESSION')
            if f['source_ts']<previous['source_ts']:reasons.append('SOURCE_REGRESSION')
            if f['source_ts']==previous['source_ts'] and f['value']!=previous['value']:reasons.append('CONFLICT')
            if f['source_ts']-previous['source_ts']>15:reasons.append('SOURCE_GAP_OVER_15S')
            if reasons:self.write('SOURCE_GAP',dict(reasons=reasons,prior=previous['observation_id'],current=f['observation_id']))
        else:
            self.write('SOURCE_GAP',dict(reason='SOURCE_START_OR_EPOCH_CHANGE',asset=f['asset'],feed=f['feed'],epoch=f['epoch']))
        self.write('SOURCE',f)
        self._sources[key]=f


def source_events(records):
    """Expand compact repeat receipts without refreshing a publication's first receipt."""
    original={}
    for r in records:
        p=r['payload'];session=r['session']
        if r['kind']=='SOURCE':
            original[(session,p['observation_id'])]=p
            yield r
        elif r['kind']=='SOURCE_REPEAT':
            first=original[(session,p['original_observation_id'])]
            yield dict(r,payload=dict(first,**p,original_receipt_ts=first['original_receipt_ts']))


def read_archive(path, max_decoded_bytes=256*1024*1024):
    """Offline bounded reader. Corrupt segment => explicit gap, no partial claims.

    Session and sequence determine order; mtime, filenames and copy order do not.
    No accepted continuity across sessions. Does not alter or repair source bytes.
    """
    sessions=defaultdict(list);gaps=[];decoded=0
    files=list(Path(str(path)+'.segments').glob('*.jsonl.gz'))
    if sum(p.stat().st_size for p in files)>256*1024*1024:raise ValueError('READ_BUDGET')
    for file in sorted(files):
        records=[]
        try:
            with gzip.open(file,'rb') as stream:
                while True:
                    raw=stream.readline(5*1024*1024+1)
                    if not raw:break
                    decoded+=len(raw)
                    if decoded>max_decoded_bytes:raise MemoryError('DECODED_ARCHIVE_BUDGET')
                    if len(raw)>5*1024*1024 or not raw.endswith(b'\n'):raise ValueError('TORN_OR_OVERSIZE_RECORD')
                    r=json.loads(raw);digest=r.pop('sha256')
                    if r['schema']!=SCHEMA or digest!=sha(canonical(r)):raise ValueError('RECORD_HASH')
                    if r['evidence_class'] not in {'FIXTURE','NATIVE_CAPTURE'}:raise ValueError('EVIDENCE_CLASS')
                    if any(r.get(k)!=v for k,v in SAFETY.items()):raise ValueError('SAFETY_INVARIANT')
                    r['sha256']=digest;records.append(r)
        except MemoryError:
            raise
        except Exception as exc:
            gaps.append(dict(reason='CORRUPT_SEGMENT',file=file.name,error=type(exc).__name__))
            continue
        for r in records:sessions[r['session']].append(r)
    valid=[]
    for session,rows in sorted(sessions.items()):
        rows.sort(key=lambda r:r['sequence']);prev=None
        for i,r in enumerate(rows,1):
            if r['sequence']!=i or r['previous_sha256']!=prev:
                gaps.append(dict(reason='SEQUENCE_OR_HASH_CHAIN',session=session));break
            valid.append(r);prev=r['sha256']
            if r['kind'] in {'EVIDENCE_GAP','SOURCE_GAP','STREAM_END','INFORMATION_FAILURE'}:
                gaps.append(dict(reason=r['kind'],session=session,sequence=i,details=r['payload']))
        if not rows or rows[0]['kind']!='START' or rows[-1]['kind']!='STOP':
            gaps.append(dict(reason='UNCLOSED_OR_INCOMPLETE_SESSION',session=session))
    return dict(records=valid,gaps=gaps,sessions=len(sessions),continuous_across_sessions=False)


def reconstruct(records):
    """Lossless input/proof reconstruction, including original proof byte hash."""
    vectors={};result=[]
    for r in records:
        p=r['payload'];session=r['session']
        if r['kind']=='VECTOR':
            old=vectors.get((session,p['base'])) if p['base'] else []
            if old is None:raise ValueError('MISSING_VECTOR_BASE')
            rows=old[p['drop']:]+p['append']
            if sha(canonical(rows))!=p['id']:raise ValueError('VECTOR_HASH')
            vectors[(session,p['id'])]=rows
        elif r['kind'] in {'INFORMATION_INPUT','QUOTE_PROOF'}:
            def expand(x):
                if isinstance(x,dict):
                    if set(x)=={'vector_ref'}:return vectors[(session,x['vector_ref'])]
                    if set(x)=={'proof_event_vector_ref'}:
                        return [json.loads(t) for t in vectors[(session,x['proof_event_vector_ref'])]]
                    return {k:expand(v) for k,v in x.items()}
                if isinstance(x,list):return [expand(v) for v in x]
                return x
            value=expand(p['skeleton'])
            if r['kind']=='QUOTE_PROOF':
                # Canonical envelope sorted keys; restore the writer's fixed order.
                value={k:value[k] for k in ('source_time','ticker','epoch','consumed_ms','identity','events')}
                raw=json.dumps(value,separators=(',', ':'),allow_nan=False).encode()
                if sha(raw)!=p['proof_sha256']:raise ValueError('PROOF_HASH')
                result.append(dict(kind=r['kind'],value=value,raw=raw,proof_sha256=p['proof_sha256'],
                                   witness=p['witness']))
            else:
                raw=canonical(value)
                if sha(raw)!=p['input_sha256']:raise ValueError('INPUT_HASH')
                result.append(dict(kind=r['kind'],value=value,raw=raw))
    return result
