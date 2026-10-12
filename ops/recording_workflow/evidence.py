"""Streaming immutable index and bounded range retrieval. No source mutations."""
from pathlib import Path
from collections import Counter,defaultdict
import base64,gzip,hashlib,json,os,sqlite3
from candidates.early_recording_20261012.archive import SCHEMA,canonical,sha,SAFETY
from .policy import local_root
MAX_LINE=5*1024**2

def file_sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()

def validate_record(r):
    body=dict(r);digest=body.pop('sha256')
    if body.get('schema')!=SCHEMA or sha(canonical(body))!=digest:raise ValueError('RECORD_HASH')
    if body.get('evidence_class') not in ('FIXTURE','NATIVE_CAPTURE'):raise ValueError('CLASS')
    if any(body.get(k)!=v for k,v in SAFETY.items()):raise ValueError('SAFETY')
    return r

def lines(path):
    with gzip.open(path,'rb') as f:
        n=0
        while True:
            raw=f.readline(MAX_LINE+1)
            if not raw:break
            n+=1
            if len(raw)>MAX_LINE or not raw.endswith(b'\n'):raise ValueError('TORN_OR_OVERSIZE_RECORD')
            yield n,validate_record(json.loads(raw)),raw

def clocks(p):
    at=next((p[k] for k in ('receipt_ts','received_at','capture_cutoff','committed_at','observed_at','accepted_at') if type(p.get(k)) in (int,float)),None)
    if at is None and type((p.get('witness') or {}).get('consumed_ms')) in (int,float):at=p['witness']['consumed_ms']/1000
    return at

