#!/usr/bin/env python3
"""
BTC15 empirical combined-system scorecard V2.

PURE / OFFLINE AGGREGATION | SIGNAL ONLY | MANUAL EXECUTION ONLY | NO ORDERS

This module scores already-evaluated protected EARLY, serial V5 SCALP, and
protected FINAL evidence on ONE common contract universe. It never qualifies a
signal, changes a threshold, calls a network, or places an order.

Key semantics
-------------
- A contract counts at most once toward UNION actionable coverage.
- Multiple serial SCALPs inside one contract remain separate opportunities.
- EARLY / FINAL accuracy is scored only against official settlement when given.
- SCALP performance is move/management performance, never FINAL accuracy.
- Expensive FINAL locks may be correct but never masquerade as <=50c entries.
- WATCH is non-actionable.
- ENDED_UNARMED remains lifecycle metadata, never an actionable exit.
"""
from __future__ import annotations

import statistics
from collections import Counter
from typing import Any, Iterable, Mapping

VALID_SIDES = {"UP", "DOWN"}
EARLY_ACTIONABLE = {"QUALIFIED"}
FINAL_ACTIONABLE = {"QUALIFIED", "LOCK"}
SCALP_ACTIONABLE_STATES = {"ACTIVE", "PROTECT", "EXIT"}


