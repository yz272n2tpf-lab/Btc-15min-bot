#!/usr/bin/env python3
"""Read-only validation reviewer for reversal/recross + re-entry ladder V1.

RESEARCH ONLY | VALIDATION ONLY | HOLDOUT SEALED | NO ORDERS
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

import scalp_reversal_reentry_ladder_v1 as ladder
import scalp_specialist_union_live_review_v1 as source

VERSION = "BTC15_SCALP_REVERSAL_REENTRY_LIVE_REVIEW_V1"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(300, int(os.environ.get("SCALP_REVERSAL_REENTRY_POLL_SEC", "900")))

LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "status": "STARTING",
    "holdout_sealed": True,
    "orders": False,
    "shadow_only": True,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact(result: dict[str, Any]) -> dict[str, Any]:
    val = dict(result.get("validation") or {})
    return {
        "version": VERSION,
        "status": result.get("status"),
        "coverage_scope": "SERIAL_ELIGIBLE_CONTRACTS_ONLY",
        "validation": val,
        "serial_meta": result.get("serial_meta"),
        "baseline_candidate_gate_unchanged": result.get("baseline_candidate_gate_unchanged"),
        "legacy_protection_lifecycle_unchanged": result.get("legacy_protection_lifecycle_unchanged"),
        "holdout_sealed": True,
        "automatic_selection": False,
        "automatic_promotion": False,
        "orders": False,
    }


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0) -> dict[str, Any]:
    print(f"SCALP_REVERSAL_REENTRY_PROGRESS | analyze_start | rows={len(rows)} | bytes={source_bytes}", flush=True)
    result = ladder.analyze(rows)
    out = compact(result)
    out.update({
        "ok": result.get("status") == "REVERSAL_REENTRY_LADDER_READY",
        "updated_utc": utcnow(),
        "source_sha256": sha,
        "source_bytes": source_bytes,
        "source_rows": len(rows),
        "shadow_only": True,
        "manual_execution_only": True,
        "production_logic_changed": False,
    })
    print("SCALP_REVERSAL_REENTRY_SUMMARY | " + json.dumps(out, separators=(",", ":"), sort_keys=True), flush=True)
    return out


def refresh_once() -> dict[str, Any]:
    print("SCALP_REVERSAL_REENTRY_PROGRESS | fetch_start", flush=True)
    rows, sha, source_bytes = source.fetch_rows()
    print(f"SCALP_REVERSAL_REENTRY_PROGRESS | fetch_ok | rows={len(rows)} | bytes={source_bytes}", flush=True)
    with LOCK:
        old_sha = STATE.get("source_sha256")
    if old_sha == sha and STATE.get("status") != "STARTING":
        with LOCK:
            STATE["last_poll_utc"] = utcnow()
            return dict(STATE)
    result = analyze_rows(rows, sha=sha, source_bytes=source_bytes)
    result["last_poll_utc"] = utcnow()
    with LOCK:
        STATE.clear(); STATE.update(result)
        return dict(STATE)


def loop() -> None:
    while True:
        try:
            refresh_once()
        except Exception as exc:
            err = f"{type(exc).__name__}:{exc}"
            print(f"SCALP_REVERSAL_REENTRY_FAIL_CLOSED | {err}", flush=True)
            with LOCK:
                STATE.update({
                    "ok": False,
                    "version": VERSION,
                    "status": "FAIL_CLOSED_REVERSAL_REENTRY_REVIEW_ERROR",
                    "error": err,
                    "last_poll_utc": utcnow(),
                    "holdout_sealed": True,
                    "orders": False,
                    "shadow_only": True,
                    "automatic_promotion": False,
                })
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15ReversalReentryV1/1.0"
    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_REVERSAL_REENTRY_HTTP | request", flush=True)
    def send_json(self, code: int, obj: dict[str, Any]) -> None:
        raw = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw))); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(raw)
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        with LOCK: state = dict(STATE)
        if path == "/health":
            return self.send_json(200, {"ok": True, "analysis_ok": state.get("ok") is True,
                                        "analysis_status": state.get("status"), "holdout_sealed": True,
                                        "orders": False, "version": VERSION})
        if path in {"/summary", "/state"}:
            return self.send_json(200, state)
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def main() -> int:
    print(f"{VERSION} START | VALIDATION ONLY | HOLDOUT SEALED | POLL={POLL_SEC}s | NO ORDERS", flush=True)
    threading.Thread(target=loop, name="reversal-reentry-review-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