def index_run(root,out,*,max_index_bytes=128*1024**2):
    root=local_root(root);out=local_root(out);out.mkdir(parents=True,exist_ok=False)
    db=sqlite3.connect(out/'index.sqlite3');db.execute('PRAGMA journal_mode=DELETE')
    db.execute('PRAGMA max_page_count='+str(max_index_bytes//4096))
    db.executescript('''CREATE TABLE records(role TEXT,session TEXT,seq INTEGER,kind TEXT,at REAL,
        contract TEXT,sha TEXT,prev TEXT,file TEXT,line INTEGER,PRIMARY KEY(session,seq));
        CREATE INDEX selection ON records(contract,at);
        CREATE TABLE dependencies(session TEXT,identity TEXT,seq INTEGER,PRIMARY KEY(session,identity));''')
    files=[];gaps=[];counts=Counter();coverage=defaultdict(lambda:dict(count=0,first=None,last=None));sessions={}
    for role in ('source','information'):
        for f in sorted((root/(role+'.segments')).glob('*.jsonl.gz')):
            rel=str(f.relative_to(root));before=file_sha(f);size=f.stat().st_size
            files.append(dict(path=rel,sha256=before,size=size,role=role))
            try:
                for n,r,raw in lines(f):
                    p=r['payload'];k=r['kind'];s=r['session'];at=clocks(p)
                    contract=p.get('ticker') or p.get('contract') or (p.get('witness') or {}).get('ticker') or (p.get('official_fields') or {}).get('ticker')
                    if k=='INFORMATION_INPUT':contract=(p['skeleton']['anchor'].get('contract') or p['skeleton']['anchor'].get('ticker'))
                    if k=='NATIVE_RECORD':contract=json.loads(p['raw']).get('contract')
                    if k=='SOURCE':
                        c=coverage[p['asset']];c['count']+=1;t=p['source_ts']
                        c['first']=t if c['first'] is None else min(c['first'],t);c['last']=t if c['last'] is None else max(c['last'],t)
                    db.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?)',(role,s,r['sequence'],k,at,contract,r['sha256'],r['previous_sha256'],rel,n))
                    for identity in [p.get('id'),p.get('sha256'),p.get('observation_id')]:
                        if identity:db.execute('INSERT OR IGNORE INTO dependencies VALUES (?,?,?)',(s,identity,r['sequence']))
                    counts[k]+=1
                    if k in ('EVIDENCE_GAP','INFORMATION_FAILURE') or (k=='SOURCE_GAP' and p.get('reason')!='SOURCE_START_OR_EPOCH_CHANGE'):
                        gaps.append(dict(reason=k,session=s,seq=r['sequence'],details=p))
                if f.stat().st_size!=size or file_sha(f)!=before:raise ValueError('SOURCE_CHANGED_DURING_INDEX')
            except Exception as exc:gaps.append(dict(reason='INDEX_OR_CORRUPT_SEGMENT',file=rel,error=str(exc)[:160]))
    for s, in db.execute('SELECT DISTINCT session FROM records'):
        previous=None;expected=1;last=None
        for seq,kind,digest,prev in db.execute('SELECT seq,kind,sha,prev FROM records WHERE session=? ORDER BY seq',(s,)):
            if seq!=expected or prev!=previous or (seq==1 and kind!='START'):
                gaps.append(dict(reason='SEQUENCE_OR_HASH_CHAIN',session=s,seq=seq))
            previous=digest;expected=seq+1;last=kind
        if last!='STOP':gaps.append(dict(reason='UNCLOSED_SESSION',session=s))
        sessions[s]=dict(last_sequence=expected-1,clean_stop=last=='STOP',last_sha256=previous)
    db.commit();db.close()
    info=dict(schema='BTC15_INDEX_V1',root=str(root),files=files,counts=dict(counts),coverage=dict(coverage),
              sessions=sessions,gaps=gaps,index_sha256=file_sha(out/'index.sqlite3'),**SAFETY)
    (out/'index_manifest.json').write_bytes(canonical(info));return info

def records_for(root,index,*,contract=None,start=None,end=None,max_bytes=32*1024**2):
    """Original envelopes, plus transitive raw/vector deps and snapshot prefix.

    Byte ceiling is a hard error, never silently truncated. Index is immutable.
    Sources are contract-independent. Contract-owned rows never change ticker.
    """
    root=local_root(root);index=Path(index)
    manifest=json.loads((index/'index_manifest.json').read_bytes())
    if file_sha(index/'index.sqlite3')!=manifest['index_sha256']:raise ValueError('INDEX_HASH')
    with sqlite3.connect((index/'index.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as db:
        selected={};todo=[]
        for row in db.execute('SELECT session,seq,kind,at,contract,file,line FROM records'):
            s,seq,kind,at,ticker,file,line=row
            if (start is None or at is not None and at>=start) and (end is None or at is not None and at<=end) and (contract is None or ticker in (contract,None)):
                todo.append((s,seq))
        file_entries={e['path']:e for e in manifest['files']};cache={};used=0
        def fetch(s,seq):
            nonlocal used
            if (s,seq) in selected:return selected[(s,seq)]
            row=db.execute('SELECT file,line FROM records WHERE session=? AND seq=?',(s,seq)).fetchone()
            if not row:raise ValueError('MISSING_RECORD_DEPENDENCY')
            name,line=row;f=root/name
            if name not in cache:
                entry=file_entries[name]
                if f.stat().st_size!=entry['size'] or file_sha(f)!=entry['sha256']:raise ValueError('SOURCE_FILE_HASH')
                rows={};decoded=0
                for n,r,raw in lines(f):
                    decoded+=len(raw)
                    if decoded>64*1024**2:raise ValueError('RETRIEVAL_SEGMENT_DECODE_BUDGET')
                    rows[n]=(r,len(raw))
                # At most one decoded segment (64MiB raw cap); no unbounded cache.
                cache.clear();cache[name]=rows
            if line not in cache[name]:raise ValueError('RECORD_LOCATION')
            r,size=cache[name][line];used+=size
            if used>max_bytes:raise ValueError('RANGE_BYTE_BUDGET')
            selected[(s,seq)]=r;return r
        def dep(s,identity):
            row=db.execute('SELECT seq FROM dependencies WHERE session=? AND identity=?',(s,identity)).fetchone()
            if row is None:raise ValueError('MISSING_DEPENDENCY:'+identity)
            todo.append((s,row[0]))
        while todo:
            s,seq=todo.pop()
            if (s,seq) in selected:continue
            r=fetch(s,seq);p=r['payload'];k=r['kind']
            if k=='VECTOR' and p.get('base'):dep(s,p['base'])
            if k in ('QUOTE_ACCEPT','QUOTE_RECEIVE','HTTP_RESPONSE'):dep(s,p['raw_sha256'])
            if k=='SOURCE_REPEAT':dep(s,p['original_observation_id'])
            def refs(x):
                if isinstance(x,dict):
                    for key,value in x.items():
                        if key in ('vector_ref','proof_event_vector_ref'):dep(s,value)
                        else:refs(value)
                elif isinstance(x,list):
                    for value in x:refs(value)
            if k in ('INFORMATION_INPUT','QUOTE_PROOF'):refs(p['skeleton'])
            # Include accepted depth prefix for selected quote identities. Never
            # invent a fresh snapshot from a consumer top-of-book observation.
            if k=='QUOTE_ACCEPT':
                for n, in db.execute("SELECT seq FROM records WHERE session=? AND seq<? AND kind IN ('QUOTE_ACCEPT','QUOTE_RECEIVE','STREAM_START','STREAM_END','EVIDENCE_GAP') AND (contract=? OR contract IS NULL)",(s,seq,p['ticker'])):
                    if (s,n) not in selected:todo.append((s,n))
        return [selected[k] for k in sorted(selected)],dict(bytes=used,scope=dict(contract=contract,start=start,end=end),
                original_manifest_sha256=file_sha(index/'index_manifest.json'),complete_session=False,
                note='Range with dependencies; original sequence gaps outside selection are intentional, not a whole-run certificate')


def independent_history(records,cut):
    """Populate corrected history API from original observations as-of receipt.

    No selected model, score, label or research BUY. Recovery records excluded.
    """
    from candidates.early_rebuild_20261012.underlying_history import Observation,UnderlyingHistory,FIXTURE,NATIVE
    from candidates.early_recording_20261012.archive import source_events
    h=UnderlyingHistory();latest={};joined=[]
    events=sorted(source_events(records),key=lambda r:(r['payload']['available_at'],r['sequence']))
    for r in events:
        p=r['payload'];t=p['available_at']
        if t>cut or p['basis']!='ORIGINAL' or not p['accepted_by_owner']:continue
        latest[p['asset']]=p
        if set(latest)!={'BTC','BRTI'}:continue
        b,z=latest['BTC'],latest['BRTI']
        o=Observation(time=t,received=t,btc=b['value'],brti=z['value'],source_id=b['feed']+'|'+z['feed'],
            source_epoch=b['epoch']+'|'+z['epoch'],record_id=b['observation_id']+'|'+z['observation_id'],
            evidence_class=FIXTURE if r['evidence_class']=='FIXTURE' else NATIVE,
            btc_source_time=b['source_ts'],btc_received_time=b['receipt_ts'],brti_source_time=z['source_ts'],
            brti_received_time=z['receipt_ts'],btc_source_id=b['feed'],brti_source_id=z['feed'],
            btc_epoch=b['epoch'],brti_epoch=z['epoch'])
        try:h.ingest(o,t);joined.append(o)
        except ValueError:h.invalidate('EXPORTED_SOURCE_NOT_CAUSALLY_READY')
    return h,joined
