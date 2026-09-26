#!/usr/bin/env python3
"""BTC15 scalp Coverage Rescue V1.

RESEARCH / SHADOW ONLY | SIGNAL ONLY | NO ORDERS

Frozen rescue purpose
---------------------
Preserve the existing baseline unchanged (seconds_left >=120 and BTC30 >=15),
while adding one narrow causal rescue lane for candidates that miss baseline
ONLY because BTC30 is moderately below 15. The rule is intentionally simple,
interpretable, and fixed before the prospective forward window.

Mechanical scoring repair
-------------------------
A missing RESULT row is not predictive edge. If PATH telemetry exists, the
scorer may reconcile the path outcome for evaluation and tag it
PATH_RECONCILED. This does not alter the signal trigger. If PATH is unavailable,
the signal remains unresolved and cannot be scored as a win or loss.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

import scalp_event_schema_adapter_v1 as adapter
import scalp_opportunity_quality_frontier_v1 as q

VERSION = "BTC15_SCALP_COVERAGE_RESCUE_V1_FROZEN"

# Baseline remains q.MIN_SECONDS_LEFT=120 and q.MIN_BTC30=15.
RESCUE_MIN_SECONDS_LEFT = 120.0
RESCUE_MIN_BTC30 = 8.0
RESCUE_MAX_BTC30_EXCLUSIVE = 15.0
RESCUE_MAX_ENTRY_ASK = 0.50
RESCUE_MIN_BTC5_NORM = 0.60
RESCUE_MIN_CONFIRM_COUNT = 2.0
RESCUE_MAX_ABS_ASK15 = 0.02

# Forward qualification gates. These are review gates, never auto-promotion.
MIN_FUTURE_CONTRACTS_FOR_CERTIFICATION = 100
MIN_SCOREABLE_RESCUE_SIGNALS = 8
MIN_RESCUE_PLUS10_RATE = 0.60
MAX_UNION_PLUS10_DEGRADATION = 0.03
MIN_RESCUE_AVG_MINUTES_LEFT = 6.0
TARGET_TRUE_CONTRACT_COVERAGE = 0.90


def finite(v: Any) -> float | None:
    x = q.f(v)
    return x if x is not None and math.isfinite(x) else None


def truthy(v: Any) -> bool:
    return bool(q.b(v))


def canonical_candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    return adapter.adapt_row(row)


def rescue_features(row: Mapping[str, Any]) -> dict[str, float]:
    r = canonical_candidate(row)
    return q.candidate_features(r)


def rescue_qualified(row: Mapping[str, Any]) -> bool:
    """Frozen causal rescue rule. No PATH/RESULT/future field is consulted."""
    r = canonical_candidate(row)
    side = str(r.get("side") or "").strip().upper()
    left = finite(r.get("seconds_left"))
    btc30 = q.btc30(r)
    ask = finite(r.get("entry_ask"))
    confirm = finite(r.get("confirm_count"))
    feats = q.candidate_features(r)
    btc5_norm = finite(feats.get("btc_move5_norm"))
    ask15 = finite(feats.get("ask_move15"))

    if side not in {"UP", "DOWN"}:
        return False
    if left is None or left < RESCUE_MIN_SECONDS_LEFT:
        return False
    if btc30 is None or not (RESCUE_MIN_BTC30 <= btc30 < RESCUE_MAX_BTC30_EXCLUSIVE):
        return False
    # Must fail the baseline specifically on BTC30; never duplicate a baseline call.
    if q.baseline_qualified(r):
        return False
    if ask is None or ask > RESCUE_MAX_ENTRY_ASK:
        return False
    if btc5_norm is None or btc5_norm < RESCUE_MIN_BTC5_NORM:
        return False
    if confirm is None or confirm < RESCUE_MIN_CONFIRM_COUNT:
        return False
    if ask15 is None or abs(ask15) > RESCUE_MAX_ABS_ASK15:
        return False
    if not bool(feats.get("structure_ok")):
        return False
    if not bool(feats.get("brti_primary_ok")):
        return False
    if not bool(feats.get("btc_brti_agree5")) or not bool(feats.get("btc_brti_agree15")):
        return False
    if bool(feats.get("btc_against_side")) or bool(feats.get("brti_against_side")):
        return False
    if bool(feats.get("dual_reversal_evidence")):
        return False
    return True


def index_tape(rows: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], set[str]]:
    adapted = adapter.adapt_rows(rows)
    paths: dict[str, list[dict[str, Any]]] = defaultdict(list)
    results: set[str] = set()
    for row in adapted:
        if q.typ(row) == "PATH" and q.cid(row):
            paths[q.cid(row)].append(dict(row))
        elif q.typ(row) == "RESULT" and q.cid(row):
            results.add(q.cid(row))
    for candidate_id in paths:
        paths[candidate_id].sort(key=lambda r: q.dt(r.get("timestamp_utc")))
    return adapted, paths, results


def outcome_record(candidate: Mapping[str, Any], paths: list[Mapping[str, Any]], has_result: bool) -> dict[str, Any]:
    pm = q.measure_path(candidate, paths)
    scoreable = pm.peak_gain is not None
    return {
        "scoreable": scoreable,
        "score_source": ("RESULT_PATH" if has_result else "PATH_RECONCILED") if scoreable else "UNRESOLVED_NO_PATH_OUTCOME",
        "plus5": None if not scoreable else int(pm.peak_gain >= .05),
        "plus10": None if not scoreable else int(pm.peak_gain >= .10),
        "plus20": None if not scoreable else int(pm.peak_gain >= .20),
        "peak_gain": pm.peak_gain,
        "adverse_gain": pm.adverse_gain,
        "protected_exit_gain": pm.exit_gain,
        "protected_exit_time_utc": pm.exit_time_utc,
        "t10_sec": pm.t10_sec,
        "t20_sec": pm.t20_sec,
    }


def first_rescue_signals(rows: Iterable[Mapping[str, Any]], eligible_contracts: set[str] | None = None) -> list[dict[str, Any]]:
    adapted, paths, results = index_tape(rows)
    by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in adapted:
        if q.typ(row) != "CANDIDATE" or not q.cid(row) or not q.contract(row):
            continue
        c = q.contract(row)
        if eligible_contracts is not None and c not in eligible_contracts:
            continue
        if rescue_qualified(row):
            by_contract[c].append(dict(row))

    out: list[dict[str, Any]] = []
    for c, candidates in by_contract.items():
        candidates.sort(key=lambda r: q.dt(r.get("timestamp_utc")))
        cand = candidates[0]  # one frozen rescue signal max per contract
        feats = q.candidate_features(cand)
        rec: dict[str, Any] = {
            "contract": c,
            "candidate_id": q.cid(cand),
            "timestamp": q.dt(cand.get("timestamp_utc")),
            "side": str(cand.get("side") or "").strip().upper(),
            "signal_type": "COVERAGE_RESCUE_V1",
            "selection_tier": "COVERAGE_RESCUE_V1",
            "entry_ask": finite(cand.get("entry_ask")),
            "seconds_left": finite(cand.get("seconds_left")),
            "minutes_left": None if finite(cand.get("seconds_left")) is None else float(finite(cand.get("seconds_left"))) / 60.0,
            "btc_move30_side": q.btc30(cand),
            "rule_version": VERSION,
        }
        rec.update(feats)
        rec.update(outcome_record(cand, paths.get(q.cid(cand), []), q.cid(cand) in results))
        out.append(rec)
    return out


def reconciled_baseline_serial(rows: Iterable[Mapping[str, Any]], eligible_contracts: set[str] | None = None) -> list[dict[str, Any]]:
    """Baseline trigger unchanged; only evaluation can reconcile missing RESULT via PATH."""
    adapted, paths, results = index_tape(rows)
    by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in adapted:
        if q.typ(row) == "CANDIDATE" and q.cid(row) and q.contract(row) and q.baseline_qualified(row):
            c = q.contract(row)
            if eligible_contracts is None or c in eligible_contracts:
                by_contract[c].append(dict(row))

    out: list[dict[str, Any]] = []
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    for c, candidates in by_contract.items():
        candidates.sort(key=lambda r: q.dt(r.get("timestamp_utc")))
        earliest = epoch
        used: set[str] = set()
        idx = 1
        while True:
            cand = next((r for r in candidates if q.cid(r) not in used and q.dt(r.get("timestamp_utc")) > earliest), None)
            if cand is None:
                break
            used.add(q.cid(cand))
            p = paths.get(q.cid(cand), [])
            outcome = outcome_record(cand, p, q.cid(cand) in results)
            feats = q.candidate_features(cand)
            rec: dict[str, Any] = {
                "contract": c,
                "candidate_id": q.cid(cand),
                "timestamp": q.dt(cand.get("timestamp_utc")),
                "opportunity_index": idx,
                "side": str(cand.get("side") or "").strip().upper(),
                "signal_type": "BASELINE",
                "entry_ask": finite(cand.get("entry_ask")),
                "seconds_left": finite(cand.get("seconds_left")),
                "minutes_left": None if finite(cand.get("seconds_left")) is None else float(finite(cand.get("seconds_left"))) / 60.0,
                "btc_move30_side": q.btc30(cand),
            }
            rec.update(feats)
            rec.update(outcome)
            out.append(rec)
            # No lookahead reset. We advance only when the observed path proves the protected exit.
            if not outcome.get("protected_exit_time_utc"):
                break
            earliest = q.dt(outcome["protected_exit_time_utc"])
            idx += 1
    return out


def score_summary(rows: list[Mapping[str, Any]], denominator_contracts: set[str]) -> dict[str, Any]:
    contracts = {str(r.get("contract") or "") for r in rows} & denominator_contracts
    scoreable = [r for r in rows if bool(r.get("scoreable"))]
    asks = [finite(r.get("entry_ask")) for r in rows]
    asks = [x for x in asks if x is not None]
    mins = [finite(r.get("minutes_left")) for r in rows]
    mins = [x for x in mins if x is not None]
    affordable_contracts = {
        str(r.get("contract") or "") for r in rows
        if finite(r.get("entry_ask")) is not None and float(finite(r.get("entry_ask"))) <= .50
    } & denominator_contracts
    def rate(name: str) -> float | None:
        vals = [int(r[name]) for r in scoreable if r.get(name) is not None]
        return None if not vals else sum(vals) / len(vals)
    denom = len(denominator_contracts)
    return {
        "signals": len(rows),
        "scoreable_signals": len(scoreable),
        "unresolved_signals": len(rows) - len(scoreable),
        "path_reconciled_signals": sum(r.get("score_source") == "PATH_RECONCILED" for r in rows),
        "covered_contracts": len(contracts),
        "true_contract_denominator": denom,
        "true_contract_coverage": None if not denom else len(contracts) / denom,
        "affordable_contracts_le50": len(affordable_contracts),
        "affordable_true_contract_coverage_le50": None if not denom else len(affordable_contracts) / denom,
        "plus5_rate_scoreable": rate("plus5"),
        "plus10_rate_scoreable": rate("plus10"),
        "plus20_rate_scoreable": rate("plus20"),
        "avg_entry_ask_c": None if not asks else 100.0 * statistics.fmean(asks),
        "median_entry_ask_c": None if not asks else 100.0 * statistics.median(asks),
        "avg_minutes_left": None if not mins else statistics.fmean(mins),
        "median_minutes_left": None if not mins else statistics.median(mins),
    }


def qualification(baseline: dict[str, Any], rescue: dict[str, Any], union: dict[str, Any], future_contracts: int, incremental_rescue_contracts: int) -> dict[str, Any]:
    sample_ready = future_contracts >= MIN_FUTURE_CONTRACTS_FOR_CERTIFICATION and (rescue.get("scoreable_signals") or 0) >= MIN_SCOREABLE_RESCUE_SIGNALS
    b10 = baseline.get("plus10_rate_scoreable")
    u10 = union.get("plus10_rate_scoreable")
    r10 = rescue.get("plus10_rate_scoreable")
    degradation_ok = b10 is not None and u10 is not None and u10 >= b10 - MAX_UNION_PLUS10_DEGRADATION
    conditions = {
        "sample_ready": sample_ready,
        "true_coverage_ge_90": (union.get("true_contract_coverage") or 0.0) >= TARGET_TRUE_CONTRACT_COVERAGE,
        "rescue_plus10_ge_60": r10 is not None and r10 >= MIN_RESCUE_PLUS10_RATE,
        "union_plus10_degradation_le_3pp": degradation_ok,
        "rescue_avg_ask_le50": rescue.get("avg_entry_ask_c") is not None and rescue["avg_entry_ask_c"] <= 50.0,
        "rescue_avg_minutes_left_ge6": rescue.get("avg_minutes_left") is not None and rescue["avg_minutes_left"] >= MIN_RESCUE_AVG_MINUTES_LEFT,
        "incremental_rescue_contracts": incremental_rescue_contracts,
    }
    return {
        "certification_sample_ready": sample_ready,
        "qualification_pass": bool(sample_ready and all(v for k, v in conditions.items() if k != "incremental_rescue_contracts")),
        "conditions": conditions,
        "automatic_promotion": False,
    }


def frozen_rule() -> dict[str, Any]:
    return {
        "version": VERSION,
        "seconds_left_min": RESCUE_MIN_SECONDS_LEFT,
        "btc30_min": RESCUE_MIN_BTC30,
        "btc30_max_exclusive": RESCUE_MAX_BTC30_EXCLUSIVE,
        "entry_ask_max": RESCUE_MAX_ENTRY_ASK,
        "btc5_norm_min": RESCUE_MIN_BTC5_NORM,
        "confirm_count_min": RESCUE_MIN_CONFIRM_COUNT,
        "abs_ask15_max": RESCUE_MAX_ABS_ASK15,
        "require_structure_ok": True,
        "require_brti_primary_ok": True,
        "require_btc_brti_agree5": True,
        "require_btc_brti_agree15": True,
        "reject_against_side": True,
        "reject_dual_reversal": True,
        "one_rescue_signal_max_per_contract": True,
        "baseline_unchanged": True,
        "orders": False,
    }
