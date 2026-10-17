"""JSON-only state and transactional integrity for the existing offline reader.

SQLite FULL transactions commit dependencies, ledgers and cursor together.
SHA-256 row accumulators cover every logical table; recovery scans them in
bounded memory. They detect accidental/logical alteration, not an attacker
able to rewrite both the checkpoint and its entire trusted input manifest.
"""
import base64
from collections import Counter
import hashlib
import json
import sqlite3
import fcntl
import os
from pathlib import Path

from .policy import canonical, sha


class ReaderLease:
    """One bounded reader per host UID and, on Railway, per mounted volume.

    Acquired BEFORE opening any database. Kernel locks release on process death.
    Lock files are never unlinked: inode replacement would defeat exclusion.
    This contains the unresolved concurrent-job failure; it is not its diagnosis.
    """
    def __init__(self):
        self.handles = []
        paths = [Path('/tmp') / ('btc15-bounded-reader-' + str(os.getuid()) + '.lock')]
        mount = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH')
        if os.environ.get('RAILWAY_SERVICE_ID'):
            if mount != '/research-evidence' or not Path(mount).is_dir():
                raise ValueError('RECOVERY_RESEARCH_VOLUME_LEASE_REQUIRED')
            paths.append(Path(mount) / '.btc15-bounded-reader.lock')
        try:
            for path in paths:
                fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
                handle = os.fdopen(fd, 'a+b'); self.handles.append(handle)
                try: fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError: raise ValueError('RECOVERY_CONCURRENT_WRITER:SERIAL_READER_REQUIRED')
        except BaseException:
            self.close(); raise

    def close(self):
        for handle in reversed(self.handles): handle.close()
        self.handles.clear()


def pack(value):
    if isinstance(value, Counter):
        return ['counter', [[pack(k), pack(v)] for k, v in value.items()]]
    if isinstance(value, dict):
        return ['dict', [[pack(k), pack(v)] for k, v in value.items()]]
    if isinstance(value, tuple):
        return ['tuple', [pack(v) for v in value]]
    if isinstance(value, set):
        return ['set', [pack(v) for v in sorted(value)]]
    if isinstance(value, list):
        return ['list', [pack(v) for v in value]]
    if isinstance(value, bytes):
        return ['bytes', base64.b64encode(value).decode()]
    if value is None or type(value) in (str, int, float, bool):
        return ['scalar', value]
    raise TypeError('UNSUPPORTED_CHECKPOINT_TYPE:' + type(value).__name__)


def unpack(value):
    kind, data = value
    if kind == 'scalar':
        if data is not None and type(data) not in (str, int, float, bool):
            raise ValueError('CHECKPOINT_SCALAR')
        return data
    if kind == 'bytes': return base64.b64decode(data, validate=True)
    if kind in ('dict', 'counter'):
        pairs = [(unpack(k), unpack(v)) for k, v in data]
        result = dict(pairs)
        if len(result) != len(pairs): raise ValueError('CHECKPOINT_DUPLICATE_KEY')
        return Counter(result) if kind == 'counter' else result
    if kind in ('tuple', 'set', 'list'):
        return {'tuple': tuple, 'set': set, 'list': list}[kind](unpack(v) for v in data)
    raise ValueError('CHECKPOINT_TAG')


class Integrity:
    """Bounded per-table XOR of SHA-256(rowid, typed columns).

    Each table's row count is included in the checkpoint as well. SQL triggers
    maintain roots inside a window; only a successful commit publishes them.
    An SQL error aborts the attempt, so Python roots never survive a rollback.
    """
    def __init__(self, db):
        self.db = db
        self.tables = {}
        self.roots = {}
        for name, in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            if name == 'recovery_checkpoint' or name.startswith('sqlite_'): continue
            if not name.replace('_', '').isalnum(): raise ValueError('STATE_TABLE_NAME')
            columns = [r[1] for r in db.execute('PRAGMA table_info(' + name + ')')]
            self.tables[name] = columns
            self.roots[name] = [0, 0]
        db.create_function('reader_integrity', -1, self.change)
        for name, cols in self.tables.items():
            for action, sign, prefix in [('INSERT', 1, 'NEW'), ('DELETE', -1, 'OLD')]:
                args = ','.join(prefix + '."' + col + '"' for col in ['rowid', *cols])
                db.execute(f"CREATE TEMP TRIGGER integrity_{name}_{action} AFTER {action} ON {name} "
                           f"BEGIN SELECT reader_integrity('{name}',{sign},{args}); END")
            old = ','.join('OLD."' + col + '"' for col in ['rowid', *cols])
            new = ','.join('NEW."' + col + '"' for col in ['rowid', *cols])
            db.execute(f"CREATE TEMP TRIGGER integrity_{name}_UPDATE AFTER UPDATE ON {name} "
                       f"BEGIN SELECT reader_integrity('{name}',-1,{old}); "
                       f"SELECT reader_integrity('{name}',1,{new}); END")

    @staticmethod
    def digest(name, values):
        return int.from_bytes(hashlib.sha256(canonical([name, pack(list(values))])).digest(), 'big')

    def change(self, name, sign, *values):
        root = self.roots[name]
        root[0] ^= self.digest(name, values)
        root[1] += sign
        return 1

    def snapshot(self):
        return {k: [f'{v[0]:064x}', v[1]] for k, v in self.roots.items()}

    def verify(self, expected):
        if set(expected) != set(self.tables): raise ValueError('CHECKPOINT_TABLE_SET')
        if self.db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('CHECKPOINT_SQLITE_INTEGRITY')
        for name, cols in self.tables.items():
            total = count = 0
            query = 'SELECT rowid,' + ','.join('"' + c + '"' for c in cols) + ' FROM ' + name
            for row in self.db.execute(query):
                total ^= self.digest(name, row)
                count += 1
            if [f'{total:064x}', count] != expected[name]:
                raise ValueError('CHECKPOINT_LOGICAL_INTEGRITY:' + name)
            self.roots[name] = [total, count]


class SqlMap:
    """Exact disk-backed association map; no per-record Python cache or expiry."""
    def __init__(self, db, name):
        self.db, self.name = db, name
        self.count = db.execute('SELECT count(*) FROM handoff_state WHERE name=?', (name,)).fetchone()[0]
    def __len__(self): return self.count
    def _key(self, key): return canonical(pack(key))
    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM handoff_state WHERE name=? AND key=?',
                              (self.name, self._key(key))).fetchone()
        return default if row is None else unpack(json.loads(row[0]))
    def __contains__(self, key):
        return self.db.execute('SELECT 1 FROM handoff_state WHERE name=? AND key=?',
                               (self.name, self._key(key))).fetchone() is not None
    def __getitem__(self, key):
        marker = object(); value = self.get(key, marker)
        if value is marker: raise KeyError(key)
        return value
    def __setitem__(self, key, value):
        # UPDATE, not REPLACE: deletion triggers must not be bypassed.
        k, v = self._key(key), canonical(pack(value))
        if key in self:
            self.db.execute('UPDATE handoff_state SET value=? WHERE name=? AND key=?', (v, self.name, k))
        else:
            self.db.execute('INSERT INTO handoff_state VALUES (?,?,?)', (self.name, k, v))
            self.count += 1
