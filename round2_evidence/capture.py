"""Offline detached-member archive. No sockets, producer I/O or authority calls."""
from dataclasses import asdict
import hashlib,hmac,json,sqlite3,zlib
from pathlib import Path
from btc15_external_evidence_admission_v1 import signature,parsed_member,MAX_COMPRESSED,MAX_MANIFEST,SCHEMA as ACQUISITION_SCHEMA
from btc15_directional_signal_authority_v1 import pack
from .contract import FIELDS,PRODUCERS

def sha(data):return hashlib.sha256(data).hexdigest()
def missing(spec,why):return dict(status='UNAVAILABLE',value=None,producer=spec['producer'],source_path=spec['source_path'],reason=why)
def extract(root,path):
    for key in path.split('.'):
        if not isinstance(root,dict) or key not in root:return None,'FIELD_NOT_EMITTED'
        root=root[key]
    return (root,None) if root is not None else (None,'EMITTED_NULL')

def normalize(record,identity):
    if (not isinstance(record,dict) or record.get('schema_version')!=1 or record.get('record_type')!='OBSERVATION'
        or record.get('orders') is not False or record.get('signal_only') is not True):raise ValueError('COMMON_RECORD_SCHEMA')
    ss=record.get('sources')
    if not isinstance(ss,list) or not 1<=len(ss)<=4:raise ValueError('COMMON_SOURCE_COUNT')
    sources={}
    for s in ss:
        if not isinstance(s,dict) or s.get('service') not in ('main','owner','v81','serial') or s['service'] in sources:raise ValueError('SOURCE_IDENTITY_CONFLICT')
        sources[s['service']]=s
    main=sources.get('main',{});raw=main.get('state')
    if main.get('http_status')!=200 or main.get('error_type'):raw=None
    def state(service):
        s=sources.get(service,{})
        return s.get('state') if s.get('http_status')==200 and not s.get('error_type') else None
    roots={'COMMON_OBSERVER':record,'COMMON_MAIN_RECEIPT':main,'PROTECTED_MAIN':raw,
        'BRTI_OWNER':{'owner_state':state('owner')},
        'V81_PUBLICATION':{'v81_state':state('v81')},
        'SERIAL_PUBLICATION':{'serial_state':state('serial')}}
    cells={}
    for spec in FIELDS:
        p=spec['producer'];path=spec['source_path']
        if path is None:cells[spec['field']]=missing(spec,spec['producer_state']);continue
        root=roots.get(p)
        if not isinstance(root,dict):cells[spec['field']]=missing(spec,'SOURCE_ERROR_OR_WAIT');continue
        value,why=extract(root,path)
        if p=='PROTECTED_MAIN' and path.startswith('final') and (not isinstance(root.get('final'),dict) or root['final'].get('source')!='FROZEN_V4_6_FINAL'):
            why='GENUINE_PROTECTED_FINAL_UNAVAILABLE';value=None
        if p=='PROTECTED_MAIN' and path.startswith('early') and (not isinstance(root.get('early'),dict) or root['early'].get('source')!='FROZEN_TIER1'):
            why='GENUINE_PROTECTED_EARLY_UNAVAILABLE';value=None
        cells[spec['field']]=missing(spec,why) if why else dict(status='OBSERVED',value=value,producer=p,source_path=path,reason=None)
    out=dict(schema='BTC15_ROUND2_EVIDENCE_V1',record_id=identity,mode='EVIDENCE_ONLY',guidance=None,orders_enabled=False,
        coverage='SOURCE_ERROR_OR_WAIT' if raw is None else 'UNAVAILABLE_INCOMPLETE_PRODUCERS',fields=cells,
        source_dispositions=[{k:v for k,v in s.items() if k!='state'} for s in ss])
    validate(out);return out

def validate(out):
    if set(out)!=set(('schema','record_id','mode','guidance','orders_enabled','coverage','source_dispositions','fields')):raise ValueError('ENVELOPE_FIELDS')
    if out['schema']!='BTC15_ROUND2_EVIDENCE_V1' or out['mode']!='EVIDENCE_ONLY' or out['guidance'] is not None or out['orders_enabled'] is not False:raise ValueError('EVIDENCE_NOT_AUTHORITY')
    if out['coverage'] not in ('UNAVAILABLE_INCOMPLETE_PRODUCERS','SOURCE_ERROR_OR_WAIT'):raise ValueError('COVERAGE_NOT_QUALIFIED')
    expected={s['field']:s for s in FIELDS}
    if set(out['fields'])!=set(expected):raise ValueError('FIELD_COVERAGE')
    for name,c in out['fields'].items():
        if set(c)!=set(('status','value','producer','source_path','reason')):raise ValueError('CELL_FIELDS')
        spec=expected[name]
        if c['producer']!=spec['producer'] or c['source_path']!=spec['source_path']:raise ValueError('PRODUCER_BINDING')
        if c['status']=='UNAVAILABLE':
            if c['value'] is not None or not isinstance(c['reason'],str) or not c['reason']:raise ValueError('UNAVAILABLE_NOT_NULL')
        elif c['status']=='OBSERVED':
            if c['value'] is None or c['reason'] is not None or spec['source_path'] is None:raise ValueError('FABRICATED_PRODUCER')
        else:raise ValueError('INVALID_CELL_STATUS')
    pack(out) # rejects nonfinite values

