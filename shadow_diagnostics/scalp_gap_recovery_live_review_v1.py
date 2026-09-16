#!/usr/bin/env python3
"""BTC15 live gap-recovery feature reviewer V1.

READ ONLY | RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Fetches the existing scalp event export and runs the descriptive missed-contract
feature audit. This service does not select thresholds, fit a production rule,
write to production, or place orders.
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

import scalp_gap_recovery_feature_audit_v1 as audit
import scalp_rescue_feasibility_v1 as feasibility
import scalp_specialist_union_live_review_v1 as live_v1

VERSION = "BTC15_SCALP_GAP_RECOVERY_LIVE_REVIEW_V1"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(60, int(os.environ.get("SCALP_SPECIALIST_REVIEW_POLL_SEC", "300")))

LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "status": "STARTING",
    "orders": False,
    "shadow_only": True,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact(result: dict[str, Any]) -> dict[str, Any]:
    base = result.get("baseline_gap_summary") or {}
    return {
        "version": VERSION,
        "status": result.get("status"),
        "full_observed_contracts": result.get("full_observed_contracts"),
        "baseline_true_contract_coverage": base.get("baseline_true_contract_coverage"),
        "baseline_covered_contracts": base.get("baseline_covered_contracts"),
        "uncovered_contracts": base.get("uncovered_contracts"),
        "contracts_needed_to_reach_90pct": base.get("contracts_needed_to_reach_90pct"),
        "complete_candidate_paths_in_uncovered_contracts": result.get("complete_candidate_paths_in_uncovered_contracts"),
        "all_candidate_path_summary": result.get("all_candidate_path_summary"),
        "by_gap_reason": result.get("by_gap_reason"),
        "reason_recoverability": result.get("reason_recoverability"),
        "top_feature_separations": (result.get("descriptive_feature_separations") or [])[:12],
        "development_only": True,
        "threshold_selection": False,
        "automatic_promotion": False,
        "orders": False,
    }


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0) -> dict[str, Any]:
    result = dict(audit.analyze(rows))
    if result.get("status") != "READY":
        return {
            **result,
            "ok": False,
            "version": VERSION,
            "source_sha256": sha,
            "source_bytes": source_bytes,
            "source_rows": len(rows),
            "orders": False,
            "shadow_only": True,
        }
    # Reuse the gap ledger once for reason-level ceiling counts.
    measured, base = audit.candidate_rows(rows)
    if "ledger" in base:
        result["reason_recoverability"] = feasibility.summarize(base["ledger"])["by_reason"]
    result.update({
        "ok": True,
        "version": VERSION,
        "status": "GAP_RECOVERY_FEATURE_AUDIT_READY",
        "updated_utc": utcnow(),
        "source_sha256": sha,
        "source_bytes": source_bytes,
        "source_rows": len(rows),
        "orders": False,
        "manual_execution_only": True,
        "shadow_only": True,
        "production_logic_changed": False,
        "automatic_promotion": False,
        "threshold_selection": False,
    })
    print("SCALP_GAP_RECOVERY_SUMMARY | " + json.dumps(compact(result), separators=(",", ":"), sort_keys=True), flush=True)
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
                    "status": "FAIL_CLOSED_GAP_RECOVERY_ERROR",
                    "last_poll_utc": utcnow(),
                    "error": f"{type(exc).__name__}:{exc}",
                    "orders": False,
                    "shadow_only": True,
                    "automatic_promotion": False,
                })
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15GapRecoveryReviewV1/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_GAP_RECOVERY_HTTP | request", flush=True)

    def send_json(self, code: int, obj: dict[str, Any]) -> None:
        raw = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw))); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(raw)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        with LOCK:
            state = dict(STATE)
        if path == "/health":
            return self.send_json(200, {"ok": True, "analysis_ok": state.get("ok") is True, "analysis_status": state.get("status"), "version": VERSION, "orders": False, "shadow_only": True})
        if path == "/summary":
            return self.send_json(200, compact(state))
        if path == "/state":
            return self.send_json(200, state)
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def main() -> int:
    print(f"{VERSION} START | READ ONLY | DEVELOPMENT-ONLY GAP RECOVERY | POLL={POLL_SEC}s | NO ORDERS", flush=True)
    threading.Thread(target=loop, name="scalp-gap-recovery-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
