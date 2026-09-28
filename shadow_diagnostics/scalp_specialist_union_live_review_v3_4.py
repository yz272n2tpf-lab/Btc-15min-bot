#!/usr/bin/env python3
"""BTC15 read-only scalp specialist live review V3.4.

SHADOW RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

V3.4 preserves V3.3 and performs one precommitted holdout reveal for three
validation-frozen roles defined in scalp_tiered_validation_freeze_v1.py.

IMPORTANT: the role definitions are code-frozen before this holdout reveal.
The holdout is report-only and must never be used to retune these roles.
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
import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_frontier_v1 as union_v1
import scalp_specialist_union_live_review_v1 as live_v1
import scalp_specialist_union_live_review_v3_3 as v33
import scalp_tiered_validation_freeze_v1 as tiered

VERSION = "BTC15_SCALP_SPECIALIST_UNION_LIVE_REVIEW_V3_4"
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


def compact_role(role: dict[str, Any] | None) -> dict[str, Any] | None:
    if not role:
        return None
    validation = role.get("validation_selection") or {}
    holdout = role.get("holdout") or {}
    return {
        "validation": {
            "model": validation.get("model"),
            "core_threshold": validation.get("core_threshold"),
            "rescue_threshold": validation.get("rescue_threshold"),
            "n": validation.get("n"),
            "plus10_rate": validation.get("plus10_rate"),
            "true_contract_coverage": validation.get("true_contract_coverage"),
            "affordable_true_contract_coverage_le50": validation.get("affordable_true_contract_coverage_le50"),
            "avg_entry_ask_c": validation.get("avg_entry_ask_c"),
            "avg_minutes_left": validation.get("avg_minutes_left"),
        },
        "holdout": {
            "n": holdout.get("n"),
            "plus5_rate": holdout.get("plus5_rate"),
            "plus10_rate": holdout.get("plus10_rate"),
            "plus20_rate": holdout.get("plus20_rate"),
            "true_contract_coverage": holdout.get("true_contract_coverage"),
            "affordable_true_contract_coverage_le50": holdout.get("affordable_true_contract_coverage_le50"),
            "avg_entry_ask_c": holdout.get("avg_entry_ask_c"),
            "avg_minutes_left": holdout.get("avg_minutes_left"),
            "core_plus10_rate": holdout.get("core_plus10_rate"),
            "coverage_rescue_plus10_rate": holdout.get("coverage_rescue_plus10_rate"),
            "core_true_contract_coverage": holdout.get("core_true_contract_coverage"),
            "coverage_gain_from_rescue": holdout.get("coverage_gain_from_rescue"),
        },
    }


def tier_summary(audit: dict[str, Any]) -> dict[str, Any]:
    roles = audit.get("roles") or {}
    return {
        "version": audit.get("version"),
        "selection_source": "VALIDATION_PARETO_FRONTIER_ONLY",
        "PRECISION_CORE": compact_role(roles.get("PRECISION_CORE")),
        "BALANCED_90": compact_role(roles.get("BALANCED_90")),
        "COVERAGE_FRONTIER": compact_role(roles.get("COVERAGE_FRONTIER")),
        "holdout_is_report_only": True,
        "retuning_after_holdout_prohibited": True,
        "forward_freeze_required_before_any_promotion": True,
        "automatic_promotion": False,
        "orders": False,
    }


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0) -> dict[str, Any]:
    base = dict(v33.analyze_rows(rows, sha=sha, source_bytes=source_bytes))
    base["version"] = VERSION
    if base.get("ok") is not True:
        return base

    pareto = base.get("multiobjective_pareto") or {}
    validation_frontier = list(pareto.get("pareto_frontier") or [])
    if not validation_frontier:
        base.update({
            "ok": False,
            "status": "FAIL_CLOSED_NO_VALIDATION_FRONTIER_FOR_TIER_FREEZE",
            "tiered_validation_freeze": None,
            "automatic_promotion": False,
        })
        return base

    adapted = adapter.adapt_rows(rows)
    universe = union_v1.full_contract_universe(adapted)
    if not universe:
        base.update({
            "ok": False,
            "status": "FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE_FOR_TIER_FREEZE",
            "tiered_validation_freeze": None,
            "automatic_promotion": False,
        })
        return base

    denominator = set(universe)
    split = union_v1.split_universe(universe)
    opps = [r for r in q.build_serial_opportunities(adapted) if r.get("contract") in denominator]
    for r in opps:
        r["split"] = split.get(r.get("contract"), "")
    dev = [r for r in opps if r.get("split") == "DEVELOPMENT"]
    cuts = union_v1.calibrate_lane_cuts(dev)
    union_v1.lane_tags(opps, cuts)

    audit = tiered.audit(opps, split, validation_frontier)
    compact = tier_summary(audit)
    base.update({
        "version": VERSION,
        "tiered_validation_freeze": audit,
        "tiered_holdout_summary": compact,
        "automatic_promotion": False,
        "v34_warning": (
            "Tier roles were fixed from validation definitions before holdout reveal. "
            "Holdout is report-only; these role definitions must not be retuned from holdout."
        ),
    })
    print("SCALP_TIERED_HOLDOUT | " + json.dumps(compact, separators=(",", ":"), sort_keys=True), flush=True)
    return base


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
                    "status": "FAIL_CLOSED_TIERED_HOLDOUT_ERROR",
                    "last_poll_utc": utcnow(),
                    "error": f"{type(exc).__name__}:{exc}",
                    "orders": False,
                    "manual_execution_only": True,
                    "shadow_only": True,
                    "production_logic_changed": False,
                    "automatic_promotion": False,
                    "last_good_source_sha256": previous.get("source_sha256"),
                })
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15ScalpSpecialistReviewV34/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_SPECIALIST_REVIEW_V3_4_HTTP | request", flush=True)

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
        if path == "/tiered-holdout":
            return self.send_json(200, state.get("tiered_holdout_summary") or {})
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def main() -> int:
    print(f"{VERSION} START | READ ONLY | VALIDATION-FROZEN HOLDOUT | POLL={POLL_SEC}s | NO ORDERS", flush=True)
    threading.Thread(target=loop, name="scalp-specialist-review-v34-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
