"""Read-only V2 development replay. Frozen V1 modules are imported unchanged.

Entries are causal decisions; outcome availability never selects a V2 entry.
All lanes are anchored to V1 serial opportunity IDs, not portfolio simulations.
"""
from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone
from typing import Any, Mapping

import scalp_candidate_verify_forward_v1 as verify_v1
import scalp_economics_exit_cert_v1 as econ
import scalp_opportunity_quality_frontier_v1 as q
import scalp_pullback_entry_forward_v1 as pullback_v1

ARM_GAIN = .05
EXIT_GIVEBACK = .04
WATCH_MODES = ("V1_1C", "V1_2C", "V1_3C", "V2_CONFIRMED_HALF_C", "V2_FALLING_TREND")
PULLBACK_MODES = ("V2_BALANCED", "V2_PRICE_DISCIPLINED")
SCALP2_MODES = ("CONTROL_V1_SCALP2", "AFFORDABLE_LE50", "EARLY_AFFORDABLE", "STRONG_AFFORDABLE")
VERIFY_MODES = ("V1_IMMEDIATE", "V1_FIXED_5S", "V1_FIXED_10S", "V1_FIXED_15S", "V1_FIXED_30S", "V2_DYNAMIC_CAUSAL")
PULLBACK_CONTROLS = tuple(f"V1_LE{int(t * 100)}_{int(w)}S" for t in pullback_v1.TARGETS for w in pullback_v1.WINDOWS_SEC)
REQUIRED_LANES = {
    "scalp2_economics_v2": SCALP2_MODES,
    "candidate_verify_v2": VERIFY_MODES,
    "watch_exit_v2": WATCH_MODES,
    "selective_pullback_v2": ("V1_IMMEDIATE_CONTROL", *PULLBACK_CONTROLS, *PULLBACK_MODES),
}


def f(value: Any) -> float | None:
    return q.f(value)


def mean(values) -> float | None:
    xs = [float(x) for x in values if f(x) is not None]
    return statistics.fmean(xs) if xs else None


def rate(flags) -> float | None:
    xs = list(flags)
    return sum(bool(x) for x in xs) / len(xs) if xs else None


def flag(value: Any) -> bool | None:
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "t"}: return True
    if text in {"false", "no", "n", "f"}: return False
    x = f(value)
    return bool(x) if x in (0., 1.) else None


