#!/usr/bin/env python3
"""BTC15 Coverage Rescue V1 prospective forward scorer.

SHADOW ONLY | SIGNAL ONLY | NO ORDERS | NO AUTO-PROMOTION

The cutoff is mandatory. A contract is eligible only if its first passive tape
observation occurs at or after the cutoff and the contract is later proven fully
observed (>=840s left and <=60s left). Pre-freeze and mid-contract data cannot
enter the prospective denominator.
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

import scalp_coverage_rescue_v1 as rescue
import scalp_event_schema_adapter_v1 as adapter
import scalp_specialist_union_frontier_v1 as union
import scalp_specialist_union_live_review_v1 as source

VERSION = "BTC15_SCALP_COVERAGE_RESCUE_FORWARD_V1_FROZEN"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(60, int(os.environ.get("SCALP_RESCUE_V1_POLL_SEC", "120")))
CUTOFF_TEXT = os.environ.get("SCALP_RESCUE_V1_CUTOFF_UTC", "").strip()

LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "status": "STARTING",
    "cutoff_utc": CUTOFF_TEXT or None,
    "orders": False,
    "shadow_only": True,
    "automatic_promotion": False,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_cutoff(text: str) -> datetime | None:
    if not text:
        return None
    try:
        x = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if x.tzinfo is None:
            x = x.replace(tzinfo=timezone.utc)
        return x.astimezone(timezone.utc)
    except Exception:
        return None


def future_universe(rows: list[Mapping[str, Any]], cutoff: datetime) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    adapted = adapter.adapt_rows(rows)
    full = union.full_contract_universe(adapted)
    future: dict[str, dict[str, Any]] = {}
    for c, meta in full.items():
        first = meta.get("first_seen")
        if isinstance(first, datetime) and first >= cutoff:
            future[c] = dict(meta)
    return future, adapted


def without_prior_baseline(rescue_rows: list[dict[str, Any]], baseline_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    earliest_baseline: dict[str, datetime] = {}
    for row in baseline_rows:
        c = str(row.get("contract") or "")
        t = row.get("timestamp")
        if c and isinstance(t, datetime):
            earliest_baseline[c] = min(earliest_baseline.get(c, t), t)
    out: list[dict[str, Any]] = []
    for row in rescue_rows:
        c = str(row.get("contract") or "")
        t = row.get("timestamp")
        bt = earliest_baseline.get(c)
        if bt is not None and isinstance(t, datetime) and bt <= t:
            continue
        out.append(row)
    return out


def compact(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": state.get("status"),
        "cutoff_utc": state.get("cutoff_utc"),
        "future_full_contracts": state.get("future_full_contracts"),
        "baseline": state.get("baseline"),
        "rescue": state.get("rescue"),
        "union": state.get("union"),
        "incremental_rescue_contracts": state.get("incremental_rescue_contracts"),
        "mechanical_reconciliation": state.get("mechanical_reconciliation"),
        "qualification": state.get("qualification"),
        "frozen_rule": rescue.frozen_rule(),
        "automatic_promotion": False,
        "orders": False,
    }


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0, cutoff_text: str | None = None) -> dict[str, Any]:
    text = CUTOFF_TEXT if cutoff_text is None else cutoff_text
    cutoff = parse_cutoff(text)
    if cutoff is None:
        return {
            "ok": False,
            "version": VERSION,
            "status": "FAIL_CLOSED_MISSING_OR_INVALID_CUTOFF",
            "cutoff_utc": text or None,
            "source_sha256": sha,
            "source_rows": len(rows),
            "orders": False,
            "automatic_promotion": False,
        }

    future, adapted = future_universe(rows, cutoff)
    contracts = set(future)
    baseline_rows = rescue.reconciled_baseline_serial(adapted, contracts)
    raw_rescue = rescue.first_rescue_signals(adapted, contracts)
    rescue_rows = without_prior_baseline(raw_rescue, baseline_rows)

    # Candidate ids are disjoint by rule (rescue BTC30 <15; baseline BTC30 >=15),
    # but preserve an explicit de-duplication guard.
    baseline_ids = {str(r.get("candidate_id") or "") for r in baseline_rows}
    rescue_rows = [r for r in rescue_rows if str(r.get("candidate_id") or "") not in baseline_ids]
    combined = list(baseline_rows) + list(rescue_rows)

    baseline_summary = rescue.score_summary(baseline_rows, contracts)
    rescue_summary = rescue.score_summary(rescue_rows, contracts)
    union_summary = rescue.score_summary(combined, contracts)
    baseline_contracts = {str(r.get("contract") or "") for r in baseline_rows}
    rescue_contracts = {str(r.get("contract") or "") for r in rescue_rows}
    incremental = len((rescue_contracts - baseline_contracts) & contracts)
    qual = rescue.qualification(baseline_summary, rescue_summary, union_summary, len(contracts), incremental)

    status = "COLLECTING_FUTURE_RESCUE_V1"
    if qual.get("certification_sample_ready"):
        status = "READY_FOR_MANUAL_REVIEW_PASS" if qual.get("qualification_pass") else "READY_FOR_MANUAL_REVIEW_FAIL"

    mechanical = {
        "baseline_path_reconciled_signals": baseline_summary.get("path_reconciled_signals"),
        "baseline_unresolved_signals": baseline_summary.get("unresolved_signals"),
        "rescue_path_reconciled_signals": rescue_summary.get("path_reconciled_signals"),
        "rescue_unresolved_signals": rescue_summary.get("unresolved_signals"),
        "result_presence_never_changes_trigger": True,
        "serial_reset_requires_observed_protected_exit": True,
    }

    result = {
        "ok": True,
        "version": VERSION,
        "status": status,
        "updated_utc": utcnow(),
        "cutoff_utc": cutoff.isoformat(),
        "source_sha256": sha,
        "source_bytes": source_bytes,
        "source_rows": len(rows),
        "future_full_contracts": len(contracts),
        "future_contract_ids": sorted(contracts),
        "baseline": baseline_summary,
        "rescue": rescue_summary,
        "union": union_summary,
        "incremental_rescue_contracts": incremental,
        "mechanical_reconciliation": mechanical,
        "qualification": qual,
        "frozen_rule": rescue.frozen_rule(),
        "manual_execution_only": True,
        "shadow_only": True,
        "production_logic_changed": False,
        "automatic_promotion": False,
        "orders": False,
    }
    print("SCALP_RESCUE_FORWARD | " + json.dumps(compact(result), separators=(",", ":"), sort_keys=True, default=str), flush=True)
    return result


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
                    "status": "FAIL_CLOSED_SOURCE_OR_ANALYSIS_ERROR",
                    "last_poll_utc": utcnow(),
                    "error": f"{type(exc).__name__}:{exc}",
                    "orders": False,
                    "automatic_promotion": False,
                    "shadow_only": True,
                })
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15CoverageRescueForwardV1/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_RESCUE_FORWARD_HTTP | request", flush=True)

    def send_json(self, code: int, obj: Mapping[str, Any]) -> None:
        raw = json.dumps(obj, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")
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
            return self.send_json(200, {
                "ok": True,
                "analysis_ok": state.get("ok") is True,
                "status": state.get("status"),
                "version": VERSION,
                "cutoff_utc": state.get("cutoff_utc"),
                "orders": False,
                "shadow_only": True,
            })
        if path == "/summary":
            return self.send_json(200, compact(state))
        if path == "/state":
            return self.send_json(200, state)
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def main() -> int:
    print(f"{VERSION} START | cutoff={CUTOFF_TEXT or 'MISSING'} | SHADOW ONLY | NO AUTO-PROMOTION | NO ORDERS", flush=True)
    threading.Thread(target=loop, name="scalp-rescue-forward-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
