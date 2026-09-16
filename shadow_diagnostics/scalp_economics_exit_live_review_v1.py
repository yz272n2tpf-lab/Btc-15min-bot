#!/usr/bin/env python3
"""Read-only live reviewer for BTC15 scalp economics + exit certification V1.

RESEARCH ONLY | HISTORICAL DIAGNOSTIC | NO ORDERS | NO PROMOTION
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

import scalp_economics_exit_cert_v1 as econ
import scalp_specialist_union_live_review_v1 as source

VERSION = "BTC15_SCALP_ECONOMICS_EXIT_LIVE_REVIEW_V1"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(300, int(os.environ.get("SCALP_ECONOMICS_POLL_SEC", "900")))

LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "status": "STARTING",
    "orders": False,
    "shadow_only": True,
    "historical_diagnostic_only": True,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": result.get("status"),
        "fee_schedule": result.get("fee_schedule"),
        "overall": result.get("overall"),
        "by_opportunity_index": result.get("by_opportunity_index"),
        "movement_vs_realized_warning": result.get("movement_vs_realized_warning"),
        "unprotected_paths_are_not_fabricated": True,
        "automatic_promotion": False,
        "historical_diagnostic_only": True,
        "production_logic_changed": False,
        "shadow_only": True,
        "orders": False,
    }


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0) -> dict[str, Any]:
    print(f"SCALP_ECONOMICS_PROGRESS | analyze_start | rows={len(rows)} | bytes={source_bytes}", flush=True)
    result = compact(econ.analyze(rows))
    result.update({
        "ok": True,
        "updated_utc": utcnow(),
        "source_sha256": sha,
        "source_bytes": source_bytes,
        "source_rows": len(rows),
        "manual_execution_only": True,
    })
    print("SCALP_ECONOMICS_SUMMARY | " + json.dumps(result, separators=(",", ":"), sort_keys=True), flush=True)
    return result


def refresh_once() -> dict[str, Any]:
    print("SCALP_ECONOMICS_PROGRESS | fetch_start", flush=True)
    rows, sha, source_bytes = source.fetch_rows()
    print(f"SCALP_ECONOMICS_PROGRESS | fetch_ok | rows={len(rows)} | bytes={source_bytes}", flush=True)
    with LOCK:
        old_sha = STATE.get("source_sha256")
        old_status = STATE.get("status")
    if old_sha == sha and old_status != "STARTING":
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
            print("SCALP_ECONOMICS_ERROR | " + err, flush=True)
            with LOCK:
                STATE.update({
                    "ok": False,
                    "version": VERSION,
                    "status": "FAIL_CLOSED_ECONOMICS_EXIT_REVIEW_ERROR",
                    "error": err,
                    "last_poll_utc": utcnow(),
                    "historical_diagnostic_only": True,
                    "automatic_promotion": False,
                    "orders": False,
                    "shadow_only": True,
                })
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15EconomicsExitReviewV1/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_ECONOMICS_HTTP | request", flush=True)

    def send_json(self, code: int, obj: dict[str, Any]) -> None:
        raw = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(raw)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        with LOCK:
            state = dict(STATE)
        if path == "/health":
            return self.send_json(200, {"ok": True,
                                        "analysis_ok": state.get("ok") is True,
                                        "analysis_status": state.get("status"),
                                        "historical_diagnostic_only": True,
                                        "orders": False,
                                        "version": VERSION})
        if path in {"/summary", "/state"}:
            return self.send_json(200, state)
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def main() -> int:
    print(f"{VERSION} START | HISTORICAL DIAGNOSTIC | POLL={POLL_SEC}s | NO ORDERS | NO PROMOTION", flush=True)
    threading.Thread(target=loop, name="economics-exit-review-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
