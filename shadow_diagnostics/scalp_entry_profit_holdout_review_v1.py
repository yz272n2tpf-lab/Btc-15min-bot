#!/usr/bin/env python3
"""One-time frozen-role holdout reviewer for Entry + Profit Ladder V1.

READ ONLY | VALIDATION SELECTS ROLES | HOLDOUT REPORT ONLY | NO ORDERS
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
import scalp_entry_profit_validation_freeze_v1 as freeze
import scalp_specialist_union_live_review_v1 as source

VERSION = "BTC15_SCALP_ENTRY_PROFIT_HOLDOUT_REVIEW_V1"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(600, int(os.environ.get("SCALP_ENTRY_PROFIT_HOLDOUT_POLL_SEC", "3600")))

LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "status": "STARTING",
    "orders": False,
    "automatic_promotion": False,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def role_report(result: dict[str, Any]) -> dict[str, Any]:
    audit = freeze.audit(result.get("policy_grid") or [])
    rows = {
        (str(r.get("entry_policy") or ""), str(r.get("exit_policy") or "")): r
        for r in result.get("policy_grid") or []
    }
    out: dict[str, Any] = {}
    for role, frozen in (audit.get("roles") or {}).items():
        key = (str(frozen.get("entry_policy") or ""), str(frozen.get("exit_policy") or ""))
        row = rows.get(key) or {}
        val = dict(row.get("validation") or {})
        hold = dict(row.get("holdout") or {})
        out[role] = {
            "entry_policy": key[0],
            "exit_policy": key[1],
            "coverage_scope": "BASELINE_QUALIFIED_SIGNAL_CONTRACTS",
            "validation": val,
            "holdout": hold,
            "validation_baseline_contract_retention": val.get("true_contract_coverage"),
            "holdout_baseline_contract_retention": hold.get("true_contract_coverage"),
            "selected_from": "VALIDATION_ONLY",
            "holdout_selected_nothing": True,
        }
    return {
        "version": VERSION,
        "status": "FROZEN_ROLES_HOLDOUT_REVEALED" if out else "FAIL_CLOSED_NO_FROZEN_ROLES",
        "roles": out,
        "role_freeze_version": audit.get("version"),
        "coverage_scope": "BASELINE_QUALIFIED_SIGNAL_CONTRACTS",
        "holdout_used_for_selection": False,
        "retuning_after_holdout_prohibited": True,
        "automatic_promotion": False,
        "fees_included": False,
        "orders": False,
    }


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0) -> dict[str, Any]:
    print(f"SCALP_ENTRY_PROFIT_HOLDOUT_PROGRESS | analyze_start | rows={len(rows)}", flush=True)
    result = ladder.analyze(rows)
    out = role_report(result)
    out.update({
        "ok": out.get("status") == "FROZEN_ROLES_HOLDOUT_REVEALED",
        "updated_utc": utcnow(),
        "source_sha256": sha,
        "source_bytes": source_bytes,
        "source_rows": len(rows),
        "shadow_only": True,
        "manual_execution_only": True,
        "production_logic_changed": False,
    })
    print("SCALP_ENTRY_PROFIT_HOLDOUT | " + json.dumps(out, separators=(",", ":"), sort_keys=True), flush=True)
    return out


def refresh_once() -> dict[str, Any]:
    print("SCALP_ENTRY_PROFIT_HOLDOUT_PROGRESS | fetch_start", flush=True)
    rows, sha, source_bytes = source.fetch_rows()
    print(f"SCALP_ENTRY_PROFIT_HOLDOUT_PROGRESS | fetch_ok | rows={len(rows)}", flush=True)
    with LOCK:
        if STATE.get("source_sha256") == sha and STATE.get("ok") is True:
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
            print(f"SCALP_ENTRY_PROFIT_HOLDOUT_FAIL_CLOSED | {err}", flush=True)
            with LOCK:
                STATE.update({"ok":False,"version":VERSION,"status":"FAIL_CLOSED_HOLDOUT_REVIEW_ERROR",
                              "error":err,"last_poll_utc":utcnow(),"orders":False,
                              "automatic_promotion":False})
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15EntryProfitHoldoutV1/1.0"
    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_ENTRY_PROFIT_HOLDOUT_HTTP | request", flush=True)
    def send_json(self, code: int, obj: dict[str, Any]) -> None:
        raw = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store")
        self.end_headers(); self.wfile.write(raw)
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        with LOCK: state = dict(STATE)
        if path == "/health":
            return self.send_json(200, {"ok":True,"analysis_ok":state.get("ok") is True,
                                        "analysis_status":state.get("status"),"orders":False,"version":VERSION})
        if path in {"/summary","/state"}:
            return self.send_json(200, state)
        return self.send_json(404, {"ok":False,"error":"not_found","orders":False})


def main() -> int:
    print(f"{VERSION} START | VALIDATION-FROZEN ROLES | HOLDOUT REPORT ONLY | NO RETUNE | NO ORDERS", flush=True)
    threading.Thread(target=loop, name="entry-profit-holdout-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
