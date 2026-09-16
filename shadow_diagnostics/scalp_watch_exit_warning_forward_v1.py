#!/usr/bin/env python3
"""BTC15 prospective Watch -> Exit warning timing ledger V1.

SHADOW ONLY | SIGNAL ONLY | NO ORDERS | NO AUTO-PROMOTION

Purpose
-------
Measure whether an earlier user-facing Watch warning can meaningfully precede
the already-frozen protected exit without changing that exit lifecycle.

Frozen mechanics
----------------
* +5c executable gain arms protection (unchanged).
* Candidate Watch levels are fixed BEFORE the prospective sample at 1c / 2c /
  3c giveback from the running post-arm peak.
* Protected Exit remains the legacy 4c giveback from peak.
* Watch levels are comparison lanes only. This sample cannot choose one and
  promote it to production; any later selected Watch rule requires a new fresh
  certification window.
* Every calculation uses the executable path already recorded by the scalp
  collector. No settlement/future data is used to trigger Watch or Exit.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

import scalp_economics_exit_cert_v1 as econ
import scalp_economics_forward_v1 as econ_forward
import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_live_review_v1 as source

VERSION = "BTC15_SCALP_WATCH_EXIT_WARNING_FORWARD_V1_FROZEN"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(60, int(os.environ.get("SCALP_WATCH_EXIT_POLL_SEC", "180")))
CUTOFF_TEXT = os.environ.get("SCALP_WATCH_EXIT_CUTOFF_UTC", "").strip()

ARM_GAIN = q.ARM_GAIN
EXIT_GIVEBACK = q.GIVEBACK
WATCH_GIVEBACKS = (0.01, 0.02, 0.03)
MIN_FULL_CONTRACTS = 100
MIN_ARMED_SIGNALS = 50

LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "status": "STARTING",
    "cutoff_utc": CUTOFF_TEXT or None,
    "policy_selection": False,
    "automatic_promotion": False,
    "orders": False,
    "shadow_only": True,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mean(xs: list[float]) -> float | None:
    z = [float(x) for x in xs if math.isfinite(float(x))]
    return None if not z else statistics.fmean(z)


def _median(xs: list[float]) -> float | None:
    z = [float(x) for x in xs if math.isfinite(float(x))]
    return None if not z else statistics.median(z)


def _rate(flags: list[bool]) -> float | None:
    return None if not flags else sum(bool(x) for x in flags) / len(flags)


def executable_timeline(op: Mapping[str, Any]) -> list[tuple[float, float]]:
    """Return elapsed seconds and executable gain (current BID - entry ASK)."""
    cand = op.get("_candidate") or {}
    t0 = q.dt(cand.get("timestamp_utc"))
    out: list[tuple[float, float]] = []
    for r in list(op.get("_paths") or []):
        e = q.elapsed(r, t0)
        g = q.f(r.get("exec_gain"))
        if e is not None and g is not None:
            out.append((float(e), float(g)))
    out.sort(key=lambda x: x[0])
    return out


def measure_watch_exit(op: Mapping[str, Any], watch_giveback: float) -> dict[str, Any]:
    """Replay one path with fixed +5c arm, Watch giveback, and 4c Exit.

    Watch never changes the peak or exit mechanics. A post-Watch new high is
    recorded as recovery/false-alarm evidence but does not erase the warning.
    """
    if watch_giveback <= 0 or watch_giveback >= EXIT_GIVEBACK:
        raise ValueError("Watch giveback must be >0 and < frozen Exit giveback")

    timeline = executable_timeline(op)
    peak = -float("inf")
    armed = False
    arm_time: float | None = None
    watch_time: float | None = None
    watch_gain: float | None = None
    watch_peak: float | None = None
    exit_time: float | None = None
    exit_gain: float | None = None
    recovered_new_high = False
    last_time: float | None = None

    for e, g in timeline:
        last_time = e
        if g > peak:
            peak = g

        if not armed and peak >= ARM_GAIN - 1e-12:
            armed = True
            arm_time = e

        if not armed:
            continue

        # Record the first Watch event. The running peak is the one known at
        # that moment; no future data participates in the trigger.
        if watch_time is None and peak - g >= watch_giveback - 1e-12:
            watch_time = e
            watch_gain = g
            watch_peak = peak

        # A warning can later recover to a new high. This is important false-
        # alarm / early-warning evidence and is reported separately.
        if (
            watch_time is not None
            and e > watch_time + 1e-12
            and watch_peak is not None
            and g > watch_peak + 1e-12
        ):
            recovered_new_high = True

        # Exit remains the legacy frozen +5 arm / 4c giveback rule.
        if peak - g >= EXIT_GIVEBACK - 1e-12:
            exit_time = e
            exit_gain = g
            break

    lead = None if watch_time is None or exit_time is None else max(0.0, exit_time - watch_time)
    warning_without_exit = bool(watch_time is not None and exit_time is None)
    return {
        "armed": armed,
        "arm_time_sec": arm_time,
        "watch_triggered": watch_time is not None,
        "watch_time_sec": watch_time,
        "watch_gain_c": None if watch_gain is None else 100.0 * watch_gain,
        "peak_at_watch_c": None if watch_peak is None else 100.0 * watch_peak,
        "watch_giveback_observed_c": None if watch_gain is None or watch_peak is None else 100.0 * (watch_peak - watch_gain),
        "exit_observed": exit_time is not None,
        "exit_time_sec": exit_time,
        "exit_gain_c": None if exit_gain is None else 100.0 * exit_gain,
        "watch_to_exit_lead_sec": lead,
        "lead_ge_5s": None if lead is None else lead >= 5.0,
        "lead_ge_10s": None if lead is None else lead >= 10.0,
        "lead_ge_15s": None if lead is None else lead >= 15.0,
        "recovered_new_high_after_watch": recovered_new_high,
        "warning_without_exit": warning_without_exit,
        "path_last_time_sec": last_time,
    }


def policy_records(opps: list[dict[str, Any]], watch_giveback: float) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for op in opps:
        m = measure_watch_exit(op, watch_giveback)
        er = econ._op_record(op)
        row: dict[str, Any] = {
            "contract": str(op.get("contract") or ""),
            "candidate_id": str(op.get("candidate_id") or ""),
            "opportunity_index": int(op.get("opportunity_index") or 0),
            "entry_ask": q.f(op.get("entry_ask")),
            "seconds_left": q.f(op.get("seconds_left")),
            "watch_giveback_c": 100.0 * watch_giveback,
            **m,
        }
        fees = er.get("fee_scenarios") or {}
        if row["watch_triggered"] and row["exit_observed"]:
            row["one_lot_taker_taker_net_c"] = (((fees.get("1") or {}).get("TAKER_TAKER") or {}).get("net_gain_c_per_contract"))
            row["ten_lot_taker_taker_net_c"] = (((fees.get("10") or {}).get("TAKER_TAKER") or {}).get("net_gain_c_per_contract"))
        else:
            row["one_lot_taker_taker_net_c"] = None
            row["ten_lot_taker_taker_net_c"] = None
        out.append(row)
    return out


def summarize_policy(rows: list[dict[str, Any]], future_full_contracts: int) -> dict[str, Any]:
    armed = [r for r in rows if r.get("armed")]
    watched = [r for r in rows if r.get("watch_triggered")]
    paired = [r for r in watched if r.get("exit_observed")]
    exits = [r for r in rows if r.get("exit_observed")]
    watch_contracts = {str(r.get("contract") or "") for r in watched if r.get("contract")}
    armed_contracts = {str(r.get("contract") or "") for r in armed if r.get("contract")}

    leads = [float(r["watch_to_exit_lead_sec"]) for r in paired if r.get("watch_to_exit_lead_sec") is not None]
    watch_gain = [float(r["watch_gain_c"]) for r in watched if r.get("watch_gain_c") is not None]
    exit_gain = [float(r["exit_gain_c"]) for r in paired if r.get("exit_gain_c") is not None]
    giveback = [float(r["watch_giveback_observed_c"]) for r in watched if r.get("watch_giveback_observed_c") is not None]
    asks = [float(r["entry_ask"]) for r in rows if r.get("entry_ask") is not None]
    left = [float(r["seconds_left"]) / 60.0 for r in rows if r.get("seconds_left") is not None]
    net1 = [float(r["one_lot_taker_taker_net_c"]) for r in paired if r.get("one_lot_taker_taker_net_c") is not None]
    net10 = [float(r["ten_lot_taker_taker_net_c"]) for r in paired if r.get("ten_lot_taker_taker_net_c") is not None]

    return {
        "signals": len(rows),
        "contracts": len({str(r.get("contract") or "") for r in rows if r.get("contract")}),
        "armed_signals": len(armed),
        "armed_contracts": len(armed_contracts),
        "armed_rate": None if not rows else len(armed) / len(rows),
        "armed_true_future_contract_coverage": None if not future_full_contracts else len(armed_contracts) / future_full_contracts,
        "watch_signals": len(watched),
        "watch_contracts": len(watch_contracts),
        "watch_rate_among_armed": None if not armed else len(watched) / len(armed),
        "watch_true_future_contract_coverage": None if not future_full_contracts else len(watch_contracts) / future_full_contracts,
        "frozen_exit_signals": len(exits),
        "frozen_exit_rate_among_armed": None if not armed else len(exits) / len(armed),
        "watch_preceded_exit_signals": len(paired),
        "watch_preceded_exit_rate": None if not exits else len(paired) / len(exits),
        "avg_watch_to_exit_lead_sec": _mean(leads),
        "median_watch_to_exit_lead_sec": _median(leads),
        "lead_ge_5s_rate": _rate([bool(r.get("lead_ge_5s")) for r in paired if r.get("lead_ge_5s") is not None]),
        "lead_ge_10s_rate": _rate([bool(r.get("lead_ge_10s")) for r in paired if r.get("lead_ge_10s") is not None]),
        "lead_ge_15s_rate": _rate([bool(r.get("lead_ge_15s")) for r in paired if r.get("lead_ge_15s") is not None]),
        "warning_without_exit_rate": _rate([bool(r.get("warning_without_exit")) for r in watched]),
        "recovered_new_high_after_watch_rate": _rate([bool(r.get("recovered_new_high_after_watch")) for r in watched]),
        "avg_gain_at_watch_c": _mean(watch_gain),
        "median_gain_at_watch_c": _median(watch_gain),
        "avg_observed_giveback_at_watch_c": _mean(giveback),
        "avg_gain_at_frozen_exit_c_after_watch": _mean(exit_gain),
        "median_gain_at_frozen_exit_c_after_watch": _median(exit_gain),
        "avg_entry_ask_c": None if not asks else 100.0 * statistics.fmean(asks),
        "entry_le50_rate": None if not asks else sum(x <= 0.50 for x in asks) / len(asks),
        "avg_minutes_left_at_entry": _mean(left),
        "one_lot_taker_taker_avg_net_c_after_watch_exit": _mean(net1),
        "one_lot_taker_taker_median_net_c_after_watch_exit": _median(net1),
        "one_lot_taker_taker_positive_net_rate_after_watch_exit": _rate([x > 0 for x in net1]),
        "ten_lot_taker_taker_avg_net_c_after_watch_exit": _mean(net10),
        "ten_lot_taker_taker_median_net_c_after_watch_exit": _median(net10),
        "ten_lot_taker_taker_positive_net_rate_after_watch_exit": _rate([x > 0 for x in net10]),
    }


def summarize_by_index(rows: list[dict[str, Any]], future_full_contracts: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for idx in sorted({int(r.get("opportunity_index") or 0) for r in rows}):
        out[str(idx)] = summarize_policy([r for r in rows if int(r.get("opportunity_index") or 0) == idx], future_full_contracts)
    return out


def frozen_rules() -> dict[str, Any]:
    return {
        "arm_gain_c": 100.0 * ARM_GAIN,
        "watch_giveback_candidates_c": [100.0 * x for x in WATCH_GIVEBACKS],
        "exit_giveback_c": 100.0 * EXIT_GIVEBACK,
        "watch_does_not_change_exit": True,
        "watch_policy_selection": False,
        "same_sample_promotion": False,
        "selected_watch_rule_requires_later_fresh_certification_window": True,
        "automatic_promotion": False,
        "orders": False,
    }


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0,
                 cutoff_text: str | None = None) -> dict[str, Any]:
    text = CUTOFF_TEXT if cutoff_text is None else cutoff_text
    cutoff = econ_forward.parse_cutoff(text)
    if cutoff is None:
        return {
            "ok": False,
            "version": VERSION,
            "status": "FAIL_CLOSED_MISSING_OR_INVALID_CUTOFF",
            "cutoff_utc": text or None,
            "source_sha256": sha,
            "source_rows": len(rows),
            "policy_selection": False,
            "automatic_promotion": False,
            "orders": False,
        }

    contracts, adapted = econ_forward.future_universe(rows, cutoff)
    opps = [op for op in q.build_serial_opportunities(adapted) if str(op.get("contract") or "") in contracts]

    policies: dict[str, Any] = {}
    policy_rows: dict[str, list[dict[str, Any]]] = {}
    for watch in WATCH_GIVEBACKS:
        key = f"WATCH_{int(round(100 * watch))}C"
        z = policy_records(opps, watch)
        policy_rows[key] = z
        policies[key] = {
            "watch_giveback_c": 100.0 * watch,
            "overall": summarize_policy(z, len(contracts)),
            "by_opportunity_index": summarize_by_index(z, len(contracts)),
        }

    # Armed count is policy-invariant because Watch never changes the arm.
    first_rows = next(iter(policy_rows.values()), [])
    armed_n = sum(bool(r.get("armed")) for r in first_rows)
    sample_ready = len(contracts) >= MIN_FULL_CONTRACTS and armed_n >= MIN_ARMED_SIGNALS
    status = "READY_FOR_MANUAL_WATCH_EXIT_REVIEW" if sample_ready else "COLLECTING_FUTURE_WATCH_EXIT_V1"

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
        "serial_signals": len(opps),
        "armed_signals": armed_n,
        "evidence_readiness": {
            "sample_ready": sample_ready,
            "observed_future_full_contracts": len(contracts),
            "required_future_full_contracts": MIN_FULL_CONTRACTS,
            "observed_armed_signals": armed_n,
            "required_armed_signals": MIN_ARMED_SIGNALS,
            "readiness_is_not_policy_selection_or_promotion": True,
        },
        "frozen_rules": frozen_rules(),
        "policies": policies,
        "policy_selection": False,
        "same_sample_promotion": False,
        "manual_execution_only": True,
        "production_logic_changed": False,
        "shadow_only": True,
        "automatic_promotion": False,
        "orders": False,
    }
    print("SCALP_WATCH_EXIT_FORWARD | " + json.dumps(compact(result), separators=(",", ":"), sort_keys=True, default=str), flush=True)
    return result


def compact(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": state.get("status"),
        "cutoff_utc": state.get("cutoff_utc"),
        "future_full_contracts": state.get("future_full_contracts"),
        "serial_signals": state.get("serial_signals"),
        "armed_signals": state.get("armed_signals"),
        "evidence_readiness": state.get("evidence_readiness"),
        "frozen_rules": frozen_rules(),
        "policies": state.get("policies"),
        "policy_selection": False,
        "same_sample_promotion": False,
        "automatic_promotion": False,
        "orders": False,
    }


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
                    "status": "FAIL_CLOSED_WATCH_EXIT_FORWARD_ERROR",
                    "last_poll_utc": utcnow(),
                    "error": f"{type(exc).__name__}:{exc}",
                    "policy_selection": False,
                    "automatic_promotion": False,
                    "orders": False,
                    "shadow_only": True,
                })
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15WatchExitForwardV1/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_WATCH_EXIT_FORWARD_HTTP | request", flush=True)

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
            return self.send_json(200, {"ok": True, "analysis_ok": state.get("ok") is True,
                                        "status": state.get("status"), "cutoff_utc": state.get("cutoff_utc"),
                                        "orders": False, "version": VERSION})
        if path == "/summary":
            return self.send_json(200, compact(state))
        if path == "/state":
            return self.send_json(200, state)
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def assert_integrity() -> None:
    if abs(ARM_GAIN - 0.05) > 1e-12:
        raise RuntimeError("frozen +5c protection arm drifted")
    if abs(EXIT_GIVEBACK - 0.04) > 1e-12:
        raise RuntimeError("frozen 4c protected exit drifted")
    if WATCH_GIVEBACKS != (0.01, 0.02, 0.03):
        raise RuntimeError("Watch comparison lanes drifted")
    if any(x <= 0 or x >= EXIT_GIVEBACK for x in WATCH_GIVEBACKS):
        raise RuntimeError("invalid Watch giveback ordering")


def main() -> int:
    assert_integrity()
    print(f"{VERSION} START | cutoff={CUTOFF_TEXT or 'MISSING'} | +5c ARM | WATCH 1/2/3c GIVEBACK | EXIT 4c GIVEBACK | NO POLICY SELECTION | NO ORDERS", flush=True)
    threading.Thread(target=loop, name="watch-exit-forward-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


assert_integrity()

if __name__ == "__main__":
    raise SystemExit(main())
