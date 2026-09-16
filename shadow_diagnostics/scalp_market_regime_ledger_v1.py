#!/usr/bin/env python3
"""BTC15 causal market-regime ledger V1.

RESEARCH ONLY | DESCRIPTIVE | NO ORDERS | NO THRESHOLD SELECTION

Regime tags are based only on information available at the candidate timestamp.
They are deliberately predeclared and may overlap. Outcomes/economics are used
only after tagging to describe how the existing ladder behaved under each state.

This module does not rescue, suppress, rank, promote, or retune any signal.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Mapping

import scalp_economics_exit_cert_v1 as econ
import scalp_event_schema_adapter_v1 as adapter
import scalp_opportunity_quality_frontier_v1 as q

VERSION = "BTC15_SCALP_MARKET_REGIME_LEDGER_V1"

# Fixed causal tag thresholds. These are descriptive labels, not trade gates.
TREND_BTC5_NORM_MIN = 0.60
TREND_BTC15_NORM_MIN = 0.50
ACCEL_BTC5_NORM_MIN = 0.75
CHOP_BTC5_NORM_MAX = 0.45
CHOP_BTC15_NORM_MAX = 0.45
KALSHI_LAG_ABS_ASK15_MAX = 0.02

PRIMARY_PRIORITY = (
    "REVERSAL_HAZARD",
    "KALSHI_LAG",
    "ACCELERATION_BURST",
    "TREND_ALIGNED",
    "CHOP_LOW_CONVICTION",
    "OTHER",
)


def f(v: Any) -> float | None:
    x = q.f(v)
    return x if x is not None and math.isfinite(x) else None


def truthy(v: Any) -> bool:
    return bool(q.b(v))


def regime_tags(op: Mapping[str, Any]) -> list[str]:
    """Assign causal, overlapping regime labels to one serial opportunity."""
    tags: list[str] = []
    structure = truthy(op.get("structure_ok"))
    agree5 = truthy(op.get("btc_brti_agree5"))
    agree15 = truthy(op.get("btc_brti_agree15"))
    against = truthy(op.get("btc_against_side")) or truthy(op.get("brti_against_side"))
    reversal = truthy(op.get("dual_reversal_evidence")) or against
    n5 = f(op.get("btc_move5_norm"))
    n15 = f(op.get("btc_move15_norm"))
    accel = f(op.get("acceleration"))
    ask15 = f(op.get("ask_move15"))

    if reversal:
        tags.append("REVERSAL_HAZARD")

    trend = bool(
        structure and agree5 and agree15 and not reversal
        and n5 is not None and n5 >= TREND_BTC5_NORM_MIN
        and n15 is not None and n15 >= TREND_BTC15_NORM_MIN
    )
    if trend:
        tags.append("TREND_ALIGNED")

    if trend and ask15 is not None and abs(ask15) <= KALSHI_LAG_ABS_ASK15_MAX:
        tags.append("KALSHI_LAG")

    if (
        structure and agree5 and not reversal
        and n5 is not None and n5 >= ACCEL_BTC5_NORM_MIN
        and accel is not None and accel > 0
    ):
        tags.append("ACCELERATION_BURST")

    if (
        not reversal and not trend
        and n5 is not None and n15 is not None
        and n5 < CHOP_BTC5_NORM_MAX and n15 < CHOP_BTC15_NORM_MAX
        and (not agree5 or not agree15)
    ):
        tags.append("CHOP_LOW_CONVICTION")

    if not tags:
        tags.append("OTHER")
    return tags


def primary_regime(tags: list[str]) -> str:
    s = set(tags)
    return next((name for name in PRIMARY_PRIORITY if name in s), "OTHER")


def build_tagged_records(rows: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    adapted = adapter.adapt_rows(rows)
    opps = q.build_serial_opportunities(adapted)
    split = q.chronological_split(opps)
    out: list[dict[str, Any]] = []
    for op in opps:
        tags = regime_tags(op)
        rec = econ._op_record(op)
        rec["tags"] = tags
        rec["primary_regime"] = primary_regime(tags)
        rec["split"] = split.get(str(op.get("contract") or ""), "DEVELOPMENT")
        out.append(rec)
    return out, split


def compact_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    s = econ.summarize(records)
    ten = (((s.get("fee_adjusted_protected_exits") or {}).get("10") or {}).get("TAKER_TAKER") or {})
    one = (((s.get("fee_adjusted_protected_exits") or {}).get("1") or {}).get("TAKER_TAKER") or {})
    return {
        "signals": s.get("signals"),
        "contracts": s.get("contracts"),
        "plus5_rate": s.get("plus5_rate"),
        "plus10_rate": s.get("plus10_rate"),
        "plus20_rate": s.get("plus20_rate"),
        "protected_exit_rate": s.get("protected_exit_rate"),
        "protected_exit_signals": s.get("protected_exit_signals"),
        "avg_entry_ask_c": s.get("avg_entry_ask_c"),
        "entry_le50_rate": s.get("entry_le50_rate"),
        "avg_minutes_left": s.get("avg_minutes_left"),
        "avg_gross_protected_gain_c": s.get("avg_gross_protected_gain_c"),
        "avg_capture_efficiency": s.get("avg_capture_efficiency"),
        "one_lot_taker_taker_avg_net_c": one.get("avg_net_gain_c_per_contract"),
        "one_lot_taker_taker_positive_net_rate": one.get("positive_net_rate"),
        "ten_lot_taker_taker_avg_net_c": ten.get("avg_net_gain_c_per_contract"),
        "ten_lot_taker_taker_median_net_c": ten.get("median_net_gain_c_per_contract"),
        "ten_lot_taker_taker_positive_net_rate": ten.get("positive_net_rate"),
        "max_opportunity_index": s.get("max_opportunity_index"),
    }


def _group(records: list[dict[str, Any]], *, primary: bool) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if primary:
        for r in records:
            groups[str(r.get("primary_regime") or "OTHER")].append(r)
    else:
        for r in records:
            for tag in r.get("tags") or ["OTHER"]:
                groups[str(tag)].append(r)
    return {name: compact_metrics(z) for name, z in sorted(groups.items())}


def _by_index(records: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for idx in sorted({int(r.get("opportunity_index") or 0) for r in records}):
        z = [r for r in records if int(r.get("opportunity_index") or 0) == idx]
        out[str(idx)] = {
            "overall": compact_metrics(z),
            "primary_regimes": _group(z, primary=True),
        }
    return out


def _split_report(records: list[dict[str, Any]], split_name: str) -> dict[str, Any]:
    z = [r for r in records if r.get("split") == split_name]
    return {
        "overall": compact_metrics(z),
        "primary_regimes": _group(z, primary=True),
        "overlapping_tags": _group(z, primary=False),
        "by_opportunity_index": _by_index(z),
    }


def _delta(a: Any, b: Any) -> float | None:
    try:
        x = float(a); y = float(b)
        if math.isfinite(x) and math.isfinite(y):
            return y - x
    except Exception:
        pass
    return None


def validation_to_holdout_shift(validation: Mapping[str, Any], holdout: Mapping[str, Any]) -> dict[str, Any]:
    vr = validation.get("primary_regimes") or {}
    hr = holdout.get("primary_regimes") or {}
    out: dict[str, Any] = {}
    for name in sorted(set(vr) | set(hr)):
        v = vr.get(name) or {}; h = hr.get(name) or {}
        out[name] = {
            "validation_signals": v.get("signals", 0),
            "holdout_signals": h.get("signals", 0),
            "plus10_rate_delta_holdout_minus_validation": _delta(v.get("plus10_rate"), h.get("plus10_rate")),
            "protected_exit_rate_delta": _delta(v.get("protected_exit_rate"), h.get("protected_exit_rate")),
            "ten_lot_avg_net_c_delta": _delta(v.get("ten_lot_taker_taker_avg_net_c"), h.get("ten_lot_taker_taker_avg_net_c")),
            "avg_entry_ask_c_delta": _delta(v.get("avg_entry_ask_c"), h.get("avg_entry_ask_c")),
            "descriptive_only": True,
        }
    return out


def analyze(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    records, _ = build_tagged_records(rows)
    development = _split_report(records, "DEVELOPMENT")
    validation = _split_report(records, "VALIDATION")
    holdout = _split_report(records, "HOLDOUT")
    return {
        "version": VERSION,
        "status": "MARKET_REGIME_LEDGER_READY",
        "tag_definitions": {
            "TREND_ALIGNED": {"btc5_norm_min": TREND_BTC5_NORM_MIN, "btc15_norm_min": TREND_BTC15_NORM_MIN,
                              "requires_structure_and_btc_brti_agree_5_15": True, "rejects_reversal_evidence": True},
            "KALSHI_LAG": {"requires_trend_aligned": True, "abs_ask15_max": KALSHI_LAG_ABS_ASK15_MAX},
            "ACCELERATION_BURST": {"btc5_norm_min": ACCEL_BTC5_NORM_MIN, "acceleration_gt_zero": True,
                                   "requires_structure_and_agree5": True, "rejects_reversal_evidence": True},
            "REVERSAL_HAZARD": {"any_against_side_or_dual_reversal": True},
            "CHOP_LOW_CONVICTION": {"btc5_norm_max_exclusive": CHOP_BTC5_NORM_MAX,
                                     "btc15_norm_max_exclusive": CHOP_BTC15_NORM_MAX,
                                     "requires_broken_5_or_15_agreement": True},
            "OTHER": {"fallback_only": True},
        },
        "primary_priority": list(PRIMARY_PRIORITY),
        "development": development,
        "validation": validation,
        "holdout": holdout,
        "validation_to_holdout_shift": validation_to_holdout_shift(validation, holdout),
        "outcomes_never_define_tags": True,
        "no_threshold_selection": True,
        "no_signal_suppression_or_rescue": True,
        "automatic_promotion": False,
        "production_logic_changed": False,
        "shadow_only": True,
        "orders": False,
    }


def assert_integrity() -> None:
    if q.ARM_GAIN != 0.05 or q.GIVEBACK != 0.04:
        raise RuntimeError("legacy lifecycle drifted")
    if any(x <= 0 or x >= 1 for x in (TREND_BTC5_NORM_MIN, TREND_BTC15_NORM_MIN,
                                      ACCEL_BTC5_NORM_MIN, CHOP_BTC5_NORM_MAX,
                                      CHOP_BTC15_NORM_MAX)):
        raise RuntimeError("normalized regime threshold out of range")


assert_integrity()
