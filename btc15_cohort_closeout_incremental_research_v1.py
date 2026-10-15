"""Research-only incremental BRTI closeout copier. Not wired to production.

The preserved production path is btc15_information_native_offpath_candidate.py.
No trading orders, upstream subscriptions, authority/model changes or deletion.

Exact-once settlement is NOT established: the legacy flow appends/fsyncs its
cohort receipt and separately enqueues a BRTI_CLOSEOUT event. A crash between
these two operations cannot be reconciled safely without a durable downstream
receipt and an idempotent consumer. Do not deploy this prototype as-is.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Callable

COHORT_SCHEMA = "BTC15_COHORT_NATIVE_V1"
_REQUIRED = frozenset({
    "contract", "timestamp_utc", "target", "final60_count",
    "final60_complete", "final60_average", "final60_side",
})


class EvidenceChanged(RuntimeError):
    """Fail-closed evidence identity, truncation or corruption alarm."""


class AppendCursor:
    """Read only complete appended newline-delimited records, never old bytes.

    A new identity or truncate fails closed rather than quietly losing unread
    bytes or accepting a new file's offsets as the original evidence clock.
    Rotation/truncation recovery requires an explicit offline reconciliation.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.offset = 0
        self.identity = None
        self._fingerprint = None
        self._prefix_size = 0
        self.bytes_read = 0

    def _open(self):
        try:
            src = self.path.open("rb")
        except FileNotFoundError:
            if self.identity is not None:
                raise EvidenceChanged("EVIDENCE_DISAPPEARED:" + self.path.name)
            return None
        stat = os.fstat(src.fileno())
        ident = (stat.st_dev, stat.st_ino)
        if self.identity is None:
            self.identity = ident
            self._prefix_size = min(stat.st_size, 4096)
            self._fingerprint = hashlib.sha256(src.read(self._prefix_size)).digest()
        elif ident != self.identity or stat.st_size < self.offset:
            src.close()
            raise EvidenceChanged("EVIDENCE_REPLACED_OR_TRUNCATED:" + self.path.name)
        if self._prefix_size:
            src.seek(0)
            prefix = src.read(self._prefix_size)
            if hashlib.sha256(prefix).digest() != self._fingerprint:
                src.close()
                raise EvidenceChanged("EVIDENCE_PREFIX_CHANGED:" + self.path.name)
        src.seek(self.offset)
        return src

    def iter_complete(self):
        src = self._open()
        if src is None:
            return
        try:
            while True:
                start = src.tell()
                raw = src.readline()
                self.bytes_read += len(raw)
                if not raw or not raw.endswith(b"\n"):
                    # A partial trailing record is retried next poll.
                    break
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise EvidenceChanged("NON_UTF8_RECORD:" + self.path.name) from exc
                yield text
                # Advance only after the consumer processed this record.
                self.offset = src.tell()
        finally:
            src.close()


