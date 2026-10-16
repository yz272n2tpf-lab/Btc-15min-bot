"""Streaming immutable index and bounded range retrieval. No source mutations."""
from pathlib import Path
from collections import Counter,defaultdict
import base64,gzip,hashlib,json,os,sqlite3,time
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

def index_run(root,out,*,max_index_bytes=128*1024**2,profile=None):
    begun=time.monotonic();decoded=0;record_count=0
    caps=dict(index=128*1024**2,decoded=512*1024**2,records=500000,compressed=512*1024**2,seconds=180)
    if profile is not None:
        from ops.live_recording.policy import PROFILES
        p=PROFILES[profile];caps=dict(index=p['index'],decoded=p['decoded'],records=p['records'],compressed=sum(p['compressed'].values()),seconds=p['reader_seconds']);max_index_bytes=caps['index']
    if not 4096<=max_index_bytes<=caps['index']:raise ValueError('INDEX_BUDGET')
    root=local_root(root);out=local_root(out);out.mkdir(parents=True,exist_ok=False)
    db=sqlite3.connect(out/'index.sqlite3');db.execute('PRAGMA journal_mode=DELETE')
    db.execute('PRAGMA cache_size=-4096');db.execute('PRAGMA temp_store=FILE')
    db.execute('PRAGMA max_page_count='+str(max_index_bytes//4096))
    db.executescript('''CREATE TABLE records(role TEXT,session TEXT,seq INTEGER,kind TEXT,at REAL,
        contract TEXT,sha TEXT,prev TEXT,file TEXT,line INTEGER,PRIMARY KEY(session,seq));
        CREATE INDEX selection ON records(contract,at);
        CREATE TABLE dependencies(session TEXT,identity TEXT,seq INTEGER,PRIMARY KEY(session,identity));''')
    files=[];gaps=[];counts=Counter();coverage=defaultdict(lambda:dict(count=0,first=None,last=None));sessions={}
    for role in ('source','information'):
        for f in sorted((root/(role+'.segments')).glob('*.jsonl.gz')):
            if f.is_symlink():raise ValueError('INDEX_SYMLINK')
            if len(files)>=4096:raise ValueError('INDEX_FILE_BUDGET')
            rel=str(f.relative_to(root));before=file_sha(f);size=f.stat().st_size
            if sum(e['size'] for e in files)+size>caps['compressed']:raise ValueError('INDEX_COMPRESSED_BUDGET')
            files.append(dict(path=rel,sha256=before,size=size,role=role))
            try:
                for n,r,raw in lines(f):
                    decoded+=len(raw);record_count+=1
                    if decoded>caps['decoded'] or record_count>caps['records'] or time.monotonic()-begun>caps['seconds'] or len(gaps)>1024:raise MemoryError('INDEX_CAPACITY_EXHAUSTED')
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
                    owner_unavailable=profile is not None and k=='INFORMATION_FAILURE' and p.get('reason') in ('INPUT_NOT_PUBLISHED','PUBLISHER_EXCEPTION')
                    if (k in ('EVIDENCE_GAP','INFORMATION_FAILURE') and not owner_unavailable) or (k=='SOURCE_GAP' and p.get('reason')!='SOURCE_START_OR_EPOCH_CHANGE'):
                        gaps.append(dict(reason=k,session=s,seq=r['sequence'],details=p))
                if f.stat().st_size!=size or file_sha(f)!=before:raise ValueError('SOURCE_CHANGED_DURING_INDEX')
            except (MemoryError,sqlite3.OperationalError):
                db.close();raise
            except Exception as exc:gaps.append(dict(reason='INDEX_OR_CORRUPT_SEGMENT',file=rel,error=str(exc)[:160]))
    for s, in db.execute('SELECT DISTINCT session FROM records'):
        previous=None;expected=1;last=None
        for seq,kind,digest,prev in db.execute('SELECT seq,kind,sha,prev FROM records WHERE session=? ORDER BY seq',(s,)):
            if seq!=expected or prev!=previous or (seq==1 and kind!='START'):
                gaps.append(dict(reason='SEQUENCE_OR_HASH_CHAIN',session=s,seq=seq))
            previous=digest;expected=seq+1;last=kind
        if last!='STOP':gaps.append(dict(reason='UNCLOSED_SESSION',session=s))
        sessions[s]=dict(last_sequence=expected-1,clean_stop=last=='STOP',last_sha256=previous)
    if not sessions:gaps.append(dict(reason='UNCLOSED_SESSION',session=None,detail='NO_DURABLE_START_OR_VALID_RECORDS'))
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
                if len(todo)>65536:raise ValueError('RANGE_RECORD_COUNT_BUDGET')
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
            if len(todo)+len(selected)>131072:raise ValueError('RANGE_DEPENDENCY_COUNT_BUDGET')
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

def streaming_window_inventory(root, out, *, window_seconds=900, max_window_bytes=8*1024**2,
                               max_window_records=20000, max_total_records=300000000,
                               max_total_decoded_bytes=256*1024**3,
                               max_files=4096, max_manifest_bytes=256*1024**2, quote_handoff=None,
                               native_handoff=None):
    """Bounded *structural* inventory in the existing evidence reader.

    Consumes every original gzip JSONL envelope; preserves per-session SHA chain
    across byte/time slices, without making a per-record SQLite index or copying
    evidence. This cannot substitute for CampaignVerifier's Kalshi, quote-book,
    native decision, settlement and EARLY lifecycle association checks.

    Source times only label observed time slices, NEVER official contract windows.
    Untimed events remain ordered and explicitly counted as untimed. A broken
    chain, incomplete session, mixed class or changed source is fatal. An
    EVIDENCE_GAP stays in the result and prevents any loss-free claim.
    """
    import math
    from collections import Counter

    if not isinstance(window_seconds,int) or not 1<=window_seconds<=3600:
        raise ValueError('WINDOW_SECONDS')
    if not isinstance(max_window_bytes,int) or not MAX_LINE<=max_window_bytes<=64*1024**2:
        raise ValueError('WINDOW_BYTE_BUDGET')
    if not isinstance(max_window_records,int) or not 1<=max_window_records<=100000:
        raise ValueError('WINDOW_RECORD_BUDGET')
    root=local_root(root);out=local_root(out)
    if not root.is_dir() or root.is_symlink() or out.exists():
        raise ValueError('WINDOWED_SOURCE_OR_OUTPUT')
    # The first validated line identifies which session and original sequence
    # this segment starts at; random filename suffixes are NOT event order.
    files=[]
    for role in ('source','information'):
        folder=root/(role+'.segments')
        if folder.is_symlink():raise ValueError('WINDOWED_SYMLINK')
        for path in folder.glob('*.jsonl.gz') if folder.exists() else ():
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError('WINDOWED_INVALID_SOURCE_PATH')
            if len(files)>=max_files:raise ValueError('WINDOWED_FILE_LIMIT')
            rel=str(path.relative_to(root))
            digest=file_sha(path)
            size=path.stat().st_size
            try:
                with gzip.open(path,'rb') as handle: first=handle.readline(MAX_LINE+1)
                if not first or len(first)>MAX_LINE or not first.endswith(b'\n'):
                    raise ValueError('WINDOWED_INVALID_SEGMENT_FIRST_RECORD')
                r=validate_record(json.loads(first))
                if type(r.get('sequence')) is not int or r['sequence']<=0 or not r.get('session'):
                    raise ValueError('WINDOWED_FIRST_RECORD_IDENTITY')
            except (OSError,EOFError,UnicodeError,ValueError) as exc:
                raise ValueError('WINDOWED_SEGMENT_FIRST_RECORD') from exc
            files.append(dict(path=rel,role=role,session=r['session'],
                              first_sequence=r['sequence'],size=size,sha256=digest))
    if not files:raise ValueError('WINDOWED_EMPTY_SOURCE')

    files.sort(key=lambda x:(x['role'],x['session'],x['first_sequence']))
    seen_start=set()
    summary=dict(schema='BTC15_STREAMING_15M_ARCHIVE_INVENTORY_V1',
                 window_seconds=window_seconds,max_window_records=max_window_records,
                 max_window_bytes=max_window_bytes,source_file_count=len(files),
                 source_files=files,record_count=0,decoded_bytes=0,windows=0,
                 max_window_observed_records=0,max_window_observed_bytes=0,
                 unclocked_records=0,clock_regressions=0,loss_indicators={},
                 per_kind={},sessions=[],
                 structural_integrity='UNVERIFIED',
                 complete_market_evidence=False,early_strategy_qualified=False,
                 actual_contract_alignment_verified=False,
                 source_time_basis='RECEIPT_OR_ACCEPTANCE_WHEN_PRESENT; NO_SYNTHETIC_CLOCKS; UNTIMED_EVENTS_SEQUENCE_ONLY',
                 native_lifecycle_and_quote_associations='NOT_EVALUATED',
                 signal_only=True,orders=False)
    out.mkdir(parents=True,mode=0o700)
    active=None;current=None;total_bytes=0;losses=Counter();kinds=Counter()

    def flush(fh):
        nonlocal current,total_bytes
        if current is None:return
        item=dict(current)
        item['kinds']=dict(item['kinds'])
        item['loss_indicators']=dict(item['loss_indicators'])
        if quote_handoff is not None:
            item['quote_state_handoff']=quote_handoff.checkpoint(item['role'],item['session'],item['last_sequence'])
        if native_handoff is not None:
            item['native_journal_handoff']=native_handoff.checkpoint(item['role'],item['session'],item['last_sequence'])
        raw=canonical(item)+b'\n'
        total_bytes+=len(raw)
        if total_bytes>max_manifest_bytes:raise ValueError('WINDOWED_MANIFEST_CAPACITY')
        fh.write(raw)
        summary['windows']+=1
        summary['max_window_observed_records']=max(summary['max_window_observed_records'],item['records'])
        summary['max_window_observed_bytes']=max(summary['max_window_observed_bytes'],item['decoded_bytes'])
        current=None

    def open_window(role,session,bucket):
        return dict(role=role,session=session,observed_utc_15m_bucket=bucket,
                    bucket_is_actual_contract=False,records=0,decoded_bytes=0,
                    timed_records=0,untimed_records=0,first_sequence=None,
                    last_sequence=None,first_predecessor_sha256=None,
                    last_record_sha256=None,ranges=[],kinds=Counter(),
                    loss_indicators=Counter())

    def switch_session(role,session):
        nonlocal active
        if active is not None:
            if not active['ended']:
                raise ValueError('WINDOWED_SESSION_NOT_CLOSED')
            summary['sessions'].append(dict(role=active['role'],session=active['session'],
                                             records=active['records'],last_record_sha256=active['last_hash'],
                                             last_sequence=active['seq'],class_=active['evidence_class'],
                                             clean_stop=True))
        if (role,session) in seen_start:
            raise ValueError('WINDOWED_SESSION_REAPPEARED')
        seen_start.add((role,session))
        active=dict(role=role,session=session,seq=0,last_hash=None,ended=False,
                    records=0,evidence_class=None,last_bucket=None)

    with (out/'windows.jsonl').open('xb') as fh:
        for entry in files:
            role=entry['role'];session=entry['session']
            if active is None or (active['role'],active['session'])!=(role,session):
                flush(fh)
                switch_session(role,session)
            path=root/entry['path']
            # Validate the original file identity before *and* after reading.
            if file_sha(path)!=entry['sha256'] or path.stat().st_size!=entry['size']:
                raise ValueError('WINDOWED_SOURCE_CHANGED_BEFORE_READ')
            for ordinal,r,raw in lines(path):
                if r['session']!=session:
                    raise ValueError('WINDOWED_MIXED_SESSION_SEGMENT')
                if active['ended']:
                    raise ValueError('WINDOWED_RECORD_AFTER_STOP')
                seq=r.get('sequence')
                if type(seq) is not int or seq!=active['seq']+1:
                    raise ValueError('WINDOWED_MISSING_DUPLICATE_OR_OUT_OF_ORDER_RECORD')
                if r.get('previous_sha256')!=active['last_hash']:
                    raise ValueError('WINDOWED_PREDECESSOR_CHAIN')
                if seq==1 and r.get('kind')!='START':
                    raise ValueError('WINDOWED_MISSING_START')
                if active['evidence_class'] is not None and r['evidence_class']!=active['evidence_class']:
                    raise ValueError('WINDOWED_CLASS_CHANGED')
                active['evidence_class']=r['evidence_class']
                k=r['kind'];p=r['payload']
                if k=='START' and seq!=1:raise ValueError('WINDOWED_DUPLICATE_START')
                if k=='STOP':
                    if p.get('clean') is not True:raise ValueError('WINDOWED_UNCLEAN_STOP')
                    active['ended']=True
                size=len(raw)
                if size>max_window_bytes:raise ValueError('WINDOWED_SINGLE_RECORD_TOO_LARGE')
                summary['record_count']+=1;summary['decoded_bytes']+=size
                if summary['record_count']>max_total_records or summary['decoded_bytes']>max_total_decoded_bytes:
                    raise ValueError('WINDOWED_TOTAL_INPUT_BUDGET')
                at=clocks(p)
                stamped=type(at) in (int,float) and math.isfinite(at)
                bucket=int(math.floor(at/window_seconds)) if stamped else active['last_bucket']
                if stamped and active['last_bucket'] is not None and bucket<active['last_bucket']:
                    summary['clock_regressions']+=1
                    bucket=active['last_bucket'] # physical sequence is always authoritative
                if stamped:active['last_bucket']=bucket
                else:summary['unclocked_records']+=1
                if current is not None and (
                    current['role']!=role or current['session']!=session
                    or current['observed_utc_15m_bucket']!=bucket
                    or current['decoded_bytes']+size>max_window_bytes
                    or current['records']>=max_window_records):
                    flush(fh)
                if current is None:current=open_window(role,session,bucket)
                # The original envelope SHA/sequence has already passed the
                # structural check. Replay its original quote state only now,
                # after the previous window's audit checkpoint is frozen.
                if quote_handoff is not None:quote_handoff.accept(role,r)
                if native_handoff is not None:native_handoff.accept(role,r)
                if current['first_sequence'] is None:
                    current['first_sequence']=seq
                    current['first_predecessor_sha256']=r['previous_sha256']
                current['last_sequence']=seq
                current['last_record_sha256']=r['sha256']
                current['records']+=1;current['decoded_bytes']+=size
                current['timed_records']+=int(stamped)
                current['untimed_records']+=int(not stamped)
                current['kinds'][k]+=1;kinds[k]+=1
                if k in ('EVIDENCE_GAP','INFORMATION_FAILURE') or (
                    k=='SOURCE_GAP' and p.get('reason')!='SOURCE_START_OR_EPOCH_CHANGE'):
                    current['loss_indicators'][k]+=1
                    losses[k]+=1
                ranges=current['ranges']
                if ranges and ranges[-1]['file']==entry['path'] and ranges[-1]['last_line']==ordinal-1:
                    ranges[-1]['last_line']=ordinal
                else:
                    ranges.append(dict(file=entry['path'],first_line=ordinal,last_line=ordinal))
                active['seq']=seq;active['last_hash']=r['sha256'];active['records']+=1
            if file_sha(path)!=entry['sha256'] or path.stat().st_size!=entry['size']:
                raise ValueError('WINDOWED_SOURCE_CHANGED_DURING_READ')
        flush(fh)
        if active is not None:
            if not active['ended']:raise ValueError('WINDOWED_SESSION_UNCLOSED')
            summary['sessions'].append(dict(role=active['role'],session=active['session'],
                                             records=active['records'],last_record_sha256=active['last_hash'],
                                             last_sequence=active['seq'],class_=active['evidence_class'],
                                             clean_stop=True))
        fh.flush();os.fsync(fh.fileno())

    summary['per_kind']=dict(kinds);summary['loss_indicators']=dict(losses)
    if quote_handoff is not None:
        summary['quote_state_handoff']=quote_handoff.finish()
    if native_handoff is not None:
        summary['native_journal_handoff']=native_handoff.finish()
    summary['windows_manifest_sha256']=file_sha(out/'windows.jsonl')
    summary['windows_manifest_bytes']=(out/'windows.jsonl').stat().st_size
    summary['structural_integrity']='PASS'
    summary['loss_free']=not bool(losses)
    (out/'window_inventory_manifest.json').write_bytes(canonical(summary))
    return summary