#!/usr/bin/env python3
"""
BTC15 generalized SCALP live event cache V1.

READ-ONLY INTEGRATION PERFORMANCE LAYER | SIGNAL ONLY | NO ORDERS

The frozen generalized collector continues to append its existing CSV exactly as
before. This module reads that file without modifying it and keeps only the small
recent slice needed by the existing V2/V3/V4 scalp-state derivation.

Why this exists:
- the persistent event tape is large and growing,
- re-reading the entire CSV for every /state or /combined-state request can add
  seconds of display latency,
- dashboard responsiveness must be improved without changing any qualification,
  management, Kalshi, EARLY, or FINAL threshold.

Safety / parity design:
- one full read is allowed at startup,
- subsequent updates consume appended CSV bytes only,
- the latest snapshot remains contract authority exactly as in the frozen V2
  state builder,
- recent neighboring contracts are retained so candidates that appear just
  before a snapshot rollover are not lost,
- the newest event of any type is retained for the existing V4 freshness check,
- the event tape is never written, truncated, renamed, or locked by this code,
- file shrink/rotation fails safely by rebuilding from the current file,
- no order code exists.
"""
from __future__ import annotations

import csv
import io
import os
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

DEFAULT_PATH = Path(os.environ.get("SCALP_EVENT_CSV", "/data/scalp_move_shadow_v1_events.csv"))
POLL_SECONDS = 0.25
MAX_RECENT_CONTRACTS = 4


def _dt(row: Mapping[str, Any]) -> datetime:
    raw = str(row.get("timestamp_utc") or "").strip()
    if not raw:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _contract(row: Mapping[str, Any]) -> str:
    return str(row.get("contract") or "").strip()


def _cid(row: Mapping[str, Any]) -> str:
    return str(row.get("candidate_id") or "").strip()


