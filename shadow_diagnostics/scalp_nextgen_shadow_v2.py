#!/usr/bin/env python3
"""One isolated, read-only shadow service. No execution or promotion routes."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import scalp_economics_forward_v1 as econ_v1
import scalp_nextgen_v2_core as core
import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_live_review_v1 as source

VERSION = "BTC15_SCALP_NEXTGEN_SHADOW_V2_R2"
# Changed research code requires a new fingerprint and a fresh cutoff.
REVISION_NOT_BEFORE_UTC = "2026-09-16T21:33:15+00:00"
CUTOFF_TEXT = os.environ.get("SCALP_NEXTGEN_V2_CUTOFF_UTC", "").strip()
EXPECTED_CODE_SHA256 = os.environ.get("SCALP_NEXTGEN_V2_EXPECTED_CODE_SHA256", "").strip()
POLL_SEC = max(60, int(os.environ.get("SCALP_NEXTGEN_V2_POLL_SEC", "180")))
PORT = int(os.environ.get("PORT", "8080"))
MIN_FULL_CONTRACTS = 100
MIN_SIGNALS = 100
LOCK = threading.Lock()
SAFETY = {"shadow_only": True, "manual_execution_only": True, "orders": False,
          "production_logic_changed": False, "same_sample_promotion": False,
          "automatic_promotion": False, "later_fresh_certification_required": True}
STATE: dict[str, Any] = {"ok": False, "status": "STARTING", "version": VERSION, **SAFETY}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def code_fingerprint() -> str:
    """Pin source/dependency/build bytes, including all local research imports."""
    root = Path(__file__).resolve().parent.parent
    paths = sorted(root.glob("shadow_diagnostics/*.py"))
    paths += [root / "requirements.txt", root / "railway.json"]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def fail_state(status: str, **extra) -> dict[str, Any]:
    return {"ok": False, "status": status, "version": VERSION, "updated_utc": now(), **SAFETY, **extra}


def integrity_report(state: Mapping[str, Any]) -> dict[str, Any]:
    families = {family: isinstance(state.get(family), Mapping)
                and set(state[family]) == set(lanes)
                and all(isinstance(state[family][lane], Mapping) and "signals" in state[family][lane] for lane in lanes)
                for family, lanes in core.REQUIRED_LANES.items()}
    watch = state.get("watch_exit_v2") or {}
    parity = bool(families["watch_exit_v2"] and
                  all(watch[lane].get("frozen_exit_time_gain_mismatches") == 0 for lane in core.WATCH_MODES)
                  and len({watch[lane].get("frozen_exit_signals") for lane in core.WATCH_MODES}) == 1)
    safety = all(state.get(k) is v for k, v in SAFETY.items())
    counts_ready = state.get("future_full_contracts", 0) >= MIN_FULL_CONTRACTS and state.get("serial_signals", 0) >= MIN_SIGNALS
    readiness = (state.get("evidence_readiness") or {}).get("sample_ready") is counts_ready
    if state.get("status") == "READY_FOR_MANUAL_V2_COMPARISON" and not counts_ready: readiness = False
    return {"all_checks_pass": all(families.values()) and parity and safety and readiness,
            "four_families_complete": families, "watch_exact_exit_parity": parity,
            "safety_flags_exact": safety, "readiness_matches_counts": readiness,
            "performance_selection_or_promotion": False}


def analyze_rows(rows, sha: str = "", source_bytes: int = 0, cutoff_text: str | None = None,
                 *, development: bool = False, expected_code_sha256: str | None = None) -> dict[str, Any]:
    cutoff = core.strict_time(CUTOFF_TEXT if cutoff_text is None else cutoff_text)
    if cutoff is None: return fail_state("FAIL_CLOSED_INVALID_CUTOFF")
    fingerprint = code_fingerprint()
    expected = EXPECTED_CODE_SHA256 if expected_code_sha256 is None else expected_code_sha256
    if not development and (cutoff < core.strict_time(REVISION_NOT_BEFORE_UTC) or expected != fingerprint):
        return fail_state("FAIL_CLOSED_UNPINNED_WINDOW", code_sha256=fingerprint,
                          cutoff_utc=cutoff.isoformat(), revision_not_before_utc=REVISION_NOT_BEFORE_UTC)
    contracts, adapted = econ_v1.future_universe(rows, cutoff)
    opps = [op for op in q.build_serial_opportunities(adapted) if op["contract"] in contracts]
    ready = len(contracts) >= MIN_FULL_CONTRACTS and len(opps) >= MIN_SIGNALS
    summaries, audit = core.analyze_opportunities(opps, len(contracts))
    window = hashlib.sha256((fingerprint + "|" + cutoff.isoformat()).encode()).hexdigest()
    state = {
        "ok": True, "version": VERSION,
        "status": "DEVELOPMENT_REPLAY" if development else
                  ("READY_FOR_MANUAL_V2_COMPARISON" if ready else "COLLECTING_NEXTGEN_V2"),
        "updated_utc": now(), "cutoff_utc": cutoff.isoformat(), "code_sha256": fingerprint,
        "window_id": window, "prospective_window": not development,
        "source_sha256": sha, "source_bytes": source_bytes, "source_rows": len(rows),
        "future_full_contracts": len(contracts), "serial_signals": len(opps), **summaries,
        "audit_records": audit,
        "opportunity_basis": "frozen V1 serial IDs; independent entry replay, not lane-specific portfolio P&L",
        "evidence_readiness": {"sample_ready": ready, "required_future_full_contracts": MIN_FULL_CONTRACTS,
            "required_serial_signals": MIN_SIGNALS, "development_comparison_only": True,
            "per_lane_sample_sufficiency_not_established": True,
            "later_fresh_certification_required": True},
        "fee_assumptions": {"source": "unchanged frozen V1 fee model; not broker statements",
                            "effective_date_in_v1": core.econ.FEE_SCHEDULE_EFFECTIVE},
        **SAFETY,
    }
    state["runtime_integrity"] = integrity_report(state)
    if not state["runtime_integrity"]["all_checks_pass"]:
        state["ok"] = False
        state["status"] = "FAIL_CLOSED_NEXTGEN_V2_INVARIANT"
    json.dumps(state, allow_nan=False)
    return state


def refresh_once() -> dict[str, Any]:
    try:
        preflight = analyze_rows([], cutoff_text=CUTOFF_TEXT)
        if not preflight["ok"]:
            result = preflight
        else:
            rows, sha, size = source.fetch_rows()
            stamps = [t for row in rows if (t := core.strict_time(row.get("timestamp_utc"))) is not None]
            latest = max(stamps) if stamps else None
            age = (datetime.now(timezone.utc) - latest).total_seconds() if latest else None
            if age is None or age < -60 or age > max(600, 2 * POLL_SEC):
                result = fail_state("FAIL_CLOSED_STALE_SOURCE", source_age_sec=age)
            else:
                # Re-score the same hash too, allowing recovery after errors.
                result = analyze_rows(rows, sha, size)
                result["source_latest_utc"] = latest.isoformat()
                result["source_age_sec"] = age
    except Exception as exc:
        # Exception strings can contain authenticated URLs; log only the type.
        result = fail_state("FAIL_CLOSED_NEXTGEN_V2_ERROR", error_type=type(exc).__name__)
    result["last_poll_utc"] = now()
    with LOCK:
        STATE.clear()
        STATE.update(result)
    fields = ("version", "status", "cutoff_utc", "code_sha256", "window_id", "future_full_contracts",
              "serial_signals", "source_sha256", "error_type", "runtime_integrity")
    print("SCALP_NEXTGEN_V2 | " + json.dumps({k: result[k] for k in fields if k in result}, allow_nan=False), flush=True)
    return result


def loop() -> None:
    while True:
        refresh_once()
        time.sleep(POLL_SEC)


def response(path: str, state: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
    last = core.strict_time(state.get("last_poll_utc"))
    fresh = bool(last and (datetime.now(timezone.utc) - last).total_seconds() <= max(600, 2 * POLL_SEC))
    healthy = state.get("ok") is True and fresh
    if path == "/health":
        return 200, {"ok": True, "analysis_ok": healthy, "status": state.get("status"), "version": VERSION, **SAFETY}
    if path == "/ready":
        return (200 if healthy else 503), {"ok": healthy, "status": state.get("status"), "version": VERSION, **SAFETY}
    if path in ("/state", "/summary", "/audit"):
        public = {k: v for k, v in state.items() if k != "audit_records"}
        if path == "/audit":
            public = {k: state.get(k) for k in ("version", "window_id", "source_sha256", "audit_records")}
            public.update(SAFETY)
        public["ok"] = healthy
        if not healthy: public["status"] = state.get("status") if not state.get("ok") else "STALE_ANALYSIS"
        return (200 if healthy else 503), public
    return 404, {"ok": False, **SAFETY}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None: pass

    def do_GET(self) -> None:
        with LOCK: state = dict(STATE)
        code, obj = response(urlparse(self.path).path, state)
        raw = json.dumps(obj, separators=(",", ":"), sort_keys=True, allow_nan=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)


def assert_integrity() -> None:
    if core.ARM_GAIN != q.ARM_GAIN or core.EXIT_GIVEBACK != q.GIVEBACK or q.ARM_GAIN != .05 or q.GIVEBACK != .04:
        raise RuntimeError("frozen exit constants changed")


def main() -> int:
    assert_integrity()
    print(f"{VERSION} START | code_sha256={code_fingerprint()} | FOUR INDEPENDENT SHADOW LANES | NO ORDERS", flush=True)
    threading.Thread(target=loop, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__": raise SystemExit(main())
