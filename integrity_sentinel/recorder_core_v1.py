#!/usr/bin/env python3
"""BTC15 Integrity Sentinel Recorder Core V1.

Pure local persistence primitives for prospective evidence recording.

This module never contacts Railway, Kalshi, Coinbase, or any external service.
It writes only Sentinel-owned derived ledgers. Source evidence is embedded by
value and hashed; the source systems themselves are never modified.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
import fcntl
import threading
from pathlib import Path
from typing import Any, Iterable, Mapping
from integrity_sentinel.identity_v1 import exact_contract, validate_contract
from integrity_sentinel.storage_guard_v1 import storage_status

VERSION = "BTC15_INTEGRITY_SENTINEL_RECORDER_CORE_V1"
GENESIS_HASH = "0" * 64
# Hard admission bounds, not a reason to drop or split an observation's events.
MAX_BATCH_ROWS = 8192
MAX_BATCH_BYTES = 32 * 1024 * 1024
BATCH_WRITE_BYTES = 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _chain_hash(previous_hash: str, body: Mapping[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(previous_hash.encode("ascii"))
    h.update(b"\0")
    h.update(canonical_json(body).encode("utf-8"))
    return h.hexdigest()


@dataclass(frozen=True)
class LedgerStatus:
    path: str
    records: int
    last_sequence: int
    last_record_hash: str
    bytes: int
    chain_valid: bool
    durability_uncertain: bool = False


class AppendOnlyHashChainLedger:
    """Single-volume ledger with a durable pre-write continuity anchor.

    A durable intent marker covers the entire ledger/anchor acknowledgment
    sequence, including final directory fsync. Unresolved markers fail closed
    across restart even when the row and committed anchor look complete.
    Diagnostic opens can expose failed status but cannot append or recover.
    Recovery never truncates, adopts, or silently repairs evidence. Coordinated
    rollback/removal of local files still requires an external witness.
    """

    def __init__(self, path: str | Path, write_guard=None, *, allow_failed_open=False) -> None:
        self.path = Path(path)
        self.anchor_path = self.path.with_suffix(self.path.suffix + ".anchor.json")
        self.durability_path = self.path.with_suffix(self.path.suffix + ".durability-pending.json")
        self._lock = threading.RLock()
        self._write_guard = write_guard
        self._sequence = self._records = 0
        self._last_hash = GENESIS_HASH
        self._write_failed = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if os.path.lexists(self.durability_path):
                raise ValueError("unacknowledged ledger durability; independent recovery required")
            if not self.path.exists() and not self.anchor_path.exists():
                self._begin_durability(None, 0, GENESIS_HASH, 0)
                self._guard()
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
                self._write_anchor(0, GENESIS_HASH, 0)
                self._finish_durability()
            # Existing ledger without anchor, or anchor without ledger, is unsafe.
            self.verify()
        except (OSError, ValueError, TypeError, UnicodeError):
            self._write_failed = True
            if not allow_failed_open:
                raise
            # Diagnostic-only open: status is failed and append remains blocked.
            # Never repair, rewrite, truncate, or adopt the existing evidence.

    def _begin_durability(self, previous, sequence, digest, size):
        """Persist uncertainty BEFORE touching either evidence or its anchor.

        Failure here cannot be followed by ledger/anchor mutation. Existing,
        empty, partial, or malformed markers all block reopen; parsing a marker
        is never needed to decide whether the ledger is healthy.
        """
        self._guard()
        raw = (canonical_json({"state": "DURABILITY_UNACKNOWLEDGED",
            "started_at_utc": utc_now(), "previous": previous,
            "candidate": {"sequence": sequence, "record_hash": digest, "bytes": size},
            "recovery": "explicit independently audited action required"}) + "\n").encode()
        fd = os.open(self.durability_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            if os.write(fd, raw) != len(raw):
                raise OSError("short durability marker write")
            os.fsync(fd)
        finally:
            os.close(fd)
        directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def _finish_durability(self):
        # Only reached AFTER the committed anchor's directory fsync succeeded.
        # Do not add a fallible durability acknowledgment after this unlink:
        # cleanup need not survive a crash. A resurrected marker conservatively
        # blocks recovery even for an acknowledged append (a safe false alarm).
        # Failed/unacknowledged transactions never reach this cleanup path.
        self.durability_path.unlink()

    def _guard(self):
        if self._write_guard is not None:
            self._write_guard()
        elif storage_status(self.path.parent)["storage_ok"] is not True:
            raise OSError("storage guard FAIL")

    def _write_anchor(self, sequence, digest, size, *, committed=True):
        self._guard()
        raw = (canonical_json({"sequence": sequence, "record_hash": digest,
                               "bytes": size, "committed": committed}) + "\n").encode()
        temp = self.anchor_path.with_name(self.anchor_path.name + ".pending")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            if os.write(fd, raw) != len(raw):
                raise OSError("short checkpoint write")
            os.fsync(fd)
        finally:
            os.close(fd)
        self._guard()
        os.replace(temp, self.anchor_path)
        directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def _iter_records(self) -> Iterable[dict[str, Any]]:
        with self.path.open("rb") as stream:
            for line_no, line in enumerate(stream, start=1):
                if not line.endswith(b"\n") or not line.strip():
                    raise ValueError(f"ledger line {line_no}: partial or empty row")
                try:
                    obj = json.loads(line)
                except (ValueError, UnicodeError) as exc:
                    raise ValueError(f"ledger line {line_no}: invalid JSON") from exc
                if not isinstance(obj, dict):
                    raise ValueError(f"ledger line {line_no}: expected object")
                yield obj

    def _verify_locked(self) -> LedgerStatus:
        if os.path.lexists(self.durability_path):
            raise ValueError("unacknowledged ledger durability; independent recovery required")
        if self._write_failed:
            raise ValueError("ledger write failed; independent recovery required")
        if self.anchor_path.with_name(self.anchor_path.name + ".pending").exists():
            raise ValueError("unfinished checkpoint write")
        try:
            anchor = json.loads(self.anchor_path.read_bytes())
        except (OSError, ValueError) as exc:
            raise ValueError("missing or invalid continuity anchor") from exc
        previous, sequence = GENESIS_HASH, 0
        for count, row in enumerate(self._iter_records(), start=1):
            body, seq = row.get("body"), row.get("sequence")
            if not isinstance(body, dict) or type(seq) is not int or seq != sequence + 1:
                raise ValueError(f"ledger record {count}: invalid body/sequence")
            expected = _chain_hash(previous, {"sequence": seq, "body": body})
            if row.get("previous_hash") != previous or row.get("record_hash") != expected:
                raise ValueError(f"ledger record {count}: hash mismatch")
            previous, sequence = expected, seq
        size = self.path.stat().st_size
        if anchor != {"sequence": sequence, "record_hash": previous, "bytes": size, "committed": True}:
            raise ValueError("ledger continuity anchor mismatch")
        if sequence < self._sequence or (sequence == self._sequence and previous != self._last_hash):
            raise ValueError("ledger rollback")
        self._sequence = self._records = sequence
        self._last_hash = previous
        return LedgerStatus(str(self.path), sequence, sequence, previous, size, True)

    def verify(self) -> LedgerStatus:
        with self._lock, self.path.open("rb") as stream:
            fcntl.flock(stream, fcntl.LOCK_SH)
            return self._verify_locked()

    def append(self, body: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock, self.path.open("rb") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            self._guard()
            status = self._verify_locked()
            normalized = json.loads(canonical_json(dict(body)))
            sequence = self._sequence + 1
            record_hash = _chain_hash(self._last_hash, {"sequence": sequence, "body": normalized})
            row = {"sequence": sequence, "previous_hash": self._last_hash,
                   "record_hash": record_hash, "body": normalized}
            raw = (canonical_json(row) + "\n").encode("utf-8")
            # Reserve the exact next committed endpoint before writing. Crash or
            # short write cannot be mistaken for a valid old tail on restart.
            try:
                self._begin_durability({"sequence": status.last_sequence,
                    "record_hash": status.last_record_hash, "bytes": status.bytes},
                    sequence, record_hash, status.bytes + len(raw))
                self._write_anchor(sequence, record_hash, status.bytes + len(raw), committed=False)
                self._guard()
                fd = os.open(self.path, os.O_WRONLY | os.O_APPEND)
                try:
                    if os.write(fd, raw) != len(raw):
                        raise OSError("short ledger write")
                    os.fsync(fd)
                finally:
                    os.close(fd)
                # A complete-looking row after failed fsync is not committed.
                # Startup accepts only the durable post-fsync acknowledgement.
                self._write_anchor(sequence, record_hash, status.bytes + len(raw))
                self._finish_durability()
            except Exception:
                self._write_failed = True
                raise
            self._sequence = sequence
            self._last_hash = record_hash
            self._records += 1
            return row

    def _verify_batch_locked(self, bodies):
        return self._verify_locked()

    def append_batch(self, bodies: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Append bounded individual rows under one lock/durability transaction.

        The existing append path is deliberately unchanged. Full verification
        runs once, including subclass integrity gates, before any mutation.
        No retry, tail adoption, truncation or partial-batch acknowledgement.
        Rejected admission before intent cannot change the acknowledged tail.
        Runtime observations separately commit their derived-event obligation
        so even a pre-intent rejection remains detectable across restart.
        """
        with self._lock, self.path.open("rb") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            normalized, normalized_bytes = [], 0
            for body in bodies:
                if len(normalized) >= MAX_BATCH_ROWS:
                    raise ValueError("membership batch row bound exceeded")
                value = canonical_json(dict(body))
                normalized_bytes += len(value.encode("utf-8"))
                if normalized_bytes > MAX_BATCH_BYTES:
                    raise ValueError("membership batch byte bound exceeded")
                normalized.append(json.loads(value))
            status = self._verify_batch_locked(normalized)
            if not normalized:
                return []
            sequence, previous = status.last_sequence, status.last_record_hash
            rows, raw = [], bytearray()
            for body in normalized:
                sequence += 1
                digest = _chain_hash(previous, {"sequence": sequence, "body": body})
                row = {"sequence": sequence, "previous_hash": previous,
                       "record_hash": digest, "body": body}
                encoded = (canonical_json(row) + "\n").encode("utf-8")
                if len(raw) + len(encoded) > MAX_BATCH_BYTES:
                    raise ValueError("membership batch encoded byte bound exceeded")
                raw.extend(encoded)
                rows.append(row)
                previous = digest
            size = status.bytes + len(raw)
            try:
                self._begin_durability({"sequence": status.last_sequence,
                    "record_hash": status.last_record_hash, "bytes": status.bytes},
                    sequence, previous, size)
                self._write_anchor(sequence, previous, size, committed=False)
                self._guard()
                fd = os.open(self.path, os.O_WRONLY | os.O_APPEND)
                try:
                    for offset in range(0, len(raw), BATCH_WRITE_BYTES):
                        self._guard()
                        chunk = memoryview(raw)[offset:offset + BATCH_WRITE_BYTES]
                        if os.write(fd, chunk) != len(chunk):
                            raise OSError("short ledger batch write")
                    os.fsync(fd)
                finally:
                    os.close(fd)
                self._write_anchor(sequence, previous, size)
                self._finish_durability()
            except BaseException:
                self._write_failed = True
                raise
            self._sequence = self._records = sequence
            self._last_hash = previous
            return rows

    def status(self) -> LedgerStatus:
        try:
            return self.verify()
        except (OSError, ValueError, TypeError, UnicodeError):
            return LedgerStatus(str(self.path), self._records, self._sequence,
                                self._last_hash, -1, False,
                                os.path.lexists(self.durability_path))