def strict_time(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def identity(op: Mapping[str, Any]) -> dict[str, Any]:
    return {"contract": str(op.get("contract") or ""),
            "candidate_id": str(op.get("candidate_id") or ""),
            "opportunity_index": int(op.get("opportunity_index") or 0)}


def key(row: Mapping[str, Any]) -> tuple[str, str, int]:
    r = identity(row)
    return r["contract"], r["candidate_id"], r["opportunity_index"]


def strong_candidate(op: Mapping[str, Any]) -> bool:
    """Only candidate-time evidence, with explicit known-safe flags."""
    c = op.get("_candidate") or {}
    safe = all(flag(c.get(k)) is False for k in
               ("btc_against_side", "brti_against_side", "dual_reversal_evidence"))
    return bool(safe and (f(c.get("confirm_count")) or 0) >= 2
                and flag(c.get("structure_ok")) is True
                and str(c.get("brti_status") or "").strip().upper() == "PRIMARY_OK"
                and (f(op.get("btc_move5_norm")) or 0) >= .60
                and (f(op.get("btc_move15_norm")) or 0) >= .50)


def path_timeline(op: Mapping[str, Any]) -> list[tuple[float, Mapping[str, Any]]]:
    """V2 event clock: no negative time, no duplicate evidence, first row wins.

    When both clocks exist they must agree within one second. Duplicates cannot
    confirm a signal. V1 replay functions retain their original clock semantics.
    """
    t0 = strict_time((op.get("_candidate") or {}).get("timestamp_utc"))
    seen: set[float] = set()
    seen_stamps: set[datetime] = set()
    out = []
    for row in op.get("_paths") or []:
        e = f(row.get("elapsed_sec"))
        ts = strict_time(row.get("timestamp_utc"))
        actual = (ts - t0).total_seconds() if ts and t0 else None
        if row.get("timestamp_utc") and ts is None: continue
        if e is None: e = actual
        if e is None or e < 0 or (actual is not None and (actual < 0 or abs(e - actual) > 1.0)):
            continue
        if e in seen or (ts is not None and ts in seen_stamps): continue
        seen.add(e)
        if ts is not None: seen_stamps.add(ts)
        out.append((e, row))
    return sorted(out, key=lambda x: x[0])


def valid_quote(row: Mapping[str, Any]) -> bool:
    ask, bid = f(row.get("current_ask")), f(row.get("current_bid"))
    return bool(ask is not None and bid is not None and 0 <= bid <= ask <= 1)


def entry_decision(ask: float, elapsed: float, reason: str, events: int = 0) -> dict[str, Any]:
    return {"entry_ask": ask, "entry_elapsed_sec": elapsed, "decision_reason": reason,
            "confirmation_events": events}


def dynamic_verify_decision(op: Mapping[str, Any]) -> dict[str, Any] | None:
    entry0 = f(op.get("entry_ask"))
    if entry0 is None or not 0 < entry0 < 1: return None
    if strong_candidate(op): return entry_decision(entry0, 0., "IMMEDIATE_STRONG")
    streak = 0
    saw_plus1 = False
    previous = None
    for elapsed, row in path_timeline(op):
        if elapsed > 30: break
        if elapsed == 0: continue
        if not valid_quote(row) or (previous is not None and elapsed - previous > 5):
            streak = 0
            saw_plus1 = False
        previous = elapsed
        if not valid_quote(row): continue
        # Derive executable follow-through from the observed quote, not a label.
        gain = float(row["current_bid"]) - entry0
        if gain < -1e-12 or float(row["current_ask"]) > entry0 + .03 + 1e-12:
            streak = 0
            saw_plus1 = False
            continue
        streak += 1
        saw_plus1 = saw_plus1 or gain >= .01 - 1e-12
        if streak >= 2 and saw_plus1:
            return entry_decision(float(row["current_ask"]), elapsed, "EVENT_CONFIRMED", streak)
    return None


def score_entry(op: Mapping[str, Any], decision: Mapping[str, Any]) -> dict[str, Any]:
    """Only quotes observed at/after the causal entry can score its outcome."""
    ask, elapsed = decision["entry_ask"], decision["entry_elapsed_sec"]
    future = [(e, float(row["current_bid"]) - ask) for e, row in path_timeline(op)
              if e >= elapsed and valid_quote(row)]
    gains = [g for _, g in future]
    peak = -math.inf
    armed = False
    exit_gain = exit_time = None
    for e, g in future:
        peak = max(peak, g)
        armed = armed or peak >= ARM_GAIN
        if armed and peak - g >= EXIT_GIVEBACK - 1e-12:
            exit_gain, exit_time = g, e
            break
    labels = {f"plus{int(target*100)}": None if not gains else int(max(gains) >= target)
              for target in (.05, .10, .20)}
    rec = econ._op_record({**identity(op), **labels, "entry_ask": ask,
                          "peak_gain": max(gains) if gains else None,
                          "adverse_gain": min(gains) if gains else None,
                          "protected_exit_gain": exit_gain})
    original = f(op.get("entry_ask"))
    left = f(op.get("seconds_left"))
    rec.update({**labels, **decision, "movement_scoreable": bool(future),
                "actual_delay_sec": elapsed, "protected_exit_elapsed_sec": exit_time,
                "entry_improvement_c_vs_candidate": None if original is None else 100 * (original - ask),
                "seconds_left_at_entry": None if left is None else max(0, left - elapsed)})
    return rec


def dynamic_verify_record(op: Mapping[str, Any]) -> dict[str, Any] | None:
    d = dynamic_verify_decision(op)
    return None if d is None else score_entry(op, d)


def net(row: Mapping[str, Any], lot: int) -> float | None:
    nested = (((row.get("fee_scenarios") or {}).get(str(lot)) or {}).get("TAKER_TAKER") or {})
    x = f(nested.get("net_gain_c_per_contract"))
    return x if x is not None else f(row.get("one_lot_taker_taker_net_c" if lot == 1 else "ten_lot_taker_taker_net_c"))


def baseline_record(op: Mapping[str, Any]) -> dict[str, Any]:
    r = verify_v1.immediate_record(op)
    r.update({"movement_scoreable": f(op.get("peak_gain")) is not None,
              "entry_elapsed_sec": 0., "entry_improvement_c_vs_candidate": 0.})
    return r


def econ_summary(records: list[dict[str, Any]], base_n: int, full_n: int) -> dict[str, Any]:
    exits = [r for r in records if r.get("protected_exit_observed")]
    scored = [r for r in records if r.get("movement_scoreable", True)]
    contracts = {r["contract"] for r in records}
    asks = [f(r.get("entry_ask")) for r in records]
    avg_ask = mean(asks)
    return {
        "signals": len(records), "contracts": len(contracts),
        "signal_retention_vs_control": len(records) / base_n if base_n else None,
        "true_contract_coverage": len(contracts) / full_n if full_n else None,
        "unavailable_or_skipped_entries": base_n - len(records),
        "movement_scoreable_entries": len(scored), "unscoreable_entries": len(records) - len(scored),
        "avg_entry_ask_c": None if avg_ask is None else 100 * avg_ask,
        "avg_entry_delay_sec": mean(r.get("entry_elapsed_sec", r.get("actual_delay_sec")) for r in records),
        "avg_entry_improvement_c_vs_candidate": mean(r.get("entry_improvement_c_vs_candidate") for r in records),
        "plus5_rate": rate(r.get("plus5") for r in scored),
        "plus10_rate": rate(r.get("plus10") for r in scored),
        "protected_exit_signals": len(exits), "without_protected_exit": len(records) - len(exits),
        "protected_exit_rate": len(exits) / len(records) if records else None,
        "avg_gross_protected_gain_c": mean(r.get("gross_protected_gain_c", 100 * r["protected_exit_gain"]
                                                   if f(r.get("protected_exit_gain")) is not None else None) for r in exits),
        "one_lot_taker_taker_avg_net_c": mean(net(r, 1) for r in exits),
        "ten_lot_taker_taker_avg_net_c": mean(net(r, 10) for r in exits),
        "economics_scope": "observed protected exits only; not total P&L",
    }


def paired_comparison(records: list[dict[str, Any]], controls: list[dict[str, Any]]) -> dict[str, Any]:
    control = {key(r): r for r in controls}
    pairs = [(r, control[key(r)]) for r in records if key(r) in control]
    both_exit = [(r, c) for r, c in pairs if r.get("protected_exit_observed") and c.get("protected_exit_observed")]
    retained = {key(r) for r in records}
    omitted = [r for r in controls if key(r) not in retained]
    return {
        "matched_entries": len(pairs), "both_protected_exits": len(both_exit),
        "only_shadow_protected_exits": sum(bool(r.get("protected_exit_observed")) and not c.get("protected_exit_observed") for r, c in pairs),
        "only_control_protected_exits": sum(bool(c.get("protected_exit_observed")) and not r.get("protected_exit_observed") for r, c in pairs),
        "omitted_control_entries": len(omitted),
        "omitted_control_protected_exits": sum(bool(r.get("protected_exit_observed")) for r in omitted),
        "omitted_control_plus10": sum(bool(r.get("plus10")) for r in omitted),
        "paired_entry_improvement_c": mean(100 * (float(c["entry_ask"]) - float(r["entry_ask"]))
                                             for r, c in pairs if f(c.get("entry_ask")) is not None and f(r.get("entry_ask")) is not None),
        "paired_one_lot_net_delta_c": mean(net(r, 1) - net(c, 1) for r, c in both_exit if net(r, 1) is not None and net(c, 1) is not None),
        "paired_ten_lot_net_delta_c": mean(net(r, 10) - net(c, 10) for r, c in both_exit if net(r, 10) is not None and net(c, 10) is not None),
        "paired_economics_scope": "both-exit subset; selection and missing outcomes remain visible",
    }


def summarize_family(lanes, controls, full_n):
    return {name: {**econ_summary(records, len(controls), full_n),
                   "paired_vs_immediate_control": paired_comparison(records, controls)}
            for name, records in lanes.items()}


def scalp2_records(opps):
    base = [op for op in opps if op.get("opportunity_index") == 2]
    affordable = lambda op: f(op.get("entry_ask")) is not None and 0 < float(op["entry_ask"]) <= .50
    predicates = (lambda op: True, affordable,
                  lambda op: affordable(op) and (f(op.get("seconds_left")) or 0) >= 360,
                  lambda op: affordable(op) and strong_candidate(op))
    return {name: [baseline_record(op) for op in base if pred(op)]
            for name, pred in zip(SCALP2_MODES, predicates)}


def verify_records(opps):
    out = {}
    for name, delay in zip(VERIFY_MODES, verify_v1.VERIFY_DELAYS_SEC):
        if delay == 0:
            out[name] = [baseline_record(op) for op in opps]
        else:
            out[name], _ = verify_v1.build_policy_records(opps, delay)
    out["V2_DYNAMIC_CAUSAL"] = [r for op in opps if (r := dynamic_verify_record(op)) is not None]
    return out


def selective_pullback_decision(op: Mapping[str, Any], lane: str) -> dict[str, Any] | None:
    ask = f(op.get("entry_ask"))
    if ask is None or not 0 < ask < 1: return None
    if lane not in PULLBACK_MODES: raise ValueError("unknown pullback lane")
    if ask <= .50 or (lane == "V2_BALANCED" and strong_candidate(op)):
        return entry_decision(ask, 0., "IMMEDIATE_AFFORDABLE" if ask <= .50 else "IMMEDIATE_STRONG")
    # Waiting is confined to expensive entries. Thresholds remain hypotheses.
    window = 30. if lane == "V2_BALANCED" or ask <= .60 else 60.
    for elapsed, row in path_timeline(op):
        if elapsed > window: break
        if elapsed > 0 and valid_quote(row) and float(row["current_ask"]) <= .50:
            return entry_decision(float(row["current_ask"]), elapsed, "SELECTIVE_PULLBACK_LE50")
    return None


def selective_pullback_record(op, lane):
    d = selective_pullback_decision(op, lane)
    return None if d is None else score_entry(op, d)


def pullback_records(opps):
    out = {"V1_IMMEDIATE_CONTROL": [baseline_record(op) for op in opps]}
    for target in pullback_v1.TARGETS:
        for window in pullback_v1.WINDOWS_SEC:
            name = f"V1_LE{int(target*100)}_{int(window)}S"
            out[name] = [r for op in opps if (r := pullback_v1.replay_from_pullback(op, target, window)) is not None]
    for name in PULLBACK_MODES:
        out[name] = [r for op in opps if (r := selective_pullback_record(op, name)) is not None]
    return out


def watch_measure(op: Mapping[str, Any], mode: str) -> dict[str, Any]:
    """V1 Watch/Exit clock unchanged; V2 trigger evidence uses unique valid times.

    Falling trend: two consecutive declines, each <=5s apart, >=0.5c combined
    fall and >=0.5c current drawdown. This can precede a 1c V1 warning.
    Sub-cent evidence may be rare at actual quote granularity; report frequency.
    """
    if mode not in WATCH_MODES: raise ValueError("unknown watch mode")
    t0 = q.dt((op.get("_candidate") or {}).get("timestamp_utc"))
    timeline = sorted([(q.elapsed(r, t0), f(r.get("exec_gain")), r) for r in op.get("_paths") or []
                       if q.elapsed(r, t0) is not None and f(r.get("exec_gain")) is not None], key=lambda x: x[0])
    eligible = {id(r) for _, r in path_timeline(op)}
    peak = -math.inf
    valid_peak = -math.inf
    armed = False
    warning = warning_peak = exit_time = exit_gain = None
    recovered = False
    recent = []
    small_streak = 0
    for e, g, row in timeline:
        peak = max(peak, g)
        armed = armed or peak >= ARM_GAIN - 1e-12
        if id(row) in eligible:
            valid_peak = max(valid_peak, g)
            if recent and e - recent[-1][0] > 5:
                recent = []
                small_streak = 0
            recent.append((e, g))
            recent = recent[-3:]
        giveback = peak - g
        if not armed: continue
        if mode.startswith("V1_"):
            trigger = giveback >= int(mode[3]) / 100 - 1e-12
        elif id(row) not in eligible or valid_peak < ARM_GAIN - 1e-12:
            trigger = False
        elif mode == "V2_CONFIRMED_HALF_C":
            small_streak = small_streak + 1 if valid_peak - g >= .005 - 1e-12 else 0
            trigger = small_streak >= 2
        else:
            trigger = bool(len(recent) == 3 and recent[0][1] > recent[1][1] > recent[2][1]
                           and recent[0][1] - g >= .005 - 1e-12 and valid_peak - g >= .005 - 1e-12)
        if warning is None and trigger:
            warning, warning_peak = e, peak if mode.startswith("V1_") else valid_peak
        if warning is not None and e > warning and g > warning_peak + 1e-12:
            recovered = True
        if giveback >= EXIT_GIVEBACK - 1e-12:
            exit_time, exit_gain = e, g
            break
    # Keep the frozen economics model's observed-exit subset. V1 Watch arms
    # with epsilon tolerance whereas the V1 economics builder arms strictly;
    # disclose that boundary discrepancy instead of silently filling fees.
    er = econ._op_record(op)
    return {**identity(op), "armed": armed, "warning": warning is not None,
            "warning_time_sec": warning, "exit": exit_time is not None,
            "exit_time_sec": exit_time, "exit_gain": exit_gain,
            "lead": None if warning is None or exit_time is None else exit_time - warning,
            "recovered_new_high_after_warning": recovered,
            "warning_without_exit": warning is not None and exit_time is None,
            "unresolved_warning": warning is not None and exit_time is None and not recovered,
            "legacy_economics_exit_matches_watch": f(op.get("protected_exit_gain")) == exit_gain,
            "gross_protected_gain_c": er["gross_protected_gain_c"],
            "one_lot_taker_taker_net_c": net(er, 1), "ten_lot_taker_taker_net_c": net(er, 10)}


def watch_records(opps):
    return {mode: [watch_measure(op, mode) for op in opps] for mode in WATCH_MODES}


def summarize_watch(lanes):
    controls = {key(r): r for r in lanes["V1_1C"]}
    out = {}
    for mode, rows in lanes.items():
        warned = [r for r in rows if r["warning"]]
        exited = [r for r in rows if r["exit"]]
        paired = [(r, controls[key(r)]) for r in rows if r["lead"] is not None and controls[key(r)]["lead"] is not None]
        mismatch = [r for r in rows if (r["exit_time_sec"], r["exit_gain"]) !=
                    (controls[key(r)]["exit_time_sec"], controls[key(r)]["exit_gain"])]
        out[mode] = {
            "signals": len(rows), "armed_signals": sum(r["armed"] for r in rows),
            "warning_signals": len(warned), "frozen_exit_signals": len(exited),
            "exits_without_warning": sum(not r["warning"] for r in exited),
            "avg_warning_to_exit_lead_sec": mean(r["lead"] for r in warned),
            "lead_ge5_rate_among_warned_exits": rate(r["lead"] >= 5 for r in warned if r["lead"] is not None),
            "exits_with_ge5s_warning_rate": rate(r["lead"] is not None and r["lead"] >= 5 for r in exited),
            "paired_warned_exits_vs_v1_1c": len(paired),
            "paired_lead_improvement_sec_vs_v1_1c": mean(r["lead"] - c["lead"] for r, c in paired),
            "materially_earlier_ge5s_pairs": sum(r["lead"] - c["lead"] >= 5 for r, c in paired),
            "false_warning_proxy_new_high_rate": rate(r["recovered_new_high_after_warning"] for r in warned),
            "false_warning_definition": "new high after first warning, before frozen exit or tape end; proxy only",
            "warning_without_exit_rate": rate(r["warning_without_exit"] for r in warned),
            "unresolved_warnings": sum(r["unresolved_warning"] for r in warned),
            "avg_gross_protected_gain_c": mean(r["gross_protected_gain_c"] for r in exited),
            "one_lot_taker_taker_avg_net_c": mean(r["one_lot_taker_taker_net_c"] for r in exited),
            "ten_lot_taker_taker_avg_net_c": mean(r["ten_lot_taker_taker_net_c"] for r in exited),
            "protected_exits_with_fee_scores": sum(r["one_lot_taker_taker_net_c"] is not None for r in exited),
            "legacy_economics_exit_discrepancies": sum(not r["legacy_economics_exit_matches_watch"] for r in rows),
            "economics_scope": "frozen V1 economics scoreable exit subset, independent of warnings; boundary discrepancies disclosed",
            "frozen_exit_time_gain_mismatches": len(mismatch), "exit_rule_unchanged": not mismatch,
        }
    return out


def analyze_opportunities(opps, full_n):
    scalp = scalp2_records(opps)
    verify = verify_records(opps)
    pullback = pullback_records(opps)
    watch = watch_records(opps)
    summary = {
        "scalp2_economics_v2": summarize_family(scalp, scalp["CONTROL_V1_SCALP2"], full_n),
        "candidate_verify_v2": summarize_family(verify, verify["V1_IMMEDIATE"], full_n),
        "watch_exit_v2": summarize_watch(watch),
        "selective_pullback_v2": summarize_family(pullback, pullback["V1_IMMEDIATE_CONTROL"], full_n),
    }
    for name, records in (("candidate_verify_v2", verify), ("selective_pullback_v2", pullback)):
        for lane, rs in records.items():
            reasons = sorted({r.get("decision_reason") for r in rs if r.get("decision_reason")})
            summary[name][lane]["decision_reasons"] = {reason: sum(r.get("decision_reason") == reason for r in rs) for reason in reasons}
    # Small per-op records make paired comparisons auditable without raw features.
    audit = {"scalp2_economics_v2": scalp, "candidate_verify_v2": verify,
             "watch_exit_v2": watch, "selective_pullback_v2": pullback}
    return summary, audit
