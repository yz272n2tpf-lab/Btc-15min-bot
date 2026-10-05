"""Bounded V8.1 input inbox. No inference, source refresh or native-clock wait.

Admission is a short durable SQLite transaction, independent of product commits.
Only the original processor creates events, at its actual processing clock.
The product transaction checkpoints the inbox cursor for exactly-once recovery.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from btc15_ladder_journal_v1 import MAX_BYTES, MAX_RECORDS, SCHEMA, packed, atomic_json

CAPACITY = 256
REJECTION_RETENTION = 256
ACTIVE = {}


class Inbox:
    def __init__(self, root, identity, capacity=CAPACITY):
        self.capacity = capacity
        self.lock = threading.RLock()
        self.path = Path(root) / 'v81.inbox.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=0, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA max_page_count=8192')  # 32 MiB database ceiling.
        self.db.execute('PRAGMA journal_size_limit=1048576')
        self.db.execute('PRAGMA wal_autocheckpoint=128')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT);
          CREATE TABLE IF NOT EXISTS pending(seq INTEGER PRIMARY KEY,sha TEXT,body BLOB);
          CREATE TABLE IF NOT EXISTS rejected(seq INTEGER PRIMARY KEY,body TEXT);''')
        with self.db:
            prior = self.get('identity')
            if prior is not None and prior != identity:
                raise ValueError('INBOX_COHORT_IDENTITY_CHANGED')
            self.set('identity', identity)
        self.accepted = int(self.get('accepted') or 0)
        self.written = int(self.get('written') or 0)
        self.dropped = int(self.get('dropped') or 0)
        self.depth = self.db.execute('SELECT count(*) FROM pending').fetchone()[0]

    def get(self, key):
        row = self.db.execute('SELECT v FROM meta WHERE k=?', (key,)).fetchone()
        return row[0] if row else None

    def set(self, key, value):
        self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key, str(value)))

    def append(self, value, at):
        raw = packed(value)  # Same 64 KiB event bound, before acknowledgment.
        sha = hashlib.sha256(raw).hexdigest()
        with self.lock:
            if self.depth >= self.capacity:
                self.dropped += 1
                f = value[0]
                evidence = dict(reason='HANDOFF_CAPACITY', sha256=sha, observed_ts=at,
                    contract=f.get('contract'), kind=f.get('kind'), captured_ts=f.get('captured_ts'))
                with self.db:
                    self.set('dropped', self.dropped)
                    self.db.execute('INSERT INTO rejected VALUES (?,?)', (self.dropped, json.dumps(evidence)))
                    self.db.execute('DELETE FROM rejected WHERE seq<=?', (self.dropped-REJECTION_RETENTION,))
                return False
            seq = self.accepted + 1
            with self.db:
                self.db.execute('INSERT INTO pending VALUES (?,?,?)', (seq, sha, raw))
                self.set('accepted', seq)
            self.accepted = seq
            self.depth += 1
            return True

    def peek(self):
        with self.lock:
            row = self.db.execute('SELECT seq,sha,body FROM pending ORDER BY seq LIMIT 1').fetchone()
        if not row:
            return None
        seq, sha, raw = row
        if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError('INBOX_INTEGRITY')
        return seq, json.loads(raw)

    def acknowledge(self, through):
        with self.lock:
            with self.db:
                self.db.execute('DELETE FROM pending WHERE seq<=?', (through,))
                self.set('written', max(self.written, through))
            self.written = max(self.written, through)
            self.depth = self.db.execute('SELECT count(*) FROM pending').fetchone()[0]

    def close(self):
        with self.lock:
            self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            self.db.close()


class DurableWorker:
    def __init__(self, root, lane, processor, clock=time.time, capacity=CAPACITY):
        import os
        from .journal import ProcessorEnvelope
        if lane != 'v81':
            raise ValueError('V81_ONLY_HANDOFF')
        self.root, self.lane, self.clock = Path(root), lane, clock
        identity = '|'.join((os.getenv('RAILWAY_DEPLOYMENT_ID', 'OFFLINE'),
                             os.getenv('RAILWAY_GIT_COMMIT_SHA', 'OFFLINE'), lane))
        self.inbox = Inbox(root, identity, capacity)
        self.processor = ProcessorEnvelope(processor, lane)
        self.epoch = str(uuid.uuid4())
        self.failed = None
        self.pressure = False
        self.stop = threading.Event()
        self.wake = threading.Event()
        self.changed = threading.Condition()
        self.settlement_reader = None
        self.maintenance_lock = threading.Lock()
        self.last_stage = 'STARTING'
        self.thread = threading.Thread(target=self.run, daemon=True, name='v81-durable-publication')
        ACTIVE[str(self.root.resolve())] = self
        self.thread.start()

    @property
    def accepted(self): return self.inbox.accepted
    @property
    def written(self): return self.inbox.written
    @property
    def dropped(self): return self.inbox.dropped

    def health(self):
        return dict(accepted=self.accepted, written=self.written, dropped=self.dropped,
            queue_depth=self.inbox.depth, capacity=self.inbox.capacity, stage=self.last_stage,
            reason=self.failed, pressure=self.pressure, worker_alive=self.thread.is_alive())

    def start_settlements(self):
        from btc15_ladder_settlement_v2 import SettlementReader
        self.settlement_reader = SettlementReader(self.root, self.lane, self.offer, clock=self.clock)
        threading.Thread(target=self.settlement_reader.run, daemon=True, name='ladder-settlement-v81').start()

    def offer(self, value):
        from .admin import LOCAL
        from .journal import ADMINS
        if value is None:
            self.stop.set(); self.wake.set(); return True
        # Only the background settlement caller waits. At most one maintenance
        # record is admitted after durable progress; native callers never wait
        # for the processor, publication writer, or a free queue slot.
        if value.get('kind') == 'SETTLEMENT':
            with self.maintenance_lock:
                if not self.wait_idle(30) or self.stop.is_set():
                    return False
                return self._admit(value, None)
        attempt = getattr(LOCAL, 'attempt', None)
        ok = self._admit(value, attempt['attempt_id'] if attempt else None)
        admin = ADMINS.get(self.lane)
        if admin and attempt:
            admin.offered(ok, value.get('kind'))
        return ok

    def _admit(self, value, attempt):
        try:
            ok = self.inbox.append((value, attempt), self.clock())
            if not ok:
                self.pressure = True
                print('V81 HANDOFF REJECTED | '+json.dumps(self.health())+' | NO ORDERS', flush=True)
            self.wake.set()
            return ok
        except (OSError, sqlite3.Error, ValueError) as exc:
            self.failed = 'HANDOFF_NOT_DURABLE:'+type(exc).__name__
            print('V81 HANDOFF REJECTED | '+self.failed+' | NO ORDERS', flush=True)
            return False

    def wait_idle(self, timeout=10):
        with self.changed:
            return self.changed.wait_for(lambda: self.inbox.depth == 0 or not self.thread.is_alive(), timeout) and self.inbox.depth == 0

    def _publish(self, journal, view, seq):
        committed = int(journal.get('handoff_cursor', '0'))
        pending = self.inbox.peek()
        unacknowledged_commit = bool(pending and pending[0] <= committed)
        view['journal'] = dict(schema=SCHEMA, sequence=seq, written=committed,
            queue_depth=max(0,self.inbox.depth-int(unacknowledged_commit)), drops=self.dropped,
            retained_from_sequence=int(journal.get('retained_from_sequence', '1')),
            retention_days=30, max_records=MAX_RECORDS, denominator='contracts',
            quiet_means='OBSERVED_WITHOUT_SIGNAL; inspect missing flag', settlement='OFFICIAL_KALSHI_FINALIZED_ONLY')
        view['handoff'] = self.health()
        self.last_stage = 'PUBLICATION_WRITE'
        atomic_json(self.root/'v81.json', view)

    def run(self):
        from .journal import RevisionJournal
        journal = None
        try:
            journal = RevisionJournal(self.root/'v81.sqlite3', 'v81')
            self.processor.restore(journal.get('state', {}))
            cursor = int(journal.get('handoff_cursor', '0'))
            # Product commit + cursor + view are one transaction. A crash after
            # commit cannot execute the same frame twice or renew its old lease.
            saved = journal.get('handoff_view')
            if saved:
                self._publish(journal, saved, int(journal.get('sequence', '0')))
            self.inbox.acknowledge(cursor)
            with self.changed:
                self.changed.notify_all()
            while not self.stop.is_set() or self.inbox.depth:
                item = self.inbox.peek()
                if item is None:
                    self.last_stage = 'IDLE'
                    self.wake.clear(); self.wake.wait(.1); continue
                sequence, value = item
                if sequence != int(journal.get('handoff_cursor', '0'))+1:
                    raise ValueError('INBOX_SEQUENCE_GAP')
                self.last_stage = 'FROZEN_PROCESSOR'
                record, state, view = self.processor.process(value, self.clock())
                record['product']['handoff_sequence'] = sequence
                journal.handoff = (sequence, view)
                self.last_stage = 'PRODUCT_COMMIT'
                while True:
                    try:
                        seq = journal.commit(record, state)
                        break
                    except (sqlite3.OperationalError, OSError) as exc:
                        self.failed = 'PRODUCT_COMMIT_RETRY:'+type(exc).__name__
                        self.wake.wait(.05); self.wake.clear()
                view['journal_committed_ts'] = self.clock()
                if record.get('kind') != 'SETTLEMENT':
                    while True:
                        try:
                            self._publish(journal, view, seq)
                            break
                        except OSError as exc:
                            self.failed = 'PUBLICATION_WRITE_RETRY:'+type(exc).__name__
                            self.wake.wait(.05); self.wake.clear()
                while True:
                    try:
                        self.inbox.acknowledge(sequence)
                        break
                    except (sqlite3.OperationalError, OSError) as exc:
                        self.failed = 'HANDOFF_ACK_RETRY:'+type(exc).__name__
                        self.wake.wait(.05); self.wake.clear()
                self.failed = None
                if self.inbox.depth == 0:
                    self.pressure = False
                with self.changed:
                    self.changed.notify_all()
        except Exception as exc:
            self.failed = 'HANDOFF_INTEGRITY_FAILURE:'+type(exc).__name__
            print('V81 HANDOFF UNAVAILABLE | '+self.failed+' | NO ORDERS', flush=True)
        finally:
            if journal:
                journal.close()
            with self.changed:
                self.changed.notify_all()

    def close(self):
        if self.settlement_reader:
            self.settlement_reader.stop.set()
        self.stop.set(); self.wake.set(); self.thread.join(10)
        if self.thread.is_alive():
            raise RuntimeError('HANDOFF_DID_NOT_STOP')
        self.inbox.close()
        ACTIVE.pop(str(self.root.resolve()), None)
