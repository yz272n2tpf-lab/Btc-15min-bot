"""Bounded whole-supplied-run verification. Never certifies production completeness.

Raw records stream once into a quota-limited SQLite work database. Reconstruction
uses original session/sequence order and disk-backed dependencies, never a subset
as a whole-run certificate. Original segments remain immutable. Fixture scope is
an explicit expectation, not a source of observations or association fields.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime
import base64, gzip, hashlib, json, math, os, sqlite3, time
from .evidence import file_sha, lines
from .policy import local_root, FLAGS
from candidates.early_recording_20261012.archive import canonical, sha, bounded_size
from btc15_kalshi_quote_provenance_v1 import Book
MiB=1024**2
LIMITS=dict(partition_bytes=8*MiB,record_bytes=5*MiB,decoded_bytes=512*MiB,
    compressed_bytes=512*MiB,journal_bytes=128*MiB,work_db_bytes=256*MiB,index_bytes=128*MiB,
    vector_bytes=3*MiB,object_bytes=32*MiB,manifest_bytes=4*MiB,
    ledger_bytes=16*MiB,files=4096,records=500000,partitions=4096,
    cache_kib=4096,seconds=180)

class Exhausted(ValueError):pass

def limits(overrides=None):
    b=dict(LIMITS);b.update(overrides or {})
    if set(b)!=set(LIMITS) or any(type(v) is not int or not 0<v<=LIMITS[k] for k,v in b.items()):raise ValueError('VERIFIER_LIMITS')
    if b['record_bytes']>b['partition_bytes']:raise ValueError('RECORD_MUST_FIT_PARTITION')
    return b

def small_json(path,limit):
    if path.stat().st_size>limit:raise Exhausted('MANIFEST_BYTES')
    return json.loads(path.read_bytes())

def require(test,reason):
    if not test:raise ValueError(reason)

def number(x):return type(x) in (int,float) and math.isfinite(x)

def timestamp(x):
    if number(x):return x
    return datetime.fromisoformat(x.replace('Z','+00:00')).timestamp()

class Verifier:
    def __init__(self,root,index,output,b):
        self.root=local_root(root);self.index=local_root(index);self.out=local_root(output)
        self.out.mkdir(parents=True,exist_ok=False);self.b=b;self.started=time.monotonic()
        self.errors=Counter();self.counts=Counter();self.metrics=Counter();self.classes=set();self.processed=Counter();self.partition_errors=Counter()
        self.total=0;self.rows=0;self.part=0;self.part_bytes=0;self.part_rows=0
        self.part_hash=hashlib.sha256();self.parts_hash=hashlib.sha256();self.ledger_used=0
        self.db=sqlite3.connect(self.out/'verification.sqlite3')
        self.db.set_progress_handler(lambda: int(time.monotonic()-self.started>b['seconds']),10000)
        self.db.execute('PRAGMA page_size=4096');self.db.execute('PRAGMA journal_mode=OFF')
        self.db.execute('PRAGMA synchronous=OFF');self.db.execute('PRAGMA temp_store=FILE')
        self.db.execute('PRAGMA mmap_size=0');self.db.execute('PRAGMA cache_size=-'+str(b['cache_kib']))
        self.db.execute('PRAGMA max_page_count='+str(b['work_db_bytes']//4096))
        try:
            self.db.executescript('''
              CREATE TABLE raw(s TEXT,q INTEGER,k TEXT,p INTEGER,r BLOB,h TEXT,role TEXT,PRIMARY KEY(s,q));
              CREATE INDEX raw_partition ON raw(p);
              CREATE TABLE deps(s TEXT,t TEXT,id TEXT,q INTEGER,p INTEGER,v BLOB,PRIMARY KEY(s,t,id));
              CREATE TABLE facts(t TEXT,id TEXT,s TEXT,q INTEGER,p INTEGER,v BLOB);
              CREATE INDEX fact_id ON facts(t,id);
              CREATE TABLE sessions(s TEXT PRIMARY KEY,role TEXT,n INTEGER,h TEXT,class TEXT);
              CREATE TABLE sources(asset TEXT,source REAL,receipt REAL,value REAL,epoch TEXT,available REAL,basis TEXT,accepted INTEGER,s TEXT,q INTEGER,p INTEGER,v BLOB);
              CREATE INDEX source_tuple ON sources(asset,source,receipt,value);
              CREATE INDEX source_availability ON sources(asset,basis,accepted,available);
              CREATE INDEX source_identity ON sources(s,json_extract(v,'$.observation_id'));
              CREATE TABLE accepted(s TEXT,epoch TEXT,ticker TEXT,market TEXT,sid INTEGER,seq INTEGER,ts INTEGER,at REAL,received REAL,event TEXT,proof_event TEXT,p INTEGER,q INTEGER);
              CREATE INDEX accepted_tuple ON accepted(epoch,ticker,market,sid,seq,ts);
              CREATE TABLE journals(id TEXT,seq INTEGER,h TEXT,s TEXT,q INTEGER,p INTEGER,v BLOB,PRIMARY KEY(id,seq));
            ''')
        except Exception:
            self.db.close();raise
        self.fgap=(self.out/'issues.jsonl').open('xb');self.fpart=(self.out/'partitions.jsonl').open('xb')
        self.fassoc=(self.out/'associations.jsonl').open('xb')

    def budget(self):
        if time.monotonic()-self.started>self.b['seconds']:raise Exhausted('TIME_BUDGET')
        if self.db.execute('PRAGMA page_count').fetchone()[0]*4096>self.b['work_db_bytes']:raise Exhausted('WORK_DB_BYTES')

    def emit(self,f,value):
        if f is self.fassoc:
            def bind_hash(x):
                if isinstance(x,dict):
                    if all(k in x for k in ('session','sequence','partition')):
                        row=self.db.execute('SELECT h FROM raw WHERE s=? AND q=?',(x['session'],x['sequence'])).fetchone()
                        if row:x['record_sha256']=row[0]
                    for item in list(x.values()):bind_hash(item)
                elif isinstance(x,list):
                    for item in x:bind_hash(item)
            bind_hash(value)
        raw=canonical(value)+b'\n';self.ledger_used+=len(raw)
        if self.ledger_used>self.b['ledger_bytes']:raise Exhausted('LEDGER_BYTES')
        f.write(raw)
        return raw

    def issue(self,reason,**detail):
        part=detail.get('partition') or (detail.get('record') or {}).get('partition')
        if part is not None:self.partition_errors[part]+=1
        self.errors[reason]+=1;self.emit(self.fgap,dict(reason=reason,**detail))

    def dep(self,s,t,id,q=None,p=None):
        row=self.db.execute('SELECT q,p,v FROM deps WHERE s=? AND t=? AND id=?',(s,t,id)).fetchone()
        require(row is not None,'MISSING_DEPENDENCY:'+t)
        if q is not None:require(row[0]<q,'DEPENDENCY_NOT_PREVIOUS_IN_SESSION')
        if p is not None and row[1]!=p:self.metrics['cross_partition_dependencies']+=1
        return json.loads(row[2])

    def put(self,s,t,id,q,p,value):
        raw=canonical(value);bounded_size(value,self.b['object_bytes'])
        if len(raw)>self.b['vector_bytes'] and t=='vector':raise Exhausted('VECTOR_BYTES')
        old=self.db.execute('SELECT v FROM deps WHERE s=? AND t=? AND id=?',(s,t,id)).fetchone()
        if old:
            require(old[0]==raw,'CONFLICTING_DEPENDENCY_IDENTITY')
            # Repeated bytes/vectors may legitimately recur after bounded writer cache eviction.
            return
        self.db.execute('INSERT INTO deps VALUES (?,?,?,?,?,?)',(s,t,id,q,p,raw))

    def fact(self,t,id,r,v):
        self.db.execute('INSERT INTO facts VALUES (?,?,?,?,?,?)',(t,str(id),r['session'],r['sequence'],r['_part'],canonical(v)))

    def finish_partition(self):
        if not self.part_rows:return
        value=dict(partition=self.part,records=self.part_rows,decoded_bytes=self.part_bytes,
            ordered_record_hashes_sha256=self.part_hash.hexdigest(),first_record=self.part_first,last_record=self.part_last)
        raw=self.emit(self.fpart,value);self.parts_hash.update(raw)
        self.part_bytes=self.part_rows=0;self.part_hash=hashlib.sha256()

    def ingest(self):
        b=self.b
        idx=small_json(self.index/'index_manifest.json',b['manifest_bytes'])
        require((self.index/'index.sqlite3').stat().st_size<=b['index_bytes'],'INDEX_BYTE_BUDGET')
        require(file_sha(self.index/'index.sqlite3')==idx['index_sha256'],'INDEX_HASH')
        expected={e['path']:e for e in idx['files']}
        require(len(expected)==len(idx['files']),'DUPLICATE_INDEX_FILE')
        actual={}
        for role in ('source','information'):
            directory=self.root/(role+'.segments')
            if directory.exists():
                for p in directory.iterdir():
                    if p.name=='writer.lock':continue
                    require(p.is_file() and not p.is_symlink() and p.name.endswith('.jsonl.gz'),'UNSUPPORTED_ARCHIVE_MEMBER')
                    actual[str(p.relative_to(self.root))]=p
                    if len(actual)>b['files']:raise Exhausted('FILES')
        require(set(actual)==set(expected),'MISSING_OR_EXTRA_SEGMENT')
        if not actual:self.issue('EMPTY_ARCHIVE')
        if sum(p.stat().st_size for p in actual.values())>b['compressed_bytes']:raise Exhausted('COMPRESSED_BYTES')
        with sqlite3.connect((self.index/'index.sqlite3').as_uri()+'?mode=ro',uri=True) as ix:
            indexed=ix.execute('SELECT count(*) FROM records').fetchone()[0]
            require(indexed<=b['records'],'RECORD_COUNT_BUDGET')
            for name,p in sorted(actual.items()):
                self.budget();e=expected[name]
                try:
                    require(p.stat().st_size==e['size'] and file_sha(p)==e['sha256'],'SEGMENT_HASH')
                    for line,r,raw in lines(p):
                        self.budget();self.total+=len(raw);self.rows+=1
                        if len(raw)>b['record_bytes']:raise Exhausted('RECORD_BYTES')
                        if self.total>b['decoded_bytes'] or self.rows>b['records']:raise Exhausted('DECODED_OR_RECORDS')
                        if self.part_bytes+len(raw)>b['partition_bytes']:self.finish_partition()
                        if not self.part_rows:
                            self.part+=1
                            if self.part>b['partitions']:raise Exhausted('PARTITIONS')
                        location=dict(file=name,line=line,session=r['session'],sequence=r['sequence'],sha256=r['sha256'])
                        if not self.part_rows:self.part_first=location
                        self.part_last=location
                        self.part_bytes+=len(raw);self.part_rows+=1;self.part_hash.update((r['sha256']+'\n').encode())
                        bounded_size(r,b['object_bytes'])
                        require(type(r['sequence']) is int and r['sequence']>0 and isinstance(r['session'],str) and r['session'],'RECORD_IDENTITY')
                        row=ix.execute('SELECT sha,file,line,kind,role FROM records WHERE session=? AND seq=?',(r['session'],r['sequence'])).fetchone()
                        require(row==(r['sha256'],name,line,r['kind'],e['role']),'INDEX_RECORD_MISMATCH')
                        try:self.db.execute('INSERT INTO raw VALUES (?,?,?,?,?,?,?)',(r['session'],r['sequence'],r['kind'],self.part,raw,r['sha256'],e['role']))
                        except sqlite3.IntegrityError:self.issue('DUPLICATE_RECORD_IDENTITY',session=r['session'],sequence=r['sequence'])
                    require(file_sha(p)==e['sha256'],'SEGMENT_CHANGED_DURING_READ')
                except (Exhausted,sqlite3.OperationalError):raise
                except Exception as exc:self.issue('UNREADABLE_OR_CORRUPT_SEGMENT',file=name,detail=str(exc)[:160])
        self.finish_partition();self.db.commit()
        require(self.rows==indexed,'INDEX_TOTAL_MISMATCH')
        self.idx=idx
        for gap in idx['gaps']:self.issue('INDEX_REPORTED_GAP',detail=gap)

    def reconstruct(self):
        for s,role in self.db.execute('SELECT s,role FROM raw GROUP BY s,role ORDER BY CASE role WHEN "information" THEN 1 ELSE 0 END,s'):
            previous=None;last=None;expected=1;ec=None;starts=stops=0;binding=None
            for q,k,p,raw in self.db.execute('SELECT q,k,p,r FROM raw WHERE s=? ORDER BY q',(s,)):
                self.budget();r=json.loads(raw);r['_part']=p;self.counts[k]+=1;self.classes.add(r['evidence_class'])
                if q!=expected or r['previous_sha256']!=previous:self.issue('SESSION_SEQUENCE_OR_CHAIN',session=s,sequence=q)
                if ec is not None and ec!=r['evidence_class']:self.issue('SESSION_CLASS_CHANGED',session=s)
                if last=='STOP':self.issue('RECORD_AFTER_STOP',session=s)
                ec=r['evidence_class'];expected=q+1;previous=r['sha256'];last=k
                try:
                    if k=='START':
                        starts+=1;require(q==1,'START_NOT_FIRST');binding=r['payload']['source_binding']
                        require(r['payload']['continuous_with_prior_session'] is False,'UNSUPPORTED_SESSION_CONTINUITY')
                    elif k=='STOP':
                        stops+=1;require(r['payload'].get('clean') is True,'UNCLEAN_STOP')
                    else:self.record(r)
                except (Exhausted,sqlite3.OperationalError):raise
                except Exception as exc:self.issue('RECORD_VERIFICATION',session=s,sequence=q,partition=p,kind=k,detail=str(exc)[:180])
                self.processed[p]+=1
            if starts!=1 or stops!=1 or last!='STOP':self.issue('SESSION_BOUNDARY',session=s,starts=starts,stops=stops,last=last)
            self.db.execute('INSERT INTO sessions VALUES (?,?,?,?,?)',(s,role,expected-1,previous,ec))
            self.fact('session',s,dict(session=s,sequence=1,_part=0),dict(binding=binding,role=role))
        for s,t,id,q,p in self.db.execute("SELECT s,t,id,q,p FROM deps WHERE t IN ('stream','receive')"):
            target='stream_end' if t=='stream' else 'accepted_receive'
            if not self.db.execute('SELECT 1 FROM deps WHERE s=? AND t=? AND id=?',(s,target,id)).fetchone():self.unresolved(s,t,id,q,p)
        self.db.commit()

    def record(self,r):
        s,q,k,p=r['session'],r['sequence'],r['kind'],r['_part'];v=r['payload']
        if k in ('QUOTE_BYTES','HTTP_BYTES'):
            raw=base64.b64decode(v['raw_base64'],validate=True);require(sha(raw)==v['sha256'],'RAW_BYTES_HASH')
            self.put(s,k,v['sha256'],q,p,v)
        elif k=='VECTOR':
            old=self.dep(s,'vector',v['base'],q,p) if v['base'] else []
            require(type(v['drop']) is int and 0<=v['drop']<=len(old),'VECTOR_DROP')
            rows=old[v['drop']:]+v['append'];require(len(rows)<=8192 and sha(canonical(rows))==v['id'],'VECTOR_HASH_OR_ROWS')
            self.put(s,'vector',v['id'],q,p,rows)
        elif k in ('SOURCE','SOURCE_REPEAT'):
            if k=='SOURCE_REPEAT':
                first=self.dep(s,'source',v['original_observation_id'],q,p)
                v=dict(first,**v,original_receipt_ts=first['original_receipt_ts'])
                # Repeat envelope stores the full original-observation digest but omits
                # its basis fields. Recreate exactly the original writer hash input.
                chk={key:value for key,value in v.items() if key not in ('observation_id','original_observation_id','first_receipt_ts')}
                chk['original_receipt_ts']=v['receipt_ts'] if v['basis']=='ORIGINAL' else None
                require(sha(canonical(chk))==v['observation_id'],'SOURCE_REPEAT_HASH')
            else:
                chk=dict(v);oid=chk.pop('observation_id');require(sha(canonical(chk))==oid,'SOURCE_OBSERVATION_HASH')
                require(v['publication_id']==sha(canonical([v['feed'],v['epoch'],v['source_ts']])),'SOURCE_PUBLICATION_HASH')
            require(v['asset'] in ('BTC','BRTI') and v['feed'] and v['epoch'],'SOURCE_IDENTITY')
            require(all(number(v[x]) for x in ('source_ts','receipt_ts','available_at','value')) and v['source_ts']<=v['receipt_ts']<=v['available_at'],'SOURCE_CHRONOLOGY')
            require(v['basis'] in ('ORIGINAL','RECOVERED') and type(v['accepted_by_owner']) is bool,'SOURCE_BASIS')
            publication=self.db.execute('SELECT v FROM deps WHERE s=? AND t="publication" AND id=?',(s,v['publication_id'])).fetchone()
            if publication:require(json.loads(publication[0])==v['value'],'CONFLICTING_SOURCE_PUBLICATION')
            else:self.put(s,'publication',v['publication_id'],q,p,v['value'])
            require((v['basis']=='RECOVERED' and v['original_receipt_ts'] is None) or (v['basis']=='ORIGINAL' and number(v['original_receipt_ts']) and v['original_receipt_ts']<=v['receipt_ts']),'ORIGINAL_RECEIPT')
            if self.db.execute('SELECT 1 FROM sources WHERE s=? AND json_extract(v,"$.observation_id")=?',(s,v['observation_id'])).fetchone():raise ValueError('DUPLICATE_SOURCE_IDENTITY')
            self.put(s,'source',v['observation_id'],q,p,v)
            self.db.execute('INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(v['asset'],v['source_ts'],v['receipt_ts'],v['value'],v['epoch'],v['available_at'],v['basis'],int(v['accepted_by_owner']),s,q,p,canonical(v)))
        elif k=='SOURCE_GAP':
            if v.get('reason')!='SOURCE_START_OR_EPOCH_CHANGE':self.issue('SOURCE_GAP',session=s,sequence=q,details=v)
        elif k in ('EVIDENCE_GAP','INFORMATION_FAILURE'):
            self.issue(k,session=s,sequence=q,details=v)
        elif k=='STREAM_START':self.put(s,'stream',v['epoch'],q,p,v)
        elif k=='STREAM_END':
            self.dep(s,'stream',v['epoch'],q,p);self.put(s,'stream_end',v['epoch'],q,p,v)
        elif k in ('QUOTE_RECEIVE','QUOTE_ACCEPT'):
            blob=self.dep(s,'QUOTE_BYTES',v['raw_sha256'],q,p);event=json.loads(base64.b64decode(blob['raw_base64']))
            require(number(v['received_at']),'QUOTE_RECEIPT')
            id=sha(canonical([v['epoch'],v['ticker'],v['raw_sha256'],v['received_at']]))
            if k=='QUOTE_RECEIVE':
                require(self.db.execute('SELECT 1 FROM deps WHERE s=? AND t="receive" AND id=?',(s,id)).fetchone() is None,'DUPLICATE_RECEIVE_IDENTITY')
                self.put(s,'receive',id,q,p,v);return
            self.dep(s,'receive',id,q,p);self.put(s,'accepted_receive',id,q,p,v);self.dep(s,'stream',v['epoch'],q,p)
            require(self.db.execute('SELECT 1 FROM deps WHERE s=? AND t="stream_end" AND id=?',(s,v['epoch'])).fetchone() is None,'ACCEPT_AFTER_STREAM_END')
            require(number(v['accepted_at']) and v['received_at']<=v['accepted_at'],'ACCEPT_CHRONOLOGY')
            key=sha(canonical([v['epoch'],v['ticker']]))
            old=self.db.execute('SELECT v FROM deps WHERE s=? AND t="book" AND id=?',(s,key)).fetchone()
            book=Book(v['ticker'])
            if old:
                z=json.loads(old[0]);from decimal import Decimal
                for field in ('market_id','sid','seq','ts_ms','last','valid'):setattr(book,field,z[field])
                book.levels={side:{Decimal(a):Decimal(b) for a,b in rows} for side,rows in z['levels'].items()}
            book.apply(event)
            require(book.ts_ms is None or book.ts_ms/1000<=v['received_at'],'EXCHANGE_AFTER_RECEIVE')
            z={x:getattr(book,x) for x in ('market_id','sid','seq','ts_ms','last','valid')}
            z['levels']={side:[[str(a),str(b)] for a,b in rows.items()] for side,rows in book.levels.items()}
            bounded_size(z,self.b['object_bytes']);require(len(canonical(z))<=self.b['vector_bytes'],'BOOK_STATE_BUDGET')
            self.db.execute('INSERT OR REPLACE INTO deps VALUES (?,?,?,?,?,?)',(s,'book',key,q,p,canonical(z)))
            self.db.execute('INSERT INTO accepted VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(s,v['epoch'],v['ticker'],book.market_id,book.sid,book.seq,book.ts_ms,v['accepted_at'],v['received_at'],v['raw_sha256'],sha(canonical(event)),p,q))
            self.metrics['book_states']+=1
        elif k=='HTTP_RESPONSE':
            blob=self.dep(s,'HTTP_BYTES',v['raw_sha256'],q,p);body=json.loads(base64.b64decode(blob['raw_base64']))
            require(number(v['received_at']),'METADATA_RECEIPT')
            if 'market' in body:
                m=body['market'];require(all(v['official_fields'].get(x)==m.get(x) for x in v['official_fields']),'METADATA_PROJECTION')
                self.fact('metadata',m['ticker'],r,dict(v,market=m))
        elif k in ('INFORMATION_INPUT','QUOTE_PROOF'):
            def expand(x):
                if isinstance(x,dict):
                    if set(x)=={'vector_ref'}:return self.dep(s,'vector',x['vector_ref'],q,p)
                    if set(x)=={'proof_event_vector_ref'}:return [json.loads(t) for t in self.dep(s,'vector',x['proof_event_vector_ref'],q,p)]
                    return {key:expand(val) for key,val in x.items()}
                if isinstance(x,list):return [expand(t) for t in x]
                return x
            value=expand(v['skeleton']);bounded_size(value,self.b['object_bytes'])
            if k=='QUOTE_PROOF':
                value={x:value[x] for x in ('source_time','ticker','epoch','consumed_ms','identity','events')}
                raw=json.dumps(value,separators=(',',':'),allow_nan=False).encode();id=v['proof_sha256']
            else:raw=canonical(value);id=v['input_sha256']
            require(sha(raw)==id,'RECONSTRUCTED_BYTES_HASH')
            self.fact(k,id,r,dict(v,value=value));self.metrics[k]+=1
        elif k=='NATIVE_RECORD':
            raw=v['raw'].encode();require(sha(raw)==v['sha256'],'NATIVE_RAW_HASH');n=json.loads(raw)
            require(v.get('original_journal') and type(v.get('sequence')) is int and v['sequence']>0,'ORIGINAL_JOURNAL_IDENTITY')
            require(number(v['committed_at']) and v['record_basis'] in ('POST_ORIGINAL_COMMIT','POST_ADMIN_COMMIT_APPLICATION_CLOCK'),'NATIVE_COMMIT_PROVENANCE')
            try:self.db.execute('INSERT INTO journals VALUES (?,?,?,?,?,?,?)',(v['original_journal'],v['sequence'],v['sha256'],s,q,p,canonical(v)))
            except sqlite3.IntegrityError:raise ValueError('DUPLICATE_OR_CONFLICTING_JOURNAL_IDENTITY')
            if n.get('kind')=='NATIVE_DECISION':
                f=n['evidence'];self.fact('decision',canonical([f['native_epoch'],f['native_sequence']]).decode(),r,dict(v,native=n))
            else:self.fact('native_other',n.get('kind') or n.get('schema'),r,dict(v,native=n))
        else:raise ValueError('UNSUPPORTED_RECORD_KIND:'+k)

    def expectations(self):
        path=self.root/'verification_scope.json'
        if not path.exists():self.issue('DECLARED_SESSION_SCOPE_MISSING');return None
        scope=small_json(path,self.b['manifest_bytes'])
        require(scope.get('schema')=='BTC15_FIXTURE_VERIFICATION_SCOPE_V1' and scope.get('evidence_class')=='FIXTURE','UNSUPPORTED_SCOPE')
        require(scope.get('run_identity_sha256')==file_sha(self.root/'identity.json'),'RUN_IDENTITY_HASH')
        ident=small_json(self.root/'identity.json',self.b['manifest_bytes'])
        require(ident.get('mode')=='OFFLINE_FIXTURE' and all(ident.get(k)==v for k,v in FLAGS.items()),'RUN_FLAGS_OR_CLASS')
        require(set(scope['sessions'])=={s for s, in self.db.execute('SELECT s FROM sessions')},'EXPECTED_SESSION_SET')
        for s,e in scope['sessions'].items():
            got=self.db.execute('SELECT role,n,h,class FROM sessions WHERE s=?',(s,)).fetchone()
            require(got==(e['role'],e['records'],e['last_sha256'],'FIXTURE'),'EXPECTED_SESSION_BOUNDARY')
            binding=json.loads(self.db.execute('SELECT v FROM facts WHERE t="session" AND id=?',(s,)).fetchone()[0])['binding']
            require(binding==ident['run_id']+(':'+('main' if e['role']=='source' else 'information')),'SOURCE_BINDING')
        # Completeness is positively supported by declared nonempty required kinds,
        # continuous source coverage, decisions and their applicable associations.
        for kind in ('SOURCE','QUOTE_ACCEPT','QUOTE_PROOF','HTTP_RESPONSE','INFORMATION_INPUT','NATIVE_RECORD'):
            require(self.counts[kind]>0,'REQUIRED_RECORD_KIND_MISSING:'+kind)
        require(set(scope['source_windows'])=={'BTC','BRTI'},'SOURCE_WINDOWS_REQUIRED')
        for asset,w in scope['source_windows'].items():
            require(number(w['start']) and number(w['end']) and w['end']-w['start']>=120 and 0<w['max_gap']<=15,'SOURCE_WINDOW_SCOPE')
            bindings=self.db.execute('SELECT count(*) FROM (SELECT DISTINCT s,epoch FROM sources WHERE asset=? AND basis="ORIGINAL" AND accepted=1 AND available>=? AND available<=?)',(asset,w['start'],w['end'])).fetchone()[0]
            require(bindings==1,'SOURCE_WINDOW_SESSION_OR_EPOCH_BOUNDARY:'+asset)
            prior=None;first=None;n=0
            for at, in self.db.execute('SELECT available FROM sources WHERE asset=? AND basis="ORIGINAL" AND accepted=1 AND available>=? AND available<=? ORDER BY available',(asset,w['start'],w['end'])):
                if first is None:first=at
                if prior is not None:require(at-prior<=w['max_gap'],'SOURCE_WINDOW_GAP:'+asset)
                prior=at;n+=1
            require(n>1 and first==w['start'] and prior==w['end'],'SOURCE_WINDOW_INCOMPLETE:'+asset)
        return scope

    def run(self):
        scope=None;finished=False
        try:
            self.ingest();self.reconstruct();scope=self.expectations()
            self.associate(scope)
            finished=True
        except (Exhausted,sqlite3.OperationalError) as exc:
            self.errors['CAPACITY_EXHAUSTED']+=1
            # Independent stderr survives failed work/output disk. No complete verdict.
            print('BTC15_VERIFY_INCOMPLETE '+str(exc),file=__import__('sys').stderr,flush=True)
        except Exception as exc:
            try:self.issue('WHOLE_RUN_INCOMPLETE',detail=str(exc)[:200])
            except Exception:self.errors['REPORT_STORAGE_FAILURE']+=1
        finally:
            self.db.set_progress_handler(None,0)
            with (self.out/'partition_results.jsonl').open('xb') as f:
                for part,n in self.db.execute('SELECT p,count(*) FROM raw GROUP BY p ORDER BY p'):
                    f.write(canonical(dict(partition=part,indexed_records=n,processed_records=self.processed[part],local_errors=self.partition_errors[part],all_global_checks_finished=finished,whole_run_errors_apply=bool(self.errors)))+b'\n')
            self.db.commit();db_bytes=self.db.execute('PRAGMA page_count').fetchone()[0]*4096;self.db.close()
            for f in (self.fgap,self.fpart,self.fassoc):f.close()
        complete=self.complete(finished,scope)
        value=dict(schema='BTC15_WHOLE_RUN_VERIFICATION_V1',status='VERIFIED' if complete else 'INCOMPLETE',
            evidence_classes=sorted(self.classes),fixture_complete=complete,complete_supplied_scope=complete,actual_production_complete=False,
            all_partitions_processed=finished,partitions=self.part,records_read=self.rows,decoded_bytes=self.total,
            counts=dict(self.counts),metrics=dict(self.metrics),issue_counts=dict(self.errors),
            partitions_sha256=file_sha(self.out/'partitions.jsonl'),issues_sha256=file_sha(self.out/'issues.jsonl'),
            associations_sha256=file_sha(self.out/'associations.jsonl'),partition_results_sha256=file_sha(self.out/'partition_results.jsonl'),work_db_bytes=db_bytes,
            elapsed_seconds=time.monotonic()-self.started,limits=self.b,
            predictive_readiness='NOT_EVALUATED',economic_readiness='BLOCKED_FEE_APPLICABILITY',
            production_authorization='NOT_AUTHORIZED',long_test='NO_GO',**FLAGS)
        value=self.result(value,complete)
        (self.out/'summary.json').write_bytes(canonical(value));return value

    def associate(self,scope):
        from .lifecycle import verify_associations
        verify_associations(self,scope)
    def complete(self,finished,scope):
        return finished and not self.errors and scope is not None and self.classes=={'FIXTURE'} and self.metrics['native_associations']>0 and self.metrics['information_associations']>0
    def result(self,value,complete):return value
    def unresolved(self,s,t,id,q,p):self.issue('UNRESOLVED_STREAM_OR_RECEIVE',session=s,sequence=q,partition=p,kind=t)

def verify_run(root,index,output,*,budget=None):
    b=limits(budget)
    try:return Verifier(root,index,output,b).run()
    except (sqlite3.OperationalError,OSError,MemoryError) as exc:
        # Failure may occur during schema creation, before normal issue ledgers
        # exist. Always expose it independently of the failed output disk.
        value=dict(schema='BTC15_WHOLE_RUN_VERIFICATION_V1',status='INCOMPLETE',
            evidence_classes=[],fixture_complete=False,complete_supplied_scope=False,
            actual_production_complete=False,all_partitions_processed=False,partitions=0,
            records_read=0,decoded_bytes=0,counts={},metrics={},
            issue_counts={'CAPACITY_OR_STORAGE_FAILURE':1},failure=str(exc)[:200],limits=b,
            economic_readiness='BLOCKED',predictive_readiness='NOT_EVALUATED',
            production_authorization='NOT_AUTHORIZED',long_test='NO_GO',**FLAGS)
        print('BTC15_VERIFY_INCOMPLETE '+json.dumps(value),file=__import__('sys').stderr,flush=True)
        try:(local_root(output)/'summary.json').write_bytes(canonical(value))
        except OSError:pass
        return value
