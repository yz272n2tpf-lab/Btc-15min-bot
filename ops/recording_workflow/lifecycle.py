"""Exact stored-identity joins only; no strategy reducer or inferred decisions.

Information is an independent informational stream, not a native decision input.
Native frames lack an information-input hash/anchor id and an HTTP response hash.
We verify exact unique source tuples and official identity tuples, explicitly
without claiming a consumed-information or consumed-HTTP-response association.
"""
from contextlib import closing
import json, sqlite3, zlib
from .whole_run import require,number,timestamp,Exhausted,small_json
from .evidence import file_sha
from candidates.early_recording_20261012.archive import canonical,sha
from btc15_ladder_journal_v1 import digest
from btc15_kalshi_quote_provenance_v1 import Book

def ref(row):return dict(session=row[0],sequence=row[1],partition=row[2])

def rows(v,t):
    for s,q,p,data in v.db.execute('SELECT s,q,p,v FROM facts WHERE t=? ORDER BY s,q',(t,)):
        v.budget();yield (s,q,p),json.loads(data)

def one(values,reason):
    it=iter(values);a=next(it,None);b=next(it,None)
    require(a is not None and b is None,reason)
    return a

def source(v,asset,src,received,value,epoch,cut,part):
    require(all(number(x) for x in (src,received,value,cut)) and src<=received<=cut,'SOURCE_CUTOFF')
    args=[asset,src,received,value]
    query='SELECT s,q,p,v FROM sources WHERE asset=? AND source=? AND receipt=? AND value=?'
    if epoch is not None:query+=' AND epoch=?';args.append(epoch)
    matches=[]
    for s,q,p,raw in v.db.execute(query,args):
        z=json.loads(raw)
        if z['basis']=='ORIGINAL' and z['accepted_by_owner'] and z['available_at']<=cut:
            matches.append((s,q,p))
            if len(matches)>1:break
    a=one(matches,'MISSING_OR_AMBIGUOUS_EXACT_ORIGINAL_SOURCE:'+asset)
    if a[2]!=part:v.metrics['cross_partition_associations']+=1
    return ref(a)

def metadata(v,ticker,opened,closed,target,cut,part):
    if hasattr(v,'fast_metadata'):return v.fast_metadata(ticker,opened,closed,target,cut,part)
    matches=[]
    for s,q,p,raw in v.db.execute('SELECT s,q,p,v FROM facts WHERE t="metadata" AND id=?',(ticker,)):
        z=json.loads(raw);m=z['market']
        if (m['ticker'],timestamp(m['open_time']),timestamp(m['close_time']),m['floor_strike'])==(ticker,opened,closed,target) and z['received_at']<=cut:
            matches.append((s,q,p))
    require(bool(matches),'MISSING_EXACT_METADATA')
    # Repeated official responses with the identical identity tuple are an
    # equivalence set, never a guessed consumed response or nearest-time join.
    a=matches[0]
    if a[2]!=part:v.metrics['cross_partition_associations']+=1
    return dict(ref(a),equivalent_observations=len(matches),basis='EXACT_OFFICIAL_IDENTITY_TUPLE_NOT_CONSUMED_HTTP_HASH')

