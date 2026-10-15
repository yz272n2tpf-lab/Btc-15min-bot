"""Research-only receipt-gated extension of the V1 incremental closeout copier.

A durable SQLite event is the ONLY successful dispatch receipt. A failure after
INTENT is never automatically replayed if no matching committed receipt exists.
The code is deliberately NOT imported by production and does NOT provide
exactly-once writes across independent processes without shared locking.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Callable

from btc15_cohort_closeout_incremental_research_v1 import (
    AppendCursor, COHORT_SCHEMA, EvidenceChanged, IncrementalCloseout,
)
from btc15_closeout_receipt_guard_research_v2 import DurableReceiptInspector

AUDIT_SCHEMA = "BTC15_CLOSEOUT_DURABLE_AUDIT_R2"


class ReceiptGatedIncrementalCloseout(IncrementalCloseout):
    def __init__(self, parity_path: Path, cohort_path: Path,
                 settlement: Callable[[str, dict], bool],
                 receipt: DurableReceiptInspector, *, audit_path: Path | None = None):
        if not isinstance(receipt, DurableReceiptInspector):
            raise TypeError("DURABLE_RECEIPT_REQUIRED")
        cohort_path = Path(cohort_path)
        super().__init__(parity_path, cohort_path, settlement,
                         audit_path or cohort_path.with_suffix(".durable-audit.jsonl"))
        self.receipt = receipt
        self.cohort_hashes: dict[str, str] = {}
        self.cohort_closeout_counts: dict[str, int] = {}
        self.committed: dict[str, int] = {}
        self.pending: dict[str, tuple[str, dict]] = {}

    def _cohort_tail(self):
        for raw in self.cohort.iter_complete():
            self.cohort_rows += 1
            try:
                record = json.loads(raw)
            except (ValueError, TypeError) as exc:
                raise EvidenceChanged("COHORT_JSON_CORRUPT") from exc
            if not isinstance(record, dict):
                raise EvidenceChanged("COHORT_RECORD_NOT_OBJECT")
            if record.get("schema") == COHORT_SCHEMA and record.get("final_status") == "CLOSEOUT_ONLY":
                ticker = record.get("contract")
                if not isinstance(ticker, str) or not ticker:
                    raise EvidenceChanged("COHORT_CLOSEOUT_TICKER_INVALID")
                digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                prior = self.cohort_hashes.setdefault(ticker, digest)
                if prior != digest:
                    raise EvidenceChanged("COHORT_CONFLICTING_CLOSEOUT")
                self.cohort_closeout_counts[ticker] = self.cohort_closeout_counts.get(ticker, 0) + 1
                if self.cohort_closeout_counts[ticker] > 1:
                    raise EvidenceChanged("COHORT_DUPLICATE_CLOSEOUT")
                self.seen.add(ticker)
        if self.cohort.identity is not None and self.cohort.path.stat().st_size > self.cohort.offset:
            raise EvidenceChanged("COHORT_PARTIAL_TRAILER")

    def _write_audit(self, ticker: str, digest: str, phase: str, *,
                     settlement: dict | None = None, seq: int | None = None) -> None:
        value = dict(schema=AUDIT_SCHEMA, contract=ticker, sha256=digest, phase=phase,
                     signal_only=True, orders=False)
        if phase == "INTENT":
            value["settlement"] = settlement
        elif phase == "COMMITTED":
            value["sequence"] = seq
        else:
            raise ValueError("UNSUPPORTED_AUDIT_PHASE")
        self.audit.path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit.path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n")
            out.flush()
            os.fsync(out.fileno())

    def _audit_bootstrap(self):
        for raw in self.audit.iter_complete():
            try:
                row = json.loads(raw)
            except (ValueError, TypeError) as exc:
                raise EvidenceChanged("AUDIT_CORRUPT") from exc
            if (not isinstance(row, dict) or row.get("schema") != AUDIT_SCHEMA or
                    row.get("signal_only") is not True or row.get("orders") is not False):
                raise EvidenceChanged("AUDIT_SCHEMA_INVALID")
            ticker, digest, phase = row.get("contract"), row.get("sha256"), row.get("phase")
            if not isinstance(ticker, str) or not ticker or not isinstance(digest, str) or len(digest) != 64:
                raise EvidenceChanged("AUDIT_IDENTITY_INVALID")
            if phase == "INTENT":
                if ticker in self.pending or ticker in self.committed or not isinstance(row.get("settlement"), dict):
                    raise EvidenceChanged("AUDIT_DUPLICATE_INTENT")
                self.pending[ticker] = (digest, row["settlement"])
            elif phase == "COMMITTED":
                proposed = self.pending.get(ticker)
                seq = row.get("sequence")
                if proposed is None or proposed[0] != digest or not isinstance(seq, int) or seq < 1:
                    raise EvidenceChanged("AUDIT_COMMIT_WITHOUT_INTENT")
                if self.cohort_hashes.get(ticker) != digest:
                    raise EvidenceChanged("AUDIT_COMMIT_COHORT_MISSING")
                actual = self.receipt.lookup(ticker, proposed[1])
                if actual != seq:
                    raise EvidenceChanged("AUDIT_COMMIT_JOURNAL_MISMATCH")
                self.committed[ticker] = seq
                del self.pending[ticker]
            else:
                raise EvidenceChanged("AUDIT_PHASE_INVALID")
        if self.audit.identity is not None and self.audit.path.stat().st_size > self.audit.offset:
            raise EvidenceChanged("AUDIT_PARTIAL_TRAILER")
        # The journal is checked when a COMMITTED entry is first seen, which
        # includes ALL entries on restart, never on every idle polling cycle.
        if self.pending:
            for ticker, (digest, settlement) in list(self.pending.items()):
                if self.cohort_hashes.get(ticker) != digest:
                    raise EvidenceChanged("AMBIGUOUS_COHORT_WRITE")
                seq = self.receipt.lookup(ticker, settlement)
                if seq is None:
                    raise EvidenceChanged("AMBIGUOUS_SETTLEMENT_WINDOW")
                # Do NOT mutate pending here: the next poll will read this
                # newly appended COMMITTED row, revalidate and consume it.
                self._write_audit(ticker, digest, "COMMITTED", seq=seq)

    def _append_cohort_checked(self, out: str) -> None:
        """Catch a changed inode or unfinished native line immediately before append.

        Still NOT cross-process atomic with the frozen native writer; both
        writers must share a single-owner/append-lock protocol before deploy.
        """
        self.cohort.path.parent.mkdir(parents=True, exist_ok=True)
        with self.cohort.path.open("a+b") as dest:
            info = os.fstat(dest.fileno())
            if self.cohort.identity is not None and (info.st_dev, info.st_ino) != self.cohort.identity:
                raise EvidenceChanged("COHORT_REPLACED_BEFORE_APPEND")
            at = dest.seek(0, os.SEEK_END)
            if at < self.cohort.offset:
                raise EvidenceChanged("COHORT_TRUNCATED_BEFORE_APPEND")
            if at:
                dest.seek(at - 1)
                if dest.read(1) != b"\n":
                    raise EvidenceChanged("COHORT_PARTIAL_BEFORE_APPEND")
            dest.write(out.encode("utf-8"))
            dest.flush()
            os.fsync(dest.fileno())

    def poll_once(self) -> list[str]:
        if self._halted:
            raise EvidenceChanged("RECONCILIATION_REQUIRED")
        self._cohort_tail()
        self._audit_bootstrap()
        added = []
        for line in self.parity.iter_complete():
            fields = self._csv_line(line)
            if self.header is None:
                if not self._valid_header(fields):
                    raise EvidenceChanged("PARITY_HEADER_INVALID")
                self.header = fields
                continue
            if len(fields) != len(self.header):
                raise EvidenceChanged("PARITY_ROW_ARITY_INVALID")
            self.parity_rows += 1
            row = dict(zip(self.header, fields))
            ticker = row.get("contract")
            if not ticker or ticker in self.seen:
                continue
            closeout = self._selection(row)
            if closeout is None:
                continue
            out = json.dumps(closeout, separators=(",", ":"), sort_keys=True, default=str) + "\n"
            digest = hashlib.sha256(out.encode("utf-8")).hexdigest()
            try:
                # A durable INTENT always precedes the cohort append. A crash
                # before/after dispatch must not silently requeue anything.
                self._write_audit(ticker, digest, "INTENT", settlement=closeout["brti"])
                self._append_cohort_checked(out)
                self.seen.add(ticker)
                ack = self.settlement(ticker, closeout["brti"])
                if ack is not True:
                    raise EvidenceChanged("JOURNAL_DISPATCH_NOT_ACKNOWLEDGED")
                seq = self.receipt.lookup(ticker, closeout["brti"])
                if seq is None:
                    raise EvidenceChanged("JOURNAL_DURABLE_RECEIPT_ABSENT")
                self._write_audit(ticker, digest, "COMMITTED", seq=seq)
            except BaseException:
                self._halted = True
                raise
            self.emitted.append(ticker)
            added.append(ticker)
        return added

    @staticmethod
    def _valid_header(fields: list[str]) -> bool:
        from btc15_cohort_closeout_incremental_research_v1 import _REQUIRED
        return _REQUIRED.issubset(fields) and len(fields) == len(set(fields))