def source_sample_body(*, source: str, observed_at_utc: str,
                       http_status: int | None, latency_ms: float | None,
                       payload: Any | None, error_type: str | None = None,
                       cycle_id: str | None = None, contract_id: str | None = None,
                       normalized: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload_hash = None if payload is None else sha256_json(payload)
    return {
        "record_type": "SOURCE_SAMPLE" if error_type is None else "SOURCE_ERROR",
        "sentinel_version": VERSION, "observed_at_utc": observed_at_utc,
        "cycle_id": cycle_id, "source": source, "contract_id": contract_id,
        "http_status": http_status, "latency_ms": latency_ms,
        "error_type": error_type, "payload_sha256": payload_hash,
        "normalized": dict(normalized or {}), "payload": payload,
        "orders": False, "source_mutation": False,
    }


def _record_contract(record: Mapping[str, Any]) -> str | None:
    return exact_contract(record)


def _iter_record_container(value: Any) -> Iterable[Mapping[str, Any]]:
    if value is None:
        return
    if isinstance(value, Mapping):
        if _record_contract(value):
            yield value
        else:
            for key, child in value.items():
                if not isinstance(child, Mapping):
                    raise ValueError("membership row must be an object")
                row = dict(child)
                # Dictionary keys are explicit exact IDs, never inferred IDs.
                validate_contract(key)
                contract = exact_contract(row, {"contract_id": key})
                if not exact_contract(row):
                    row["contract"] = contract
                yield row
    elif isinstance(value, list):
        for item in value:
            if not isinstance(item, Mapping) or not _record_contract(item):
                raise ValueError("membership row missing exact contract ID")
            yield item
    else:
        raise ValueError("membership container must be object or list")


MEMBERSHIP_CONTAINERS = {
    "early": ("call_records", "settled_records"),
    "final": ("lock_records", "settled_records"),
    "combined": ("records", "settled_records", "audit_records"),
    "nextgen": ("audit_records",),
}


def membership_events(source: str, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Copy already-recorded exact-ID strategy membership without rescoring."""
    family = source.lower()
    names: tuple[str, ...] = ()
    for marker, candidate in MEMBERSHIP_CONTAINERS.items():
        if marker in family:
            names = candidate
            break
    if not names:
        raise ValueError("unsupported membership source schema")
    live = payload.get("live") if isinstance(payload.get("live"), Mapping) else payload
    results: list[dict[str, Any]] = []
    containers = []
    recognized = False
    for container_name in names:
        container = live.get(container_name) if isinstance(live, Mapping) else None
        if container is None and container_name in payload:
            container = payload.get(container_name)
        if container is not None:
            recognized = True
        if "nextgen" in family and container_name == "audit_records" and isinstance(container, Mapping):
            # Deployed shape: audit_records -> family -> lane -> records.
            for group, lanes in container.items():
                if not isinstance(lanes, Mapping):
                    raise ValueError("invalid Nextgen family")
                for lane, detail in lanes.items():
                    if isinstance(detail, list):
                        containers.append((f"audit_records/{group}/{lane}", detail))
                    elif isinstance(detail, Mapping) and "records" in detail:
                        containers.append((f"audit_records/{group}/{lane}/records", detail["records"]))
                    else:
                        raise ValueError("invalid Nextgen lane")
        else:
            containers.append((container_name, container))
    if "combined" in family:
        scorecard = payload.get("scorecard")
        if isinstance(scorecard, Mapping) and "contract_rows" in scorecard:
            if scorecard["contract_rows"] is None:
                raise ValueError("missing Combined contract_rows")
            recognized = True
            containers.append(("scorecard.contract_rows", scorecard["contract_rows"]))
    if not recognized:
        raise ValueError("missing recognized membership container")
    for container_name, container in containers:
        for row in _iter_record_container(container):
            rec = dict(row)
            contract = _record_contract(rec)
            if not contract:
                continue
            event_payload = {"source": source, "container": container_name,
                             "contract_id": contract, "record": rec}
            event_id = sha256_json(event_payload)
            results.append({
                "record_type": "STRATEGY_MEMBERSHIP", "sentinel_version": VERSION,
                "event_id": event_id, "source": source, "container": container_name,
                "contract_id": contract, "record_sha256": sha256_json(rec),
                "record": rec, "orders": False, "rescore_performed": False,
            })
    return list({row["event_id"]: row for row in results}.values())


def existing_membership_ids(ledger: AppendOnlyHashChainLedger) -> set[str]:
    out: set[str] = set()
    for row in ledger._iter_records():
        body = row.get("body")
        if isinstance(body, Mapping) and body.get("record_type") == "STRATEGY_MEMBERSHIP":
            event_id = body.get("event_id")
            if isinstance(event_id, str):
                out.add(event_id)
    return out