def verify_proof(v,loc,z):
    p=z['value'];w=z['witness'];s,q,part=loc
    require([w[x] for x in ('market_id','sid','seq','exchange_ts_ms')]==p['identity'],'PROOF_WITNESS_IDENTITY')
    require(all(w[x]==p[x] for x in ('ticker','epoch','source_time','consumed_ms')),'PROOF_WITNESS_FIELDS')
    require(p['events'],'EMPTY_PROOF')
    book=Book(p['ticker']);last_part=part
    for event in p['events']:
        v.budget();book.apply(event)
        # Canonical event identity compares parsed original bytes without
        # falsely requiring source whitespace/member order to match proof JSON.
        candidates=v.db.execute('SELECT s,q,p,at,received FROM accepted WHERE epoch=? AND ticker=? AND market=? AND sid=? AND seq=? AND proof_event=? AND at<=?',
          (p['epoch'],p['ticker'],book.market_id,book.sid,book.seq,sha(canonical(event)),p['consumed_ms']/1000))
        candidates=list(candidates)
        require(bool(candidates),'MISSING_EXACT_PROOF_RECEIPT')
        require(len({x[0] for x in candidates})==1,'PROOF_RECEIPT_CROSSES_SESSIONS')
        a=candidates[0] # identical replay-event identity; all queried receipts precede cut
        require(a[4]<=a[3]<=p['consumed_ms']/1000,'PROOF_AVAILABILITY')
        if a[2]!=part:v.metrics['cross_partition_associations']+=1
        if event is p['events'][0]:source_session=a[0]
        require(a[0]==source_session,'PROOF_CROSSES_SOURCE_SESSION')
    require([book.market_id,book.sid,book.seq,book.ts_ms]==p['identity'],'PROOF_REPLAY_IDENTITY')
    prices=list(book.quotes(p['consumed_ms'],w['close_ms']))
    prior=v.db.execute('SELECT v FROM facts WHERE t="verified_proof" AND id=?',(z['proof_sha256'],)).fetchone()
    if prior:
        require(json.loads(prior[0])==dict(witness=w,quotes=prices),'CONFLICTING_VERIFIED_PROOF')
        v.metrics['proof_receipts_verified']+=1
        return
    v.fact('verified_proof',z['proof_sha256'],dict(session=s,sequence=q,_part=part),dict(witness=w,quotes=prices))
    fields=('ticker','source_time','epoch','consumed_ms','market_id','sid','seq','exchange_ts_ms','close_ms')
    v.fact('verified_proof_key',sha(canonical([w.get(x) for x in fields])),dict(session=s,sequence=q,_part=part),dict(witness=w,quotes=prices))
    v.metrics['proof_receipts_verified']+=1

def quote(v,frame,part):
    q=frame['quote'];matches=[]
    fields=('ticker','source_time','epoch','consumed_ms','market_id','sid','seq','exchange_ts_ms','close_ms')
    require(q['ticker']==frame['contract'] and q['close_ms']==int(frame['official_close']*1000),'CROSS_CONTRACT_QUOTE')
    require(timestamp(q['source_time'])==frame['feature_cutoff'],'QUOTE_SOURCE_CUTOFF_IDENTITY')
    require(q['exchange_ts_ms']/1000<=q['consumed_ms']/1000<=frame['captured_ts'],'QUOTE_DECISION_AVAILABILITY')
    for s,n,p,data in v.db.execute('SELECT s,q,p,v FROM facts WHERE t="verified_proof_key" AND id=?',(sha(canonical([q.get(x) for x in fields])),)):
        z=json.loads(data)
        if all(z['witness'].get(x)==q.get(x) for x in fields):
            require(z['quotes']==list(q['quotes']),'QUOTE_DISPLAYED_PRICES')
            matches.append((s,n,p))
    require(bool(matches),'MISSING_EXACT_NATIVE_PROOF')
    a=matches[0]
    if a[2]!=part:v.metrics['cross_partition_associations']+=1
    return dict(ref(a),equivalent_proofs=len(matches),basis='EXACT_WITNESS_EQUIVALENCE')

