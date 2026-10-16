"""Transactional window adapter for CampaignVerifier, never a new validator.

Original evidence is immutable. Quote replay, MAIN lifecycle, source and outcome
joins call the established CampaignVerifier. The existing V81 causal consumer
uses SQL-backed exact maps instead of expiring evidence from an in-memory LRU.
All working state and ledgers share one bounded, durable SQLite transaction.
"""
from collections import Counter
import fcntl
import json
import math
import os
from pathlib import Path
import sqlite3
import time

from .reader import CampaignVerifier, budgets
from .policy import canonical, sha, file_sha, atomic, safe_path
from .recovery_state import Integrity, SqlMap, pack, unpack
from .v81_window_associations_research import V81WindowAssociations
from ops.recording_workflow.lifecycle import frame_links, ref
from ops.recording_workflow.whole_run import require, Exhausted

STATE_FIELDS = ('errors', 'counts', 'metrics', 'classes', 'partition_errors',
                'current_vectors', 'lifecycle', 'pending', 'source_scope',
                'outcome_status', 'contracts', 'ledger_used', 'quarantined',
                'windows', 'generation')
V81_FIELDS = ('counts', 'total_original_native_matches', 'audit_bytes',
              'max_retained_inputs', 'max_retained_brti', 'max_retained_http')
CODE_FILES = ('ops/live_recording/windowed_campaign.py',
              'ops/live_recording/recovery_state.py', 'ops/live_recording/reader.py',
              'ops/live_recording/v81_window_associations_research.py',
              'ops/recording_workflow/evidence.py', 'ops/recording_workflow/whole_run.py',
              'ops/recording_workflow/lifecycle.py', 'ops/live_recording/policy.py',
              'btc15_kalshi_quote_provenance_v1.py', 'btc15_v81_qualified_inputs_v1.py',
              'btc15_ladder_settlement_v2.py', 'btc15_ladder_journal_v1.py',
              'candidates/early_recording_20261012/archive.py')


class Ledger:
    def __init__(self, owner, name): self.owner, self.name = owner, name
    def write(self, raw):
        row = self.owner.db.execute('SELECT n,h FROM ledger_tail WHERE name=?', (self.name,)).fetchone()
        n, previous = row if row else (0, '')
        digest = sha(previous.encode() + raw)
        self.owner.db.execute('INSERT INTO ledger VALUES (?,?,?,?,?)',
                              (self.name, n + 1, raw, previous, digest))
        if row:
            self.owner.db.execute('UPDATE ledger_tail SET n=?,h=? WHERE name=?', (n+1, digest, self.name))
        else: self.owner.db.execute('INSERT INTO ledger_tail VALUES (?,?,?)', (self.name,n+1,digest))
        return len(raw)
    def flush(self): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass


class QuoteSQL:
    def __init__(self, owner): self.owner = owner
    def match_native_v81_quote(self, session, q, cut, opened, closed):
        from btc15_kalshi_quote_provenance_v1 import MAX_AGE
        require(q.get('transport')=='timestamped_contiguous_ws','QUOTE_HANDOFF_V81_ORIGINAL_TRANSPORT')
        require(all(type(q.get(k)) is int for k in ('sid','sequence','source_ts_ms','validated_at_ms')),
                'QUOTE_HANDOFF_V81_EXACT_NUMERIC_IDENTITY')
        require(all(type(x) in (int,float) and math.isfinite(x) for x in (cut,opened,closed)),
                'QUOTE_HANDOFF_NATIVE_CUTOFF_CLOCK')
        require(closed-opened==900 and opened<=q['source_ts_ms']/1000<=q['validated_at_ms']/1000<=cut<closed,
                'QUOTE_HANDOFF_V81_15M_CUTOFF')
        require(0<=cut-q['source_ts_ms']/1000<=MAX_AGE, 'QUOTE_HANDOFF_V81_EXCHANGE_FRESHNESS')
        wanted=[q.get(k) for k in ('up_bid','up_ask','down_bid','down_ask')]
        params=(session,q['epoch'],q['ticker'],q['market_id'],q['sid'],q['sequence'],q['source_ts_ms'],q['validated_at_ms']/1000)
        count=0; sequences=[]; first=None
        for raw, at, seq in self.owner.db.execute('SELECT quotes,at,q FROM book_quotes WHERE s=? AND epoch=? AND ticker=? AND market=? AND sid=? AND seq=? AND ts=? AND at<=? ORDER BY q',params):
            require(json.loads(raw)==wanted,'QUOTE_HANDOFF_EXACT_ACCEPTED_DEPTH_PRICE_MISMATCH')
            count+=1;first=at if first is None else min(first,at)
            if len(sequences)<8:sequences.append(seq)
        require(count,'QUOTE_HANDOFF_EXACT_ACCEPTED_DEPTH_MISSING')
        return dict(identity_sha256=sha(canonical(list(params[:-1]))),original_accept_count=count,
                    original_sequences=sequences,first_accepted_at=first,reconstructed_prices=wanted,
                    source='EXACT_ORIGINAL_ACCEPTED_KALSHI_DEPTH')


