#!/usr/bin/env python3
"""BTC15 read-only scalp specialist live review V3.3.

SHADOW RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

V3.3 preserves V3.2 schema adaptation and analysis exactly, adding only a
compact decision-metric log surface so results can be inspected through Railway
without exposing raw event rows.
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

import scalp_specialist_union_live_review_v1 as live_v1
import scalp_specialist_union_live_review_v3_2 as v32

VERSION = "BTC15_SCALP_SPECIALIST_UNION_LIVE_REVIEW_V3_3"
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


def compact_summary(state: dict[str, Any]) -> dict[str, Any]:
    specialist = state.get("specialist_union") or {}
    lag = state.get("normalized_kalshi_lag") or {}
    pareto = state.get("multiobjective_pareto") or {}
    complement = state.get("lane_complementarity") or {}
    return {
        "version": VERSION,
        "ok": state.get("ok"),
        "status": state.get("status"),
        "source_sha256": state.get("source_sha256"),
        "source_rows": state.get("source_rows"),
        "full_observed_contracts": state.get("full_observed_contracts"),
        "serial_opportunities": state.get("serial_opportunities"),
        "baseline": state.get("baseline"),
        "lane_breakdown": specialist.get("lane_breakdown"),
        "union_validation": specialist.get("validation_selected_candidate"),
        "union_holdout": specialist.get("untouched_holdout_result"),
        "kalshi_lag_validation": lag.get("validation_selected_candidate"),
        "kalshi_lag_holdout": lag.get("untouched_holdout_result"),
        "contract_zone_map": state.get("contract_zone_map"),
        "cumulative_coverage": state.get("cumulative_coverage"),
        "pareto": {
            "input_rows": pareto.get("input_rows"),
            "eligible_rows": pareto.get("eligible_rows"),
            "pareto_rows": pareto.get("pareto_rows"),
            "frontier": pareto.get("pareto_frontier"),
        },
        "lane_unique_coverage": complement.get("unique_lane_coverage"),
        "lane_pairwise_overlap": complement.get("pairwise_overlap"),
        "schema_ready": (state.get("schema_adapter") or {}).get("ready"),
        "schema_adaptation": state.get("schema_adaptation"),
        "automatic_promotion": False,
        "orders": False,
    }


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0) -> dict[str, Any]:
    result = dict(v32.analyze_rows(rows, sha=sha, source_bytes=source_bytes))
    result["version"] = VERSION
    summary = compact_summary(result)
    print("SCALP_REAL_TAPE_SUMMARY | " + json.dumps(summary, separators=(",", ":"), sort_keys=True), flush=True)
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
    server_version = "BTC15ScalpSpecialistReviewV33/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_SPECIALIST_REVIEW_V3_3_HTTP | request", flush=True)

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
        if path == "/summary":
            return self.send_json(200, compact_summary(state))
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def main() -> int:
    print(f"{VERSION} START | READ ONLY | COMPACT RESULTS | POLL={POLL_SEC}s | NO ORDERS", flush=True)
    threading.Thread(target=loop, name="scalp-specialist-review-v33-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