def verify_journals(v,scope):
    if scope is None:v.issue('DETACHED_JOURNAL_EXPECTATIONS_MISSING');return
    expected=scope.get('journals',[]);seen=set();journal_bytes=0
    require(len(expected)<=v.b['files'],'DETACHED_JOURNAL_COUNT')
    for e in expected:
        name=e['path'];path=v.root/name
        require(not path.is_symlink() and path.resolve().is_relative_to(v.root) and name.startswith('detached/'),'DETACHED_PATH')
        journal_bytes+=path.stat().st_size
        if journal_bytes>v.b['journal_bytes']:raise Exhausted('COMBINED_DETACHED_JOURNAL_BYTES')
        require(file_sha(path)==e['sha256'],'DETACHED_JOURNAL_HASH')
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
            db.execute('PRAGMA query_only=ON')
            require(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','DETACHED_SQLITE_INTEGRITY')
            meta=dict(db.execute('SELECT k,v FROM meta'));jid=meta['journal_id']
            require(jid==e['journal_id'] and jid not in seen,'JOURNAL_IDENTITY');seen.add(jid)
            lo,hi,n=db.execute('SELECT min(seq),max(seq),count(*) FROM events').fetchone()
            require((lo,hi,n)==(e['first_sequence'],e['last_sequence'],e['records']) and n>0 and hi-lo+1==n,'JOURNAL_SEQUENCE_SCOPE')
            require(v.db.execute('SELECT count(*) FROM journals WHERE id=?',(jid,)).fetchone()[0]==n,'MISSING_OR_EXTRA_JOURNAL_MIRROR')
            for seq,h,body in db.execute('SELECT seq,sha256,CASE WHEN length(body)<=? THEN body ELSE NULL END FROM events ORDER BY seq',(v.b['record_bytes'],)):
                require(body is not None,'COMPRESSED_JOURNAL_RECORD_BUDGET')
                v.budget();de=zlib.decompressobj();raw=de.decompress(body,v.b['record_bytes']+1)
                require(de.eof and not de.unconsumed_tail and len(raw)<=v.b['record_bytes'],'JOURNAL_RECORD_BUDGET_OR_CORRUPT')
                require(sha(raw)==h,'DETACHED_NATIVE_HASH')
                mirror=v.db.execute('SELECT h,v FROM journals WHERE id=? AND seq=?',(jid,seq)).fetchone()
                require(mirror is not None and mirror[0]==h and json.loads(mirror[1])['raw'].encode()==raw,'EXACT_JOURNAL_MIRROR_MISSING')
                v.metrics['original_journal_records_verified']+=1
        require(file_sha(path)==e['sha256'],'DETACHED_JOURNAL_CHANGED')
    require(seen=={r[0] for r in v.db.execute('SELECT DISTINCT id FROM journals')},'UNDECLARED_NATIVE_JOURNAL')

def frame_links(v,f,part):
    cut=f['feature_cutoff'];b=f['brti']
    require(number(cut) and f['official_open']<=cut<=f['captured_ts']<f['official_close'] and f['official_close']-f['official_open']==900,'DECISION_CONTRACT_CLOCK')
    return dict(BTC=source(v,'BTC',f['btc_source'],f['btc_received'],f['btc_price'],None,cut,part),
        BRTI=source(v,'BRTI',b['cf_ts'],b['delivery']['observed_ts'],b['value'],b['delivery']['owner_epoch'],cut,part),
        metadata=metadata(v,f['contract'],f['official_open'],f['official_close'],f['target'],cut,part),
        quote=quote(v,f,part))

def verify_associations(v,scope):
    try:verify_journals(v,scope)
    except (Exhausted,sqlite3.OperationalError):raise
    except Exception as exc:v.issue('ORIGINAL_JOURNAL_ASSOCIATION',detail=str(exc))
    for loc,z in rows(v,'QUOTE_PROOF'):
        try:verify_proof(v,loc,z)
        except (Exhausted,sqlite3.OperationalError):raise
        except Exception as exc:v.issue('PROOF_ASSOCIATION',record=ref(loc),detail=str(exc))
    # Duplicate native epoch/sequence is never resolved by nearest timestamp.
    for id,n in v.db.execute('SELECT id,count(*) FROM facts WHERE t="decision" GROUP BY id HAVING count(*)>1'):
        v.issue('DUPLICATE_OR_CONFLICTING_NATIVE_DECISION',identity=id,count=n)
    # Index original origins first so cross-partition links do not require rescans.
    for loc,z in rows(v,'decision'):
        n=z['native'];o=n.get('origin')
        if o:
            f=n['evidence'];key=[o['native_epoch'],o['native_sequence']]
            try:
                require(n.get('event')=='BUY' and o['origin_id']==digest([n['candidate'],o['contract'],key,o['side']]),'ORIGIN_ID_HASH')
                require(o['entry_provenance']==f and key==[f['native_epoch'],f['native_sequence']],'ORIGIN_ENTRY_PROVENANCE')
                require(all(o[k]==f[k] for k in ('contract','target','official_open','official_close')),'ORIGIN_CONTRACT')
                v.fact('origin',o['origin_id'],dict(session=loc[0],sequence=loc[1],_part=loc[2]),o)
            except (Exhausted,sqlite3.OperationalError):raise
            except Exception as exc:v.issue('ORIGIN_ASSOCIATION',record=ref(loc),detail=str(exc))
    for loc,z in rows(v,'decision'):
        n=z['native'];f=n['evidence'];part=loc[2]
        try:
            require(n['contract']==f['contract'] and f['captured_ts']<=n['published_ts']<=z['committed_at'],'NATIVE_PUBLICATION_CHRONOLOGY')
            if n.get('unavailable_reason'):
                v.emit(v.fassoc,dict(record=ref(loc),status='LEGITIMATE_UNAVAILABLE',reason=n['unavailable_reason'],terminal_required=False))
                v.metrics['legitimate_unavailable']+=1;continue
            links=frame_links(v,f,part);final=n.get('final')
            require(final is not None,'MISSING_NATIVE_FINAL_PUBLICATION')
            require(final['publication_id']==digest([n['candidate'],'FINAL',[f['native_epoch'],f['native_sequence']]]),'FINAL_PUBLICATION_ID')
            require(final.get('state') in ('FINAL_CALL','PASS') and final.get('ready')==(final['state']=='FINAL_CALL'),'FINAL_STATE')
            oid=n.get('origin_id');terminal=n.get('terminal');management=n.get('management')
            if oid:
                o=one(v.db.execute('SELECT s,q,p,v FROM facts WHERE t="origin" AND id=?',(oid,)),'MISSING_OR_AMBIGUOUS_ORIGIN')
                origin=json.loads(o[3]);entry=origin['entry_provenance']
                require(all(origin[k]==f[k] for k in ('contract','target','official_open','official_close')),'CROSS_CONTRACT_ORIGIN')
                require(entry['captured_ts']<=f['captured_ts'] and final.get('early_origin_id')==oid,'FINAL_ORIGIN_CHRONOLOGY')
                links['origin']=ref(o)
                if o[2]!=part:v.metrics['cross_partition_associations']+=1
                require(management is not None,'MISSING_MANAGEMENT')
                if management.get('state')=='EXIT':require(terminal is not None,'MISSING_APPLICABLE_TERMINAL')
                if terminal:
                    require(terminal['state']=='EXIT' and terminal['origin_id']==oid and terminal['contract']==f['contract'] and terminal['side']==origin['side'],'TERMINAL_IDENTITY')
                    require(entry['captured_ts']<=terminal['decision_ts']<=f['captured_ts'],'TERMINAL_CHRONOLOGY')
                    require(management['terminal']==terminal,'MANAGEMENT_TERMINAL_CONFLICT')
                    tq=terminal['quote']
                    owner=one(( (ownerloc,ownerz) for ownerloc,ownerz in rows(v,'decision') if ownerz['native']['evidence']['captured_ts']==terminal['decision_ts'] and ownerz['native']['evidence']['quote']==tq and ownerz['native'].get('origin_id')==oid),'MISSING_EXACT_TERMINAL_DECISION')
                    links['terminal_decision']=ref(owner[0]);v.metrics['terminal_associations']+=1
            else:
                require(final.get('early_origin_id') is None and terminal is None and management is None,'ORPHAN_LIFECYCLE_LINK')
                v.metrics['legitimate_no_origin']+=1
            v.emit(v.fassoc,dict(record=ref(loc),native_journal=dict(id=z['original_journal'],sequence=z['sequence'],record_sha256=z['sha256']),
                native_identity=[f['native_epoch'],f['native_sequence']],contract=f['contract'],cutoff=f['feature_cutoff'],
                status='VERIFIED_FIXTURE_LINKS',links=links,final_state=final['state'],
                information_consumption='NOT_A_NATIVE_INPUT; no input_sha256/anchor_id stored',
                terminal_required=bool(management and management.get('state')=='EXIT')))
            v.metrics['native_associations']+=1
        except (Exhausted,sqlite3.OperationalError):raise
        except Exception as exc:v.issue('NATIVE_LIFECYCLE_ASSOCIATION',record=ref(loc),detail=str(exc))
    for loc,z in rows(v,'INFORMATION_INPUT'):
        try:
            f=z['value'];a=f['anchor'];b=f['brti'];cut=f['cut'];p=f['proof']
            require(f.get('schema')=='BTC15_INFORMATION_INPUT_V1' and a.get('schema')=='BTC15_NATIVE_INFORMATION_ANCHOR_V1','UNSUPPORTED_INFORMATION_SCHEMA')
            require(f['anchor_id']==sha(canonical(a)),'INFORMATION_ANCHOR_HASH')
            require(not a['completed'],'COMPLETED_CANDLE_ORIGINAL_PROVENANCE_NOT_RECORDED')
            require(0<len(a['ticks'])<=4096,'TICK_HISTORY_BOUND')
            prior=None
            for st,rt,val in a['ticks']:
                require(prior is None or rt>=prior,'TICK_RECEIPT_ORDER')
                source(v,'BTC',st,rt,val,None,a['decision'],loc[2]);prior=rt
            require(a['ticks'][-1]==[a['btc']['source'],a['btc']['received'],a['btc']['value']],'ANCHOR_LAST_TICK')
            require(a['opened']<=a['decision']<=a['captured']<=cut<a['closed'],'INFORMATION_CUTOFF')
            links=dict(BTC=source(v,'BTC',a['btc']['source'],a['btc']['received'],a['btc']['value'],None,a['decision'],loc[2]),
                BRTI=source(v,'BRTI',b['source'],b['received'],b['value'],b['epoch'],cut,loc[2]),
                metadata=metadata(v,a['ticker'],a['opened'],a['closed'],a['target'],cut,loc[2]))
            proof=one(((p_loc,p_z) for p_loc,p_z in rows(v,'QUOTE_PROOF') if p_z['value']==p),'INFORMATION_EXACT_PROOF_MISSING')
            require(v.db.execute('SELECT 1 FROM facts WHERE t="verified_proof" AND id=?',(proof[1]['proof_sha256'],)).fetchone(),'INFORMATION_PROOF_RECEIPTS_UNVERIFIED')
            require(p['ticker']==a['ticker'] and p['consumed_ms']/1000<=f['quote_received']<=cut,'INFORMATION_QUOTE_CUTOFF')
            links['proof']=ref(proof[0]);v.emit(v.fassoc,dict(record=ref(loc),input_sha256=z['input_sha256'],status='VERIFIED_INDEPENDENT_INFORMATION_INPUT',links=links,cutoff=cut,native_consumption_link='NOT_STORED_OR_CLAIMED'))
            v.metrics['information_associations']+=1
        except (Exhausted,sqlite3.OperationalError):raise
        except Exception as exc:v.issue('INFORMATION_ASSOCIATION',record=ref(loc),detail=str(exc))
    for loc,z in rows(v,'native_other'):
        n=z['native'];kind=n.get('kind')
        if kind=='UNAVAILABLE' and n.get('unavailable_reason'):
            v.emit(v.fassoc,dict(record=ref(loc),status='LEGITIMATE_UNAVAILABLE',terminal_required=False));v.metrics['legitimate_unavailable']+=1
        else:v.issue('UNSUPPORTED_NATIVE_LIFECYCLE_SCHEMA',record=ref(loc),kind=kind,schema=n.get('schema'))
    if scope is not None:
        expected=scope.get('native_decisions')
        actual=v.db.execute('SELECT count(*) FROM facts WHERE t="decision"').fetchone()[0]
        if not isinstance(expected,int) or expected<=0 or expected!=actual:v.issue('EXPECTED_NATIVE_DECISION_COUNT',expected=expected,actual=actual)
    v.db.commit()
