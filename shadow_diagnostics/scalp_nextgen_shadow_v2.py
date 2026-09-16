#!/usr/bin/env python3
"""Combined BTC15 next-generation shadow experiment V2.

One read-only service, four independently scored lanes:
1) SCALP-2 economics filters; 2) causal Candidate->Verify;
3) earlier Watch->Exit; 4) selective pullback entry.

SHADOW ONLY | SIGNAL ONLY | NO ORDERS | NO AUTO/SAME-SAMPLE PROMOTION
The frozen V1 collectors and the frozen +5c arm / 4c exit remain controls.
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

import scalp_candidate_verify_forward_v1 as verify_v1
import scalp_economics_exit_cert_v1 as econ
import scalp_economics_forward_v1 as econ_v1
import scalp_opportunity_quality_frontier_v1 as q
import scalp_pullback_entry_forward_v1 as pullback_v1
import scalp_specialist_union_live_review_v1 as source

VERSION = "BTC15_SCALP_NEXTGEN_SHADOW_V2_FROZEN"
DEFAULT_CUTOFF_UTC = "2026-09-16T19:50:00+00:00"
CUTOFF_TEXT = os.environ.get("SCALP_NEXTGEN_V2_CUTOFF_UTC", DEFAULT_CUTOFF_UTC).strip()
POLL_SEC = max(60, int(os.environ.get("SCALP_NEXTGEN_V2_POLL_SEC", "180")))
PORT = int(os.environ.get("PORT", "8080"))
MIN_FULL_CONTRACTS = 100
MIN_SIGNALS = 100
ARM_GAIN = 0.05
EXIT_GIVEBACK = 0.04
LOCK = threading.Lock()
STATE: dict[str, Any] = {"ok": False, "version": VERSION, "status": "STARTING", "orders": False}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def f(v: Any) -> float | None:
    x = q.f(v)
    return x if x is not None and math.isfinite(float(x)) else None


def truth(v: Any) -> bool:
    return q.b(v) == 1


def mean(xs: list[float]) -> float | None:
    return None if not xs else statistics.fmean(xs)


def rate(xs: list[bool]) -> float | None:
    return None if not xs else sum(xs) / len(xs)


def strong_candidate(op: Mapping[str, Any]) -> bool:
    """Frozen candidate-time strong-evidence definition; no path labels."""
    c = op.get("_candidate") or {}
    confirm = f(c.get("confirm_count")) or 0.0
    b5 = f(op.get("btc_move5_norm"))
    b15 = f(op.get("btc_move15_norm"))
    brti = str(c.get("brti_status") or "").upper() == "PRIMARY_OK"
    safe = not any(truth(c.get(k)) for k in (
        "btc_against_side", "brti_against_side", "dual_reversal_evidence"
    ))
    return bool(confirm >= 2 and truth(c.get("structure_ok")) and brti and safe
                and b5 is not None and b5 >= 0.60 and b15 is not None and b15 >= 0.50)


def path_timeline(op: Mapping[str, Any]) -> list[tuple[float, Mapping[str, Any]]]:
    c = op.get("_candidate") or {}
    t0 = q.dt(c.get("timestamp_utc"))
    out = []
    for row in list(op.get("_paths") or []):
        e = q.elapsed(row, t0)
        if e is not None:
            out.append((float(e), row))
    return sorted(out, key=lambda z: z[0])


def dynamic_verify_record(op: Mapping[str, Any]) -> dict[str, Any] | None:
    """Immediate if strong; otherwise confirm causal executable follow-through.

    Confirmation is event-based: two consecutive non-negative executable-gain
    observations, with at least one >= +1c, while the current ASK has not chased
    more than 3c above the candidate ASK. Maximum observation horizon is 30s.
    """
    if strong_candidate(op):
        rec = verify_v1.immediate_record(op)
        rec.update({"verify_mode": "IMMEDIATE_STRONG", "confirmation_events": 0})
        return rec
    entry0 = f(op.get("entry_ask"))
    if entry0 is None:
        return None
    streak = 0
    saw_plus1 = False
    for elapsed, row in path_timeline(op):
        if elapsed > 30.0:
            break
        gain = f(row.get("exec_gain"))
        ask = f(row.get("current_ask"))
        if gain is None or ask is None:
            continue
        if gain >= 0:
            streak += 1
            saw_plus1 = saw_plus1 or gain >= 0.01
        else:
            streak = 0
            saw_plus1 = False
        if streak >= 2 and saw_plus1 and ask <= entry0 + 0.03 + 1e-12:
            rec = verify_v1.delayed_record(op, elapsed)
            if rec is not None:
                rec.update({"verify_mode": "EVENT_CONFIRMED", "confirmation_events": streak})
            return rec
    return None


def econ_summary(records: list[dict[str, Any]], base_n: int, full_n: int) -> dict[str, Any]:
    n = len(records)
    exits = [r for r in records if r.get("protected_exit_observed")]
    contracts = {str(r.get("contract") or "") for r in records if r.get("contract")}
    asks = [float(r["entry_ask"]) for r in records if f(r.get("entry_ask")) is not None]
    gross = [float(r["gross_protected_gain_c"]) for r in exits if f(r.get("gross_protected_gain_c")) is not None]
    net1, net10 = [], []
    for r in exits:
        fs = r.get("fee_scenarios") or {}
        a = (((fs.get("1") or {}).get("TAKER_TAKER") or {}).get("net_gain_c_per_contract"))
        b = (((fs.get("10") or {}).get("TAKER_TAKER") or {}).get("net_gain_c_per_contract"))
        if f(a) is not None: net1.append(float(a))
        if f(b) is not None: net10.append(float(b))
    return {
        "signals": n, "contracts": len(contracts),
        "signal_retention_vs_control": None if not base_n else n / base_n,
        "true_contract_coverage": None if not full_n else len(contracts) / full_n,
        "avg_entry_ask_c": None if not asks else 100 * mean(asks),
        "entry_le50_rate": rate([x <= .50 for x in asks]),
        "plus5_rate": rate([bool(r.get("plus5")) for r in records]),
        "plus10_rate": rate([bool(r.get("plus10")) for r in records]),
        "protected_exit_rate": None if not n else len(exits) / n,
        "avg_gross_protected_gain_c": mean(gross),
        "one_lot_taker_taker_avg_net_c": mean(net1),
        "ten_lot_taker_taker_avg_net_c": mean(net10),
    }


def scalp2_lanes(opps: list[dict[str, Any]], full_n: int) -> dict[str, Any]:
    base_ops = [op for op in opps if int(op.get("opportunity_index") or 0) == 2]
    base = [econ._op_record(op) for op in base_ops]
    filters = {
        "CONTROL_V1_SCALP2": lambda op: True,
        "AFFORDABLE_LE50": lambda op: (f(op.get("entry_ask")) or 9) <= .50,
        "EARLY_AFFORDABLE": lambda op: (f(op.get("entry_ask")) or 9) <= .50 and (f(op.get("seconds_left")) or 0) >= 360,
        "STRONG_AFFORDABLE": lambda op: (f(op.get("entry_ask")) or 9) <= .50 and strong_candidate(op),
    }
    return {name: econ_summary([econ._op_record(op) for op in base_ops if pred(op)], len(base), full_n)
            for name, pred in filters.items()}


def verify_lanes(opps: list[dict[str, Any]], full_n: int) -> dict[str, Any]:
    base_n = len(opps)
    out = {}
    for delay in verify_v1.VERIFY_DELAYS_SEC:
        recs, unavailable = verify_v1.build_policy_records(opps, delay)
        x = econ_summary(recs, base_n, full_n); x["unavailable_entries"] = unavailable
        out["V1_IMMEDIATE" if delay == 0 else f"V1_FIXED_{int(delay)}S"] = x
    dyn = [x for op in opps if (x := dynamic_verify_record(op)) is not None]
    out["V2_DYNAMIC_CAUSAL"] = econ_summary(dyn, base_n, full_n)
    out["V2_DYNAMIC_CAUSAL"]["immediate_strong"] = sum(r.get("verify_mode") == "IMMEDIATE_STRONG" for r in dyn)
    out["V2_DYNAMIC_CAUSAL"]["event_confirmed"] = sum(r.get("verify_mode") == "EVENT_CONFIRMED" for r in dyn)
    return out


def watch_measure(op: Mapping[str, Any], mode: str) -> dict[str, Any]:
    """Earlier V2 Watch; frozen Exit remains exactly 4c giveback."""
    points = [(e, f(r.get("exec_gain"))) for e, r in path_timeline(op)]
    points = [(e, g) for e, g in points if g is not None]
    peak = -float("inf"); armed = False; warning = None; exit_at = None
    prior: tuple[float, float] | None = None; small_giveback_streak = 0
    for elapsed, gain in points:
        peak = max(peak, float(gain))
        armed = armed or peak >= ARM_GAIN - 1e-12
        if not armed:
            prior = (elapsed, float(gain)); continue
        giveback = peak - float(gain)
        if mode == "V1_1C": trigger = giveback >= .01 - 1e-12
        elif mode == "V2_CONFIRMED_HALF_C":
            small_giveback_streak = small_giveback_streak + 1 if giveback >= .005 - 1e-12 else 0
            trigger = small_giveback_streak >= 2
        elif mode == "V2_VELOCITY_OR_1C":
            velocity_drop = bool(prior and elapsed - prior[0] <= 5.0 and prior[1] - float(gain) >= .01 - 1e-12)
            trigger = giveback >= .01 - 1e-12 or velocity_drop
        else: raise ValueError("unknown watch mode")
        if warning is None and trigger: warning = elapsed
        if giveback >= EXIT_GIVEBACK - 1e-12:
            exit_at = elapsed; break
        prior = (elapsed, float(gain))
    return {"armed": armed, "warning": warning is not None, "exit": exit_at is not None,
            "lead": None if warning is None or exit_at is None else max(0.0, exit_at - warning),
            "warning_without_exit": warning is not None and exit_at is None}


def watch_lanes(opps: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for mode in ("V1_1C", "V2_CONFIRMED_HALF_C", "V2_VELOCITY_OR_1C"):
        rows = []
        for op in opps:
            row = watch_measure(op, mode)
            er = econ._op_record(op)
            fees = er.get("fee_scenarios") or {}
            row["gross_protected_gain_c"] = er.get("gross_protected_gain_c") if row["exit"] else None
            row["one_lot_taker_taker_net_c"] = (
                (((fees.get("1") or {}).get("TAKER_TAKER") or {}).get("net_gain_c_per_contract"))
                if row["exit"] else None
            )
            row["ten_lot_taker_taker_net_c"] = (
                (((fees.get("10") or {}).get("TAKER_TAKER") or {}).get("net_gain_c_per_contract"))
                if row["exit"] else None
            )
            rows.append(row)
        watched = [r for r in rows if r["warning"]]
        paired = [r for r in watched if r["exit"]]
        leads = [float(r["lead"]) for r in paired if r["lead"] is not None]
        gross = [float(r["gross_protected_gain_c"]) for r in paired if f(r.get("gross_protected_gain_c")) is not None]
        net1 = [float(r["one_lot_taker_taker_net_c"]) for r in paired if f(r.get("one_lot_taker_taker_net_c")) is not None]
        net10 = [float(r["ten_lot_taker_taker_net_c"]) for r in paired if f(r.get("ten_lot_taker_taker_net_c")) is not None]
        out[mode] = {
            "signals": len(rows), "armed_signals": sum(r["armed"] for r in rows),
            "warning_signals": len(watched), "frozen_exit_signals": sum(r["exit"] for r in rows),
            "avg_warning_to_exit_lead_sec": mean(leads),
            "lead_ge5_rate": rate([x >= 5 for x in leads]),
            "false_warning_rate": rate([r["warning_without_exit"] for r in watched]),
            "avg_gross_protected_gain_c": mean(gross),
            "one_lot_taker_taker_avg_net_c": mean(net1),
            "ten_lot_taker_taker_avg_net_c": mean(net10),
            "exit_rule_unchanged": True,
        }
    return out


def selective_pullback_record(op: Mapping[str, Any], lane: str) -> dict[str, Any] | None:
    ask = f(op.get("entry_ask"))
    if ask is None: return None
    strong = strong_candidate(op)
    if lane == "V2_BALANCED":
        if ask <= .50 or strong: return pullback_v1.immediate_record(op)
        return pullback_v1.replay_from_pullback(op, .50, 30.0)
    if lane == "V2_PRICE_DISCIPLINED":
        if strong and ask <= .50: return pullback_v1.immediate_record(op)
        window = 30.0 if ask <= .60 else 60.0
        return pullback_v1.replay_from_pullback(op, .50, window)
    raise ValueError("unknown pullback lane")


def pullback_lanes(opps: list[dict[str, Any]], full_n: int) -> dict[str, Any]:
    immediate = [pullback_v1.immediate_record(op) for op in opps]
    out = {"V1_IMMEDIATE_CONTROL": pullback_v1.summarize_immediate(immediate, full_n)}
    for lane in ("V2_BALANCED", "V2_PRICE_DISCIPLINED"):
        rows = [x for op in opps if (x := selective_pullback_record(op, lane)) is not None]
        out[lane] = pullback_v1.summarize_pullback(rows, len(immediate),
            len({r["contract"] for r in immediate}), full_n)
    return out


def frozen_rules() -> dict[str, Any]:
    return {
        "cutoff_default_utc": DEFAULT_CUTOFF_UTC,
        "control_collectors_unchanged": True,
        "four_lanes_independently_scored": True,
        "candidate_inputs_are_causal_only": True,
        "exit_rule": "+5c arm / 4c giveback unchanged",
        "same_sample_promotion": False, "automatic_promotion": False,
        "later_fresh_certification_required": True, "orders": False,
    }


def integrity_report(state: Mapping[str, Any]) -> dict[str, Any]:
    """Runtime evidence-integrity checks; never a performance/promotion gate."""
    required = ("scalp2_economics_v2", "candidate_verify_v2", "watch_exit_v2", "selective_pullback_v2")
    present = {name: isinstance(state.get(name), Mapping) for name in required}
    watch = state.get("watch_exit_v2") or {}
    exit_counts = [lane.get("frozen_exit_signals") for lane in watch.values()
                   if isinstance(lane, Mapping) and lane.get("frozen_exit_signals") is not None]
    watch_parity = bool(exit_counts) and len(set(exit_counts)) == 1
    cutoff_ok = str(state.get("cutoff_utc") or "") == DEFAULT_CUTOFF_UTC
    safety_ok = (state.get("orders") is False and state.get("automatic_promotion") is False
                 and state.get("same_sample_promotion") is False
                 and state.get("production_logic_changed") is False)
    all_ok = all(present.values()) and watch_parity and cutoff_ok and safety_ok
    return {
        "all_checks_pass": all_ok,
        "four_families_present": present,
        "watch_frozen_exit_count_parity": watch_parity,
        "watch_frozen_exit_counts": exit_counts,
        "prospective_cutoff_exact": cutoff_ok,
        "safety_flags_exact": safety_ok,
        "performance_selection_or_promotion": False,
    }


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0,
                 cutoff_text: str | None = None) -> dict[str, Any]:
    cutoff = econ_v1.parse_cutoff(CUTOFF_TEXT if cutoff_text is None else cutoff_text)
    if cutoff is None:
        return {"ok": False, "version": VERSION, "status": "FAIL_CLOSED_INVALID_CUTOFF", "orders": False}
    contracts, adapted = econ_v1.future_universe(rows, cutoff)
    opps = [op for op in q.build_serial_opportunities(adapted) if str(op.get("contract") or "") in contracts]
    ready = len(contracts) >= MIN_FULL_CONTRACTS and len(opps) >= MIN_SIGNALS
    state = {
        "ok": True, "version": VERSION,
        "status": "READY_FOR_MANUAL_V2_COMPARISON" if ready else "COLLECTING_NEXTGEN_V2",
        "updated_utc": now(), "cutoff_utc": cutoff.isoformat(), "source_sha256": sha,
        "source_bytes": source_bytes, "source_rows": len(rows),
        "future_full_contracts": len(contracts), "serial_signals": len(opps),
        "scalp2_economics_v2": scalp2_lanes(opps, len(contracts)),
        "candidate_verify_v2": verify_lanes(opps, len(contracts)),
        "watch_exit_v2": watch_lanes(opps),
        "selective_pullback_v2": pullback_lanes(opps, len(contracts)),
        "evidence_readiness": {"sample_ready": ready, "required_future_full_contracts": 100,
            "required_serial_signals": 100, "development_comparison_only": True,
            "later_fresh_certification_required": True},
        "frozen_rules": frozen_rules(), "manual_execution_only": True,
        "production_logic_changed": False, "same_sample_promotion": False,
        "automatic_promotion": False, "shadow_only": True, "orders": False,
    }
    state["runtime_integrity"] = integrity_report(state)
    if not state["runtime_integrity"]["all_checks_pass"]:
        state["ok"] = False
        state["status"] = "FAIL_CLOSED_NEXTGEN_V2_INVARIANT"
    print("SCALP_NEXTGEN_V2 | " + json.dumps({k: state[k] for k in (
        "version", "status", "cutoff_utc", "future_full_contracts", "serial_signals",
        "evidence_readiness", "frozen_rules")}, separators=(",", ":"), sort_keys=True), flush=True)
    return state


def refresh_once() -> dict[str, Any]:
    rows, sha, source_bytes = source.fetch_rows()
    with LOCK:
        if STATE.get("source_sha256") == sha and STATE.get("status") != "STARTING":
            STATE["last_poll_utc"] = now(); return dict(STATE)
    result = analyze_rows(rows, sha, source_bytes); result["last_poll_utc"] = now()
    with LOCK:
        STATE.clear(); STATE.update(result); return dict(STATE)


def loop() -> None:
    while True:
        try: refresh_once()
        except Exception as exc:
            with LOCK:
                STATE.update({"ok": False, "status": "FAIL_CLOSED_NEXTGEN_V2_ERROR",
                    "error": f"{type(exc).__name__}:{exc}", "orders": False,
                    "automatic_promotion": False, "same_sample_promotion": False})
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None: pass
    def send_json(self, code: int, obj: Mapping[str, Any]) -> None:
        raw = json.dumps(obj, separators=(",", ":"), sort_keys=True, default=str).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw))); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(raw)
    def do_GET(self) -> None:
        with LOCK: state = dict(STATE)
        path = urlparse(self.path).path
        if path == "/health": return self.send_json(200, {"ok": True, "analysis_ok": state.get("ok"),
            "status": state.get("status"), "version": VERSION, "orders": False})
        if path in ("/state", "/summary"): return self.send_json(200, state)
        return self.send_json(404, {"ok": False, "orders": False})


def assert_integrity() -> None:
    assert ARM_GAIN == q.ARM_GAIN == .05 and EXIT_GIVEBACK == q.GIVEBACK == .04
    assert DEFAULT_CUTOFF_UTC == "2026-09-16T19:50:00+00:00"
    assert frozen_rules()["orders"] is False
    assert frozen_rules()["same_sample_promotion"] is False


def main() -> int:
    assert_integrity()
    print(f"{VERSION} START | cutoff={CUTOFF_TEXT} | FOUR INDEPENDENT SHADOW LANES | NO ORDERS", flush=True)
    threading.Thread(target=loop, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


assert_integrity()
if __name__ == "__main__": raise SystemExit(main())
