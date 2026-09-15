#!/usr/bin/env python3
"""
BTC15 authoritative live scoreboard V1.

READ ONLY | PRIVATE RAILWAY AGGREGATOR | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

Reads authoritative collector /state endpoints over Railway private networking,
validates exact expected versions, and passes only current snapshots into the
pure BTC15_AUTHORITATIVE_SCOREBOARD_V1 combiner.

No source snapshot is cached across requests. If a collector is unavailable,
wrong-versioned, malformed, or unsafe, that lane is returned as NOT CONNECTED
for that request instead of reusing stale data.
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

import requests

import BTC15_AUTHORITATIVE_SCOREBOARD_V1 as boardmod

VERSION = "BTC15_AUTHORITATIVE_SCOREBOARD_LIVE_V1"
PORT = int(os.environ.get("PORT", "8080"))
TIMEOUT_SEC = 2.5

SOURCES: dict[str, dict[str, str]] = {
    "final": {
        "url": "http://final-forward-scorecard-v1.railway.internal:8080/state",
        "version": "BTC15_FINAL_FORWARD_SCORECARD_V4",
    },
    "early": {
        "url": "http://early-forward-scorecard-v1.railway.internal:8080/state",
        "version": "BTC15_EARLY_FORWARD_SCORECARD_V1",
    },
    "handoff": {
        "url": "http://early-final-handoff-v1.railway.internal:8080/state",
        "version": "BTC15_EARLY_FINAL_HANDOFF_FORWARD_V1",
    },
    "excursion": {
        "url": "http://early-excursion-forward-v1.railway.internal:8080/state",
        "version": "BTC15_EARLY_EXCURSION_FORWARD_V1",
    },
    "flip": {
        "url": "http://scalp-coverage-audit-v1.railway.internal:8080/state",
        "version": "BTC15_DIRECT_BRTI_FLIP_RISK_FORWARD_V2",
    },
}


def _top_version(payload: Mapping[str, Any]) -> str | None:
    v = payload.get("version")
    if v:
        return str(v)
    for key in ("live", "summary", "scorecard", "snapshot"):
        q = payload.get(key)
        if isinstance(q, Mapping) and q.get("version"):
            return str(q.get("version"))
    return None


def _is_unsafe(payload: Mapping[str, Any]) -> str | None:
    checks = [payload]
    for key in ("live", "summary", "scorecard", "snapshot"):
        q = payload.get(key)
        if isinstance(q, Mapping):
            checks.append(q)
    for q in checks:
        if q.get("orders") is True:
            return "orders_true"
        if q.get("manual_execution_only") is False:
            return "manual_execution_false"
        if q.get("production_behavior_changed") is True:
            return "production_behavior_changed"
    return None


def fetch_source(name: str, get: Callable[..., Any] = requests.get) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    spec = SOURCES[name]
    started = time.monotonic()
    try:
        r = get(
            spec["url"], timeout=TIMEOUT_SEC,
            headers={"User-Agent": VERSION, "Cache-Control": "no-cache"},
        )
        status = int(getattr(r, "status_code", 0))
        if status != 200:
            return None, {
                "connected": False, "reason": f"http_{status}",
                "latency_ms": round((time.monotonic()-started)*1000, 1),
            }
        payload = r.json()
        if not isinstance(payload, Mapping):
            return None, {"connected": False, "reason": "non_object_json"}
        actual = _top_version(payload)
        if actual != spec["version"]:
            return None, {
                "connected": False, "reason": "version_mismatch",
                "expected_version": spec["version"], "actual_version": actual,
            }
        unsafe = _is_unsafe(payload)
        if unsafe:
            return None, {"connected": False, "reason": f"unsafe_{unsafe}"}
        return dict(payload), {
            "connected": True,
            "version": actual,
            "latency_ms": round((time.monotonic()-started)*1000, 1),
            "transport": "railway_private_network",
        }
    except Exception as exc:
        return None, {
            "connected": False,
            "reason": f"fetch_error:{type(exc).__name__}",
            "latency_ms": round((time.monotonic()-started)*1000, 1),
        }


def collect_live(fetcher: Callable[[str], tuple[dict[str, Any] | None, dict[str, Any]]] = fetch_source) -> dict[str, Any]:
    payloads: dict[str, dict[str, Any] | None] = {}
    source_health: dict[str, dict[str, Any]] = {}

    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        futs = {pool.submit(fetcher, name): name for name in SOURCES}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                payload, health = fut.result()
            except Exception as exc:
                payload, health = None, {"connected": False, "reason": f"worker_error:{type(exc).__name__}"}
            payloads[name] = payload
            source_health[name] = health

    board = boardmod.combine_scoreboard(
        final_payload=payloads.get("final"),
        early_payload=payloads.get("early"),
        handoff_payload=payloads.get("handoff"),
        excursion_payload=payloads.get("excursion"),
        flip_payload=payloads.get("flip"),
        numeric_flip_user_facing_approved=False,
    )
    connected_n = sum(bool(v.get("connected")) for v in source_health.values())
    return {
        "ok": True,
        "version": VERSION,
        "generated_unix": time.time(),
        "source_health": source_health,
        "connected_sources": connected_n,
        "expected_sources": len(SOURCES),
        "all_sources_connected": connected_n == len(SOURCES),
        "scoreboard": board,
        "scoreboard_text": boardmod.render_text(board),
        "orders": False,
        "manual_execution_only": True,
        "production_behavior_changed": False,
        "network_scope": "RAILWAY_PRIVATE_COLLECTORS_ONLY",
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15AuthoritativeScoreboardLiveV1/1.0"

    def _json(self, code: int, payload: Mapping[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, code: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            # Self-health only. Upstream collector failure must not create a
            # restart loop in this presentation service.
            return self._json(200, {
                "ok": True, "version": VERSION,
                "orders": False, "manual_execution_only": True,
                "production_behavior_changed": False,
            })
        if path in {"/scoreboard", "/state"}:
            try:
                return self._json(200, collect_live())
            except Exception as exc:
                return self._json(500, {
                    "ok": False, "version": VERSION,
                    "error": f"{type(exc).__name__}: {exc}",
                    "orders": False, "manual_execution_only": True,
                })
        if path == "/scoreboard.txt":
            try:
                return self._text(200, collect_live()["scoreboard_text"])
            except Exception as exc:
                return self._text(500, f"SCOREBOARD ERROR: {type(exc).__name__}: {exc}\n")
        return self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        return self._json(405, {"ok": False, "error": "read_only"})

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"SCOREBOARD_HTTP | {fmt % args}", flush=True)


def main() -> int:
    print(
        f"{VERSION} START | PRIVATE COLLECTOR READS ONLY | NO CACHE | "
        "NO MODEL RECOMPUTE | NO ORDERS",
        flush=True,
    )
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
