#!/usr/bin/env python3
"""BTC15 Integrity Sentinel / Prospective Evidence Recorder V1.

Standalone read-only recorder. It reads existing BTC15 service state endpoints
and appends timestamped, hash-chained evidence to Sentinel-owned storage.

CRITICAL SAFETY:
- HTTP GET only.
- Railway service endpoints only; direct Kalshi/Coinbase/BRTI upstream hosts are
  rejected by configuration validation.
- No order/trade endpoint, no POST/PUT/PATCH/DELETE, no strategy selection.
- Does not certify or promote strategies. It records evidence for the hardened
  reconciler to evaluate later.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Mapping
from urllib.parse import urlparse
import uuid

import requests

from integrity_sentinel.recorder_core_v1 import (
    AppendOnlyHashChainLedger, existing_membership_ids, membership_events,
    source_sample_body, utc_now,
)
from integrity_sentinel.source_adapters_v1 import adapt_source
from integrity_sentinel.storage_guard_v1 import storage_status
from integrity_sentinel.control_attestation_v1 import load_manifest, manifest_sha256

VERSION = "BTC15_INTEGRITY_SENTINEL_RECORDER_V1"
DEFAULT_POLL_SEC = 5.0
DEFAULT_MEMBERSHIP_POLL_SEC = 10.0
DEFAULT_TIMEOUT_SEC = 2.5

DEFAULT_SOURCES = {
    "production_main": {"url": "https://btc-15min-bot-production.up.railway.app/dashboard_state.json", "kind": "telemetry"},
    "brti_shared": {"url": "https://brti-shared-feed-v1-production.up.railway.app/state", "kind": "telemetry"},
    "scalp_combined": {"url": "https://scalp-move-shadow-v1-production.up.railway.app/combined-state", "kind": "telemetry"},
    "early_membership": {"url": "https://early-forward-scorecard-v1-production.up.railway.app/state", "kind": "membership"},
    "final_membership": {"url": "https://final-forward-scorecard-v1-production.up.railway.app/state", "kind": "membership"},
    "combined_membership": {"url": "https://combined-forward-scorecard-v1-production.up.railway.app/state", "kind": "membership"},
    "nextgen_membership": {"url": "https://scalp-nextgen-shadow-v2-production.up.railway.app/audit", "kind": "membership"},
}


@dataclass(frozen=True)
class SourceConfig:
    name: str
    url: str
    kind: str


def validate_source_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        raise ValueError("sentinel sources must use https")
    if not host.endswith(".up.railway.app"):
        raise ValueError(f"sentinel refuses non-Railway source host: {host}")
    if parsed.username or parsed.password:
        raise ValueError("credentials in source URL are forbidden")
    return url


def load_sources() -> list[SourceConfig]:
    raw = os.environ.get("SENTINEL_SOURCES_JSON", "").strip()
    obj = DEFAULT_SOURCES if not raw else json.loads(raw)
    if not isinstance(obj, Mapping):
        raise ValueError("SENTINEL_SOURCES_JSON must be an object")
    out: list[SourceConfig] = []
    for name, cfg in obj.items():
        if not isinstance(cfg, Mapping):
            raise ValueError(f"invalid source config: {name}")
        kind = str(cfg.get("kind") or "telemetry")
        if kind not in {"telemetry", "membership"}:
            raise ValueError(f"invalid source kind: {kind}")
        out.append(SourceConfig(str(name), validate_source_url(str(cfg.get("url") or "")), kind))
    return out


class RecorderRuntime:
    def __init__(self, root: str | Path, sources: list[SourceConfig]) -> None:
        self.root = Path(root)
        self.sources = sources
        self.telemetry = AppendOnlyHashChainLedger(self.root / "telemetry.jsonl")
        self.membership = AppendOnlyHashChainLedger(self.root / "membership.jsonl")
        self.seen_membership = existing_membership_ids(self.membership)
        self.lock = threading.RLock()
        self.session = requests.Session()
        self.state: dict[str, Any] = {
            "version": VERSION, "started_at_utc": utc_now(), "last_cycle_utc": None,
            "last_membership_cycle_utc": None, "cycles": 0, "membership_cycles": 0,
            "last_contract_id": None, "source_status": {}, "orders": False,
            "automatic_promotion": False, "storage": None,
            "control_manifest_sha256": None, "control_manifest_status": "MISSING",
        }
        manifest_path = os.environ.get("SENTINEL_CONTROL_MANIFEST", "").strip()
        if manifest_path:
            manifest = load_manifest(manifest_path)
            digest = manifest_sha256(manifest)
            self.telemetry.append({
                "record_type": "CONTROL_EXPECTATION", "sentinel_version": VERSION,
                "observed_at_utc": utc_now(), "manifest_sha256": digest,
                "manifest": manifest, "actual_control_plane_match": None,
                "orders": False, "production_mutation": False,
            })
            self.state["control_manifest_sha256"] = digest
            self.state["control_manifest_status"] = "EXPECTED_ONLY_REQUIRES_EXTERNAL_ATTESTATION"

    def fetch(self, source: SourceConfig) -> tuple[SourceConfig, int | None, float, Any | None, str | None]:
        started = time.perf_counter()
        try:
            response = self.session.get(
                source.url,
                timeout=float(os.environ.get("SENTINEL_TIMEOUT_SEC", DEFAULT_TIMEOUT_SEC)),
                headers={"Cache-Control": "no-cache", "User-Agent": VERSION},
            )
            latency = (time.perf_counter() - started) * 1000.0
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("source payload must be a JSON object")
            return source, response.status_code, latency, payload, None
        except Exception as exc:
            latency = (time.perf_counter() - started) * 1000.0
            return source, getattr(getattr(exc, "response", None), "status_code", None), latency, None, type(exc).__name__

    def _current_contract(self, results) -> str | None:
        for name in ("production_main", "scalp_combined"):
            for source, _, _, payload, error in results:
                if source.name == name and error is None and isinstance(payload, Mapping):
                    cid = adapt_source(source.name, payload).get("contract_id")
                    if isinstance(cid, str) and cid:
                        return cid
        return None

    def telemetry_cycle(self) -> None:
        disk = storage_status(self.root)
        with self.lock:
            self.state["storage"] = disk
        self.telemetry.append({
            "record_type": "SENTINEL_STORAGE", "sentinel_version": VERSION,
            "observed_at_utc": utc_now(), **disk, "orders": False,
        })
        if disk["storage_ok"] is not True:
            return
        sources = [s for s in self.sources if s.kind == "telemetry"]
        cycle_id = str(uuid.uuid4())
        observed = utc_now()
        with ThreadPoolExecutor(max_workers=max(1, len(sources))) as pool:
            futures = [pool.submit(self.fetch, s) for s in sources]
            results = [f.result() for f in as_completed(futures)]
        contract_id = self._current_contract(results)
        for source, http_status, latency, payload, error in sorted(results, key=lambda x: x[0].name):
            normalized: dict[str, Any] = {}
            if error is None and isinstance(payload, Mapping):
                normalized = adapt_source(source.name, payload)
            source_contract = normalized.get("contract_id") or contract_id
            self.telemetry.append(source_sample_body(
                source=source.name, observed_at_utc=observed, http_status=http_status,
                latency_ms=round(latency, 3), payload=payload, error_type=error,
                cycle_id=cycle_id, contract_id=source_contract, normalized=normalized,
            ))
            with self.lock:
                self.state["source_status"][source.name] = {
                    "observed_at_utc": observed, "ok": error is None,
                    "http_status": http_status, "latency_ms": round(latency, 3),
                    "error_type": error,
                }
        with self.lock:
            self.state["cycles"] += 1
            self.state["last_cycle_utc"] = observed
            self.state["last_contract_id"] = contract_id

    def membership_cycle(self) -> None:
        sources = [s for s in self.sources if s.kind == "membership"]
        observed = utc_now()
        with ThreadPoolExecutor(max_workers=max(1, len(sources))) as pool:
            futures = [pool.submit(self.fetch, s) for s in sources]
            results = [f.result() for f in as_completed(futures)]
        for source, http_status, latency, payload, error in sorted(results, key=lambda x: x[0].name):
            if error is not None or not isinstance(payload, Mapping):
                self.telemetry.append(source_sample_body(
                    source=source.name, observed_at_utc=observed, http_status=http_status,
                    latency_ms=round(latency, 3), payload=payload,
                    error_type=error or "InvalidPayload", cycle_id="membership",
                ))
                continue
            for event in membership_events(source.name, payload):
                event_id = event["event_id"]
                if event_id in self.seen_membership:
                    continue
                event["observed_by_sentinel_utc"] = observed
                event["source_http_status"] = http_status
                event["source_latency_ms"] = round(latency, 3)
                self.membership.append(event)
                self.seen_membership.add(event_id)
        with self.lock:
            self.state["membership_cycles"] += 1
            self.state["last_membership_cycle_utc"] = observed

    def public_state(self) -> dict[str, Any]:
        with self.lock:
            out = json.loads(json.dumps(self.state))
        out["telemetry_ledger"] = self.telemetry.status().__dict__
        out["membership_ledger"] = self.membership.status().__dict__
        out["membership_events_seen"] = len(self.seen_membership)
        out["source_count"] = len(self.sources)
        out["read_only_sources"] = True
        out["direct_market_api_polling"] = False
        return out


def _loop(runtime: RecorderRuntime) -> None:
    poll = max(2.0, float(os.environ.get("SENTINEL_POLL_SEC", DEFAULT_POLL_SEC)))
    membership_poll = max(poll, float(os.environ.get("SENTINEL_MEMBERSHIP_POLL_SEC", DEFAULT_MEMBERSHIP_POLL_SEC)))
    next_membership = 0.0
    while True:
        started = time.monotonic()
        runtime.telemetry_cycle()
        if started >= next_membership:
            runtime.membership_cycle()
            next_membership = started + membership_poll
        elapsed = time.monotonic() - started
        time.sleep(max(0.05, poll - elapsed))


class Handler(BaseHTTPRequestHandler):
    runtime: RecorderRuntime

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _json(self, code: int, obj: Any) -> None:
        raw = json.dumps(obj, separators=(",", ":"), sort_keys=True, allow_nan=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/health", "/state"):
            state = self.runtime.public_state()
            storage_ok = (state.get("storage") or {}).get("storage_ok") is True
            ok = bool(storage_ok and state["telemetry_ledger"]["chain_valid"] and state["membership_ledger"]["chain_valid"])
            code = 200 if (path != "/health" or ok) else 503
            return self._json(code, {"ok": ok, **state})
        return self._json(404, {"ok": False, "orders": False, "error": "not_found"})

    def _reject(self) -> None:
        return self._json(405, {"ok": False, "orders": False, "error": "read_only_sentinel"})

    do_POST = _reject
    do_PUT = _reject
    do_PATCH = _reject
    do_DELETE = _reject


def main() -> int:
    root = os.environ.get("SENTINEL_DATA_DIR", "/data/integrity_sentinel_v1")
    sources = load_sources()
    runtime = RecorderRuntime(root, sources)
    handler = type("BoundHandler", (Handler,), {"runtime": runtime})
    threading.Thread(target=_loop, args=(runtime,), daemon=True, name="integrity-sentinel-loop").start()
    port = int(os.environ.get("PORT", "8080"))
    print(
        f"{VERSION} START | poll={os.environ.get('SENTINEL_POLL_SEC', DEFAULT_POLL_SEC)}s | "
        f"sources={len(sources)} | APPEND-ONLY HASH-CHAINED EVIDENCE | "
        "RAILWAY STATE READS ONLY | NO DIRECT MARKET API | NO ORDERS",
        flush=True,
    )
    ThreadingHTTPServer(("0.0.0.0", port), handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
