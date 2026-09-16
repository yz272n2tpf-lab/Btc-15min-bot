#!/usr/bin/env python3
"""BTC15 market-regime tag coverage / feature availability audit V1.

RESEARCH ONLY | CAUSAL FEATURE DIAGNOSTIC | NO OUTCOME SELECTION | NO ORDERS

Explains why the predeclared regime tags are sparse using candidate-time fields
only.  Movement labels, protected exits, settlement, future path rows and
realized economics are never carried into the audit record.
"""
from __future__ import annotations

import math
import statistics
from collections import Counter
from typing import Any, Mapping

import scalp_event_schema_adapter_v1 as adapter
import scalp_market_regime_ledger_v1 as regime
import scalp_opportunity_quality_frontier_v1 as q

VERSION = "BTC15_SCALP_REGIME_TAG_COVERAGE_AUDIT_V1"

NUMERIC_FEATURES = (
    "btc_move5_norm", "btc_move15_norm", "acceleration", "ask_move15",
    "btc_move5_side", "btc_move15_side", "brti_move5_side", "brti_move15_side",
)
BOOL_FEATURES = (
    "structure_ok", "btc_brti_agree5", "btc_brti_agree15",
    "btc_against_side", "brti_against_side", "dual_reversal_evidence",
    "brti_primary_ok",
)
AUDIT_ID_KEYS = ("contract", "candidate_id", "opportunity_index", "side", "timestamp")
AUDIT_ALLOWED_KEYS = frozenset(NUMERIC_FEATURES + BOOL_FEATURES + AUDIT_ID_KEYS)
FORBIDDEN_OUTCOME_KEYS = (
    "plus5", "plus10", "plus20", "plus30", "peak_gain", "adverse_gain",
    "protected_exit_gain", "t10_sec", "t20_sec", "result", "outcome",
    "settle", "future", "exec_gain", "current_bid", "current_ask", "_candidate", "_paths",
)


def f(v: Any) -> float | None:
    x = q.f(v)
    return x if x is not None and math.isfinite(x) else None


def b(v: Any) -> bool:
    return bool(q.b(v))


def _quantile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    z = sorted(values)
    if len(z) == 1:
        return z[0]
    pos = (len(z) - 1) * p
    lo = int(math.floor(pos)); hi = int(math.ceil(pos))
    if lo == hi:
        return z[lo]
    frac = pos - lo
    return z[lo] * (1.0 - frac) + z[hi] * frac


def numeric_summary(rows: list[Mapping[str, Any]], key: str) -> dict[str, Any]:
    vals = [x for x in (f(r.get(key)) for r in rows) if x is not None]
    return {
        "total": len(rows), "present": len(vals), "missing": len(rows) - len(vals),
        "availability_rate": None if not rows else len(vals) / len(rows),
        "min": None if not vals else min(vals), "p10": _quantile(vals, .10),
        "p25": _quantile(vals, .25), "median": None if not vals else statistics.median(vals),
        "p75": _quantile(vals, .75), "p90": _quantile(vals, .90),
        "max": None if not vals else max(vals), "mean": None if not vals else statistics.fmean(vals),
    }


def bool_summary(rows: list[Mapping[str, Any]], key: str) -> dict[str, Any]:
    present = [r for r in rows if key in r and r.get(key) is not None]
    true_n = sum(b(r.get(key)) for r in present)
    return {
        "total": len(rows), "present": len(present), "missing": len(rows) - len(present),
        "availability_rate": None if not rows else len(present) / len(rows),
        "true_count": true_n, "false_count": len(present) - true_n,
        "true_rate": None if not present else true_n / len(present),
    }


def reversal_evidence(r: Mapping[str, Any]) -> bool:
    return b(r.get("dual_reversal_evidence")) or b(r.get("btc_against_side")) or b(r.get("brti_against_side"))


