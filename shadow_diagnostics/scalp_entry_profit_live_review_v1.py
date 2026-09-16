#!/usr/bin/env python3
"""Read-only live reviewer for BTC15 entry + profit ladder research V1.

RESEARCH ONLY | VALIDATION VIEW | HOLDOUT SEALED | NO ORDERS
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

import scalp_entry_profit_ladder_v1 as ladder
import scalp_specialist_union_live_review_v1 as source

VERSION = "BTC15_SCALP_ENTRY_PROFIT_LIVE_REVIEW_V1"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(120, int(os.environ.get("SCALP_ENTRY_PROFIT_POLL_SEC", "600")))

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
    grid = result.get("policy_grid") or []
    validation = []
    for row in grid:
        v = dict(row.get("validation") or {})
        validation.append({
            "entry_policy": row.get("entry_policy"),
            "exit_policy": row.get("exit_policy"),
            "signals": v.get("signals"),
            "contracts": v.get("contracts"),
            "true_contract_coverage": v.get("true_contract_coverage"),
            "plus5_rate": v.get("plus5_rate"),
            "plus10_rate": v.get("plus10_rate"),
            "plus20_rate": v.get("plus20_rate"),
            "entry_le50_rate": v.get("entry_le50_rate"),
            "entry_ideal_25_35_rate": v.get("entry_ideal_25_35_rate"),
            "avg_entry_ask_c": v.get("avg_entry_ask_c"),
            "avg_minutes_left": v.get("avg_minutes_left"),
            "avg_executable_exit_gain_c": v.get("avg_executable_exit_gain_c"),
            "positive_exit_rate": v.get("positive_exit_rate"),
            "protected_exit_rate": v.get("protected_exit_rate"),
            "avg_opportunities_per_covered_contract": v.get("avg_opportunities_per_covered_contract"),
            "max_opportunity_index": v.get("max_opportunity_index"),
        })
    return {
        "version": VERSION,
        "status": result.get("status"),
        "validation_policy_grid": validation,
        "entry_policies": result.get("entry_policies"),
        "exit_policies": result.get("exit_policies"),
        "holdout_sealed": True,
        "automatic_selection": False,
        "fees_included": False,
        "orders": False,
    }


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0) -> dict[str, Any]:
    result = ladder.analyze(rows)
    out = compact(result)
    out.update({
        "ok": True,
        "updated_utc": utcnow(),
        "source_sha256": sha,
        "source_bytes": source_bytes,
        "source_rows": len(rows),
        "shadow_only": True,
        "manual_execution_only": True,
        "production_logic_changed": False,
    })
    print("SCALP_ENTRY_PROFIT_SUMMARY | " + json.dumps(out, separators=(",", ":"), sort_keys=True), flush=True)
    return out


def refresh_once() -> dict[str, Any]:
    rows, sha, source_bytes = source.fetch_rows()
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
            with LOCK:
                STATE.update({
                    "ok": False,
                    "version": VERSION,
                    "status": "FAIL_CLOSED_ENTRY_PROFIT_REVIEW_ERROR",
                    "error": f"{type(exc).__name__}:{exc}",
                    "last_poll_utc": utcnow(),
                    "holdout_sealed": True,
                    "orders": False,
                    "shadow_only": True,
                })
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15EntryProfitReviewV1/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_ENTRY_PROFIT_HTTP | request", flush=True)

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
            return self.send_json(200, {"ok": True, "analysis_ok": state.get("ok") is True,
                                        "analysis_status": state.get("status"), "holdout_sealed": True,
                                        "orders": False, "version": VERSION})
        if path in {"/summary", "/state"}:
            return self.send_json(200, state)
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def main() -> int:
    print(f"{VERSION} START | VALIDATION ONLY | HOLDOUT SEALED | POLL={POLL_SEC}s | NO ORDERS", flush=True)
    threading.Thread(target=loop, name="entry-profit-review-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
