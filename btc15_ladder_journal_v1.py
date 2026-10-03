"""Small product-event journal. No quotes are fetched and no orders exist here.

One bounded queue; one disk worker; transactional state plus compressed records.
Retention is explicit: 30 days or 300,000 records, whichever is reached first.
No existing evidence file is changed. A failed/missing journal disables guidance.
"""
import hashlib
import json
import os
from pathlib import Path
import queue
import sqlite3
import threading
import time
import uuid
import zlib

SCHEMA = 'BTC15_LADDER_JOURNAL_V1'
MAX_RECORDS = 300000
MAX_BYTES = 65536


def packed(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if len(raw) > MAX_BYTES:
        raise ValueError('OVERSIZE_LADDER_EVENT')
    return raw


def digest(value):
    return hashlib.sha256(packed(value)).hexdigest()


class Journal:
    def __init__(self, path, lane):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=.2)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA max_page_count=131072')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,at REAL NOT NULL,
              contract TEXT,kind TEXT NOT NULL,sha256 TEXT NOT NULL,body BLOB NOT NULL);
            CREATE INDEX IF NOT EXISTS by_contract ON events(contract,seq);
            CREATE TABLE IF NOT EXISTS contracts(opened INTEGER PRIMARY KEY,ticker TEXT,
              first_at REAL,last_at REAL,observations INTEGER DEFAULT 0,unavailable INTEGER DEFAULT 0,
              signals INTEGER DEFAULT 0,final_calls INTEGER DEFAULT 0,missing INTEGER DEFAULT 1,
              settlement_status TEXT DEFAULT 'PENDING',settlement_checked REAL DEFAULT 0,settlement TEXT);

        ''')
        self.db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('schema', SCHEMA))
        self.db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('lane', lane))
        self.db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('journal_id', str(uuid.uuid4())))
        self.db.commit()
        if self.get('schema') != SCHEMA or self.get('lane') != lane:
            raise ValueError('JOURNAL_IDENTITY_MISMATCH')

    def get(self, key, default=None):
        row = self.db.execute('SELECT v FROM meta WHERE k=?', (key,)).fetchone()
        return json.loads(row[0]) if row and row[0].startswith(('{', '[', '"')) else row[0] if row else default

    def coverage(self, record):
        kind=record['kind'];at=record['published_ts']
        if kind=='SETTLEMENT':
            value=record['settlement']
            self.db.execute("UPDATE contracts SET settlement_status=?,settlement_checked=?,settlement=? WHERE ticker=? AND opened=?",
                (value['status'],value['received_ts'],packed(value).decode(),record['contract'],value['open_ts']))
            return
        if kind=='BRTI_CLOSEOUT':return
        opened=int(at//900)*900
        previous=self.db.execute('SELECT max(opened) FROM contracts').fetchone()[0]
        # A restart makes skipped slots explicitly MISSING, never silent PASS.
        if previous is not None and opened>previous:
            self.db.execute('UPDATE contracts SET missing=1 WHERE opened=? AND (last_at IS NULL OR last_at < ?)',
                (previous,previous+900-(15 if self.get('lane')=='main' else 6)))
        start=max((previous+900 if previous is not None else opened),opened-30*86400)
        for slot in range(start,opened+1,900):
            self.db.execute('INSERT OR IGNORE INTO contracts(opened) VALUES (?)',(slot,))
        prior=self.db.execute('SELECT first_at,last_at,missing FROM contracts WHERE opened=?',(opened,)).fetchone()
        if prior is None:return
        unavailable='unavailable_reason' in record
        interval=15 if self.get('lane')=='main' else 6
        gap=unavailable or (at-prior[1]>interval if prior[1] is not None else at-opened>interval)
        missing=(prior[2] if prior[1] is not None else False) or gap
        ticker=record.get('contract') if not unavailable else None
        self.db.execute("""UPDATE contracts SET ticker=coalesce(ticker,?),first_at=coalesce(first_at,?),last_at=?,
            observations=observations+1,unavailable=unavailable+?,signals=signals+?,final_calls=final_calls+?,missing=? WHERE opened=?""",
            (ticker,at,at,int(unavailable),int(record.get('event') in ('BUY','SCALP_SIGNAL')),
             int((record.get('final') or {}).get('ready') is True),int(missing),opened))

    def commit(self, record, state):
        raw = packed(record)
        at = float(record['published_ts'])
        with self.db:
            self.coverage(record)
            seq = int(self.get('sequence', '0')) + 1
            self.db.execute('INSERT INTO events VALUES (?,?,?,?,?,?)',
                (seq, at, record.get('contract'), record['kind'], hashlib.sha256(raw).hexdigest(), zlib.compress(raw)))
            for key, value in [('sequence', str(seq)), ('state', packed(state).decode()),
                               ('latest', raw.decode())]:
                self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key, value))
            if seq % 120 == 0:
                self.db.execute('DELETE FROM events WHERE seq <= ? OR at < ?',
                                (seq - MAX_RECORDS, at - 30 * 86400))
                self.db.execute('DELETE FROM contracts WHERE opened < ?', (at-30*86400,))
                first = self.db.execute('SELECT min(seq) FROM events').fetchone()[0]
                self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('retained_from_sequence', str(first)))
        return seq

    def close(self):
        self.db.close()


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    with tmp.open('wb') as out:
        out.write(packed(value)); out.flush(); os.fsync(out.fileno())
    tmp.replace(path)


class Worker:
    def __init__(self, root, lane, processor, clock=time.time):
        self.root, self.lane, self.processor, self.clock = Path(root), lane, processor, clock
        self.queue = queue.Queue(maxsize=16)
        self.failed = None
        self.accepted = self.written = self.dropped = 0
        self.epoch = str(uuid.uuid4())
        self.thread = threading.Thread(target=self.run, daemon=True, name='ladder-journal-' + lane)
        self.thread.start()
        self.settlement_reader = None

    def start_settlements(self):
        from btc15_ladder_settlement_v2 import SettlementReader
        self.settlement_reader=SettlementReader(self.root,self.lane,self.offer,clock=self.clock)
        threading.Thread(target=self.settlement_reader.run,daemon=True,name='ladder-settlement-'+self.lane).start()

    def offer(self, value):
        if self.failed:
            return False
        try:
            self.queue.put_nowait(value)
            self.accepted += 1
            return True
        except queue.Full:
            self.dropped += 1
            self.failed = 'JOURNAL_QUEUE_FULL'
            return False

    def run(self):
        journal = None
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            journal = Journal(self.root / (self.lane + '.sqlite3'), self.lane)
            self.processor.restore(journal.get('state', {}))
            while True:
                value = self.queue.get()
                try:
                    if value is None:
                        return
                    if self.failed:
                        continue
                    record, state, view = self.processor.process(value, self.clock())
                    seq = journal.commit(record, state)
                    self.written += 1
                    if record.get('kind') in ('SETTLEMENT','BRTI_CLOSEOUT'):
                        continue
                    # This clock describes completed durable acceptance, separately
                    # from the source and evaluator clocks retained in the record.
                    view['journal_committed_ts'] = self.clock()
                    view['journal'] = dict(schema=SCHEMA, sequence=seq, written=self.written,
                        queue_depth=self.queue.qsize(), drops=self.dropped,
                        retained_from_sequence=int(journal.get('retained_from_sequence', '1')),
                        retention_days=30, max_records=MAX_RECORDS,denominator='contracts',
                        quiet_means='OBSERVED_WITHOUT_SIGNAL; inspect missing flag',settlement='OFFICIAL_KALSHI_FINALIZED_ONLY')
                    atomic_json(self.root / (self.lane + '.json'), view)
                    if record.get('event') or self.written % 12 == 1:
                        print('LADDER PRODUCT | ' + json.dumps(dict(lane=self.lane,
                            status=view.get('status'), contract=view.get('contract'), sequence=seq,
                            event=record.get('event'), signal_only=True, orders=False)), flush=True)
                finally:
                    self.queue.task_done()
        except Exception as exc:
            self.failed = 'JOURNAL_FAILURE:' + type(exc).__name__
            print('LADDER PRODUCT UNAVAILABLE | ' + self.failed + ' | NO ORDERS', flush=True)
        finally:
            if journal:
                journal.close()
            if self.failed:
                try:
                    atomic_json(self.root / (self.lane + '.json'), dict(status='UNAVAILABLE',
                        reason=self.failed, signal_only=True, orders=False))
                except OSError:
                    pass


def view(root, lane, now=None):
    now = time.time() if now is None else now
    try:
        raw = (Path(root) / (lane + '.json')).read_bytes()
        if len(raw) > MAX_BYTES:
            raise ValueError('OVERSIZE_VIEW')
        value = json.loads(raw)
        if value.get('signal_only') is not True or value.get('orders') is not False:
            raise ValueError('SIGNAL_ONLY_BOUNDARY')
        if value.get('status') != 'UNAVAILABLE' and not value['published_ts'] <= now < value['expires_at']:
            return dict(status='UNAVAILABLE', reason='SOURCE_EXPIRED', contract=value.get('contract'),
                        origin=value.get('origin'), historical_only=True, signal_only=True, orders=False)
        value['served_ts']=now
        return value
    except (OSError, ValueError, KeyError, TypeError):
        return dict(status='UNAVAILABLE', reason='JOURNAL_UNAVAILABLE', signal_only=True, orders=False)


def coverage_view(root,lane,limit=96):
    """Bounded read-only contract denominator and final-result receipts."""
    try:
        path=Path(root)/(lane+'.sqlite3')
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.2) as db:
            db.row_factory=sqlite3.Row
            rows=[dict(r) for r in db.execute('SELECT * FROM contracts ORDER BY opened DESC LIMIT ?', (min(96,limit),))]
        for row in rows:
            row['quiet']=row['signals']==0 and row['observations']>row['unavailable']
            row['coverage_state']='MISSING_OR_PARTIAL' if row['missing'] else 'OBSERVED_TO_LAST_RECEIPT'
            if row['settlement']:row['settlement']=json.loads(row['settlement'])
        return dict(contracts=rows,signal_only=True,orders=False,retention_days=30)
    except (OSError,sqlite3.Error,ValueError):
        return dict(status='UNAVAILABLE',signal_only=True,orders=False)