def condition_flags(r: Mapping[str, Any]) -> dict[str, bool]:
    n5 = f(r.get("btc_move5_norm")); n15 = f(r.get("btc_move15_norm"))
    accel = f(r.get("acceleration")); ask15 = f(r.get("ask_move15"))
    structure = b(r.get("structure_ok")); agree5 = b(r.get("btc_brti_agree5")); agree15 = b(r.get("btc_brti_agree15"))
    no_rev = not reversal_evidence(r)
    return {
        "structure_ok": structure,
        "agree5": agree5,
        "agree15": agree15,
        "no_reversal_evidence": no_rev,
        "btc5_norm_present": n5 is not None,
        "btc5_norm_ge_trend_min": n5 is not None and n5 >= regime.TREND_BTC5_NORM_MIN,
        "btc15_norm_present": n15 is not None,
        "btc15_norm_ge_trend_min": n15 is not None and n15 >= regime.TREND_BTC15_NORM_MIN,
        "ask15_present": ask15 is not None,
        "kalshi_response_muted": ask15 is not None and abs(ask15) <= regime.KALSHI_LAG_ABS_ASK15_MAX,
        "btc5_norm_ge_accel_min": n5 is not None and n5 >= regime.ACCEL_BTC5_NORM_MIN,
        "acceleration_present": accel is not None,
        "acceleration_gt_zero": accel is not None and accel > 0,
        "btc5_norm_lt_chop_max": n5 is not None and n5 < regime.CHOP_BTC5_NORM_MAX,
        "btc15_norm_lt_chop_max": n15 is not None and n15 < regime.CHOP_BTC15_NORM_MAX,
        "broken_agreement": (not agree5) or (not agree15),
        "reversal_evidence": not no_rev,
    }


def _sequential_funnel(rows: list[Mapping[str, Any]], steps: list[tuple[str, Any]]) -> dict[str, Any]:
    survivors = list(rows)
    out: dict[str, Any] = {"start": len(rows), "steps": []}
    for name, predicate in steps:
        survivors = [r for r in survivors if predicate(r)]
        out["steps"].append({"condition": name, "survivors": len(survivors),
                             "share_of_start": None if not rows else len(survivors) / len(rows)})
    out["final"] = len(survivors)
    return out


def trend_blockers(r: Mapping[str, Any]) -> list[str]:
    x = condition_flags(r); z: list[str] = []
    if not x["structure_ok"]: z.append("STRUCTURE_FALSE")
    if not x["agree5"]: z.append("AGREE5_FALSE")
    if not x["agree15"]: z.append("AGREE15_FALSE")
    if not x["no_reversal_evidence"]: z.append("REVERSAL_EVIDENCE")
    if not x["btc5_norm_present"]: z.append("BTC5_NORM_MISSING")
    elif not x["btc5_norm_ge_trend_min"]: z.append("BTC5_NORM_BELOW_0_60")
    if not x["btc15_norm_present"]: z.append("BTC15_NORM_MISSING")
    elif not x["btc15_norm_ge_trend_min"]: z.append("BTC15_NORM_BELOW_0_50")
    return z


def acceleration_blockers(r: Mapping[str, Any]) -> list[str]:
    x = condition_flags(r); z: list[str] = []
    if not x["structure_ok"]: z.append("STRUCTURE_FALSE")
    if not x["agree5"]: z.append("AGREE5_FALSE")
    if not x["no_reversal_evidence"]: z.append("REVERSAL_EVIDENCE")
    if not x["btc5_norm_present"]: z.append("BTC5_NORM_MISSING")
    elif not x["btc5_norm_ge_accel_min"]: z.append("BTC5_NORM_BELOW_0_75")
    if not x["acceleration_present"]: z.append("ACCELERATION_MISSING")
    elif not x["acceleration_gt_zero"]: z.append("ACCELERATION_NOT_POSITIVE")
    return z


def lag_blockers(r: Mapping[str, Any]) -> list[str]:
    z = trend_blockers(r); x = condition_flags(r)
    if not x["ask15_present"]: z.append("ASK15_MISSING")
    elif not x["kalshi_response_muted"]: z.append("ASK15_ABS_GT_0_02")
    return z


def _blocker_summary(rows: list[Mapping[str, Any]], fn: Any) -> dict[str, Any]:
    counts: Counter[str] = Counter(); zero = 0; multi = 0
    for r in rows:
        z = fn(r)
        if not z: zero += 1
        else:
            counts.update(z)
            if len(z) > 1: multi += 1
    return {
        "total": len(rows), "zero_blocker_count": zero,
        "zero_blocker_rate": None if not rows else zero / len(rows),
        "multi_blocker_count": multi,
        "blockers": [{"reason": k, "count": v, "share_of_rows": None if not rows else v / len(rows)}
                     for k, v in counts.most_common()],
    }