class SourceSQL:
    def __init__(self, owner): self.owner = owner
    def _match_market(self, role, session, ticker, opened, closed, target, cut):
        require(closed-opened==900,'SOURCE_HANDOFF_15M_OFFICIAL_CLOCK')
        n=self.owner.db.execute('SELECT count(*) FROM official WHERE s=? AND ticker=? AND opened=? AND closed=? AND target=? AND at<=?',
                               (session,ticker,opened,closed,target,cut)).fetchone()[0]
        require(n,'SOURCE_HANDOFF_EXACT_OFFICIAL_MARKET_MISSING')
        return range(n)  # caller needs count; never materialize repeated metadata


class DurableV81(V81WindowAssociations):
    def __init__(self, owner):
        super().__init__(QuoteSQL(owner),SourceSQL(owner))
        self.owner=owner
        self.inputs=SqlMap(owner.db,'v81_inputs')
        self.brti=SqlMap(owner.db,'v81_brti')
        self.http=SqlMap(owner.db,'v81_http')
    def _bound(self, cache, key, entry, capacity, counter):
        if key in cache:
            require(cache[key]==entry,'V81_LINKS_CONFLICTING_EXACT_RECEIPT')
        else: cache[key]=entry
    def _audit_native_receipt(self, receipt):
        self.owner.emit(self.owner.v81_ledger,receipt)
        self.audit_bytes+=len(canonical(receipt))+1
        self.total_original_native_matches+=1