def initialize(path,policy,*,quota_bytes=64*1024*1024):
    """Explicit NEW offline store only; never automatically recreate missing state."""
    if type(quota_bytes) is not int or quota_bytes<32768:raise ValueError('STORE_QUOTA')
    path=Path(path)
    with path.open('xb'):pass
    with sqlite3.connect(path) as db:
        db.executescript('''PRAGMA synchronous=FULL;
        CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT NOT NULL);
        CREATE TABLE members(seq INTEGER PRIMARY KEY,offset INTEGER UNIQUE,digest TEXT NOT NULL,original BLOB NOT NULL,manifest TEXT NOT NULL,projection TEXT NOT NULL);
        CREATE TRIGGER no_member_update BEFORE UPDATE ON members BEGIN SELECT RAISE(ABORT,'immutable'); END;
        CREATE TRIGGER no_member_delete BEFORE DELETE ON members BEGIN SELECT RAISE(ABORT,'immutable'); END;''')
        for k,v in dict(policy=asdict(policy),quota=quota_bytes,offset=policy.start_offset,sequence=policy.start_sequence).items():
            db.execute('INSERT INTO meta VALUES (?,?)',(k,pack(v)))

class DetachedRecorder:
    """Consumer-local bounded persistence. No queue/callback/ACK to any producer.
    Returning a receipt to this offline caller is not a network acknowledgement.
    Runtime attachment/acquisition is deliberately absent until qualified.
    """
    def __init__(self,path,policy,*,acquisition_key):
        if type(acquisition_key) is not bytes or len(acquisition_key)<32:raise ValueError('KEY_REQUIRED')
        self.path=Path(path);self.policy=policy;self.key=acquisition_key
        self.status='UNAVAILABLE_NO_INPUT'
    def _db(self):
        if self.path.is_symlink():raise ValueError('STORE_SYMLINK')
        db=sqlite3.connect(self.path.resolve().as_uri()+'?mode=rw',uri=True,timeout=0)
        db.execute('PRAGMA synchronous=FULL');return db
    def accept(self,data,envelope):
        try:
            if type(data) is not bytes or not 0<len(data)<=MAX_COMPRESSED:raise ValueError('MEMBER_SIZE')
            if type(envelope) is not bytes or not 0<len(envelope)<=MAX_MANIFEST:raise ValueError('MANIFEST_SIZE')
            from btc15_protected_publication_handoff_v1 import strict_json
            env=strict_json(envelope.decode());m=env['manifest']
            if not isinstance(env,dict) or not isinstance(m,dict):raise ValueError('MANIFEST_OBJECT_REQUIRED')
            if not isinstance(env['mac'],str) or not hmac.compare_digest(env['mac'],signature(m,self.key)):raise ValueError('ACQUISITION_AUTHENTICATION')
            policy=asdict(self.policy)
            for name in ('endpoint','service_id','run_id','observer_epoch','collector_commit','run_manifest_sha256','signer_id','stream_id'):
                if m.get(name)!=policy[name]:raise ValueError('ACQUISITION_BINDING:'+name)
            if m.get('fingerprints')!=dict(self.policy.fingerprints):raise ValueError('BUILD_FINGERPRINTS')
            if m.get('schema')!=ACQUISITION_SCHEMA or m.get('acquisition')!='DETACHED_IMMUTABLE_MEMBER' or m.get('orders') is not False:raise ValueError('ACQUISITION_SCHEMA')
            if m.get('v2_admitted') is not False or m.get('native_decision_id') is not None:raise ValueError('FORGED_NATIVE_WITNESS')
            if any(type(m.get(x)) is not int for x in ('offset','end_offset','sequence','byte_count')):raise ValueError('STREAM_TYPES')
            if m['offset']<0 or m['sequence']<1 or m['sha256']!=sha(data) or m['byte_count']!=len(data) or m['end_offset']!=m['offset']+len(data):raise ValueError('MEMBER_INTEGRITY')
            r=parsed_member(data)
            if any(r.get(k)!=m[k] for k in ('run_id','observer_epoch')) or r.get('sequence_in_process')!=m['sequence']:raise ValueError('MEMBER_IDENTITY')
            ident=sha(pack([m['stream_id'],m['run_id'],m['observer_epoch'],m['sequence'],m['sha256']]).encode())
            out=normalize(r,ident)
            with self._db() as db:
                db.execute('BEGIN IMMEDIATE')
                meta={k:json.loads(v) for k,v in db.execute('SELECT k,v FROM meta')}
                if pack(meta['policy'])!=pack(policy):raise ValueError('STORE_POLICY_CONFLICT')
                old=db.execute('SELECT digest,offset FROM members WHERE seq=?',(m['sequence'],)).fetchone()
                if old:
                    if tuple(old)!=(m['sha256'],m['offset']):raise ValueError('REPLAY_CONFLICT')
                    self.status='DUPLICATE_RECORDED';return dict(status=self.status,guidance=None,orders_enabled=False)
                if m['offset']!=meta['offset'] or m['sequence']!=meta['sequence']:raise ValueError('STREAM_GAP_OR_REPLAY')
                projection=pack(out)
                if self.path.stat().st_size+len(data)+len(projection.encode())+len(envelope)+16384>meta['quota']:raise ValueError('STORE_QUOTA_EXCEEDED')
                db.execute('PRAGMA max_page_count='+str(meta['quota']//4096))
                db.execute('INSERT INTO members VALUES (?,?,?,?,?,?)',(m['sequence'],m['offset'],m['sha256'],data,envelope.decode(),projection))
                for k,v in [('offset',m['end_offset']),('sequence',m['sequence']+1)]:db.execute('UPDATE meta SET v=? WHERE k=?',(pack(v),k))
            self.status='RECORDED_PARTIAL';return dict(status=self.status,record=out,guidance=None,orders_enabled=False)
        except (ValueError,TypeError,KeyError,UnicodeError,RecursionError,OSError,sqlite3.Error,zlib.error) as exc:
            self.status='UNAVAILABLE';return dict(status=self.status,reason=str(exc),guidance=None,orders_enabled=False)
