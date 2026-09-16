#!/usr/bin/env python3
"""BTC15 Regime Tag Coverage Audit V1.1 — numeric boolean semantic repair.

RESEARCH ONLY | CAUSAL FEATURE AUDIT | NO OUTCOME SELECTION | NO ORDERS

V1.1 changes exactly one semantic behavior from V1: candidate-time boolean
features materialized as numeric 1.0/0.0 are interpreted as true/false
correctly.  Thresholds, features, causal allow-list, splits and regime priority
remain identical to V1.  Historical V1 is preserved as the bug-discovery run.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

import scalp_market_regime_ledger_v1 as regime_v1
import scalp_market_regime_ledger_v1_1 as regime_v11
import scalp_regime_tag_coverage_audit_v1 as audit_v1

VERSION = "BTC15_SCALP_REGIME_TAG_COVERAGE_AUDIT_V1_1_SEMANTIC_REPAIR"

NUMERIC_FEATURES = audit_v1.NUMERIC_FEATURES
BOOL_FEATURES = audit_v1.BOOL_FEATURES
AUDIT_ID_KEYS = audit_v1.AUDIT_ID_KEYS
AUDIT_ALLOWED_KEYS = audit_v1.AUDIT_ALLOWED_KEYS
FORBIDDEN_OUTCOME_KEYS = audit_v1.FORBIDDEN_OUTCOME_KEYS


def f(v: Any) -> float | None:
    return audit_v1.f(v)


def b(v: Any) -> bool:
    return regime_v11.truthy(v)


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
        "btc5_norm_ge_trend_min": n5 is not None and n5 >= regime_v1.TREND_BTC5_NORM_MIN,
        "btc15_norm_present": n15 is not None,
        "btc15_norm_ge_trend_min": n15 is not None and n15 >= regime_v1.TREND_BTC15_NORM_MIN,
        "ask15_present": ask15 is not None,
        "kalshi_response_muted": ask15 is not None and abs(ask15) <= regime_v1.KALSHI_LAG_ABS_ASK15_MAX,
        "btc5_norm_ge_accel_min": n5 is not None and n5 >= regime_v1.ACCEL_BTC5_NORM_MIN,
        "acceleration_present": accel is not None,
        "acceleration_gt_zero": accel is not None and accel > 0,
        "btc5_norm_lt_chop_max": n5 is not None and n5 < regime_v1.CHOP_BTC5_NORM_MAX,
        "btc15_norm_lt_chop_max": n15 is not None and n15 < regime_v1.CHOP_BTC15_NORM_MAX,
        "broken_agreement": (not agree5) or (not agree15),
        "reversal_evidence": not no_rev,
    }


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


def _tag_counts(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    overlap: Counter[str] = Counter(); primary: Counter[str] = Counter()
    for r in rows:
        tags = regime_v11.regime_tags(r)
        overlap.update(tags)
        primary[regime_v11.primary_regime(tags)] += 1
    return {"overlapping": dict(sorted(overlap.items())), "primary": dict(sorted(primary.items()))}


def split_audit(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    flags = [condition_flags(r) for r in rows]
    cond: dict[str, Any] = {}
    for key in sorted(flags[0]) if flags else []:
        n = sum(bool(x[key]) for x in flags)
        cond[key] = {"count": n, "rate": None if not rows else n / len(rows)}

    trend_steps = [
        ("structure_ok", lambda r: condition_flags(r)["structure_ok"]),
        ("agree5", lambda r: condition_flags(r)["agree5"]),
        ("agree15", lambda r: condition_flags(r)["agree15"]),
        ("no_reversal_evidence", lambda r: condition_flags(r)["no_reversal_evidence"]),
        (f"btc5_norm>={regime_v1.TREND_BTC5_NORM_MIN}", lambda r: condition_flags(r)["btc5_norm_ge_trend_min"]),
        (f"btc15_norm>={regime_v1.TREND_BTC15_NORM_MIN}", lambda r: condition_flags(r)["btc15_norm_ge_trend_min"]),
    ]
    lag_steps = trend_steps + [
        (f"abs(ask15)<={regime_v1.KALSHI_LAG_ABS_ASK15_MAX}", lambda r: condition_flags(r)["kalshi_response_muted"]),
    ]
    accel_steps = [
        ("structure_ok", lambda r: condition_flags(r)["structure_ok"]),
        ("agree5", lambda r: condition_flags(r)["agree5"]),
        ("no_reversal_evidence", lambda r: condition_flags(r)["no_reversal_evidence"]),
        (f"btc5_norm>={regime_v1.ACCEL_BTC5_NORM_MIN}", lambda r: condition_flags(r)["btc5_norm_ge_accel_min"]),
        ("acceleration>0", lambda r: condition_flags(r)["acceleration_gt_zero"]),
    ]
    rev_n = sum(reversal_evidence(r) for r in rows)
    return {
        "rows": len(rows),
        "numeric_features": {k: audit_v1.numeric_summary(rows, k) for k in NUMERIC_FEATURES},
        "boolean_features": {k: bool_summary(rows, k) for k in BOOL_FEATURES},
        "condition_pass_counts": cond,
        "tag_counts": _tag_counts(rows),
        "trend_funnel": audit_v1._sequential_funnel(rows, trend_steps),
        "kalshi_lag_funnel": audit_v1._sequential_funnel(rows, lag_steps),
        "acceleration_funnel": audit_v1._sequential_funnel(rows, accel_steps),
        "trend_blockers": audit_v1._blocker_summary(rows, trend_blockers),
        "kalshi_lag_blockers": audit_v1._blocker_summary(rows, lag_blockers),
        "acceleration_blockers": audit_v1._blocker_summary(rows, acceleration_blockers),
        "reversal_evidence_count": rev_n,
        "reversal_evidence_rate": None if not rows else rev_n / len(rows),
    }


def build_causal_opportunities(rows: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    return audit_v1.build_causal_opportunities(rows)


def analyze(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    clean, _ = build_causal_opportunities(rows)
    return {
        "version": VERSION,
        "status": "REGIME_TAG_COVERAGE_AUDIT_V1_1_READY",
        "all_serial_opportunities": split_audit(clean),
        "development": split_audit([r for r in clean if r.get("split") == "DEVELOPMENT"]),
        "validation": split_audit([r for r in clean if r.get("split") == "VALIDATION"]),
        "holdout": split_audit([r for r in clean if r.get("split") == "HOLDOUT"]),
        "audit_record_allowed_keys": sorted(AUDIT_ALLOWED_KEYS | {"split"}),
        "semantic_repair": {
            "numeric_float_boolean_flags_recognized": True,
            "thresholds_changed": False,
            "features_changed": False,
            "causal_allow_list_changed": False,
            "historical_v1_preserved": True,
        },
        "threshold_selection": False,
        "outcomes_used_for_blockers_or_distributions": False,
        "no_signal_suppression_or_rescue": True,
        "holdout_cannot_select_v1_1_rule": True,
        "automatic_promotion": False,
        "production_logic_changed": False,
        "shadow_only": True,
        "orders": False,
    }


def assert_integrity() -> None:
    audit_v1.assert_integrity()
    regime_v11.assert_integrity()
    if b(1.0) is not True or b(0.0) is not False:
        raise RuntimeError("numeric boolean audit repair failed")
    if AUDIT_ALLOWED_KEYS != audit_v1.AUDIT_ALLOWED_KEYS:
        raise RuntimeError("causal allow-list drifted")


assert_integrity()