def _tag_counts(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    overlap: Counter[str] = Counter(); primary: Counter[str] = Counter()
    for r in rows:
        tags = regime.regime_tags(r); overlap.update(tags); primary[regime.primary_regime(tags)] += 1
    return {"overlapping": dict(sorted(overlap.items())), "primary": dict(sorted(primary.items()))}


def split_audit(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    flags = [condition_flags(r) for r in rows]
    cond = {}
    for key in sorted(flags[0]) if flags else []:
        n = sum(bool(x[key]) for x in flags); cond[key] = {"count": n, "rate": None if not rows else n / len(rows)}
    trend_steps = [
        ("structure_ok", lambda r: condition_flags(r)["structure_ok"]),
        ("agree5", lambda r: condition_flags(r)["agree5"]),
        ("agree15", lambda r: condition_flags(r)["agree15"]),
        ("no_reversal_evidence", lambda r: condition_flags(r)["no_reversal_evidence"]),
        (f"btc5_norm>={regime.TREND_BTC5_NORM_MIN}", lambda r: condition_flags(r)["btc5_norm_ge_trend_min"]),
        (f"btc15_norm>={regime.TREND_BTC15_NORM_MIN}", lambda r: condition_flags(r)["btc15_norm_ge_trend_min"]),
    ]
    lag_steps = trend_steps + [(f"abs(ask15)<={regime.KALSHI_LAG_ABS_ASK15_MAX}", lambda r: condition_flags(r)["kalshi_response_muted"])]
    accel_steps = [
        ("structure_ok", lambda r: condition_flags(r)["structure_ok"]),
        ("agree5", lambda r: condition_flags(r)["agree5"]),
        ("no_reversal_evidence", lambda r: condition_flags(r)["no_reversal_evidence"]),
        (f"btc5_norm>={regime.ACCEL_BTC5_NORM_MIN}", lambda r: condition_flags(r)["btc5_norm_ge_accel_min"]),
        ("acceleration>0", lambda r: condition_flags(r)["acceleration_gt_zero"]),
    ]
    rev_n = sum(reversal_evidence(r) for r in rows)
    return {
        "rows": len(rows),
        "numeric_features": {k: numeric_summary(rows, k) for k in NUMERIC_FEATURES},
        "boolean_features": {k: bool_summary(rows, k) for k in BOOL_FEATURES},
        "condition_pass_counts": cond, "tag_counts": _tag_counts(rows),
        "trend_funnel": _sequential_funnel(rows, trend_steps),
        "kalshi_lag_funnel": _sequential_funnel(rows, lag_steps),
        "acceleration_funnel": _sequential_funnel(rows, accel_steps),
        "trend_blockers": _blocker_summary(rows, trend_blockers),
        "kalshi_lag_blockers": _blocker_summary(rows, lag_blockers),
        "acceleration_blockers": _blocker_summary(rows, acceleration_blockers),
        "reversal_evidence_count": rev_n,
        "reversal_evidence_rate": None if not rows else rev_n / len(rows),
    }


def build_causal_opportunities(rows: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    adapted = adapter.adapt_rows(rows)
    opps = q.build_serial_opportunities(adapted)
    split = q.chronological_split(opps)
    clean: list[dict[str, Any]] = []
    for op in opps:
        # Explicit allow-list: private path/candidate objects and every outcome
        # field are discarded before the audit sees a record.
        z = {k: op.get(k) for k in AUDIT_ALLOWED_KEYS if k in op}
        z["split"] = split.get(str(op.get("contract") or ""), "DEVELOPMENT")
        clean.append(z)
    return clean, split


def analyze(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    clean, _ = build_causal_opportunities(rows)
    return {
        "version": VERSION, "status": "REGIME_TAG_COVERAGE_AUDIT_READY",
        "all_serial_opportunities": split_audit(clean),
        "development": split_audit([r for r in clean if r.get("split") == "DEVELOPMENT"]),
        "validation": split_audit([r for r in clean if r.get("split") == "VALIDATION"]),
        "holdout": split_audit([r for r in clean if r.get("split") == "HOLDOUT"]),
        "audit_record_allowed_keys": sorted(AUDIT_ALLOWED_KEYS | {"split"}),
        "thresholds_are_existing_v1_descriptive_thresholds": True,
        "threshold_selection": False, "outcomes_used_for_blockers_or_distributions": False,
        "no_signal_suppression_or_rescue": True, "automatic_promotion": False,
        "production_logic_changed": False, "shadow_only": True, "orders": False,
    }


def assert_integrity() -> None:
    bad = [k for k in AUDIT_ALLOWED_KEYS if any(tok in k.lower() for tok in FORBIDDEN_OUTCOME_KEYS)]
    if bad: raise RuntimeError(f"outcome leakage in audit allow-list: {bad}")
    if any(k.startswith("_") for k in AUDIT_ALLOWED_KEYS):
        raise RuntimeError("private serial objects are forbidden from audit records")


assert_integrity()
