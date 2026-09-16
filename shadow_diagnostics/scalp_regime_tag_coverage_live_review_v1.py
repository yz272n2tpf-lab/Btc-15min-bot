#!/usr/bin/env python3
"""Read-only live reviewer for BTC15 regime tag coverage audit V1.

CAUSAL FEATURE AUDIT | DESCRIPTIVE ONLY | NO THRESHOLD SELECTION | NO ORDERS
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

import scalp_regime_tag_coverage_audit_v1 as audit
import scalp_specialist_union_live_review_v1 as source

VERSION = "BTC15_SCALP_REGIME_TAG_COVERAGE_LIVE_REVIEW_V1"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(300, int(os.environ.get("SCALP_REGIME_TAG_AUDIT_POLL_SEC", "900")))

LOCK = threading.Lock()
STATE: dict[str, Any] = {"ok": False, "version": VERSION, "status": "STARTING",
                         "causal_feature_audit": True, "orders": False, "shadow_only": True}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _top_blockers(section: Mapping[str, Any], key: str, n: int = 8) -> dict[str, Any]:
    z = dict(section.get(key) or {})
    z["blockers"] = list(z.get("blockers") or [])[:n]
    return z


def compact_split(section: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rows": section.get("rows"),
        "numeric_features": section.get("numeric_features"),
        "boolean_features": section.get("boolean_features"),
        "condition_pass_counts": section.get("condition_pass_counts"),
        "tag_counts": section.get("tag_counts"),
        "trend_funnel": section.get("trend_funnel"),
        "kalshi_lag_funnel": section.get("kalshi_lag_funnel"),
        "acceleration_funnel": section.get("acceleration_funnel"),
        "trend_blockers": _top_blockers(section, "trend_blockers"),
        "kalshi_lag_blockers": _top_blockers(section, "kalshi_lag_blockers"),
        "acceleration_blockers": _top_blockers(section, "acceleration_blockers"),
        "reversal_evidence_count": section.get("reversal_evidence_count"),
        "reversal_evidence_rate": section.get("reversal_evidence_rate"),
    }


def compact(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": result.get("status"),
        "all_serial_opportunities": compact_split(result.get("all_serial_opportunities") or {}),
        "validation": compact_split(result.get("validation") or {}),
        "holdout": compact_split(result.get("holdout") or {}),
        "thresholds_are_existing_v1_descriptive_thresholds": True,
        "threshold_selection": False,
        "outcomes_used_for_blockers_or_distributions": False,
        "no_signal_suppression_or_rescue": True,
        "automatic_promotion": False,
        "causal_feature_audit": True,
        "orders": False,
    }


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0) -> dict[str, Any]:
    print(f"SCALP_REGIME_TAG_AUDIT_PROGRESS | analyze_start | rows={len(rows)} | bytes={source_bytes}", flush=True)
    out = compact(audit.analyze(rows))
    out.update({"ok": True, "updated_utc": utcnow(), "source_sha256": sha,
                "source_bytes": source_bytes, "source_rows": len(rows),
                "manual_execution_only": True, "production_logic_changed": False,
                "shadow_only": True})
    print("SCALP_REGIME_TAG_AUDIT_SUMMARY | " + json.dumps(out, separators=(",", ":"), sort_keys=True), flush=True)
    return out


def refresh_once() -> dict[str, Any]:
    print("SCALP_REGIME_TAG_AUDIT_PROGRESS | fetch_start", flush=True)
    rows, sha, source_bytes = source.fetch_rows()
    print(f"SCALP_REGIME_TAG_AUDIT_PROGRESS | fetch_ok | rows={len(rows)} | bytes={source_bytes}", flush=True)
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
            print("SCALP_REGIME_TAG_AUDIT_ERROR | " + err, flush=True)
            with LOCK:
                STATE.update({"ok": False, "version": VERSION,
                              "status": "FAIL_CLOSED_REGIME_TAG_AUDIT_ERROR",
                              "error": err, "last_poll_utc": utcnow(),
                              "threshold_selection": False, "automatic_promotion": False,
                              "causal_feature_audit": True, "orders": False, "shadow_only": True})
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15RegimeTagAuditV1/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_REGIME_TAG_AUDIT_HTTP | request", flush=True)

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
                                        "status": state.get("status"), "causal_feature_audit": True,
                                        "orders": False, "version": VERSION})
        if path in {"/summary", "/state"}:
            return self.send_json(200, state)
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def main() -> int:
    print(f"{VERSION} START | CAUSAL FEATURE AUDIT | NO THRESHOLD SELECTION | NO ORDERS", flush=True)
    threading.Thread(target=loop, name="regime-tag-audit-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
