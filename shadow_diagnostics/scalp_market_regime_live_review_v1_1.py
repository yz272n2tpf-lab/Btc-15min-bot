#!/usr/bin/env python3
"""Read-only reviewer for BTC15 Regime V1.1 semantic repair.

DESCRIPTIVE SEMANTIC REPAIR | NO THRESHOLD SELECTION | NO ORDERS

Holdout is descriptive because V1's holdout was already observed before this
representation bug was found. V1.1 cannot select or promote a rule from it.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

import scalp_market_regime_ledger_v1_1 as regime
import scalp_specialist_union_live_review_v1 as source

VERSION = "BTC15_SCALP_MARKET_REGIME_LIVE_REVIEW_V1_1"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(300, int(os.environ.get("SCALP_REGIME_V11_POLL_SEC", "900")))
LOCK = threading.Lock()
STATE: dict[str, Any] = {"ok": False, "version": VERSION, "status": "STARTING",
                         "semantic_repair": True, "orders": False, "shadow_only": True}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact_metrics(part: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "overall": part.get("overall"),
        "primary_regimes": part.get("primary_regimes"),
        "overlapping_tags": part.get("overlapping_tags"),
        "by_opportunity_index": part.get("by_opportunity_index"),
    }


def compact(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": result.get("status"),
        "semantic_repair": result.get("semantic_repair"),
        "tag_definitions": result.get("tag_definitions"),
        "validation": compact_metrics(result.get("validation") or {}),
        "holdout": compact_metrics(result.get("holdout") or {}),
        "validation_to_holdout_shift": result.get("validation_to_holdout_shift"),
        "holdout_is_descriptive_after_semantic_repair": True,
        "holdout_cannot_select_v1_1_rule": True,
        "no_threshold_selection": True,
        "no_signal_suppression_or_rescue": True,
        "automatic_promotion": False,
        "semantic_repair_only": True,
        "orders": False,
    }


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0) -> dict[str, Any]:
    print(f"SCALP_REGIME_V11_PROGRESS | analyze_start | rows={len(rows)} | bytes={source_bytes}", flush=True)
    out = compact(regime.analyze(rows))
    out.update({"ok": True, "updated_utc": utcnow(), "source_sha256": sha,
                "source_bytes": source_bytes, "source_rows": len(rows),
                "manual_execution_only": True, "production_logic_changed": False,
                "shadow_only": True})
    print("SCALP_REGIME_V11_SUMMARY | " + json.dumps(out, separators=(",", ":"), sort_keys=True), flush=True)
    return out


def refresh_once() -> dict[str, Any]:
    print("SCALP_REGIME_V11_PROGRESS | fetch_start", flush=True)
    rows, sha, source_bytes = source.fetch_rows()
    print(f"SCALP_REGIME_V11_PROGRESS | fetch_ok | rows={len(rows)} | bytes={source_bytes}", flush=True)
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
            print("SCALP_REGIME_V11_ERROR | " + err, flush=True)
            with LOCK:
                STATE.update({"ok": False, "version": VERSION,
                              "status": "FAIL_CLOSED_REGIME_V11_ERROR",
                              "error": err, "last_poll_utc": utcnow(),
                              "semantic_repair_only": True,
                              "holdout_cannot_select_v1_1_rule": True,
                              "automatic_promotion": False, "orders": False,
                              "shadow_only": True})
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15RegimeV11Review/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_REGIME_V11_HTTP | request", flush=True)

    def send_json(self, code: int, obj: Mapping[str, Any]) -> None:
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
                                        "status": state.get("status"), "semantic_repair_only": True,
                                        "orders": False, "version": VERSION})
        if path in {"/summary", "/state"}:
            return self.send_json(200, state)
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def main() -> int:
    print(f"{VERSION} START | SEMANTIC REPAIR ONLY | HOLDOUT DESCRIPTIVE | NO THRESHOLD SELECTION | NO ORDERS", flush=True)
    threading.Thread(target=loop, name="regime-v11-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