class IncrementalCloseout:
    """Streaming shadow of the legacy CLOSEOUT_ONLY selection and append.

    On the first poll, scan each evidence file ONCE; on later polls consume only
    appended bytes. The cohort tail remains tracked because native appends
    regular, non-closeout rows to the same file.

    Settlement callback is deliberately injected and synchronous. Passing a
    real production worker here is NOT an authorized integration.
    """

    def __init__(
        self,
        parity_path: Path,
        cohort_path: Path,
        settlement: Callable[[str, dict], None],
        audit_path: Path | None = None,
    ):
        self.parity = AppendCursor(Path(parity_path))
        self.cohort = AppendCursor(Path(cohort_path))
        self.audit = AppendCursor(Path(audit_path) if audit_path is not None
                                  else Path(cohort_path).with_suffix(".closeout-audit.jsonl"))
        self.settlement = settlement
        self._pending_audit: dict[str, str] = {}
        self._halted = False
        self.seen: set[str] = set()
        self.header: list[str] | None = None
        self.emitted: list[str] = []
        self.parity_rows = 0
        self.cohort_rows = 0

    def _cohort_tail(self):
        for raw in self.cohort.iter_complete():
            self.cohort_rows += 1
            try:
                record = json.loads(raw)
            except (ValueError, TypeError) as exc:
                raise EvidenceChanged("COHORT_JSON_CORRUPT") from exc
            if not isinstance(record, dict):
                raise EvidenceChanged("COHORT_RECORD_NOT_OBJECT")
            if (record.get("schema") == COHORT_SCHEMA
                    and record.get("final_status") == "CLOSEOUT_ONLY"):
                ticker = record.get("contract")
                if not isinstance(ticker, str) or not ticker:
                    raise EvidenceChanged("COHORT_CLOSEOUT_TICKER_INVALID")
                self.seen.add(ticker)
        # The native process concurrently appends ordinary cohort rows. Never
        # concatenate our JSON onto a native row not yet newline-terminated.
        if (self.cohort.identity is not None
                and self.cohort.path.stat().st_size > self.cohort.offset):
            raise EvidenceChanged("COHORT_PARTIAL_TRAILER")

    def _audit_bootstrap(self):
        pending = self._pending_audit
        for raw in self.audit.iter_complete():
            try:
                row = json.loads(raw)
            except (ValueError, TypeError) as exc:
                raise EvidenceChanged("AUDIT_CORRUPT") from exc
            if not isinstance(row, dict) or row.get("schema") != "BTC15_CLOSEOUT_DISPATCH_AUDIT_R1":
                raise EvidenceChanged("AUDIT_SCHEMA_INVALID")
            ticker, digest, phase = row.get("contract"), row.get("sha256"), row.get("phase")
            if not isinstance(ticker, str) or not ticker or not isinstance(digest, str):
                raise EvidenceChanged("AUDIT_IDENTITY_INVALID")
            if phase == "INTENT":
                if ticker in pending:
                    raise EvidenceChanged("AUDIT_DUPLICATE_INTENT")
                pending[ticker] = digest
            elif phase == "ENQUEUED":
                if pending.get(ticker) != digest or ticker not in self.seen:
                    raise EvidenceChanged("AUDIT_ACK_WITHOUT_COHORT")
                del pending[ticker]
            else:
                raise EvidenceChanged("AUDIT_PHASE_INVALID")
        if self.audit.identity is not None and self.audit.path.stat().st_size > self.audit.offset:
            raise EvidenceChanged("AUDIT_PARTIAL_TRAILER")
        if pending:
            # No durable downstream acknowledgement exists. Do not assume the
            # callback was lost OR delivered, and never retry it automatically.
            raise EvidenceChanged("AMBIGUOUS_SETTLEMENT_WINDOW")
    def _append_audit(self, ticker: str, digest: str, phase: str) -> None:
        row = dict(schema="BTC15_CLOSEOUT_DISPATCH_AUDIT_R1", contract=ticker,
                   sha256=digest, phase=phase, signal_only=True, orders=False)
        self.audit.path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit.path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")
            out.flush()
            os.fsync(out.fileno())

    @staticmethod
    def _csv_line(raw: str) -> list[str]:
        try:
            rows = list(csv.reader(io.StringIO(raw), strict=True))
        except csv.Error as exc:
            raise EvidenceChanged("PARITY_CSV_CORRUPT") from exc
        if len(rows) != 1:
            raise EvidenceChanged("PARITY_CSV_LINE_COUNT")
        return rows[0]

    @staticmethod
    def _selection(row: dict[str, str | None]) -> dict | None:
        ticker = row.get("contract")
        if not ticker:
            return None
        if str(row.get("final60_complete", "")).lower() not in ("true", "1"):
            return None
        try:
            count = int(float(row.get("final60_count") or 0))
        except (TypeError, ValueError, OverflowError) as exc:
            raise EvidenceChanged("PARITY_COUNT_INVALID") from exc
        if count != 60:
            return None
        avg, side, target = (row.get(k) for k in (
            "final60_average", "final60_side", "target"))
        if avg in (None, "") or side not in ("UP", "DOWN") or target in (None, ""):
            return None
        try:
            avg, target = float(avg), float(target)
        except (TypeError, ValueError, OverflowError) as exc:
            raise EvidenceChanged("PARITY_NUMERIC_INVALID") from exc
        return dict(
            schema=COHORT_SCHEMA,
            timestamp_utc=row.get("timestamp_utc"),
            contract=ticker,
            target=target,
            seconds_left=0.0,
            up_bid=None, up_ask=None, down_bid=None, down_ask=None,
            final_status="CLOSEOUT_ONLY", final_side=None,
            final_confidence=None, final_call_source="BRTI_CLOSEOUT",
            early=None, unified_row_count=0, true_scalp_pending=0,
            profit_pending=0,
            brti=dict(contract=ticker, target=target, final60_count=60,
                      final60_average=avg, final60_side=side,
                      final60_complete=True),
            signal_only=True, orders=False,
        )

    def poll_once(self) -> list[str]:
        if self._halted:
            raise EvidenceChanged("RECONCILIATION_REQUIRED")
        self._cohort_tail()
        self._audit_bootstrap()
        added = []
        for line in self.parity.iter_complete():
            fields = self._csv_line(line)
            if self.header is None:
                if not _REQUIRED.issubset(fields) or len(fields) != len(set(fields)):
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
            out = (json.dumps(closeout, separators=(",", ":"),
                              sort_keys=True, default=str) + "\n")
            digest = hashlib.sha256(out.encode("utf-8")).hexdigest()
            try:
                # Explicit durable ambiguity marker: a crash during the cohort
                # append or async settlement offer MUST stop automated replay.
                self._append_audit(ticker, digest, "INTENT")
                self.cohort.path.parent.mkdir(parents=True, exist_ok=True)
                with self.cohort.path.open("a", encoding="utf-8") as dest:
                    dest.write(out)
                    dest.flush()
                    os.fsync(dest.fileno())
                self.seen.add(ticker)
                self.settlement(ticker, closeout["brti"])
                self._append_audit(ticker, digest, "ENQUEUED")
            except BaseException:
                self._halted = True
                raise
            self.emitted.append(ticker)
            added.append(ticker)
        return added

    def stats(self) -> dict:
        return dict(
            parity_bytes_read=self.parity.bytes_read,
            cohort_bytes_read=self.cohort.bytes_read,
            audit_bytes_read=self.audit.bytes_read,
            parity_offset=self.parity.offset,
            cohort_offset=self.cohort.offset,
            parity_rows=self.parity_rows,
            cohort_rows=self.cohort_rows,
            closeouts=len(self.emitted),
            seen_closeouts=len(self.seen),
            incomplete_evidence=self._halted,
            production_ready=False,
            no_orders=True,
        )
