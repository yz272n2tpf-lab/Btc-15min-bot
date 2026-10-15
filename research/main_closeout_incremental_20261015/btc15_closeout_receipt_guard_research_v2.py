"""Research-only, read-only durable BRTI closeout journal receipt validation.

This cannot enable production, cause an order, or submit to a journal. It reads
an existing SQLite journal using a read-only connection and checks the exact
V2 event envelope, deployment identity, and the committed settlement payload.
No inferred acknowledgements: queue acceptance and cohort fsync are NOT proof.
"""
from __future__ import annotations

import json
import hashlib
from contextlib import closing
import sqlite3
from pathlib import Path
import zlib

from btc15_cohort_closeout_incremental_research_v1 import EvidenceChanged

SCHEMA = "BTC15_LADDER_JOURNAL_V1"


class DurableReceiptInspector:
    def __init__(self, db_path: Path, *, deployment: str, build: str,
                 revision: str, lane: str = "main"):
        if not all((deployment, build, revision, lane)):
            raise ValueError("PINNED_JOURNAL_IDENTITY_REQUIRED")
        self.db_path = Path(db_path)
        self.expected = dict(deployment=deployment, build=build,
                             product_revision=revision, lane=lane)

    def lookup(self, ticker: str, settlement: dict) -> int | None:
        """Return durable commit sequence, None if absent, fail on uncertainty.

        Exactly one matching event is required. A conflicting or duplicate
        BRTI_CLOSEOUT with the same contract is a quarantine condition.
        """
        if not ticker or not isinstance(settlement, dict):
            raise EvidenceChanged("JOURNAL_LOOKUP_INVALID_IDENTITY")
        if not self.db_path.is_file():
            raise EvidenceChanged("JOURNAL_MISSING")
        try:
            with closing(sqlite3.connect(self.db_path.resolve().as_uri() + "?mode=ro",
                                         uri=True, timeout=0.5)) as db:
                db.execute("PRAGMA query_only=ON")
                meta = dict(db.execute("SELECT k,v FROM meta"))
                for name, value in self.expected.items():
                    if meta.get(name) != value:
                        raise EvidenceChanged("JOURNAL_IDENTITY_MISMATCH:" + name)
                rows = db.execute(
                    "SELECT seq,body,sha256 FROM events WHERE contract=? AND kind='BRTI_CLOSEOUT' ORDER BY seq",
                    (ticker,),
                ).fetchall()
        except (sqlite3.Error, OSError) as exc:
            raise EvidenceChanged("JOURNAL_READ_UNAVAILABLE") from exc

        if not rows:
            return None
        if len(rows) != 1:
            raise EvidenceChanged("JOURNAL_DUPLICATE_CLOSEOUT")
        seq, blob, stored_digest = rows[0]
        try:
            raw = zlib.decompress(blob)
            if hashlib.sha256(raw).hexdigest() != stored_digest:
                raise EvidenceChanged("JOURNAL_EVENT_DIGEST_MISMATCH")
            row = json.loads(raw)
        except (ValueError, TypeError, zlib.error) as exc:
            raise EvidenceChanged("JOURNAL_RECEIPT_UNREADABLE") from exc
        if not isinstance(row, dict) or row.get("schema") != SCHEMA or row.get("kind") != "BRTI_CLOSEOUT":
            raise EvidenceChanged("JOURNAL_RECEIPT_SCHEMA")
        if row.get("contract") != ticker or row.get("brti_closeout") != settlement:
            raise EvidenceChanged("JOURNAL_RECEIPT_PAYLOAD_MISMATCH")
        evidence = row.get("evidence") or {}
        if (evidence.get("kind") != "BRTI_CLOSEOUT" or
                evidence.get("contract") != ticker or
                evidence.get("settlement") != settlement):
            raise EvidenceChanged("JOURNAL_EVIDENCE_MISMATCH")
        product = row.get("product") or {}
        if (product.get("revision") != self.expected["product_revision"] or
                product.get("lane") != self.expected["lane"] or
                product.get("deployment") != self.expected["deployment"] or
                product.get("build") != self.expected["build"] or
                row.get("signal_only") is not True or row.get("orders") is not False):
            raise EvidenceChanged("JOURNAL_ORIGIN_UNSAFE")
        if not isinstance(seq, int) or seq < 1:
            raise EvidenceChanged("JOURNAL_SEQUENCE_INVALID")
        return seq
