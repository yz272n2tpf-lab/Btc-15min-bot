#!/usr/bin/env python3
"""BTC15 read-only live review wrapper for scalp specialist research.

SHADOW RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

This service is intentionally separate from production. It reads the existing
scalp event export with GET only, runs the frozen research analyzers in-memory,
and exposes review JSON at /state and health at /health.

It does NOT modify the source event tape, FINAL, EARLY, the scalp collector,
or any production signal logic. It does not place orders.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import requests

import scalp_contract_zone_map_v1 as zones
import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_frontier_v1 as v1
import scalp_specialist_union_frontier_v2 as v2

VERSION = "BTC15_SCALP_SPECIALIST_UNION_LIVE_REVIEW_V1"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(60, int(os.environ.get("SCALP_SPECIALIST_REVIEW_POLL_SEC", "300")))
SOURCE_URL = os.environ.get(
    "SCALP_PATH_EXPORT_URL",
    "https://scalp-move-shadow-v1-production.up.railway.app/research/path-export",
).strip()
SOURCE_TOKEN = os.environ.get("SCALP_PATH_EXPORT_TOKEN", "").strip()
INCREMENTAL_URL = os.environ.get("SCALP_INCREMENTAL_URL", "").strip()
_INCREMENTAL_RAW = bytearray()
_INCREMENTAL_OFFSET = 0
_INCREMENTAL_GENERATION = ""

LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "status": "STARTING",
    "orders": False,
    "manual_execution_only": True,
    "shadow_only": True,
    "production_logic_changed": False,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_rows() -> tuple[list[dict[str, str]], str, int]:
    global _INCREMENTAL_OFFSET, _INCREMENTAL_GENERATION
    if INCREMENTAL_URL:
        # Canary transport only: reconstruct exact source bytes from bounded deltas.
        # Analysis below is unchanged, allowing exact parity before deeper state optimization.
        while True:
            u = f"{INCREMENTAL_URL.rstrip('/')}/research/path-delta?offset={_INCREMENTAL_OFFSET}&max_bytes=4194304"
            r = requests.get(u, timeout=45); r.raise_for_status()
            gen = r.headers.get("X-Generation", "")
            if _INCREMENTAL_GENERATION and gen != _INCREMENTAL_GENERATION:
                _INCREMENTAL_RAW.clear(); _INCREMENTAL_OFFSET = 0
            _INCREMENTAL_GENERATION = gen
            start = int(r.headers.get("X-Start-Offset", _INCREMENTAL_OFFSET))
            end = int(r.headers.get("X-End-Offset", start + len(r.content)))
            if start != _INCREMENTAL_OFFSET:
                raise ValueError("incremental offset mismatch")
            if hashlib.sha256(r.content).hexdigest() != r.headers.get("X-Chunk-SHA256", ""):
                raise ValueError("incremental chunk hash mismatch")
            _INCREMENTAL_RAW.extend(r.content); _INCREMENTAL_OFFSET = end
            size = int(r.headers.get("X-Source-Size", end))
            if end >= size or not r.content: break
        raw = bytes(_INCREMENTAL_RAW)\n        manifest = requests.get(f"{INCREMENTAL_URL.rstrip('/')}/research/path-manifest", timeout=15); manifest.raise_for_status()\n        meta = manifest.json()\n        if len(raw) != int(meta.get("bytes", -1)) or hashlib.sha256(raw).hexdigest() != str(meta.get("sha256", "")):\n            raise ValueError("incremental reconstructed snapshot parity mismatch")
    else:
        headers = {"Cache-Control": "no-cache"}
        if SOURCE_TOKEN: headers["Authorization"] = f"Bearer {SOURCE_TOKEN}"
        r = requests.get(SOURCE_URL, headers=headers, timeout=45); r.raise_for_status()
        raw = r.content
    if not raw or b"record_type" not in raw[:4096]:
        raise ValueError("unexpected scalp event export")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8", "replace"))))
    return rows, hashlib.sha256(raw).hexdigest(), len(raw)


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0) -> dict[str, Any]:
    universe = v1.full_contract_universe(rows)
    if not universe:
        return {
            "ok": False,
            "version": VERSION,
            "status": "FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE",
            "updated_utc": utcnow(),
            "source_sha256": sha,
            "source_bytes": source_bytes,
            "source_rows": len(rows),
            "orders": False,
            "manual_execution_only": True,
            "shadow_only": True,
            "production_logic_changed": False,
            "promotion": False,
        }

    denom = set(universe)
    split = v1.split_universe(universe)
    opps = [r for r in q.build_serial_opportunities(rows) if r.get("contract") in denom]
    for r in opps:
        r["split"] = split.get(r.get("contract"), "")
    dev = [r for r in opps if r.get("split") == "DEVELOPMENT"]
    cuts = v1.calibrate_lane_cuts(dev)
    v1.lane_tags(opps, cuts)
    zones.add_zone_tags(opps)

    baseline = v1.score_with_true_coverage(opps, denom)
    lane_breakdown = v1.lane_breakdown(opps, denom)
    zone_map = zones.score_zone_map(opps, denom)
    cumulative = zones.cumulative_map(opps, denom)
    frontier, winner, holdout, selected_holdout = v2.model_frontier(opps, split)

    return v1.clean({
        "ok": True,
        "version": VERSION,
        "status": "RESEARCH_SNAPSHOT_READY",
        "updated_utc": utcnow(),
        "source_sha256": sha,
        "source_bytes": source_bytes,
        "source_rows": len(rows),
        "full_observed_contracts": len(denom),
        "serial_opportunities": len(opps),
        "split_contracts": {s: sum(v == s for v in split.values()) for s in ("DEVELOPMENT", "VALIDATION", "HOLDOUT")},
        "development_only_lane_cuts": cuts,
        "baseline": baseline,
        "lane_breakdown": lane_breakdown,
        "zone_map": zone_map,
        "cumulative_coverage": cumulative,
        "validation_selected_candidate": winner,
        "untouched_holdout_result": holdout,
        "holdout_selected_n": len(selected_holdout),
        "frontier_rows": len(frontier),
        "orders": False,
        "manual_execution_only": True,
        "shadow_only": True,
        "production_logic_changed": False,
        "automatic_promotion": False,
        "research_warning": (
            "Discovery/review snapshot only. Repeated snapshots do not certify a production rule. "
            "Any candidate chosen after inspection still requires a newly frozen untouched forward test."
        ),
    })


def refresh_once() -> dict[str, Any]:
    rows, sha, source_bytes = fetch_rows()
    with LOCK:
        old_sha = STATE.get("source_sha256")
        old_ok = STATE.get("ok")
    if old_ok and old_sha == sha:
        with LOCK:
            STATE["last_poll_utc"] = utcnow()
        return dict(STATE)
    result = analyze_rows(rows, sha=sha, source_bytes=source_bytes)
    result["last_poll_utc"] = utcnow()
    with LOCK:
        STATE.clear()
        STATE.update(result)
        return dict(STATE)


def loop() -> None:
    while True:
        try:
            refresh_once()
        except Exception as exc:
            with LOCK:
                previous = dict(STATE)
                STATE.update({
                    "ok": False,
                    "status": "FAIL_CLOSED_SOURCE_OR_ANALYSIS_ERROR",
                    "last_poll_utc": utcnow(),
                    "error": f"{type(exc).__name__}:{exc}",
                    "orders": False,
                    "manual_execution_only": True,
                    "shadow_only": True,
                    "production_logic_changed": False,
                    "last_good_source_sha256": previous.get("source_sha256"),
                })
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15ScalpSpecialistReviewV1/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_SPECIALIST_REVIEW_HTTP | request", flush=True)

    def send_json(self, code: int, obj: dict[str, Any]) -> None:
        raw = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        with LOCK:
            state = dict(STATE)
        if path == "/health":
            return self.send_json(200, {
                "ok": True,
                "version": VERSION,
                "analysis_ok": state.get("ok") is True,
                "analysis_status": state.get("status"),
                "orders": False,
                "shadow_only": True,
            })
        if path == "/state":
            return self.send_json(200, state)
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def main() -> int:
    print(
        f"{VERSION} START | READ ONLY | POLL={POLL_SEC}s | SIGNAL ONLY | NO ORDERS",
        flush=True,
    )
    t = threading.Thread(target=loop, name="scalp-specialist-review-loop", daemon=True)
    t.start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