class LiveEventCache:
    """Thread-safe bounded view of an append-only scalp event CSV."""

    def __init__(
        self,
        path: str | Path = DEFAULT_PATH,
        *,
        poll_seconds: float = POLL_SECONDS,
        max_recent_contracts: int = MAX_RECENT_CONTRACTS,
    ):
        self.path = Path(path)
        self.poll_seconds = max(0.05, float(poll_seconds))
        self.max_recent_contracts = max(2, int(max_recent_contracts))
        self._lock = threading.RLock()
        self._fieldnames: list[str] = []
        self._by_contract: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        self._candidate_contract: dict[str, str] = {}
        self._latest_snapshot: dict[str, str] | None = None
        self._latest_any: dict[str, str] | None = None
        self._latest_candidate_without_snapshot: dict[str, str] | None = None
        self._offset = 0
        self._partial = b""
        self._inode: tuple[int, int] | None = None
        self._initialized = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.full_load_rows = 0
        self.appended_rows = 0
        self.rebuilds = 0

    @property
    def initialized(self) -> bool:
        with self._lock:
            return self._initialized

    def _reset_locked(self):
        self._fieldnames = []
        self._by_contract = OrderedDict()
        self._candidate_contract = {}
        self._latest_snapshot = None
        self._latest_any = None
        self._latest_candidate_without_snapshot = None
        self._offset = 0
        self._partial = b""
        self._inode = None
        self._initialized = False

    def _prune_locked(self):
        while len(self._by_contract) > self.max_recent_contracts:
            old_contract, _ = self._by_contract.popitem(last=False)
            stale = [cid for cid, c in self._candidate_contract.items() if c == old_contract]
            for cid in stale:
                self._candidate_contract.pop(cid, None)

    def _route_contract_locked(self, row: Mapping[str, Any]) -> str:
        contract = _contract(row)
        cid = _cid(row)
        typ = str(row.get("record_type") or "").strip().upper()
        if typ == "CANDIDATE" and contract and cid:
            self._candidate_contract[cid] = contract
        if not contract and cid:
            contract = self._candidate_contract.get(cid, "")
        return contract

    def _ingest_locked(self, row: Mapping[str, Any]):
        r = {str(k): "" if v is None else str(v) for k, v in row.items()}
        typ = str(r.get("record_type") or "").strip().upper()
        stamp = _dt(r)

        if self._latest_any is None or stamp >= _dt(self._latest_any):
            self._latest_any = r
        if typ == "SNAPSHOT" and _contract(r):
            if self._latest_snapshot is None or stamp >= _dt(self._latest_snapshot):
                self._latest_snapshot = r
        if typ == "CANDIDATE" and _contract(r):
            if self._latest_candidate_without_snapshot is None or stamp >= _dt(self._latest_candidate_without_snapshot):
                self._latest_candidate_without_snapshot = r

        contract = self._route_contract_locked(r)
        if contract:
            bucket = self._by_contract.setdefault(contract, [])
            bucket.append(r)
            # OrderedDict order tracks recent file activity, which safely keeps
            # neighboring rollover contracts even if a late PATH/RESULT arrives.
            self._by_contract.move_to_end(contract)
            self._prune_locked()

    def initialize(self) -> int:
        """Read the current tape once, then become append-only."""
        with self._lock:
            self._reset_locked()
            if not self.path.exists():
                self._initialized = True
                return 0

            st = self.path.stat()
            self._inode = (int(st.st_dev), int(st.st_ino))
            count = 0
            with self.path.open("r", newline="", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                self._fieldnames = list(reader.fieldnames or [])
                for row in reader:
                    self._ingest_locked(row)
                    count += 1
            self._offset = self.path.stat().st_size
            self._partial = b""
            self._initialized = True
            self.full_load_rows = count
            self.rebuilds += 1
            return count

    def _parse_complete_bytes_locked(self, payload: bytes) -> int:
        if not payload or not self._fieldnames:
            return 0
        text = payload.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text), fieldnames=self._fieldnames)
        count = 0
        for row in reader:
            # A repeated header can occur after a replace/rotation race. Skip it.
            if str(row.get(self._fieldnames[0]) or "") == self._fieldnames[0]:
                continue
            self._ingest_locked(row)
            count += 1
        self.appended_rows += count
        return count

    def poll_once(self) -> int:
        """Consume only bytes appended since the prior poll."""
        with self._lock:
            if not self._initialized:
                return self.initialize()
            if not self.path.exists():
                # Keep the previous in-memory slice; freshness will naturally
                # expire in V4. Do not fabricate new events.
                return 0

            st = self.path.stat()
            inode = (int(st.st_dev), int(st.st_ino))
            if self._inode is not None and inode != self._inode:
                self.initialize()
                return self.full_load_rows
            if st.st_size < self._offset:
                self.initialize()
                return self.full_load_rows
            if st.st_size == self._offset:
                return 0

            with self.path.open("rb") as f:
                f.seek(self._offset)
                new = f.read()
            self._offset = st.st_size
            data = self._partial + new
            if not data:
                return 0

            if b"\n" not in data:
                self._partial = data
                return 0
            complete, tail = data.rsplit(b"\n", 1)
            self._partial = tail
            return self._parse_complete_bytes_locked(complete + b"\n")

    def state_rows(self) -> list[dict[str, str]]:
        """Return the minimal row set that preserves frozen V2/V3/V4 state."""
        with self._lock:
            snapshot = self._latest_snapshot
            if snapshot is not None:
                contract = _contract(snapshot)
            elif self._latest_candidate_without_snapshot is not None:
                contract = _contract(self._latest_candidate_without_snapshot)
            else:
                contract = ""

            rows = list(self._by_contract.get(contract, ())) if contract else []

            # V4 freshness is based on the newest source event of any type. Keep
            # one newest event even when it belongs to a neighboring contract.
            newest = self._latest_any
            if newest is not None and all(id(x) != id(newest) for x in rows):
                # Equality, not object identity, is what matters because rows are
                # copied from CSV dictionaries.
                if newest not in rows:
                    rows.append(dict(newest))

            if snapshot is not None and snapshot not in rows:
                rows.append(dict(snapshot))
            return [dict(r) for r in rows]

    def diagnostics(self) -> dict:
        with self._lock:
            snapshot = self._latest_snapshot
            current = _contract(snapshot) if snapshot else (
                _contract(self._latest_candidate_without_snapshot)
                if self._latest_candidate_without_snapshot else None
            )
            return {
                "initialized": self._initialized,
                "path": str(self.path),
                "current_contract": current,
                "cached_contracts": list(self._by_contract.keys()),
                "cached_rows": sum(len(v) for v in self._by_contract.values()),
                "state_rows": len(self.state_rows()),
                "full_load_rows": self.full_load_rows,
                "appended_rows": self.appended_rows,
                "rebuilds": self.rebuilds,
                "offset": self._offset,
                "partial_bytes": len(self._partial),
                "orders": False,
            }

    def _loop(self):
        while not self._stop.wait(self.poll_seconds):
            try:
                self.poll_once()
            except Exception as exc:
                print(
                    f"SCALP LIVE CACHE WARNING | {type(exc).__name__}: {exc} | "
                    "previous cache retained; freshness will fail closed | NO ORDERS",
                    flush=True,
                )

    def start(self) -> threading.Thread:
        with self._lock:
            if not self._initialized:
                self.initialize()
            if self._thread and self._thread.is_alive():
                return self._thread
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="scalp-live-event-cache-v1", daemon=True)
            self._thread.start()
            return self._thread

    def stop(self):
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=max(1.0, self.poll_seconds * 4))


__all__ = ["LiveEventCache", "DEFAULT_PATH", "POLL_SECONDS", "MAX_RECENT_CONTRACTS"]
