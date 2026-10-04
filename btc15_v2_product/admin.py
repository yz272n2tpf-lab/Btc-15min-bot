"""Separate bounded administrative evidence. NEVER a strategy input or coverage row."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import queue
import sqlite3
import threading
import time
import uuid
from . import REVISION

LOCAL=threading.local()
MAX_RECORDS=100000
MAX_STORED_BYTES=64*1024*1024


class Admin:
    def __init__(self, root, lane, clock=time.time, monotonic=time.perf_counter):
        self.root,self.lane,self.clock,self.monotonic=Path(root),lane,clock,monotonic
        self.epoch=str(uuid.uuid4());self.counter=0
        self.queue=queue.Queue(128);self.accepted=self.written=self.dropped=0;self.failed=None
        self.retained_bytes=0;self.first_sequence=None;self.last_sequence=None
        self.thread=threading.Thread(target=self.run,daemon=True,name='v2-administrative-evidence')
        self.thread.start()

    def offer(self, value):
        if self.failed:return False
        try:self.queue.put_nowait(value);self.accepted+=1;return True
        except queue.Full:self.dropped+=1;self.failed='ADMIN_QUEUE_FULL';return False

    def begin(self):
        self.counter+=1
        LOCAL.attempt=dict(schema='BTC15_NATIVE_ATTEMPT_R1',revision=REVISION,lane=self.lane,
            attempt_id=f'{self.epoch}:{self.counter}',started_ts=self.clock(),stages=[],
            outcome='EXCEPTION_OR_INCOMPLETE',signal_only=True,orders=False)
        LOCAL.started=self.monotonic()
        self.offer({k:v for k,v in dict(LOCAL.attempt,schema='BTC15_NATIVE_ATTEMPT_START_R1').items() if k not in ('stages','outcome')})

    @contextmanager
    def stage(self,name):
        a=getattr(LOCAL,'attempt',None)
        start=self.monotonic();at=self.clock()
        try:yield
        except Exception as exc:
            if a is not None:a['exception_type']=type(exc).__name__;a['failed_stage']=name
            raise
        finally:
            if a is not None:a['stages'].append(dict(stage=name,started_ts=at,elapsed_ms=(self.monotonic()-start)*1000))

    def call(self,name,fn,*args,**kwargs):
        with self.stage(name):result=fn(*args,**kwargs)
        a=getattr(LOCAL,'attempt',None)
        if a is not None:
            if name in ('get_active_market','snap') and isinstance(result,dict):
                a['contract']=result.get('ticker')
            if name=='get_active_market' and result is None:a['outcome']='NO_ACTIVE'
            if name=='consume_ws_quotes' and result is None:a['outcome']='QUOTE_WAIT'
            if name=='coinbase_http':a['btc_http_received_ts']=self.clock()
            if name=='snap' and isinstance(result,dict):
                p=result.get('input_provenance') or {};q=p.get('quote') or {};b=p.get('brti') or {}
                a['source_clocks']=dict(btc_source_utc=p.get('btc_source_utc'),btc_received_ts=a.get('btc_http_received_ts'),
                    brti_source_ms=b.get('source_ts_ms'),quote_source_ms=q.get('source_ts_ms'),quote_validated_ms=q.get('validated_at_ms'),native_cutoff=result.get('ts'))
        return result

    def offered(self,accepted,kind):
        a=getattr(LOCAL,'attempt',None)
        if a is not None:a.update(outcome='PUBLICATION_QUEUED' if accepted else 'PUBLICATION_REJECTED',offered_kind=kind)

    def exception(self,exc):
        a=getattr(LOCAL,'attempt',None)
        if a is not None:
            a['exception_type']=type(exc).__name__
            a['outcome']='NATIVE_EXCEPTION'
            # Only known code-owned reasons, never credentials/HTTP exception text.
            reason=str(exc)
            if reason in ('Active market missing target/clock after exact-market fallback',
                          'OFFICIAL_MARKET_UNAVAILABLE','TIMESTAMPED_QUOTES_UNAVAILABLE',
                          'BRTI_SOURCE_UNQUALIFIED','BTC_SOURCE_UNQUALIFIED','FIXED_OFFICIAL_IDENTITY_CHANGED',
                          'OFFICIAL_WINDOW_OR_TICKER','OFFICIAL_TARGET','STAGED_EXACT_IDENTITY_CONFLICT'):
                a['source_subreason']=reason

    def finish(self,ns=None):
        a=getattr(LOCAL,'attempt',None)
        if a is None:return
        a.update(finished_ts=self.clock(),elapsed_ms=(self.monotonic()-LOCAL.started)*1000)
        self.offer(a);LOCAL.attempt=None

    def pipeline(self, record, seq, committed):
        self.offer(dict(schema='BTC15_PUBLICATION_TIMING_R1',revision=REVISION,lane=self.lane,
            attempt_id=record.get('product',{}).get('attempt_id'),journal_sequence=seq,
            contract=record.get('contract'),processed_ts=record['published_ts'],committed_ts=committed,
            clocks=source_clocks(record),original_rejection=record.get('unavailable_reason'),
            signal_only=True,orders=False))

    def health(self):
        return dict(status='UNAVAILABLE' if self.failed else 'AVAILABLE',reason=self.failed,
            accepted=self.accepted,written=self.written,drops=self.dropped,queue_depth=self.queue.qsize(),
            max_records=MAX_RECORDS,days=7,authority='ADMINISTRATIVE_ONLY_NOT_STRICT_COVERAGE')

    def run(self):
        db=None
        try:
            self.root.mkdir(parents=True,exist_ok=True)
            db=sqlite3.connect(self.root/(self.lane+'.admin.sqlite3'),timeout=.2)
            db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
            db.execute('PRAGMA max_page_count=32768')
            db.execute('CREATE TABLE IF NOT EXISTS evidence(seq INTEGER PRIMARY KEY AUTOINCREMENT,at REAL,sha256 TEXT,body TEXT)')
            self.retained_bytes=db.execute('SELECT coalesce(sum(length(cast(body AS BLOB))),0) FROM evidence').fetchone()[0]
            while True:
                v=self.queue.get()
                try:
                    if v is None:return
                    raw=json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
                    if len(raw.encode())>32768:raise ValueError('ADMIN_RECORD_SIZE')
                    at=self.clock()
                    with db:
                        cur=db.execute('INSERT INTO evidence(at,sha256,body) VALUES (?,?,?)',(at,hashlib.sha256(raw.encode()).hexdigest(),raw))
                        self.retained_bytes+=len(raw.encode())
                        if cur.lastrowid%120==0:
                            expired=db.execute('SELECT coalesce(sum(length(cast(body AS BLOB))),0) FROM evidence WHERE seq<=? OR at<?',(cur.lastrowid-MAX_RECORDS,at-7*86400)).fetchone()[0]
                            db.execute('DELETE FROM evidence WHERE seq<=? OR at<?',(cur.lastrowid-MAX_RECORDS,at-7*86400))
                            self.retained_bytes-=expired
                        while self.retained_bytes>MAX_STORED_BYTES:
                            rows=db.execute('SELECT seq,length(cast(body AS BLOB)) FROM evidence ORDER BY seq LIMIT 120').fetchall()
                            db.execute('DELETE FROM evidence WHERE seq<=?',(rows[-1][0],));self.retained_bytes-=sum(r[1] for r in rows)
                        self.first_sequence,self.last_sequence=db.execute('SELECT min(seq),max(seq) FROM evidence').fetchone()
                    self.written+=1
                    if self.written%12==1:self.write_health()
                finally:self.queue.task_done()
        except Exception as exc:
            self.failed='ADMIN_WRITER_FAILURE:'+type(exc).__name__
            print('V2 ADMIN UNAVAILABLE | '+self.failed+' | NO ORDERS',flush=True)
            try:self.write_health()
            except Exception:pass
        finally:
            if db:db.close()

    def write_health(self):
        from btc15_ladder_journal_v1 import atomic_json
        value=self.health();value.update(retained_from_sequence=self.first_sequence,last_sequence=self.last_sequence,
            max_payload_bytes=MAX_STORED_BYTES,retained_payload_bytes=self.retained_bytes,checked_ts=self.clock(),
            effective_retention='EARLIEST_OF_7_DAYS_100000_RECORDS_64_MIB; ADMIN_ONLY')
        atomic_json(self.root/(self.lane+'.admin-health.json'),value)


def source_clocks(record):
    f=record.get('evidence') or {};p=record.get('provenance') or {}
    q=f.get('quote') or p.get('quote') or {};b=f.get('brti') or p.get('brti') or {}
    out=dict(btc_source=f.get('btc_source') or p.get('btc_source_utc'),btc_received=f.get('btc_received'),
        feature_cutoff=f.get('feature_cutoff'),captured_ts=f.get('captured_ts'),
        quote_source_ms=q.get('exchange_ts_ms',q.get('source_ts_ms')),
        quote_received_ms=q.get('consumed_ms',q.get('validated_at_ms')),
        brti_source=b.get('cf_ts',b.get('source_ts_ms')),brti_observed=(b.get('delivery') or {}).get('observed_ts'),
        # Null is an honest missing clock; no receipt/source substitution.
        administrative_only=True)
    cut=f.get('feature_cutoff');processed=record.get('published_ts')
    for name,source,limit in [('btc',f.get('btc_source'),10),('brti',b.get('cf_ts'),5),('quote',(q.get('exchange_ts_ms') or 0)/1000,6)]:
        if all(type(x) in (int,float) for x in (cut,processed,source)) and source:
            out[name+'_age_at_cut']=cut-source;out[name+'_age_at_processing']=processed-source
            out[name+'_expired_during_processing']=0<=cut-source<=limit<processed-source
    return out
