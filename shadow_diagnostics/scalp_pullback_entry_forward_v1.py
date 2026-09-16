#!/usr/bin/env python3
"""BTC15 prospective pullback-entry window study V1.

SHADOW ONLY | SIGNAL ONLY | DEVELOPMENT COMPARISON | NO ORDERS

Compares the unchanged immediate serial opportunities with fixed absolute-price
pullback lanes.  A pullback lane enters only at the first THEN-current
executable ASK at or below its frozen target within its frozen wait window.
Only executable BID observations at/after that actual entry may score movement
or the +5c arm / 4c giveback protected exit.

This first future sample cannot select or promote a pullback rule. Any later
selected rule requires a new prospective certification window.
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

VERSION = "BTC15_SCALP_PULLBACK_ENTRY_FORWARD_V1_FROZEN_LANES"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(60, int(os.environ.get("SCALP_PULLBACK_FORWARD_POLL_SEC", "180")))
CUTOFF_TEXT = os.environ.get("SCALP_PULLBACK_FORWARD_CUTOFF_UTC", "").strip()

TARGETS = (0.50, 0.40, 0.35)
WINDOWS_SEC = (30.0, 60.0)
ARM_GAIN = q.ARM_GAIN
EXIT_GIVEBACK = q.GIVEBACK
MIN_FULL_CONTRACTS = 100
MIN_IMMEDIATE_SIGNALS = 100

LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "status": "STARTING",
    "cutoff_utc": CUTOFF_TEXT or None,
    "lane_selection": False,
    "same_sample_promotion": False,
    "automatic_promotion": False,
    "orders": False,
    "shadow_only": True,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def f(v: Any) -> float | None:
    x = q.f(v)
    return x if x is not None and math.isfinite(float(x)) else None


def mean(xs: list[float]) -> float | None:
    return None if not xs else statistics.fmean(xs)


def median(xs: list[float]) -> float | None:
    return None if not xs else statistics.median(xs)


def rate(flags: list[bool]) -> float | None:
    return None if not flags else sum(bool(x) for x in flags) / len(flags)


def candidate_time(op: Mapping[str, Any]) -> datetime:
    cand = op.get("_candidate") or {}
    return q.dt(cand.get("timestamp_utc"))


def ask_timeline(op: Mapping[str, Any]) -> list[tuple[float, float, Mapping[str, Any] | None]]:
    """Candidate ASK at t=0 plus actual PATH current ASK observations."""
    out: list[tuple[float, float, Mapping[str, Any] | None]] = []
    initial = f(op.get("entry_ask"))
    if initial is not None:
        out.append((0.0, initial, None))
    t0 = candidate_time(op)
    for r in list(op.get("_paths") or []):
        e = q.elapsed(r, t0)
        ask = f(r.get("current_ask"))
        if e is not None and ask is not None:
            out.append((float(e), ask, r))
    out.sort(key=lambda x: x[0])
    return out


def first_pullback_entry(op: Mapping[str, Any], target: float, window_sec: float) -> dict[str, Any] | None:
    """First executable ASK <= frozen target within the frozen wait window."""
    if target not in TARGETS or window_sec not in WINDOWS_SEC:
        raise ValueError("unfrozen pullback lane")
    for elapsed, ask, row in ask_timeline(op):
        if elapsed > window_sec + 1e-12:
            break
        if ask <= target + 1e-12:
            return {"entry_elapsed_sec": elapsed, "entry_ask": ask, "entry_row": row}
    return None


def bid_timeline_after(op: Mapping[str, Any], entry_elapsed: float, entry_ask: float) -> list[tuple[float, float]]:
    """Executable gain from actual pullback ASK using only subsequent BIDs."""
    t0 = candidate_time(op)
    out: list[tuple[float, float]] = []
    for r in list(op.get("_paths") or []):
        e = q.elapsed(r, t0)
        bid = f(r.get("current_bid"))
        if e is not None and bid is not None and float(e) + 1e-12 >= entry_elapsed:
            out.append((float(e), bid - entry_ask))
    out.sort(key=lambda x: x[0])
    return out


def replay_from_pullback(op: Mapping[str, Any], target: float, window_sec: float) -> dict[str, Any] | None:
    entry = first_pullback_entry(op, target, window_sec)
    if entry is None:
        return None

    candidate_ask = f(op.get("entry_ask"))
    entry_elapsed = float(entry["entry_elapsed_sec"])
    entry_ask = float(entry["entry_ask"])
    future = bid_timeline_after(op, entry_elapsed, entry_ask)
    left0 = f(op.get("seconds_left"))

    rec: dict[str, Any] = {
        "contract": str(op.get("contract") or ""),
        "candidate_id": str(op.get("candidate_id") or ""),
        "opportunity_index": int(op.get("opportunity_index") or 0),
        "target_ask_c": 100.0 * target,
        "window_sec": window_sec,
        "candidate_ask": candidate_ask,
        "entry_ask": entry_ask,
        "entry_elapsed_sec": entry_elapsed,
        "entry_improvement_c_vs_candidate": None if candidate_ask is None else 100.0 * (candidate_ask - entry_ask),
        "qualified_immediately": entry_elapsed <= 1e-12,
        "post_candidate_price_improvement": bool(candidate_ask is not None and entry_elapsed > 1e-12 and entry_ask < candidate_ask - 1e-12),
        "seconds_left_at_entry": None if left0 is None else max(0.0, left0 - entry_elapsed),
        "movement_scoreable": bool(future),
        "plus5": None,
        "plus10": None,
        "plus20": None,
        "peak_gain": None,
        "adverse_gain": None,
        "protected_exit_observed": False,
        "protected_exit_gain": None,
        "protected_exit_elapsed_sec": None,
        "one_lot_taker_taker_net_c": None,
        "ten_lot_taker_taker_net_c": None,
    }
    if not future:
        return rec

    gains = [g for _, g in future]
    peak_gain = max(gains)
    rec["peak_gain"] = peak_gain
    rec["adverse_gain"] = min(gains)
    rec["plus5"] = int(peak_gain >= 0.05 - 1e-12)
    rec["plus10"] = int(peak_gain >= 0.10 - 1e-12)
    rec["plus20"] = int(peak_gain >= 0.20 - 1e-12)

    peak = -float("inf")
    armed = False
    for elapsed, gain in future:
        peak = max(peak, gain)
        armed = armed or peak >= ARM_GAIN - 1e-12
        if armed and peak - gain >= EXIT_GIVEBACK - 1e-12:
            rec["protected_exit_observed"] = True
            rec["protected_exit_gain"] = gain
            rec["protected_exit_elapsed_sec"] = elapsed
            exit_bid = entry_ask + gain
            one = econ.fee_adjusted_per_contract(entry_ask, exit_bid, 1)
            ten = econ.fee_adjusted_per_contract(entry_ask, exit_bid, 10)
            rec["one_lot_taker_taker_net_c"] = 100.0 * one["net_gain_dollars_per_contract"]
            rec["ten_lot_taker_taker_net_c"] = 100.0 * ten["net_gain_dollars_per_contract"]
            break
    return rec


def immediate_record(op: Mapping[str, Any]) -> dict[str, Any]:
    er = econ._op_record(op)
    fees = er.get("fee_scenarios") or {}
    return {
        "contract": str(op.get("contract") or ""),
        "candidate_id": str(op.get("candidate_id") or ""),
        "opportunity_index": int(op.get("opportunity_index") or 0),
        "entry_ask": f(op.get("entry_ask")),
        "entry_elapsed_sec": 0.0,
        "seconds_left_at_entry": f(op.get("seconds_left")),
        "plus5": int(bool(op.get("plus5"))),
        "plus10": int(bool(op.get("plus10"))),
        "plus20": int(bool(op.get("plus20"))),
        "protected_exit_observed": bool(er.get("protected_exit_observed")),
        "protected_exit_gain": f(op.get("protected_exit_gain")),
        "one_lot_taker_taker_net_c": (((fees.get("1") or {}).get("TAKER_TAKER") or {}).get("net_gain_c_per_contract")),
        "ten_lot_taker_taker_net_c": (((fees.get("10") or {}).get("TAKER_TAKER") or {}).get("net_gain_c_per_contract")),
    }


def summarize_immediate(rows: list[dict[str, Any]], full_contracts: int) -> dict[str, Any]:
    n = len(rows)
    contracts = {str(r.get("contract") or "") for r in rows if r.get("contract")}
    asks = [float(r["entry_ask"]) for r in rows if r.get("entry_ask") is not None]
    left = [float(r["seconds_left_at_entry"]) / 60.0 for r in rows if r.get("seconds_left_at_entry") is not None]
    exits = [r for r in rows if r.get("protected_exit_observed")]
    net1 = [float(r["one_lot_taker_taker_net_c"]) for r in exits if r.get("one_lot_taker_taker_net_c") is not None]
    net10 = [float(r["ten_lot_taker_taker_net_c"]) for r in exits if r.get("ten_lot_taker_taker_net_c") is not None]
    return {
        "signals": n,
        "contracts": len(contracts),
        "true_future_contract_coverage": None if not full_contracts else len(contracts) / full_contracts,
        "avg_entry_ask_c": None if not asks else 100.0 * mean(asks),
        "median_entry_ask_c": None if not asks else 100.0 * median(asks),
        "entry_le50_rate": None if not asks else sum(x <= .50 for x in asks) / len(asks),
        "entry_ideal_25_35_rate": None if not asks else sum(.25 <= x <= .35 for x in asks) / len(asks),
        "avg_minutes_left": mean(left),
        "plus5_rate": None if not n else sum(int(r.get("plus5") or 0) for r in rows) / n,
        "plus10_rate": None if not n else sum(int(r.get("plus10") or 0) for r in rows) / n,
        "plus20_rate": None if not n else sum(int(r.get("plus20") or 0) for r in rows) / n,
        "protected_exit_rate": None if not n else len(exits) / n,
        "protected_exit_signals": len(exits),
        "one_lot_taker_taker_avg_net_c": mean(net1),
        "one_lot_taker_taker_median_net_c": median(net1),
        "one_lot_taker_taker_positive_net_rate": rate([x > 0 for x in net1]),
        "ten_lot_taker_taker_avg_net_c": mean(net10),
        "ten_lot_taker_taker_median_net_c": median(net10),
        "ten_lot_taker_taker_positive_net_rate": rate([x > 0 for x in net10]),
        "max_opportunity_index": max((int(r.get("opportunity_index") or 0) for r in rows), default=0),
    }


def summarize_pullback(rows: list[dict[str, Any]], immediate_signals: int,
                       immediate_contracts: int, full_contracts: int) -> dict[str, Any]:
    n = len(rows)
    contracts = {str(r.get("contract") or "") for r in rows if r.get("contract")}
    scoreable = [r for r in rows if r.get("movement_scoreable")]
    exits = [r for r in scoreable if r.get("protected_exit_observed")]
    asks = [float(r["entry_ask"]) for r in rows if r.get("entry_ask") is not None]
    delays = [float(r["entry_elapsed_sec"]) for r in rows]
    improvements = [float(r["entry_improvement_c_vs_candidate"]) for r in rows if r.get("entry_improvement_c_vs_candidate") is not None]
    left = [float(r["seconds_left_at_entry"]) / 60.0 for r in rows if r.get("seconds_left_at_entry") is not None]
    net1 = [float(r["one_lot_taker_taker_net_c"]) for r in exits if r.get("one_lot_taker_taker_net_c") is not None]
    net10 = [float(r["ten_lot_taker_taker_net_c"]) for r in exits if r.get("ten_lot_taker_taker_net_c") is not None]
    return {
        "qualifying_entries": n,
        "contracts": len(contracts),
        "signal_retention_vs_immediate": None if not immediate_signals else n / immediate_signals,
        "contract_retention_vs_immediate": None if not immediate_contracts else len(contracts) / immediate_contracts,
        "true_future_contract_coverage": None if not full_contracts else len(contracts) / full_contracts,
        "unqualified_immediate_signals": max(0, immediate_signals - n),
        "qualified_immediately": sum(bool(r.get("qualified_immediately")) for r in rows),
        "qualified_immediately_rate": None if not n else sum(bool(r.get("qualified_immediately")) for r in rows) / n,
        "post_candidate_price_improvement_entries": sum(bool(r.get("post_candidate_price_improvement")) for r in rows),
        "post_candidate_price_improvement_rate": None if not n else sum(bool(r.get("post_candidate_price_improvement")) for r in rows) / n,
        "avg_entry_delay_sec": mean(delays),
        "median_entry_delay_sec": median(delays),
        "avg_entry_ask_c": None if not asks else 100.0 * mean(asks),
        "median_entry_ask_c": None if not asks else 100.0 * median(asks),
        "avg_entry_improvement_c_vs_candidate": mean(improvements),
        "median_entry_improvement_c_vs_candidate": median(improvements),
        "entry_le50_rate": None if not asks else sum(x <= .50 for x in asks) / len(asks),
        "entry_ideal_25_35_rate": None if not asks else sum(.25 <= x <= .35 for x in asks) / len(asks),
        "avg_minutes_left": mean(left),
        "movement_scoreable_entries": len(scoreable),
        "plus5_rate": None if not scoreable else sum(int(r.get("plus5") or 0) for r in scoreable) / len(scoreable),
        "plus10_rate": None if not scoreable else sum(int(r.get("plus10") or 0) for r in scoreable) / len(scoreable),
        "plus20_rate": None if not scoreable else sum(int(r.get("plus20") or 0) for r in scoreable) / len(scoreable),
        "protected_exit_rate": None if not scoreable else len(exits) / len(scoreable),
        "protected_exit_signals": len(exits),
        "one_lot_taker_taker_avg_net_c": mean(net1),
        "one_lot_taker_taker_median_net_c": median(net1),
        "one_lot_taker_taker_positive_net_rate": rate([x > 0 for x in net1]),
        "ten_lot_taker_taker_avg_net_c": mean(net10),
        "ten_lot_taker_taker_median_net_c": median(net10),
        "ten_lot_taker_taker_positive_net_rate": rate([x > 0 for x in net10]),
        "max_opportunity_index": max((int(r.get("opportunity_index") or 0) for r in rows), default=0),
    }


def by_index_pullback(rows: list[dict[str, Any]], immediate: list[dict[str, Any]], full_contracts: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for idx in sorted({int(r.get("opportunity_index") or 0) for r in immediate}):
        imm = [r for r in immediate if int(r.get("opportunity_index") or 0) == idx]
        z = [r for r in rows if int(r.get("opportunity_index") or 0) == idx]
        out[str(idx)] = summarize_pullback(z, len(imm), len({r["contract"] for r in imm}), full_contracts)
    return out


def lane_key(target: float, window_sec: float) -> str:
    return f"LE{int(round(100 * target))}C_WITHIN_{int(window_sec)}S"


def frozen_rules() -> dict[str, Any]:
    return {
        "absolute_ask_targets_c": [100.0 * x for x in TARGETS],
        "wait_windows_sec": list(WINDOWS_SEC),
        "actual_entry_is_first_then_current_ask_at_or_below_target": True,
        "pre_entry_movement_is_discarded": True,
        "post_entry_scoring_uses_subsequent_executable_bid": True,
        "protection_rebased_from_actual_pullback_entry": True,
        "arm_gain_c": 100.0 * ARM_GAIN,
        "exit_giveback_c": 100.0 * EXIT_GIVEBACK,
        "serial_opportunity_set_is_frozen_immediate_lifecycle": True,
        "lane_selection": False,
        "same_sample_promotion": False,
        "selected_rule_requires_new_fresh_certification_window": True,
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
            "lane_selection": False,
            "same_sample_promotion": False,
            "automatic_promotion": False,
            "orders": False,
        }

    contracts, adapted = econ_forward.future_universe(rows, cutoff)
    opps = [op for op in q.build_serial_opportunities(adapted) if str(op.get("contract") or "") in contracts]
    immediate = [immediate_record(op) for op in opps]
    imm_contracts = len({r["contract"] for r in immediate})

    lanes: dict[str, Any] = {}
    for target in TARGETS:
        for window in WINDOWS_SEC:
            key = lane_key(target, window)
            z = [x for op in opps if (x := replay_from_pullback(op, target, window)) is not None]
            lanes[key] = {
                "target_ask_c": 100.0 * target,
                "window_sec": window,
                "overall": summarize_pullback(z, len(immediate), imm_contracts, len(contracts)),
                "by_opportunity_index": by_index_pullback(z, immediate, len(contracts)),
            }

    sample_ready = len(contracts) >= MIN_FULL_CONTRACTS and len(immediate) >= MIN_IMMEDIATE_SIGNALS
    result = {
        "ok": True,
        "version": VERSION,
        "status": "READY_FOR_MANUAL_PULLBACK_DEVELOPMENT_REVIEW" if sample_ready else "COLLECTING_FUTURE_PULLBACK_ENTRY_V1",
        "updated_utc": utcnow(),
        "cutoff_utc": cutoff.isoformat(),
        "source_sha256": sha,
        "source_bytes": source_bytes,
        "source_rows": len(rows),
        "future_full_contracts": len(contracts),
        "immediate": summarize_immediate(immediate, len(contracts)),
        "lanes": lanes,
        "evidence_readiness": {
            "sample_ready": sample_ready,
            "observed_future_full_contracts": len(contracts),
            "required_future_full_contracts": MIN_FULL_CONTRACTS,
            "observed_immediate_signals": len(immediate),
            "required_immediate_signals": MIN_IMMEDIATE_SIGNALS,
            "readiness_is_development_comparison_only": True,
            "selected_rule_requires_new_fresh_certification_window": True,
        },
        "frozen_rules": frozen_rules(),
        "lane_selection": False,
        "same_sample_promotion": False,
        "manual_execution_only": True,
        "production_logic_changed": False,
        "shadow_only": True,
        "automatic_promotion": False,
        "orders": False,
    }
    print("SCALP_PULLBACK_FORWARD | " + json.dumps(compact(result), separators=(",", ":"), sort_keys=True, default=str), flush=True)
    return result


def compact(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": state.get("status"),
        "cutoff_utc": state.get("cutoff_utc"),
        "future_full_contracts": state.get("future_full_contracts"),
        "immediate": state.get("immediate"),
        "lanes": state.get("lanes"),
        "evidence_readiness": state.get("evidence_readiness"),
        "frozen_rules": frozen_rules(),
        "lane_selection": False,
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
                    "status": "FAIL_CLOSED_PULLBACK_FORWARD_ERROR",
                    "last_poll_utc": utcnow(),
                    "error": f"{type(exc).__name__}:{exc}",
                    "lane_selection": False,
                    "same_sample_promotion": False,
                    "automatic_promotion": False,
                    "orders": False,
                    "shadow_only": True,
                })
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15PullbackForwardV1/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_PULLBACK_FORWARD_HTTP | request", flush=True)

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
    if TARGETS != (0.50, 0.40, 0.35):
        raise RuntimeError("pullback ASK targets drifted")
    if WINDOWS_SEC != (30.0, 60.0):
        raise RuntimeError("pullback windows drifted")
    if ARM_GAIN != 0.05 or EXIT_GIVEBACK != 0.04:
        raise RuntimeError("frozen protection lifecycle drifted")


def main() -> int:
    assert_integrity()
    print(f"{VERSION} START | cutoff={CUTOFF_TEXT or 'MISSING'} | ASK TARGETS <=50/40/35c | WINDOWS 30/60s | ACTUAL ASK -> SUBSEQUENT BID | DEVELOPMENT ONLY | NO ORDERS", flush=True)
    threading.Thread(target=loop, name="pullback-forward-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


assert_integrity()

if __name__ == "__main__":
    raise SystemExit(main())
