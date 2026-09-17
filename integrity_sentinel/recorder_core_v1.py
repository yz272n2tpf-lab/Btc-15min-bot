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
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION = "BTC15_INTEGRITY_SENTINEL_RECORDER_CORE_V1"
GENESIS_HASH = "0" * 64


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


class AppendOnlyHashChainLedger:
    """Append-only JSONL ledger with a cryptographic hash chain."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        self._sequence = 0
        self._last_hash = GENESIS_HASH
        self._records = 0
        self.verify()

    def _iter_records(self) -> Iterable[dict[str, Any]]:
        with self.path.open("r", encoding="utf-8") as stream:
            for line_no, line in enumerate(stream, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    obj = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"ledger line {line_no}: invalid JSON") from exc
                if not isinstance(obj, dict):
                    raise ValueError(f"ledger line {line_no}: expected object")
                yield obj

    def verify(self) -> LedgerStatus:
        previous = GENESIS_HASH
        sequence = 0
        count = 0
        for row in self._iter_records():
            count += 1
            body = row.get("body")
            if not isinstance(body, dict):
                raise ValueError(f"ledger record {count}: body missing")
            seq = row.get("sequence")
            if not isinstance(seq, int) or isinstance(seq, bool) or seq != sequence + 1:
                raise ValueError(f"ledger record {count}: non-contiguous sequence")
            if row.get("previous_hash") != previous:
                raise ValueError(f"ledger record {count}: previous hash mismatch")
            expected = _chain_hash(previous, {"sequence": seq, "body": body})
            if row.get("record_hash") != expected:
                raise ValueError(f"ledger record {count}: record hash mismatch")
            previous = expected
            sequence = seq
        self._sequence = sequence
        self._last_hash = previous
        self._records = count
        return self.status(chain_valid=True)

    def append(self, body: Mapping[str, Any]) -> dict[str, Any]:
        normalized = json.loads(canonical_json(dict(body)))
        sequence = self._sequence + 1
        hash_body = {"sequence": sequence, "body": normalized}
        record_hash = _chain_hash(self._last_hash, hash_body)
        row = {
            "sequence": sequence,
            "previous_hash": self._last_hash,
            "record_hash": record_hash,
            "body": normalized,
        }
        raw = (canonical_json(row) + "\n").encode("utf-8")
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND)
        try:
            os.write(fd, raw)
            os.fsync(fd)
        finally:
            os.close(fd)
        self._sequence = sequence
        self._last_hash = record_hash
        self._records += 1
        return row

    def status(self, *, chain_valid: bool = True) -> LedgerStatus:
        return LedgerStatus(
            path=str(self.path), records=self._records, last_sequence=self._sequence,
            last_record_hash=self._last_hash, bytes=self.path.stat().st_size,
            chain_valid=chain_valid,
        )


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
    for key in ("contract", "contract_id", "ticker"):
        value = str(record.get(key) or "").strip()
        if value:
            return value
    return None


def _iter_record_container(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        if _record_contract(value):
            yield value
        else:
            for key, child in value.items():
                if isinstance(child, Mapping):
                    row = dict(child)
                    if not _record_contract(row) and isinstance(key, str) and key.startswith("KXBTC15M-"):
                        row["contract"] = key
                    yield row
                elif isinstance(child, list):
                    for item in child:
                        if isinstance(item, Mapping):
                            yield item
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                yield item


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
        return []
    live = payload.get("live") if isinstance(payload.get("live"), Mapping) else payload
    results: list[dict[str, Any]] = []
    for container_name in names:
        container = live.get(container_name) if isinstance(live, Mapping) else None
        if container is None and container_name in payload:
            container = payload.get(container_name)
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
