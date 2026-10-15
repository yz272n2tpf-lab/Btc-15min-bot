"""RESEARCH ONLY: append-only BRTI parity -> isolated SQLite outbox -> idempotent journal.

This experiment NEVER opens or writes the native cohort JSONL, connects to
Kalshi, invokes the production worker or alters production. It demonstrates the
protocol needed to eliminate the frozen full-file scan safely:

  - an explicit cutover leaves pre-existing historical parity rows untouched;
  - an incremental cursor and eligible outbox are committed in one transaction;
  - the idempotent test journal commits at most one exact BRTI_CLOSEOUT/contract;
  - a crash between journal commit and outbox acknowledgement can be replayed;
  - historical cohort-equivalent rows are exposed read-only, not appended to
    the native-owned file (no competing writer).

The journal adapter BELOW IS A RESEARCH TEST DOUBLE, not an approved V2 worker
replacement. Publication and production integration are explicitly NO-GO.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import time
import zlib
from contextlib import contextmanager, closing
import fcntl

from btc15_cohort_closeout_incremental_research_v1 import (
    COHORT_SCHEMA, _REQUIRED, EvidenceChanged, IncrementalCloseout,
)
from btc15_closeout_receipt_guard_research_v2 import DurableReceiptInspector

OUTBOX_SCHEMA = "BTC15_CLOSEOUT_OUTBOX_RESEARCH_R3"
JOURNAL_SCHEMA = "BTC15_LADDER_JOURNAL_V1"
MAX_LINE = 1024 * 1024


def _research_guard(*paths: Path) -> None:
    # No production filesystem, even if this experimental source is later copied.
    if os.environ.get("RAILWAY_PROJECT_ID") or os.environ.get("RAILWAY_ENVIRONMENT_ID"):
        raise EvidenceChanged("RAILWAY_RUNTIME_FORBIDDEN")
    for path in paths:
        resolved = Path(path).resolve()
        if resolved == Path("/data") or Path("/data") in resolved.parents:
            raise EvidenceChanged("PRODUCTION_DATA_PATH_FORBIDDEN")


def _pack(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_meta(db: sqlite3.Connection) -> dict[str, str]:
    return dict(db.execute("SELECT k,v FROM meta"))


@contextmanager
def _lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as lockfile:
        try:
            fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise EvidenceChanged("OUTBOX_OWNER_BUSY") from exc
        try:
            yield
        finally:
            fcntl.flock(lockfile.fileno(), fcntl.LOCK_UN)


class ResearchJournalV3:
    """Standalone OFFLINE transactional double of the V2 BRTI journal envelope.

    Unlike the deployed V2 worker, this test double has a unique BRTI_CLOSEOUT
    contract key enforced by SQLite. Never point at a production journal.
    """

    def __init__(self, path: Path, *, deployment: str, build: str, revision: str):
        self.path = Path(path)
        _research_guard(self.path)
        self.identity = dict(deployment=deployment, build=build,
                             product_revision=revision, lane="main", schema=JOURNAL_SCHEMA)
        if not all(self.identity.values()):
            raise ValueError("JOURNAL_IDENTITY_REQUIRED")

    def init_fixture(self) -> None:
        """Explicitly create a test-only V2-schema SQLite file."""
        if self.path.exists():
            raise EvidenceChanged("JOURNAL_ALREADY_EXISTS")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT NOT NULL)")
            db.execute("CREATE TABLE events(seq INTEGER PRIMARY KEY,at REAL NOT NULL,"
                       "contract TEXT,kind TEXT NOT NULL,sha256 TEXT NOT NULL,body BLOB NOT NULL)")
            db.execute("CREATE INDEX by_contract ON events(contract,seq)")
            db.execute("CREATE UNIQUE INDEX unique_closeout_research_v3 ON events(contract) "
                       "WHERE kind='BRTI_CLOSEOUT'")
            for k, v in self.identity.items():
                db.execute("INSERT INTO meta VALUES (?,?)", (k, v))
            db.execute("INSERT INTO meta VALUES (?,?)", ("sequence", "0"))
            db.execute("INSERT INTO meta VALUES (?,?)", ("runtime_epoch", "OFFLINE_RESEARCH_V3"))

    def commit_once(self, ticker: str, settlement: dict, *, hook=None) -> int:
        """Durably return the same sequence across retries, reject conflicts.

        Uses BEGIN IMMEDIATE before lookup, so two concurrent calls cannot both
        see absence. This double uses the on-disk V2 event shape and full fsync
        SQLite WAL durability; the real V2 consumer needs a reviewed equivalent.
        """
        if not isinstance(ticker, str) or not ticker or not isinstance(settlement, dict):
            raise EvidenceChanged("JOURNAL_INPUT_INVALID")
        with closing(sqlite3.connect(self.path, timeout=5, isolation_level=None)) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            try:
                if any(_read_meta(db).get(k) != v for k, v in self.identity.items()):
                    raise EvidenceChanged("JOURNAL_IDENTITY_MISMATCH")
                rows = db.execute("SELECT seq,body,sha256 FROM events "
                                  "WHERE contract=? AND kind='BRTI_CLOSEOUT'", (ticker,)).fetchall()
                if len(rows) > 1:
                    raise EvidenceChanged("JOURNAL_DUPLICATE_CLOSEOUT")
                if rows:
                    seq, compressed, digest = rows[0]
                    try:
                        raw = zlib.decompress(compressed)
                        if _sha(raw) != digest:
                            raise EvidenceChanged("JOURNAL_CORRUPT_DIGEST")
                        event = json.loads(raw)
                    except (ValueError, zlib.error) as exc:
                        raise EvidenceChanged("JOURNAL_RECEIPT_UNREADABLE") from exc
                    if (event.get("brti_closeout") != settlement or
                            event.get("evidence", {}).get("settlement") != settlement or
                            event.get("product", {}).get("deployment") != self.identity["deployment"]):
                        raise EvidenceChanged("JOURNAL_CONFLICTING_CLOSEOUT")
                    db.execute("COMMIT")
                    return int(seq)
                meta = _read_meta(db)
                seq = int(meta.get("sequence", "0")) + 1
                if hook:
                    hook("BEFORE_JOURNAL_INSERT")
                timestamp = time.time()
                evidence = dict(kind="BRTI_CLOSEOUT", contract=ticker, settlement=settlement)
                event = dict(schema=JOURNAL_SCHEMA, candidate="BTC15_INTEGRATED_FINISH_20261006",
                             build=self.identity["build"], kind="BRTI_CLOSEOUT", contract=ticker,
                             published_ts=timestamp, brti_closeout=settlement, evidence=evidence,
                             signal_only=True, orders=False,
                             product=dict(revision=self.identity["product_revision"], lane="main",
                                          deployment=self.identity["deployment"], build=self.identity["build"],
                                          attempt_id=None, runtime_epoch=meta["runtime_epoch"]))
                raw = _pack(event)
                db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)",
                           (seq, timestamp, ticker, "BRTI_CLOSEOUT", _sha(raw), zlib.compress(raw)))
                db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", ("sequence", str(seq)))
                db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", ("latest", raw.decode()))
                if hook:
                    hook("BEFORE_JOURNAL_COMMIT")
                db.execute("COMMIT")
                if hook:
                    hook("AFTER_JOURNAL_COMMIT")
                return seq
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    def inspector(self) -> DurableReceiptInspector:
        return DurableReceiptInspector(self.path, deployment=self.identity["deployment"],
                                        build=self.identity["build"],
                                        revision=self.identity["product_revision"])


class ResearchOutboxV3:
    """Single-owned, append-only *source* reader, separate durable settlement outbox.

    This is a testable design reference only. Initial source cutover must be
    explicitly authorized in an isolated working directory. It cannot migrate
    historic production CLOSEOUT_ONLY rows or silently assume old settlements.
    """

    def __init__(self, parity: Path, outbox_db: Path, journal: ResearchJournalV3):
        self.parity = Path(parity)
        self.outbox_db = Path(outbox_db)
        self.lock_path = self.outbox_db.with_suffix(".owner.lock")
        self.journal = journal
        _research_guard(self.parity, self.outbox_db, self.journal.path)
        self.processed_bytes = 0
        self.new_candidates = 0
        self.commits = 0

    @staticmethod
    def _read_csv(raw: bytes) -> list[str]:
        if len(raw) > MAX_LINE:
            raise EvidenceChanged("PARITY_RECORD_OVERSIZE")
        try:
            parsed = list(csv.reader(io.StringIO(raw.decode("utf-8")), strict=True))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise EvidenceChanged("PARITY_ROW_CORRUPT") from exc
        if len(parsed) != 1:
            raise EvidenceChanged("PARITY_MULTILINE_UNSUPPORTED")
        return parsed[0]

    def explicit_cutover(self) -> None:
        """Mark EXISTING prefix historical; never backfill or rewrite it.

        Historical qualified contract identities are indexed once so a late
        duplicate appended after the cutover cannot become a NEW settlement.
        This once-only migration scan is not part of the recurring hot path.
        """
        if self.outbox_db.exists():
            raise EvidenceChanged("OUTBOX_ALREADY_EXISTS")
        with _lock(self.lock_path):
            with self.parity.open("rb") as source:
                st = os.fstat(source.fileno())
                prefix = source.read(min(4096, st.st_size))
                source.seek(0)
                header_raw = source.readline()
                if not header_raw.endswith(b"\n"):
                    raise EvidenceChanged("PARITY_HEADER_INCOMPLETE")
                header = self._read_csv(header_raw)
                if not _REQUIRED.issubset(header) or len(header) != len(set(header)):
                    raise EvidenceChanged("PARITY_HEADER_INVALID")
                if st.st_size:
                    source.seek(st.st_size - 1)
                    if source.read(1) != b"\n":
                        raise EvidenceChanged("PARITY_INCOMPLETE_CUTOVER")
                self.outbox_db.parent.mkdir(parents=True, exist_ok=True)
                with closing(sqlite3.connect(self.outbox_db)) as db, db:
                    db.execute("PRAGMA journal_mode=WAL")
                    db.execute("PRAGMA synchronous=FULL")
                    db.execute("CREATE TABLE meta(k TEXT PRIMARY KEY,v TEXT NOT NULL)")
                    db.execute("CREATE TABLE items(contract TEXT PRIMARY KEY,payload TEXT NOT NULL,"
                               "sha256 TEXT NOT NULL,source_offset INTEGER NOT NULL,"
                               "journal_seq INTEGER,created REAL NOT NULL)")
                    db.execute("CREATE TABLE historical(contract TEXT PRIMARY KEY,sha256 TEXT NOT NULL)")
                    source.seek(len(header_raw))
                    while source.tell() < st.st_size:
                        raw = source.readline(MAX_LINE + 2)
                        if not raw.endswith(b"\n"):
                            raise EvidenceChanged("HISTORICAL_PARITY_INCOMPLETE")
                        fields = self._read_csv(raw)
                        if len(fields) != len(header):
                            raise EvidenceChanged("HISTORICAL_ROW_ARITY")
                        closeout = IncrementalCloseout._selection(dict(zip(header, fields)))
                        if closeout is not None:
                            db.execute("INSERT OR IGNORE INTO historical VALUES (?,?)",
                                       (closeout["contract"], _sha(_pack(closeout))))
                    if source.tell() != st.st_size or os.fstat(source.fileno()).st_size != st.st_size:
                        raise EvidenceChanged("PARITY_CHANGED_DURING_CUTOVER")
                    historical_count = db.execute("SELECT count(*) FROM historical").fetchone()[0]
                    meta = dict(schema=OUTBOX_SCHEMA, cursor=str(st.st_size),
                                inode_dev=str(st.st_dev), inode_num=str(st.st_ino),
                                prefix_size=str(len(prefix)),prefix_sha256=_sha(prefix),
                                header=json.dumps(header, separators=(",", ":")),
                                deployment=self.journal.identity["deployment"],
                                build=self.journal.identity["build"],
                                product_revision=self.journal.identity["product_revision"],
                                historical_cutover="EXPLICIT_NO_BACKFILL",
                                historical_eligible_contracts=str(historical_count))
                    for k, v in meta.items():
                        db.execute("INSERT INTO meta VALUES (?,?)", (k, v))

    def _verify_source(self, src, meta: dict):
        st = os.fstat(src.fileno())
        if (str(st.st_dev) != meta["inode_dev"] or str(st.st_ino) != meta["inode_num"]
                or st.st_size < int(meta["cursor"])):
            raise EvidenceChanged("PARITY_ROTATED_OR_TRUNCATED")
        src.seek(0)
        prefix = src.read(int(meta["prefix_size"]))
        if _sha(prefix) != meta["prefix_sha256"]:
            raise EvidenceChanged("PARITY_PREFIX_MUTATED")
        src.seek(int(meta["cursor"]))

    def _assert_identity(self, meta: dict) -> None:
        required = dict(schema=OUTBOX_SCHEMA, deployment=self.journal.identity["deployment"],
                        build=self.journal.identity["build"],
                        product_revision=self.journal.identity["product_revision"],
                        historical_cutover="EXPLICIT_NO_BACKFILL")
        if any(meta.get(k) != v for k, v in required.items()):
            raise EvidenceChanged("OUTBOX_IDENTITY_MISMATCH")

    def _capture_new(self, db: sqlite3.Connection, *, max_rows: int = 200, hook=None) -> None:
        meta = _read_meta(db)
        self._assert_identity(meta)
        with self.parity.open("rb") as src:
            self._verify_source(src, meta)
            header = json.loads(meta["header"])
            n = 0
            while n < max_rows:
                begin = src.tell()
                raw = src.readline(MAX_LINE + 2)
                if not raw or not raw.endswith(b"\n"):
                    if len(raw) > MAX_LINE:
                        raise EvidenceChanged("PARITY_RECORD_OVERSIZE")
                    return  # Ignore incomplete last record, retry on the next pass.
                fields = self._read_csv(raw)
                if len(fields) != len(header):
                    raise EvidenceChanged("PARITY_ROW_ARITY")
                row = dict(zip(header, fields))
                selected = IncrementalCloseout._selection(row)
                next_at = src.tell()
                db.execute("BEGIN IMMEDIATE")
                try:
                    old = db.execute("SELECT v FROM meta WHERE k='cursor'").fetchone()[0]
                    if int(old) != begin:
                        raise EvidenceChanged("CONCURRENT_SOURCE_CURSOR")
                    if selected is not None:
                        body = _pack(selected)
                        ticker = selected["contract"]
                        historical = db.execute("SELECT 1 FROM historical WHERE contract=?",
                                                (ticker,)).fetchone()
                        if historical is None:
                            existing = db.execute("SELECT sha256 FROM items WHERE contract=?", (ticker,)).fetchone()
                            if existing and existing[0] != _sha(body):
                                raise EvidenceChanged("PARITY_CONFLICTING_CLOSEOUT")
                            if not existing:
                                db.execute("INSERT INTO items VALUES (?,?,?,?,NULL,?)",
                                           (ticker, body.decode(), _sha(body), next_at, time.time()))
                                if hook:
                                    hook("BEFORE_OUTBOX_COMMIT", ticker)
                                self.new_candidates += 1
                    db.execute("UPDATE meta SET v=? WHERE k='cursor'", (str(next_at),))
                    db.execute("COMMIT")
                    if hook:
                        hook("AFTER_OUTBOX_COMMIT", row.get("contract"))
                except BaseException:
                    if db.in_transaction:
                        db.execute("ROLLBACK")
                    raise
                self.processed_bytes += len(raw)
                n += 1

    def _dispatch_pending(self, db: sqlite3.Connection, *, hook=None, max_dispatch=200) -> list[str]:
        self._assert_identity(_read_meta(db))
        items = db.execute("SELECT contract,payload,sha256 FROM items WHERE journal_seq IS NULL "
                           "ORDER BY source_offset LIMIT ?", (max_dispatch,)).fetchall()
        completed=[]
        inspector = self.journal.inspector()
        for ticker, payload, digest in items:
            if _sha(payload.encode()) != digest:
                raise EvidenceChanged("OUTBOX_PAYLOAD_CORRUPT")
            record = json.loads(payload)
            if record.get("contract") != ticker or record.get("schema") != COHORT_SCHEMA:
                raise EvidenceChanged("OUTBOX_ROW_IDENTITY")
            if hook:
                hook("BEFORE_JOURNAL", ticker)
            # Retry is safe only in the isolated test journal that atomically
            # enforces one CLOSEOUT per contract, not in the real V2 worker.
            seq = self.journal.commit_once(ticker, record["brti"])
            if hook:
                hook("AFTER_JOURNAL", ticker)
            if inspector.lookup(ticker, record["brti"]) != seq:
                raise EvidenceChanged("OUTBOX_JOURNAL_RECEIPT_MISMATCH")
            db.execute("BEGIN IMMEDIATE")
            try:
                result = db.execute("UPDATE items SET journal_seq=? WHERE contract=? "
                                    "AND journal_seq IS NULL AND sha256=?", (seq, ticker, digest))
                if result.rowcount != 1:
                    raise EvidenceChanged("OUTBOX_ACK_CONFLICT")
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
            completed.append(ticker)
            self.commits += 1
            if hook:
                hook("AFTER_ACK", ticker)
        return completed

    def poll_once(self, *, hook=None, max_rows=200, max_dispatch=200) -> list[str]:
        if not self.outbox_db.exists() or not self.journal.path.exists():
            raise EvidenceChanged("EXPLICIT_CUTOVER_AND_JOURNAL_REQUIRED")
        with _lock(self.lock_path):
            with closing(sqlite3.connect(self.outbox_db, timeout=5, isolation_level=None)) as db:
                db.execute("PRAGMA synchronous=FULL")
                # Check the append-only evidence identity BEFORE replaying any
                # pending settlement, including a crash-recovery dispatch.
                self._assert_identity(_read_meta(db))
                with self.parity.open("rb") as src:
                    self._verify_source(src, _read_meta(db))
                pending = self._dispatch_pending(db, hook=hook, max_dispatch=max_dispatch)
                self._capture_new(db, max_rows=max_rows, hook=hook)
                completed = self._dispatch_pending(db, hook=hook, max_dispatch=max_dispatch)
                return pending + completed

    def status(self):
        with closing(sqlite3.connect(self.outbox_db)) as db, db:
            total, acked = db.execute("SELECT count(*),sum(journal_seq IS NOT NULL) FROM items").fetchone()
            return dict(schema=OUTBOX_SCHEMA, total=total, acked=acked or 0,
                        pending=total - (acked or 0), production_ready=False,
                        signal_only=True, orders=False,
                        parity_bytes_since_cutover=self.processed_bytes)

    def read_only_cohort_projection(self) -> list[str]:
        """Exact legacy JSONL projection, gated by current durable receipts.

        This does not create or append an output file. A stale/tampered outbox
        acknowledgement is never accepted as current journal evidence.
        """
        inspector = self.journal.inspector()
        with closing(sqlite3.connect(self.outbox_db.resolve().as_uri()+"?mode=ro", uri=True)) as db:
            self._assert_identity(_read_meta(db))
            result = []
            for ticker, payload, digest, seq in db.execute(
                    "SELECT contract,payload,sha256,journal_seq FROM items WHERE journal_seq IS NOT NULL "
                    "ORDER BY source_offset"):
                if _sha(payload.encode()) != digest:
                    raise EvidenceChanged("OUTBOX_PAYLOAD_CORRUPT")
                record = json.loads(payload)
                if record.get("contract") != ticker or inspector.lookup(ticker, record["brti"]) != seq:
                    raise EvidenceChanged("PROJECTION_JOURNAL_MISMATCH")
                result.append(json.dumps(record, separators=(",", ":"), sort_keys=True,
                                         default=str) + "\n")
            return result