class WindowedCampaignVerifier(CampaignVerifier):
    def __init__(self, root, output, *, resume=False, work_db_bytes=4*1024**3,
                 ledger_bytes=512*1024**2, seconds=3600, fault=None):
        self.root=safe_path(root);self.out=safe_path(output)
        require(not self.out.is_relative_to(self.root) and not self.root.is_relative_to(self.out),
                'RECOVERY_SOURCE_OUTPUT_SEPARATION')
        require(type(work_db_bytes) is int and 1024**2<=work_db_bytes<=48*1024**3,'RECOVERY_DB_BUDGET')
        require(type(ledger_bytes) is int and 1024<=ledger_bytes<=4*1024**3,'RECOVERY_LEDGER_BUDGET')
        require(type(seconds) is int and 1<=seconds<=86400,'RECOVERY_TIME_BUDGET')
        self.b=budgets('preflight');self.b.update(work_db_bytes=work_db_bytes,ledger_bytes=ledger_bytes,seconds=seconds)
        self.config=dict(work_db_bytes=work_db_bytes,ledger_bytes=ledger_bytes,seconds=seconds)
        self.fault=fault or (lambda phase, owner: None)
        self.lock=None;self.db=None
        self.resume=resume;self.resume_state=None;self.binding=None
        self.quarantined=False;self.windows=0;self.generation=0
        if resume:
            require(self.out.is_dir(),'RECOVERY_OUTPUT_MISSING')
            require((self.out/'verification.sqlite3').is_file() and not (self.out/'verification.sqlite3').is_symlink(),
                    'RECOVERY_DATABASE_MISSING_OR_SYMLINK')
            self._lock()
            self.db=sqlite3.connect(self.out/'verification.sqlite3')
            self.started=time.monotonic()
        else:
            # Reuse the exact existing schema and methods, with no index ingest.
            super().__init__(self.root,self.root,self.out,self.b)
            for f in (self.fgap,self.fpart,self.fassoc):f.close()
            self._lock()
            self.db.executescript('''
              CREATE TABLE ledger(name TEXT,n INTEGER,raw BLOB,prev TEXT,h TEXT,PRIMARY KEY(name,n));
              CREATE TABLE ledger_tail(name TEXT PRIMARY KEY,n INTEGER,h TEXT);
              CREATE TABLE handoff_state(name TEXT,key BLOB,value BLOB,PRIMARY KEY(name,key));
              CREATE TABLE journal_ranges(id TEXT PRIMARY KEY,first INTEGER,last INTEGER,n INTEGER,h TEXT);
              CREATE TABLE native_identity(id TEXT PRIMARY KEY,s TEXT,q INTEGER);
              CREATE TABLE recovery_checkpoint(id INTEGER PRIMARY KEY,body BLOB,h TEXT);
            ''')
            self.db.commit()
        self.db.execute('PRAGMA journal_mode=DELETE')
        self.db.execute('PRAGMA synchronous=EXTRA')
        self.db.execute('PRAGMA recursive_triggers=ON')
        self.db.execute('PRAGMA temp_store=FILE')
        self.db.execute('PRAGMA mmap_size=0')
        self.db.execute('PRAGMA cache_size=-4096')
        self.db.execute('PRAGMA max_page_count='+str(work_db_bytes//4096))
        self.db.set_progress_handler(lambda:int(time.monotonic()-self.started>seconds),10000)
        self.integrity=Integrity(self.db)
        self.fgap=Ledger(self,'issues');self.fpart=Ledger(self,'partitions');self.fassoc=Ledger(self,'associations')
        self.window_ledger=Ledger(self,'windows');self.v81_ledger=Ledger(self,'v81_native_original_associations')
        self.v81=DurableV81(self)
        if resume:
            try:self._restore()
            except BaseException:
                self.close();raise

    def _lock(self):
        self.lock=(self.out/'recovery.lock').open('a+b')
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.lock.close();raise ValueError('RECOVERY_CONCURRENT_WRITER')

    def _restore(self):
        row=self.db.execute('SELECT body,h FROM recovery_checkpoint WHERE id=1').fetchone()
        require(row is not None and isinstance(row[0],bytes) and sha(row[0])==row[1],'CHECKPOINT_STATE_HASH')
        checkpoint=json.loads(row[0])
        require(checkpoint['schema']=='BTC15_RECOVERY_V1','CHECKPOINT_SCHEMA')
        require(checkpoint['config']==self.config,'CHECKPOINT_CONFIG_DRIFT')
        require(checkpoint['sql_schema_sha256']==self.schema_hash(),'CHECKPOINT_SQL_SCHEMA_DRIFT')
        self.integrity.verify(checkpoint['roots'])
        self.binding=checkpoint['binding']
        self.resume_state=unpack(checkpoint['inventory'])
        for key,value in unpack(checkpoint['verifier']).items():setattr(self,key,value)
        for key,value in unpack(checkpoint['v81']).items():setattr(self.v81,key,value)
        self.checkpoint_hash=row[1]

    def schema_hash(self):
        return sha(canonical(list(self.db.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"))))

    def bind(self, files, options):
        repo=Path(__file__).resolve().parents[2]
        value=dict(root=str(self.root),files=files,options=options,
                   code={p:file_sha(repo/p) for p in CODE_FILES},
                   scope=file_sha(self.root/'campaign-scope.json') if (self.root/'campaign-scope.json').exists() else None)
        if self.resume:require(value==self.binding,'CHECKPOINT_SOURCE_CODE_OR_OPTIONS_DRIFT')
        else:self.binding=value
        return self.resume_state

    def commit_snapshot(self, inventory):
        self.budget();self.generation+=1
        require(len(self.current_vectors)<=128 and len(self.contracts)<=512 and
                len(self.pending)<=512 and len(self.outcome_status)<=512,'RECOVERY_COMPACT_STATE_CAP')
        payload=dict(schema='BTC15_RECOVERY_V1',config=self.config,binding=self.binding,
                     sql_schema_sha256=self.schema_hash(),
                     generation=self.generation,previous=getattr(self,'checkpoint_hash',None),
                     roots=self.integrity.snapshot(),inventory=pack(inventory),
                     verifier=pack({k:getattr(self,k) for k in STATE_FIELDS}),
                     v81=pack({k:getattr(self.v81,k) for k in V81_FIELDS}))
        body=canonical(payload)
        require(len(body)<=8*1024**2,'CHECKPOINT_STATE_BYTE_CAP')
        digest=sha(body)
        self.db.execute('INSERT OR REPLACE INTO recovery_checkpoint VALUES (1,?,?)',(body,digest))
        self.fault('before_commit',self)
        self.db.commit()
        fd=os.open(self.out,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
        self.checkpoint_hash=digest
        self.fault('after_commit',self)

    def accept(self, role, record, partition):
        self.budget()
        r=dict(record,_part=partition);s,q,k=r['session'],r['sequence'],r['kind'];v=r['payload']
        self.counts[k]+=1;self.classes.add(r['evidence_class'])
        self.db.execute('INSERT INTO raw VALUES (?,?,?,?,?,?,?)',(s,q,k,partition,None,r['sha256'],role))
        if k=='START':
            require(v.get('continuous_with_prior_session') is False,'UNSUPPORTED_SESSION_CONTINUITY')
            self.fact('session',s,r,dict(binding=v['source_binding'],role=role))
            return
        if k=='STOP':
            self.db.execute('INSERT INTO sessions VALUES (?,?,?,?,?)',(s,role,q,r['sha256'],r['evidence_class']))
            return
        loss=k in ('EVIDENCE_GAP','INFORMATION_FAILURE') or (k=='SOURCE_GAP' and v.get('reason')!='SOURCE_START_OR_EPOCH_CHANGE')
        if loss:
            self.quarantined=True;self.issue(k,session=s,sequence=q,details=v)
        if self.quarantined:
            self.metrics['records_quarantined_after_loss']+=1
            return
        if k=='STREAM_START':
            require(not self.db.execute('SELECT 1 FROM deps WHERE s=? AND t="stream" AND id=?',
                    (s,v['epoch'])).fetchone(),'QUOTE_HANDOFF_DUPLICATE_STREAM')
        if k=='QUOTE_ACCEPT':
            identity=sha(canonical([v['epoch'],v['ticker'],v['raw_sha256'],v['received_at']]))
            require(not self.db.execute('SELECT 1 FROM deps WHERE s=? AND t="accepted_receive" AND id=?',
                    (s,identity)).fetchone(),'QUOTE_HANDOFF_ACCEPT_WITHOUT_EXACT_RECEIPT')
        if k=='HTTP_RESPONSE' and v.get('official_fields'):
            require(isinstance(v.get('endpoint'),str) and v['endpoint'].startswith('/trade-api/v2/markets'),
                    'SOURCE_HANDOFF_UNTRUSTED_METADATA_ENDPOINT')
        if k=='ORIGINAL_RESPONSE':
            require(isinstance(v.get('endpoint'),str) and v['endpoint'].startswith((
                    'https://external-api.kalshi.com/','https://api.elections.kalshi.com/',
                    'https://api.exchange.coinbase.com/')),'SOURCE_HANDOFF_UNTRUSTED_HTTP_ORIGIN')
        if k=='NATIVE_RECORD':
            prior=self.db.execute('SELECT first,last,n FROM journal_ranges WHERE id=?',(v['original_journal'],)).fetchone()
            if prior:
                require(v['sequence']==prior[1]+1,'NATIVE_WINDOW_GAP_OR_DUPLICATE_ORIGINAL_COMMIT')
                self.db.execute('UPDATE journal_ranges SET last=?,n=n+1,h=? WHERE id=?',(v['sequence'],v['sha256'],v['original_journal']))
            else:self.db.execute('INSERT INTO journal_ranges VALUES (?,?,?,?,?)',(v['original_journal'],v['sequence'],v['sequence'],1,v['sha256']))
        # All original schema, depth replay, vector, source and proof checks.
        try:super().record(r)
        except (ValueError,KeyError,TypeError) as exc:
            # Match the existing reconstruct() diagnostic path, with stricter
            # permanent quarantine. Invalid evidence is never repaired or
            # credited, but its immutable archive can still be scanned/resumed.
            # Capacity/SQLite/I/O failures remain fatal and roll back the window.
            if isinstance(exc,Exhausted):raise
            self.issue('RECORD_VERIFICATION',session=s,sequence=q,partition=partition,
                       kind=k,detail=str(exc)[:180])
            self.quarantined=True
            return
        require(len(self.current_vectors)<=128 and len(self.contracts)<=512,'RECOVERY_COMPACT_STATE_CAP')
        # All original V81 source-age and causal checks; disk-backed retention.
        self.v81.accept(role,r)
        if k=='NATIVE_RECORD':
            n=json.loads(v['raw']);z=dict(v,native=n);loc=(s,q,partition)
            if n.get('kind')=='NATIVE_DECISION':
                f=n['evidence']
                require(n['contract']==f['contract'] and f['captured_ts']<=n['published_ts']<=v['committed_at'],'NATIVE_CHRONOLOGY')
                if n.get('unavailable_reason'):self.metrics['legitimate_unavailable']+=1
                else:
                    prior=self.contracts.get(f['contract'])
                    require(prior is None or prior==dict(opened=f['official_open'],closed=f['official_close'],target=f['target']),
                            'MAIN_CONTRACT_IDENTITY_DRIFT')
                    identity=canonical([f['native_epoch'],f['native_sequence']]).decode()
                    try:self.db.execute('INSERT INTO native_identity VALUES (?,?,?)',(identity,s,q))
                    except sqlite3.IntegrityError:raise ValueError('DUPLICATE_NATIVE_DECISION_IDENTITY')
                    self.native_lifecycle(loc,z,frame_links(self,f,partition))
                    self.metrics['native_associations']+=1
            elif v['record_basis']=='POST_ADMIN_COMMIT_APPLICATION_CLOCK':self.admin(loc,z)
            elif n.get('kind')=='SCALP_OBSERVATION':self.scalp(loc,z)
            elif n.get('kind') in ('SETTLEMENT','BRTI_CLOSEOUT'):self.outcome(loc,z)
            elif n.get('kind')=='UNAVAILABLE' and n.get('unavailable_reason'):self.metrics['legitimate_unavailable']+=1
            else:raise ValueError('UNSUPPORTED_NATIVE_SCHEMA')
        require(len(self.contracts)<=512,'RECOVERY_CONTRACT_CAP')
        # A failed proof/information association never becomes a later success.
        if self.errors:self.quarantined=True
        self.fault('after_record',self)

    def checkpoint(self, role, session, sequence):
        self.windows+=1
        return dict(schema='BTC15_CAMPAIGN_WINDOW_V1',window=self.windows,role=role,session=session,
                    last_original_sequence=sequence,metrics=dict(self.metrics),issues=dict(self.errors),
                    quarantined=self.quarantined,full_early_qualified=False)

    def finish(self):
        for s,t,identity,q,p in self.db.execute("SELECT s,t,id,q,p FROM deps WHERE t IN ('stream','receive')"):
            target='stream_end' if t=='stream' else 'accepted_receive'
            if not self.db.execute('SELECT 1 FROM deps WHERE s=? AND t=? AND id=?',(s,target,identity)).fetchone():
                self.unresolved(s,t,identity,q,p)
        scope=None
        if (self.root/'campaign-scope.json').exists():
            try:scope=self.expectations()
            except Exception as exc:self.issue('CAMPAIGN_EXPECTATIONS',detail=str(exc))
        else:self.issue('DECLARED_CAMPAIGN_SCOPE_MISSING')
        for metric,reason in [('native_associations','MAIN_APPLICABLE_DECISION_LINKS_MISSING'),
                              ('scalp_associations','V81_APPLICABLE_DECISION_LINKS_MISSING'),
                              ('information_associations','INFORMATION_LINKS_MISSING')]:
            if not self.metrics[metric]:self.issue(reason)
        if self.metrics['origins_outside_recorded_journal_interval'] or self.metrics['terminals_outside_recorded_interval']:
            self.issue('MAIN_LIFECYCLE_OUTSIDE_RECORDED_INTERVAL')
        value=dict(schema='BTC15_WINDOWED_CAMPAIGN_V1',status='VERIFIED' if self.complete(True,scope) else 'INCOMPLETE',
                   metrics=dict(self.metrics),issue_counts=dict(self.errors),v81_causal_matches=self.v81.total_original_native_matches,
                   state_retention='EXACT_SQL_DISK_BACKING; NO_TIME_BASED_EVICTION',
                   sqlite_cache_kib=4096,work_db_bytes=self.db.execute('PRAGMA page_count').fetchone()[0]*4096,
                   limits=self.config,checkpoint_resume_implemented=True,production_authorization='NOT_AUTHORIZED',
                   long_test='NO_GO',signal_only=True,orders=False)
        return self.result(value,self.complete(True,scope))

    def export(self):
        for name in ('windows','issues','associations','v81_native_original_associations'):
            target=self.out/(name+'.jsonl');tmp=self.out/(name+'.jsonl.tmp')
            n=0;previous=''
            with tmp.open('wb') as f:
                for seq,raw,prev,digest in self.db.execute('SELECT n,raw,prev,h FROM ledger WHERE name=? ORDER BY n',(name,)):
                    require(seq==n+1 and prev==previous and sha(prev.encode()+raw)==digest,'RECOVERY_LEDGER_CHAIN')
                    f.write(raw);n=seq;previous=digest
                f.flush();os.fsync(f.fileno())
            tail=self.db.execute('SELECT n,h FROM ledger_tail WHERE name=?',(name,)).fetchone()
            require(tail==(n,previous) if n else tail is None,'RECOVERY_LEDGER_TAIL')
            os.replace(tmp,target)
        fd=os.open(self.out,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)

    def close(self):
        if self.db is not None:self.db.close();self.db=None
        if self.lock is not None:self.lock.close();self.lock=None


def run(root, output, *, resume=False, window_records=20000,
        work_db_bytes=4*1024**3, ledger_bytes=512*1024**2, seconds=3600, fault=None):
    from ops.recording_workflow.evidence import streaming_window_inventory
    verifier=WindowedCampaignVerifier(root,output,resume=resume,work_db_bytes=work_db_bytes,
                                     ledger_bytes=ledger_bytes,seconds=seconds,fault=fault)
    try:
        return streaming_window_inventory(root,output,max_window_records=window_records,campaign_handoff=verifier)
    finally:verifier.close()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root');parser.add_argument('output');parser.add_argument('--resume',action='store_true')
    parser.add_argument('--window-records',type=int,default=20000)
    parser.add_argument('--work-db-mib',type=int,default=4096)
    args=parser.parse_args()
    result=run(args.root,args.output,resume=args.resume,window_records=args.window_records,
               work_db_bytes=args.work_db_mib*1024**2)
    print(json.dumps(result,sort_keys=True))
