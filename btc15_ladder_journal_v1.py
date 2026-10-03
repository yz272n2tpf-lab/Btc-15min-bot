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

    def commit(self, record, state):
        raw = packed(record)
        at = float(record['published_ts'])
        with self.db:
            seq = int(self.get('sequence', '0')) + 1
            self.db.execute('INSERT INTO events VALUES (?,?,?,?,?,?)',
                (seq, at, record.get('contract'), record['kind'], hashlib.sha256(raw).hexdigest(), zlib.compress(raw)))
            for key, value in [('sequence', str(seq)), ('state', packed(state).decode()),
                               ('latest', raw.decode())]:
                self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key, value))
            if seq % 120 == 0:
                self.db.execute('DELETE FROM events WHERE seq <= ? OR at < ?',
                                (seq - MAX_RECORDS, at - 30 * 86400))
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
                    if record.get('kind') == 'SETTLEMENT':
                        continue
                    # This clock describes completed durable acceptance, separately
                    # from the source and evaluator clocks retained in the record.
                    view['journal_committed_ts'] = self.clock()
                    view['journal'] = dict(schema=SCHEMA, sequence=seq, written=self.written,
                        queue_depth=self.queue.qsize(), drops=self.dropped,
                        retained_from_sequence=int(journal.get('retained_from_sequence', '1')),
                        retention_days=30, max_records=MAX_RECORDS)
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
        return value
    except (OSError, ValueError, KeyError, TypeError):
        return dict(status='UNAVAILABLE', reason='JOURNAL_UNAVAILABLE', signal_only=True, orders=False)
