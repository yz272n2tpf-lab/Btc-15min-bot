#!/usr/bin/env python3
"""BTC15 schema-adaptive read-only scalp specialist review V3.2.

SHADOW RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Pipeline:
1. fetch the existing read-only event export;
2. probe the raw schema;
3. require all causal source dependencies;
4. adapt explicit aliases/units only;
5. run the unchanged V3 research analysis on adapted rows.

No outcome/future field is used as a model input. No production writes.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import scalp_event_schema_adapter_v1 as adapter
import scalp_event_schema_probe_v1 as schema
import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_live_review_v1 as live_v1
import scalp_specialist_union_live_review_v3 as v3

VERSION = "BTC15_SCALP_SPECIALIST_UNION_LIVE_REVIEW_V3_2"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(60, int(os.environ.get("SCALP_SPECIALIST_REVIEW_POLL_SEC", "300")))

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


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0) -> dict[str, Any]:
    probe = schema.schema_probe(rows, q.FEATURES)
    source_status = adapter.candidate_schema_status(rows)
    print(
        "SCALP_SCHEMA_ADAPTER | " + json.dumps({
            "ready": source_status["ready"],
            "candidate_rows": source_status["candidate_rows"],
            "missing_source_dependencies": source_status["missing_source_dependencies"],
            "alias_status": source_status["alias_status"],
        }, separators=(",", ":"), sort_keys=True),
        flush=True,
    )

    if not source_status["ready"]:
        return {
            "ok": False,
            "version": VERSION,
            "status": "SCHEMA_ADAPTATION_REQUIRED",
            "updated_utc": utcnow(),
            "source_sha256": sha,
            "source_bytes": source_bytes,
            "source_rows": len(rows),
            "raw_schema_probe": probe,
            "schema_adapter": source_status,
            "model_fit_attempted": False,
            "orders": False,
            "manual_execution_only": True,
            "shadow_only": True,
            "production_logic_changed": False,
            "automatic_promotion": False,
        }

    adapted = adapter.adapt_rows(rows)
    result = dict(v3.analyze_rows(adapted, sha=sha, source_bytes=source_bytes))
    result.update({
        "version": VERSION,
        "raw_schema_probe": probe,
        "schema_adapter": source_status,
        "schema_adaptation": "PASS_EXPLICIT_ALIASES_AND_UNITS_ONLY",
        "model_fit_attempted": True,
        "automatic_promotion": False,
    })
    return result


def refresh_once() -> dict[str, Any]:
    rows, sha, source_bytes = live_v1.fetch_rows()
    with LOCK:
        old_sha = STATE.get("source_sha256")
    if old_sha == sha and STATE.get("status") != "STARTING":
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
                    "version": VERSION,
                    "status": "FAIL_CLOSED_SOURCE_SCHEMA_OR_ANALYSIS_ERROR",
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
    server_version = "BTC15ScalpSpecialistReviewV32/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_SPECIALIST_REVIEW_V3_2_HTTP | request", flush=True)

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
    print(f"{VERSION} START | READ ONLY | SCHEMA-ADAPTIVE | POLL={POLL_SEC}s | NO ORDERS", flush=True)
    threading.Thread(target=loop, name="scalp-specialist-review-v32-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
