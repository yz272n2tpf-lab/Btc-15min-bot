#!/usr/bin/env python3
"""BTC15 scalp entry + profit-protection ladder V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Purpose
-------
Measure whether waiting for a better executable entry and using alternate
profit-protection rules can improve scalp economics without rewriting the
frozen generalized detector.

Integrity
---------
* Baseline candidate qualification is imported unchanged.
* Delayed/price-gated entries use the THEN-current executable ASK.
* All move/exit scoring uses later executable BID minus that actual entry ASK.
* Entry and exit policy grids are predeclared; this module does not fit a model.
* HOLDOUT is report-only and never selects a policy.
* No production imports/writes and no order capability.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping

import scalp_opportunity_quality_frontier_v1 as q

VERSION = "BTC15_SCALP_ENTRY_PROFIT_LADDER_V1"

ENTRY_POLICIES: dict[str, dict[str, Any]] = {
    "IMMEDIATE": {"mode": "immediate"},
    "AFFORDABLE_15": {"mode": "max_ask", "max_ask": 0.50, "wait_sec": 15.0},
    "AFFORDABLE_30": {"mode": "max_ask", "max_ask": 0.50, "wait_sec": 30.0},
    "AFFORDABLE_45": {"mode": "max_ask", "max_ask": 0.50, "wait_sec": 45.0},
    "AFFORDABLE_60": {"mode": "max_ask", "max_ask": 0.50, "wait_sec": 60.0},
    "IDEAL_25_35_60": {"mode": "band", "min_ask": 0.25, "max_ask": 0.35, "wait_sec": 60.0},
}

EXIT_POLICIES: dict[str, dict[str, Any]] = {
    "LEGACY_5_4": {"mode": "trail", "arm": 0.05, "giveback": 0.04},
    "PROTECT_5_3": {"mode": "trail", "arm": 0.05, "giveback": 0.03},
    "PROTECT_5_2": {"mode": "trail", "arm": 0.05, "giveback": 0.02},
    "STEPLOCK_5_3_10_4": {"mode": "steplock", "arm": 0.05, "pre10_giveback": 0.03,
                            "post10_giveback": 0.04, "post10_floor": 0.05},
    "RUNNER_10_4": {"mode": "trail", "arm": 0.10, "giveback": 0.04},
}


def finite(v: Any) -> float | None:
    x = q.f(v)
    return x if x is not None and math.isfinite(x) else None


def _timeline(candidate: Mapping[str, Any], paths: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    t0 = q.dt(candidate.get("timestamp_utc"))
    out: list[dict[str, Any]] = []
    for r in paths:
        e = q.elapsed(r, t0)
        if e is None:
            continue
        out.append({
            "elapsed_sec": float(e),
            "timestamp": q.dt(r.get("timestamp_utc")),
            "ask": finite(r.get("current_ask")),
            "bid": finite(r.get("current_bid")),
            "row": r,
        })
    return sorted(out, key=lambda z: z["elapsed_sec"])


def choose_entry(candidate: Mapping[str, Any], paths: list[Mapping[str, Any]], policy: Mapping[str, Any]) -> dict[str, Any] | None:
    """Choose an entry using information available up to the entry moment only."""
    base_ask = finite(candidate.get("entry_ask"))
    if base_ask is None:
        return None
    mode = str(policy.get("mode") or "")
    if mode == "immediate":
        e = 0.0; ask = base_ask; row = None
    else:
        lo = finite(policy.get("min_ask"))
        hi = finite(policy.get("max_ask"))
        wait = finite(policy.get("wait_sec"))
        if hi is None or wait is None:
            return None
        if base_ask <= hi and (lo is None or base_ask >= lo):
            e = 0.0; ask = base_ask; row = None
        else:
            z = next((x for x in _timeline(candidate, paths)
                      if x["elapsed_sec"] <= wait + 1e-12
                      and x["ask"] is not None
                      and x["ask"] <= hi + 1e-12
                      and (lo is None or x["ask"] >= lo - 1e-12)), None)
            if z is None:
                return None
            e = float(z["elapsed_sec"]); ask = float(z["ask"]); row = z
    left0 = finite(candidate.get("seconds_left"))
    left = None if left0 is None else max(0.0, left0 - e)
    t0 = q.dt(candidate.get("timestamp_utc"))
    ts = t0 if e <= 0 else (row["timestamp"] if row and row["timestamp"] != datetime.min.replace(tzinfo=timezone.utc) else t0)
    return {
        "entry_elapsed_sec": e,
        "entry_ask": ask,
        "entry_timestamp": ts,
        "seconds_left_at_entry": left,
        "affordable_le50": ask <= 0.50,
        "ideal_25_35": 0.25 <= ask <= 0.35,
    }


def simulate_exit(candidate: Mapping[str, Any], paths: list[Mapping[str, Any]], entry: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    """Score future executable BID against the actual selected entry ASK."""
    entry_e = float(entry["entry_elapsed_sec"])
    ask = float(entry["entry_ask"])
    z = [x for x in _timeline(candidate, paths) if x["elapsed_sec"] + 1e-12 >= entry_e and x["bid"] is not None]
    if not z:
        return {"scoreable": False}
    gains = [(x["elapsed_sec"], float(x["bid"]) - ask, x) for x in z]
    peak = -float("inf")
    trough = float("inf")
    hit5 = hit10 = hit20 = False
    exit_gain = None; exit_e = None; exit_ts = None; protected = False
    mode = str(policy.get("mode") or "")
    for e, g, x in gains:
        peak = max(peak, g); trough = min(trough, g)
        hit5 = hit5 or g >= 0.05 - 1e-12
        hit10 = hit10 or g >= 0.10 - 1e-12
        hit20 = hit20 or g >= 0.20 - 1e-12
        if mode == "trail":
            arm = float(policy["arm"]); giveback = float(policy["giveback"])
            if peak >= arm - 1e-12 and peak - g >= giveback - 1e-12:
                exit_gain = g; exit_e = e; exit_ts = x["timestamp"]; protected = True; break
        elif mode == "steplock":
            if peak >= float(policy["arm"]) - 1e-12:
                if peak >= 0.10 - 1e-12:
                    floor = max(float(policy["post10_floor"]), peak - float(policy["post10_giveback"]))
                else:
                    floor = peak - float(policy["pre10_giveback"])
                if g <= floor + 1e-12:
                    exit_gain = g; exit_e = e; exit_ts = x["timestamp"]; protected = True; break
    # Report terminal executable value even if no protection exit occurred, but
    # do not use terminal fallback to unlock another serial scalp.
    terminal_e, terminal_gain, terminal_x = gains[-1]
    realized = exit_gain if protected else terminal_gain
    return {
        "scoreable": True,
        "hit5": hit5,
        "hit10": hit10,
        "hit20": hit20,
        "mfe": peak,
        "mae": trough,
        "protected_exit": protected,
        "exit_gain": realized,
        "protected_exit_gain": exit_gain,
        "exit_elapsed_sec": exit_e if protected else terminal_e,
        "protected_exit_timestamp": exit_ts if protected else None,
        "terminal_gain": terminal_gain,
        "terminal_timestamp": terminal_x["timestamp"],
    }


def _raw_parts(rows: list[Mapping[str, Any]]) -> tuple[set[str], dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    done = {q.cid(r) for r in rows if q.typ(r) == "RESULT" and q.cid(r)}
    paths: dict[str, list[dict[str, Any]]] = defaultdict(list)
    byc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r0 in rows:
        r = dict(r0)
        if q.typ(r) == "PATH" and q.cid(r):
            paths[q.cid(r)].append(r)
        elif q.typ(r) == "CANDIDATE" and q.cid(r) and q.contract(r):
            byc[q.contract(r)].append(r)
    for k in paths:
        paths[k].sort(key=lambda r: q.elapsed(r, q.dt(next((c.get("timestamp_utc") for rs in byc.values() for c in rs if q.cid(c) == k), None))) or 0.0)
    return done, paths, byc


def contract_split(rows: list[Mapping[str, Any]]) -> dict[str, str]:
    first: dict[str, datetime] = {}
    for r in rows:
        if q.typ(r) != "CANDIDATE" or not q.baseline_qualified(r):
            continue
        c = q.contract(r); t = q.dt(r.get("timestamp_utc"))
        if not c:
            continue
        first[c] = min(first.get(c, t), t)
    ordered = sorted(first, key=lambda c: first[c]); n = len(ordered)
    if n < 10:
        return {c: "DEVELOPMENT" for c in ordered}
    i60 = max(1, int(n * .60)); i80 = max(i60 + 1, int(n * .80))
    return {c: ("DEVELOPMENT" if i < i60 else "VALIDATION" if i < i80 else "HOLDOUT") for i, c in enumerate(ordered)}


def simulate_ladder(rows: list[Mapping[str, Any]], entry_policy: Mapping[str, Any], exit_policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    done, paths, byc = _raw_parts(rows)
    out: list[dict[str, Any]] = []
    for c, raw in byc.items():
        candidates = [r for r in sorted(raw, key=lambda x: q.dt(x.get("timestamp_utc"))) if q.baseline_qualified(r)]
        earliest = datetime.min.replace(tzinfo=timezone.utc)
        used: set[str] = set(); idx = 1
        while True:
            cand = next((r for r in candidates if q.cid(r) not in used and q.dt(r.get("timestamp_utc")) > earliest), None)
            if cand is None:
                break
            used.add(q.cid(cand))
            if q.cid(cand) not in done:
                continue
            pr = paths.get(q.cid(cand), [])
            entry = choose_entry(cand, pr, entry_policy)
            if entry is None:
                continue
            ex = simulate_exit(cand, pr, entry, exit_policy)
            if not ex.get("scoreable"):
                continue
            rec = {
                "contract": c,
                "candidate_id": q.cid(cand),
                "opportunity_index": idx,
                "side": str(cand.get("side") or "").strip().upper(),
                **entry,
                **ex,
            }
            out.append(rec)
            # Only a real protection exit unlocks another scalp; terminal fallback
            # is accounting telemetry, not a synthetic reset.
            nxt = ex.get("protected_exit_timestamp")
            if not nxt:
                break
            earliest = nxt; idx += 1
    return out


def summarize(records: list[dict[str, Any]], denominator_contracts: set[str] | None = None) -> dict[str, Any]:
    n = len(records)
    denom = len(denominator_contracts or set())
    contracts = {r["contract"] for r in records}
    if not n:
        return {"signals": 0, "contracts": 0, "true_contract_denominator": denom,
                "true_contract_coverage": None if not denom else 0.0}
    asks = [float(r["entry_ask"]) for r in records]
    left = [float(r["seconds_left_at_entry"]) / 60 for r in records if r.get("seconds_left_at_entry") is not None]
    exits = [float(r["exit_gain"]) for r in records if r.get("exit_gain") is not None]
    protected = [r for r in records if r.get("protected_exit")]
    return {
        "signals": n,
        "contracts": len(contracts),
        "true_contract_denominator": denom,
        "true_contract_coverage": None if not denom else len(contracts & (denominator_contracts or set())) / denom,
        "plus5_rate": sum(bool(r.get("hit5")) for r in records) / n,
        "plus10_rate": sum(bool(r.get("hit10")) for r in records) / n,
        "plus20_rate": sum(bool(r.get("hit20")) for r in records) / n,
        "entry_le50_rate": sum(a <= .50 for a in asks) / n,
        "entry_ideal_25_35_rate": sum(.25 <= a <= .35 for a in asks) / n,
        "avg_entry_ask_c": 100 * statistics.fmean(asks),
        "median_entry_ask_c": 100 * statistics.median(asks),
        "avg_minutes_left": None if not left else statistics.fmean(left),
        "avg_executable_exit_gain_c": None if not exits else 100 * statistics.fmean(exits),
        "median_executable_exit_gain_c": None if not exits else 100 * statistics.median(exits),
        "positive_exit_rate": None if not exits else sum(x > 0 for x in exits) / len(exits),
        "protected_exit_rate": len(protected) / n,
        "avg_opportunities_per_covered_contract": n / len(contracts) if contracts else None,
        "max_opportunity_index": max(int(r.get("opportunity_index") or 0) for r in records),
        "fees_included": False,
        "orders": False,
    }


def analyze(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    split = contract_split(rows)
    out: list[dict[str, Any]] = []
    for ename, ep in ENTRY_POLICIES.items():
        for xname, xp in EXIT_POLICIES.items():
            recs = simulate_ladder(rows, ep, xp)
            result = {"entry_policy": ename, "exit_policy": xname}
            for part in ("DEVELOPMENT", "VALIDATION", "HOLDOUT"):
                dcontracts = {c for c, s in split.items() if s == part}
                z = [r for r in recs if split.get(r["contract"]) == part]
                result[part.lower()] = summarize(z, dcontracts)
            out.append(result)
    return {
        "version": VERSION,
        "status": "ENTRY_PROFIT_POLICY_GRID_READY",
        "entry_policies": ENTRY_POLICIES,
        "exit_policies": EXIT_POLICIES,
        "policy_grid": out,
        "holdout_report_only": True,
        "automatic_selection": False,
        "fees_included": False,
        "orders": False,
    }


def assert_integrity() -> None:
    if "orders" in ENTRY_POLICIES or "orders" in EXIT_POLICIES:
        raise RuntimeError("invalid policy namespace")
    if q.ARM_GAIN != 0.05 or q.GIVEBACK != 0.04:
        raise RuntimeError("legacy lifecycle drifted")


assert_integrity()
