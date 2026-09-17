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

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import base64
import hashlib
import math
from datetime import datetime, timezone
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
    utc_now,
)
from integrity_sentinel.source_adapters_v1 import adapt_source
from integrity_sentinel.watchdog_health_v3 import watchdog_failures
from integrity_sentinel.storage_guard_v1 import storage_status
from integrity_sentinel.control_attestation_v1 import load_manifest, manifest_sha256, compare_manifest, validate_manifest

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
    if not isinstance(url, str) or any(ord(c) < 33 for c in url) or "\\" in url:
        raise ValueError("invalid source URL syntax")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        raise ValueError("sentinel sources must use https")
    if not host.endswith(".up.railway.app"):
        raise ValueError(f"sentinel refuses non-Railway source host: {host}")
    if "@" in parsed.netloc or parsed.username is not None or parsed.password is not None:
        raise ValueError("credentials in source URL are forbidden")
    if parsed.port not in (None, 443) or parsed.fragment:
        raise ValueError("source port/fragment forbidden")
    if not host[:-len(".up.railway.app")] or "%" in host:
        raise ValueError("invalid Railway host")
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


def _number_env(name, default, minimum):
    value = float(os.environ.get(name, default))
    if not math.isfinite(value) or value < minimum:
        raise ValueError(f"invalid {name}")
    return value


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("missing capture timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed > datetime.now(timezone.utc):
        raise ValueError("invalid capture timestamp")
    return parsed


def _payload_failures(payload):
    failures = []
    objects = [payload]
    for key in ("live", "health", "source_health"):
        if isinstance(payload.get(key), Mapping):
            objects.append(payload[key])
    for obj in objects:
        for key in ("ok", "healthy", "source_ok", "source_fresh", "fresh",
                    "clean_for_qualification", "scalp_source_fresh", "scalp_contract_aligned",
                    "brti_fresh", "kalshi_fresh", "coinbase_fresh", "parity_ok"):
            if key in obj and obj[key] is not True:
                failures.append(key)
        for key in ("stale", "source_stale", "failed"):
            if key in obj and obj[key] is not False:
                failures.append(key)
        for key in ("status", "state"):
            value = obj.get(key)
            if isinstance(value, str) and any(word in value.upper() for word in
                    ("FAIL", "ERROR", "STALE", "UNAVAILABLE", "UNKNOWN", "DEGRADED", "STOPPED")):
                failures.append(key + ":" + value)
        if obj.get("error"):
            failures.append("error")
    return failures


class NoRedirectSession(requests.Session):
    """Keep the first response, including an unparseable Location header.

    Requests normally calls resolve_redirects even with allow_redirects=False
    to construct Response.next. An empty iterator prevents that parsing and
    every redirect hop, while retaining normal adapter timeout/TLS handling.
    """

    def resolve_redirects(self, response, request, **kwargs):
        return iter(())


class RecorderRuntime:
    def __init__(self, root: str | Path, sources: list[SourceConfig], *,
                 expected_manifest=None, actual_snapshot=None) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        if len({s.name for s in sources}) != len(sources):
            raise ValueError("duplicate source name")
        for source in sources:
            validate_source_url(source.url)
            if source.kind not in {"telemetry", "membership"}:
                raise ValueError("invalid source kind")
        self.sources = sources
        self.lock = threading.RLock()
        self._thread = None
        self._last_success_mono = None
        self._source_mono = {}
        self.poll_sec = _number_env("SENTINEL_POLL_SEC", DEFAULT_POLL_SEC, 2)
        self.membership_poll_sec = _number_env("SENTINEL_MEMBERSHIP_POLL_SEC", DEFAULT_MEMBERSHIP_POLL_SEC, self.poll_sec)
        self.max_cycle_age_sec = max(30.0, 3 * self.membership_poll_sec)
        self.source_max_age_sec = max(30.0, 3 * self.membership_poll_sec)
        self.session = NoRedirectSession()
        self.state = {
            "version": VERSION, "started_at_utc": utc_now(), "last_cycle_utc": None,
            "last_membership_cycle_utc": None, "cycles": 0, "membership_cycles": 0,
            "last_contract_id": None, "contract_agreement": None,
            "source_status": {}, "orders": False, "automatic_promotion": False,
            "certifiable_evidence": False, "storage": None,
            "control_manifest_sha256": None, "control_manifest_status": "UNKNOWN",
            "control_attestation": {"control_plane_pass": None},
            "recorder": {"last_start_utc": None, "last_success_utc": None,
                         "last_cycle_utc": None, "failure_count": 0,
                         "last_failure_utc": None, "last_exception_type": None,
                         "unrecovered_failure": False},
        }
        self.telemetry = AppendOnlyHashChainLedger(self.root / "telemetry.jsonl", self._storage_guard,
                                                 allow_failed_open=True)
        self.membership = AppendOnlyHashChainLedger(self.root / "membership.jsonl", self._storage_guard,
                                                  allow_failed_open=True)
        ledgers_ok = self.telemetry.status().chain_valid and self.membership.status().chain_valid
        self.seen_membership = existing_membership_ids(self.membership) if ledgers_ok else set()
        if not ledgers_ok:
            self._failure(ValueError("startup ledger integrity failed; independent recovery required"))
        try:
            manifest_path = os.environ.get("SENTINEL_CONTROL_MANIFEST", "").strip()
            actual_path = os.environ.get("SENTINEL_CONTROL_SNAPSHOT", "").strip()
            if expected_manifest is None and manifest_path:
                expected_manifest = load_manifest(manifest_path)
            if actual_snapshot is None and actual_path:
                actual_snapshot = json.loads(Path(actual_path).read_text(encoding="utf-8"))
            expected = validate_manifest(expected_manifest)
            report = compare_manifest(expected, actual_snapshot)
            if not isinstance(actual_snapshot, Mapping):
                raise ValueError("missing actual control snapshot")
            _timestamp(actual_snapshot.get("captured_at_utc"))
            if any(source.name not in expected["sources"] for source in sources):
                raise ValueError("control expectations omit configured sources")
            self.state["control_manifest_sha256"] = manifest_sha256(expected)
            self.state["control_attestation"] = report
            self.state["control_manifest_status"] = (
                "PASS" if report["control_plane_pass"] is True else
                "FAIL" if report["control_plane_pass"] is False else "UNKNOWN")
        except (ValueError, OSError, TypeError) as exc:
            self.state["control_attestation"] = {"control_plane_pass": None, "error_type": type(exc).__name__}
        # Freeze by value, including the separately supplied actual capture.
        if ledgers_ok:
            try:
                self.telemetry.append({"record_type": "CONTROL_ATTESTATION", "observed_at_utc": utc_now(),
                    "expected": expected_manifest, "actual": actual_snapshot,
                    "attestation": self.state["control_attestation"], "orders": False})
            except Exception as exc:
                self._failure(exc)

    def _failure(self, exc):
        with self.lock:
            rec = self.state["recorder"]
            rec["failure_count"] += 1
            rec["last_failure_utc"] = utc_now()
            rec["last_exception_type"] = type(exc).__name__
            rec["unrecovered_failure"] = True

    def _storage_guard(self):
        try:
            disk = storage_status(self.root)
        except Exception as exc:
            disk = {"storage_ok": False, "state": "FAIL", "error_type": type(exc).__name__}
        with self.lock:
            self.state["storage"] = disk
        if disk.get("storage_ok") is not True:
            raise OSError("storage inspection/availability failed")
        return disk

    def fetch(self, source: SourceConfig):
        started = time.perf_counter()
        envelope = {
            "observation_id": str(uuid.uuid4()), "sentinel_version": VERSION, "source": source.name,
            "source_kind": source.kind, "request_url": source.url,
            "method": "GET", "started_at_utc": utc_now(), "http_status": None,
            "response_url": None, "headers": {}, "body_base64": None,
            "body_sha256": None, "body_bytes": None, "body_complete": False,
            "body_representation": "HTTP entity bytes after Requests content decoding",
            "payload": None,
            "parse_outcome": "NO_RESPONSE", "parse_error": None,
            "error_type": None, "normalized": {},
        }
        response = None
        try:
            # Never rely on configuration-time validation, and never follow a
            # redirect, even to another otherwise permitted Railway host.
            validate_source_url(source.url)
            response = self.session.get(source.url,
                timeout=_number_env("SENTINEL_TIMEOUT_SEC", DEFAULT_TIMEOUT_SEC, 0.01),
                headers={"Cache-Control": "no-cache", "User-Agent": VERSION},
                allow_redirects=False, stream=True)
            envelope["http_status"] = response.status_code
            envelope["response_url"] = response.url
            envelope["headers"] = dict(response.headers)
            chunks = []
            try:
                for chunk in response.iter_content(chunk_size=65536):
                    chunks.append(chunk)
                envelope["body_complete"] = True
            finally:
                raw = b"".join(chunks)
                envelope.update(body_base64=base64.b64encode(raw).decode("ascii"),
                    body_sha256=hashlib.sha256(raw).hexdigest(), body_bytes=len(raw))
            try:
                def reject_constant(value):
                    raise ValueError("non-finite JSON constant: " + value)
                payload = json.loads(raw, parse_constant=reject_constant)
                # Reject finite-parser overflow too (e.g. 1e999).
                json.dumps(payload, allow_nan=False)
                if not isinstance(payload, dict):
                    envelope["parse_outcome"] = "WRONG_TYPE"
                    envelope["parse_error"] = "ExpectedJSONObject"
                else:
                    envelope["payload"] = payload
                    envelope["parse_outcome"] = "OBJECT"
            except (ValueError, UnicodeError) as exc:
                envelope["parse_outcome"] = "MALFORMED_JSON"
                envelope["parse_error"] = type(exc).__name__
            validate_source_url(response.url)
            if response.url != source.url:
                raise ValueError("unexpected response destination")
            if 300 <= response.status_code < 400:
                envelope["error_type"] = "RedirectBlocked"
            elif not 200 <= response.status_code < 300:
                envelope["error_type"] = "HTTPError"
            elif envelope["parse_error"]:
                envelope["error_type"] = envelope["parse_error"]
        except Exception as exc:
            envelope["error_type"] = type(exc).__name__
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception as exc:
                    envelope["error_type"] = type(exc).__name__
            envelope["completed_at_utc"] = utc_now()
            envelope["_completed_mono"] = time.monotonic()
            envelope["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return source, envelope

    def _cycle(self, kind):
        try:
            disk = self._storage_guard()
            if not self.telemetry.status().chain_valid or not self.membership.status().chain_valid:
                raise ValueError("ledger integrity failed; independent recovery required")
            if kind == "telemetry":
                self.telemetry.append({"record_type": "SENTINEL_STORAGE", "observed_at_utc": utc_now(),
                                       **disk, "orders": False})
            sources = [s for s in self.sources if s.kind == kind]
            cycle_id = str(uuid.uuid4())
            with ThreadPoolExecutor(max_workers=max(1, len(sources))) as pool:
                results = list(pool.map(self.fetch, sources))
            contracts = {}
            statuses = {}
            observed_times = {}
            for source, observation in results:
                observed_times[source.name] = observation.pop("_completed_mono")
                payload = observation["payload"]
                events = []
                # Evaluate watchdog before normalization/membership extraction,
                # even for a parsed error response or another validation fault.
                # The original payload/body remain untouched in the envelope.
                failures = watchdog_failures(payload, required=source.name in {
                    "early_membership", "final_membership"}) if isinstance(payload, Mapping) else []
                if observation["error_type"] is None and isinstance(payload, Mapping):
                    try:
                        observation["normalized"] = adapt_source(source.name, payload)
                        failures.extend(_payload_failures(payload))
                        normalized = observation["normalized"]
                        for key in ("source_age_sec", "age_sec", "kalshi_age_sec", "coinbase_age_sec", "brti_age_sec"):
                            if key in payload:
                                age = payload[key]
                                if type(age) not in (int, float) or not math.isfinite(age) or not 0 <= age <= self.source_max_age_sec:
                                    failures.append(key)
                        for key in ("updated_at_utc", "updated_utc", "source_timestamp_utc",
                                    "kalshi_success_timestamp_utc", "coinbase_success_timestamp_utc"):
                            if key in payload:
                                try:
                                    stamp = _timestamp(payload[key])
                                    if (datetime.now(timezone.utc) - stamp).total_seconds() > self.source_max_age_sec:
                                        failures.append(key)
                                except ValueError:
                                    failures.append(key)
                        if "brti_shared" in source.name:
                            age = normalized.get("brti_age_sec")
                            if age is None or age > self.source_max_age_sec:
                                failures.append("brti_age_sec")
                        if kind == "membership":
                            events = membership_events(source.name, payload)
                        else:
                            cid = normalized.get("contract_id")
                            if cid:
                                contracts[source.name] = cid
                            elif source.name in {"production_main", "scalp_combined"}:
                                failures.append("missing_contract_id")
                    except (ValueError, TypeError, OverflowError) as exc:
                        observation["error_type"] = "ValidationError"
                        observation["validation_error"] = str(exc)
                observation["source_failures"] = failures
                observation["cycle_id"] = cycle_id
                observation["record_type"] = "SOURCE_OBSERVATION"
                observation["orders"] = False
                observation["source_mutation"] = False
                # Every attempt, including empty/invalid membership, gets an
                # immutable envelope BEFORE any derived membership event.
                ledger = self.membership if kind == "membership" else self.telemetry
                envelope_row = ledger.append(observation)
                for event in events:
                    if event["event_id"] in self.seen_membership:
                        continue
                    event.update(observed_by_sentinel_utc=observation["completed_at_utc"],
                        observation_id=observation["observation_id"],
                        observation_record_hash=envelope_row["record_hash"])
                    self.membership.append(event)
                    self.seen_membership.add(event["event_id"])
                statuses[source.name] = {
                    "observed_at_utc": observation["completed_at_utc"],
                    "ok": observation["error_type"] is None and not failures,
                    "http_status": observation["http_status"],
                    "error_type": observation["error_type"], "source_failures": failures,
                    "normalized": observation["normalized"],
                }
            if kind == "telemetry":
                agreement = bool(contracts) and len(set(contracts.values())) == 1
                self.telemetry.append({"record_type": "CONTRACT_AGREEMENT", "cycle_id": cycle_id,
                    "observed_at_utc": utc_now(), "contracts": contracts, "agreement": agreement})
            with self.lock:
                self.state["source_status"].update(statuses)
                self._source_mono.update(observed_times)
                if kind == "telemetry":
                    self.state["contract_agreement"] = agreement
                    self.state["last_contract_id"] = next(iter(contracts.values())) if agreement else None
                    self.state["cycles"] += 1
                    self.state["last_cycle_utc"] = utc_now()
                else:
                    self.state["membership_cycles"] += 1
                    self.state["last_membership_cycle_utc"] = utc_now()
        except Exception as exc:
            self._failure(exc)
            raise

    def telemetry_cycle(self):
        self._cycle("telemetry")

    def membership_cycle(self):
        self._cycle("membership")

    def run_cycle(self, include_membership=True):
        with self.lock:
            self.state["recorder"]["last_start_utc"] = utc_now()
            before = self.state["recorder"]["failure_count"]
        try:
            self.telemetry_cycle()
            if include_membership:
                self.membership_cycle()
            with self.lock:
                self._last_success_mono = time.monotonic()
                self.state["recorder"]["last_success_utc"] = utc_now()
                self.state["recorder"]["unrecovered_failure"] = False
        except Exception as exc:
            if self.state["recorder"]["failure_count"] == before:
                self._failure(exc)
        finally:
            with self.lock:
                self.state["recorder"]["last_cycle_utc"] = utc_now()

    def public_state(self):
        try:
            self._storage_guard()
        except Exception as exc:
            self._failure(exc)
        with self.lock:
            out = json.loads(json.dumps(self.state, allow_nan=False))
            now = time.monotonic()
            ages = {name: now - stamp for name, stamp in self._source_mono.items()}
            success_age = None if self._last_success_mono is None else now - self._last_success_mono
        out["telemetry_ledger"] = self.telemetry.status().__dict__
        out["membership_ledger"] = self.membership.status().__dict__
        rec = out["recorder"]
        rec["thread_alive"] = self._thread is not None and self._thread.is_alive()
        rec["last_success_age_sec"] = success_age
        rec["fresh"] = success_age is not None and 0 <= success_age <= self.max_cycle_age_sec
        reasons = []
        if not rec["thread_alive"] or not rec["fresh"] or rec["unrecovered_failure"]:
            reasons.append("recorder_unhealthy")
        if not self.sources:
            reasons.append("no_sources")
        for source in self.sources:
            status = out["source_status"].get(source.name, {})
            age = ages.get(source.name)
            if status.get("ok") is not True or age is None or not 0 <= age <= self.source_max_age_sec:
                reasons.append("source_unhealthy:" + source.name)
        if out["contract_agreement"] is not True:
            reasons.append("contract_agreement_unknown_or_failed")
        if out["control_attestation"].get("control_plane_pass") is not True:
            reasons.append("control_attestation_unknown_or_failed")
        if (out["storage"] or {}).get("storage_ok") is not True:
            reasons.append("storage_failed")
        if not out["telemetry_ledger"]["chain_valid"] or not out["membership_ledger"]["chain_valid"]:
            reasons.append("ledger_integrity_failed")
        out.update(ok=not reasons, health_failures=reasons,
            membership_events_seen=len(self.seen_membership), source_count=len(self.sources),
            read_only_sources=True, direct_market_api_polling=False)
        out["provider_evidence"] = {}
        for provider in ("kalshi", "coinbase"):
            explicit = any(s.get("normalized", {}).get(provider + "_freshness_status") == "EXPLICIT_EVIDENCE"
                           for s in out["source_status"].values())
            out["provider_evidence"][provider] = "EXPLICIT_FIELDS_REQUIRE_RECONCILIATION" if explicit else "INSUFFICIENT"
        return out


def _loop(runtime):
    runtime._thread = threading.current_thread()
    next_membership = 0.0
    while True:
        started = time.monotonic()
        try:
            runtime.run_cycle(started >= next_membership)
            if started >= next_membership:
                next_membership = started + runtime.membership_poll_sec
        except Exception as exc:
            runtime._failure(exc)
        time.sleep(max(0.05, runtime.poll_sec - (time.monotonic() - started)))


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
            ok = state["ok"]
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