def _f(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _side(v: Any) -> str | None:
    x = str(v or "").strip().upper()
    return x if x in VALID_SIDES else None


def _state(v: Any, default: str) -> str:
    return str(v or default).strip().upper()


def _mean(xs: list[float]) -> float | None:
    return statistics.fmean(xs) if xs else None


def _median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def _rate(n: int, d: int) -> float | None:
    return n / d if d else None


def _minutes(module: Mapping[str, Any]) -> float | None:
    m = _f(module.get("minutes_left"))
    if m is not None:
        return m
    s = _f(module.get("seconds_left"))
    return None if s is None else s / 60.0


def _ask(module: Mapping[str, Any]) -> float | None:
    for key in ("ask", "preferred_ask", "entry_ask", "entry_price"):
        x = _f(module.get(key))
        if x is not None:
            return x
    return None


def _scalp_key(row: Mapping[str, Any], fallback: int) -> str:
    cid = str(row.get("candidate_id") or "").strip()
    if cid:
        return "cid:" + cid
    idx = row.get("opportunity_index")
    if idx is not None:
        return "opp:" + str(idx)
    return "row:" + str(fallback)


def _prefer_scalp(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict[str, Any]:
    """Merge duplicate current/terminal views of one serial opportunity safely."""
    out = dict(a)
    b_terminal = bool(b.get("terminal_state") or b.get("completed") is True)
    a_terminal = bool(a.get("terminal_state") or a.get("completed") is True)
    if b_terminal and not a_terminal:
        out = dict(b)
        source = a
    else:
        source = b
    for k, v in source.items():
        if out.get(k) in (None, "", False) and v not in (None, ""):
            out[k] = v
    return out


def normalize_scalps(rows: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for i, raw in enumerate(rows or ()):  # terminal + current may duplicate a candidate
        r = dict(raw)
        key = _scalp_key(r, i)
        if key not in seen:
            seen[key] = r
            order.append(key)
        else:
            seen[key] = _prefer_scalp(seen[key], r)
    return [seen[k] for k in order]


def _module_summary(rows: list[dict[str, Any]], key: str, actionable_states: set[str]) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    for r in rows:
        mod = dict(r.get(key) or {})
        if _state(mod.get("state"), "PASS" if key == "early" else "WATCH") not in actionable_states:
            continue
        side = _side(mod.get("side"))
        if side is None:
            continue
        ask = _ask(mod)
        mins = _minutes(mod)
        official = _side(r.get("official_side"))
        calls.append({
            "contract": r["contract"],
            "side": side,
            "official_side": official,
            "correct": None if official is None else side == official,
            "ask": ask,
            "minutes_left": mins,
            "fair": _f(mod.get("fair", mod.get("confidence"))),
        })

    settled = [x for x in calls if x["correct"] is not None]
    correct_n = sum(x["correct"] is True for x in settled)
    asks = [float(x["ask"]) for x in calls if x["ask"] is not None]
    times = [float(x["minutes_left"]) for x in calls if x["minutes_left"] is not None]
    le50 = [x for x in calls if x["ask"] is not None and float(x["ask"]) <= 0.50 + 1e-12]
    settled_le50 = [x for x in le50 if x["correct"] is not None]
    le50_correct = sum(x["correct"] is True for x in settled_le50)
    ideal = [x for x in calls if x["ask"] is not None and 0.25 - 1e-12 <= float(x["ask"]) <= 0.35 + 1e-12]

    return {
        "calls": len(calls),
        "settled_calls": len(settled),
        "correct_n": correct_n,
        "accuracy": _rate(correct_n, len(settled)),
        "avg_ask": _mean(asks),
        "median_ask": _median(asks),
        "ask_le_50c_n": len(le50),
        "ask_le_50c_rate": _rate(len(le50), len(calls)),
        "ask_le_50c_settled_n": len(settled_le50),
        "ask_le_50c_accuracy": _rate(le50_correct, len(settled_le50)),
        "ask_25_35c_n": len(ideal),
        "avg_minutes_left": _mean(times),
        "median_minutes_left": _median(times),
        "contracts": [x["contract"] for x in calls],
    }


def _scalp_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    all_opps: list[dict[str, Any]] = []
    contract_counts: Counter[str] = Counter()

    for r in rows:
        opps = normalize_scalps(r.get("scalps") or ())
        if opps:
            contract_counts[r["contract"]] = len(opps)
        for o in opps:
            x = dict(o)
            x["contract"] = r["contract"]
            all_opps.append(x)

    completed = [o for o in all_opps if bool(o.get("completed") is True or o.get("terminal_state"))]
    peak_known = [o for o in completed if _f(o.get("peak_exec_gain")) is not None]
    entries = [_ask(o) for o in all_opps]
    entries = [float(x) for x in entries if x is not None]
    entry_times: list[float] = []
    for o in all_opps:
        m = _minutes(o)
        if m is None:
            s = _f(o.get("entry_seconds_left"))
            m = None if s is None else s / 60.0
        if m is not None:
            entry_times.append(float(m))

    def hit(threshold: float) -> int:
        return sum(float(_f(o.get("peak_exec_gain")) or -999.0) >= threshold - 1e-12 for o in peak_known)

    exits = [o for o in completed if _state(o.get("terminal_state", o.get("state")), "") == "EXIT"]
    positive_exits = sum((_f(o.get("exit_gain")) or -999.0) > 0 for o in exits)
    ended_unarmed = sum(_state(o.get("terminal_state"), "") == "ENDED_UNARMED" for o in completed)
    actionable_exit_false_ok = all(
        o.get("actionable_exit") is not True
        for o in completed
        if _state(o.get("terminal_state"), "") == "ENDED_UNARMED"
    )
    le50 = [x for x in entries if x <= 0.50 + 1e-12]

    return {
        "contracts_with_scalp": len(contract_counts),
        "opportunities": len(all_opps),
        "completed_opportunities": len(completed),
        "completed_with_peak": len(peak_known),
        "avg_opportunities_per_scalp_contract": _mean([float(v) for v in contract_counts.values()]),
        "multi_scalp_contracts": sum(v >= 2 for v in contract_counts.values()),
        "max_scalps_in_one_contract": max(contract_counts.values(), default=0),
        "plus_5c_n": hit(0.05),
        "plus_5c_rate": _rate(hit(0.05), len(peak_known)),
        "plus_10c_n": hit(0.10),
        "plus_10c_rate": _rate(hit(0.10), len(peak_known)),
        "plus_15c_n": hit(0.15),
        "plus_15c_rate": _rate(hit(0.15), len(peak_known)),
        "plus_20c_n": hit(0.20),
        "plus_20c_rate": _rate(hit(0.20), len(peak_known)),
        "protected_exit_n": len(exits),
        "positive_protected_exit_n": positive_exits,
        "positive_protected_exit_rate": _rate(positive_exits, len(exits)),
        "ended_unarmed_n": ended_unarmed,
        "ended_unarmed_non_actionable_exit_invariant": actionable_exit_false_ok,
        "avg_entry_ask": _mean(entries),
        "median_entry_ask": _median(entries),
        "entry_le_50c_n": len(le50),
        "entry_le_50c_rate": _rate(len(le50), len(entries)),
        "avg_entry_minutes_left": _mean(entry_times),
        "median_entry_minutes_left": _median(entry_times),
        "contract_opportunity_counts": dict(contract_counts),
    }


def score_records(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    seen_contracts: set[str] = set()
    for raw in records:
        r = dict(raw)
        contract = str(r.get("contract") or "").strip()
        if not contract:
            raise ValueError("every scorecard record requires contract")
        if contract in seen_contracts:
            raise ValueError(f"duplicate contract record would double-count union coverage: {contract}")
        seen_contracts.add(contract)
        r["contract"] = contract
        r["scalps"] = normalize_scalps(r.get("scalps") or ())
        rows.append(r)

    early = _module_summary(rows, "early", EARLY_ACTIONABLE)
    final = _module_summary(rows, "final", FINAL_ACTIONABLE)
    scalp = _scalp_summary(rows)

    path_pattern_counts: Counter[str] = Counter()
    contract_rows: list[dict[str, Any]] = []
    union_n = 0
    early_n = 0
    final_n = 0
    scalp_n = 0

    for r in rows:
        es = _state((r.get("early") or {}).get("state"), "PASS")
        fs = _state((r.get("final") or {}).get("state"), "WATCH")
        has_early = es in EARLY_ACTIONABLE and _side((r.get("early") or {}).get("side")) is not None
        has_final = fs in FINAL_ACTIONABLE and _side((r.get("final") or {}).get("side")) is not None
        scalp_opps = normalize_scalps(r.get("scalps") or ())
        has_scalp = bool(scalp_opps)

        paths = tuple(p for p, yes in (("EARLY", has_early), ("SCALP", has_scalp), ("FINAL", has_final)) if yes)
        actionable = bool(paths)
        union_n += int(actionable)
        early_n += int(has_early)
        scalp_n += int(has_scalp)
        final_n += int(has_final)
        pattern = "+".join(paths) if paths else "NONE"
        path_pattern_counts[pattern] += 1
        contract_rows.append({
            "contract": r["contract"],
            "official_side": _side(r.get("official_side")),
            "actionable_paths": paths,
            "union_actionable": actionable,
            "serial_scalp_opportunities": len(scalp_opps),
        })

    n = len(rows)
    if union_n > n:
        raise AssertionError("union coverage double-count detected")

    return {
        "version": "BTC15_COMBINED_EMPIRICAL_SCORECARD_V2",
        "contracts": n,
        "early_contracts": early_n,
        "early_contract_coverage": _rate(early_n, n),
        "scalp_contracts": scalp_n,
        "scalp_contract_coverage": _rate(scalp_n, n),
        "final_contracts": final_n,
        "final_contract_coverage": _rate(final_n, n),
        "union_actionable_contracts": union_n,
        "union_actionable_coverage": _rate(union_n, n),
        "uncovered_contracts": n - union_n,
        "path_pattern_counts": dict(path_pattern_counts),
        "early": early,
        "scalp": scalp,
        "final": final,
        "contract_rows": contract_rows,
        "union_counts_each_contract_once": True,
        "serial_scalps_preserved_separately": True,
        "final_accuracy_is_not_entry_quality": True,
        "scalp_metrics_are_not_final_accuracy": True,
        "price_is_evaluation_not_hidden_filter": True,
        "numeric_flip_risk_validated": False,
        "module_thresholds_changed": False,
        "production_behavior_changed": False,
        "manual_execution_only": True,
        "orders": False,
    }


__all__ = ["normalize_scalps", "score_records"]
