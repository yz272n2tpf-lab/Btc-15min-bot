#!/usr/bin/env python3
"""BTC15 causal market-regime ledger V1.1 — semantic boolean repair.

RESEARCH ONLY | DESCRIPTIVE ONLY | NO ORDERS | NO THRESHOLD SELECTION

V1.1 changes exactly one semantic behavior from V1:
- candidate features materialize booleans as numeric 1.0/0.0;
- V1 reparsed them with a helper that recognized string "1" but not "1.0";
- V1.1 recognizes finite numeric nonzero values as true.

No regime threshold, feature, priority, lifecycle, split or outcome definition is
changed.  V1 historical results remain preserved and are not overwritten.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

import scalp_economics_exit_cert_v1 as econ
import scalp_event_schema_adapter_v1 as adapter
import scalp_market_regime_ledger_v1 as v1
import scalp_opportunity_quality_frontier_v1 as q

VERSION = "BTC15_SCALP_MARKET_REGIME_LEDGER_V1_1_SEMANTIC_REPAIR"


def truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    try:
        x = float(v)
        if math.isfinite(x):
            return x != 0.0
    except Exception:
        pass
    return str(v).strip().lower() in {"true", "yes", "y", "t"}


def f(v: Any) -> float | None:
    return v1.f(v)


def regime_tags(op: Mapping[str, Any]) -> list[str]:
    tags: list[str] = []
    structure = truthy(op.get("structure_ok"))
    agree5 = truthy(op.get("btc_brti_agree5"))
    agree15 = truthy(op.get("btc_brti_agree15"))
    against = truthy(op.get("btc_against_side")) or truthy(op.get("brti_against_side"))
    reversal = truthy(op.get("dual_reversal_evidence")) or against
    n5 = f(op.get("btc_move5_norm")); n15 = f(op.get("btc_move15_norm"))
    accel = f(op.get("acceleration")); ask15 = f(op.get("ask_move15"))

    if reversal:
        tags.append("REVERSAL_HAZARD")

    trend = bool(
        structure and agree5 and agree15 and not reversal
        and n5 is not None and n5 >= v1.TREND_BTC5_NORM_MIN
        and n15 is not None and n15 >= v1.TREND_BTC15_NORM_MIN
    )
    if trend:
        tags.append("TREND_ALIGNED")

    if trend and ask15 is not None and abs(ask15) <= v1.KALSHI_LAG_ABS_ASK15_MAX:
        tags.append("KALSHI_LAG")

    if (
        structure and agree5 and not reversal
        and n5 is not None and n5 >= v1.ACCEL_BTC5_NORM_MIN
        and accel is not None and accel > 0
    ):
        tags.append("ACCELERATION_BURST")

    if (
        not reversal and not trend
        and n5 is not None and n15 is not None
        and n5 < v1.CHOP_BTC5_NORM_MAX and n15 < v1.CHOP_BTC15_NORM_MAX
        and (not agree5 or not agree15)
    ):
        tags.append("CHOP_LOW_CONVICTION")

    if not tags:
        tags.append("OTHER")
    return tags


def primary_regime(tags: list[str]) -> str:
    s = set(tags)
    return next((name for name in v1.PRIMARY_PRIORITY if name in s), "OTHER")


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


def analyze(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    records, _ = build_tagged_records(rows)
    development = v1._split_report(records, "DEVELOPMENT")
    validation = v1._split_report(records, "VALIDATION")
    holdout = v1._split_report(records, "HOLDOUT")
    return {
        "version": VERSION,
        "status": "MARKET_REGIME_LEDGER_V1_1_SEMANTIC_REPAIR_READY",
        "semantic_repair": {
            "numeric_float_boolean_flags_recognized": True,
            "example_old_v1_truthy_1_0": v1.truthy(1.0),
            "example_v1_1_truthy_1_0": truthy(1.0),
            "thresholds_changed": False,
            "features_changed": False,
            "primary_priority_changed": False,
            "split_changed": False,
            "historical_v1_preserved": True,
        },
        "tag_definitions": {
            "TREND_ALIGNED": {"btc5_norm_min": v1.TREND_BTC5_NORM_MIN, "btc15_norm_min": v1.TREND_BTC15_NORM_MIN,
                              "requires_structure_and_btc_brti_agree_5_15": True, "rejects_reversal_evidence": True},
            "KALSHI_LAG": {"requires_trend_aligned": True, "abs_ask15_max": v1.KALSHI_LAG_ABS_ASK15_MAX},
            "ACCELERATION_BURST": {"btc5_norm_min": v1.ACCEL_BTC5_NORM_MIN, "acceleration_gt_zero": True,
                                   "requires_structure_and_agree5": True, "rejects_reversal_evidence": True},
            "REVERSAL_HAZARD": {"any_against_side_or_dual_reversal": True},
            "CHOP_LOW_CONVICTION": {"btc5_norm_max_exclusive": v1.CHOP_BTC5_NORM_MAX,
                                     "btc15_norm_max_exclusive": v1.CHOP_BTC15_NORM_MAX,
                                     "requires_broken_5_or_15_agreement": True},
            "OTHER": {"fallback_only": True},
        },
        "primary_priority": list(v1.PRIMARY_PRIORITY),
        "development": development,
        "validation": validation,
        "holdout": holdout,
        "validation_to_holdout_shift": v1.validation_to_holdout_shift(validation, holdout),
        "holdout_is_descriptive_after_semantic_repair": True,
        "holdout_cannot_select_v1_1_rule": True,
        "outcomes_never_define_tags": True,
        "no_threshold_selection": True,
        "no_signal_suppression_or_rescue": True,
        "automatic_promotion": False,
        "production_logic_changed": False,
        "shadow_only": True,
        "orders": False,
    }


def assert_integrity() -> None:
    if truthy(1.0) is not True or truthy(0.0) is not False:
        raise RuntimeError("numeric flag semantic repair failed")
    if any([
        v1.TREND_BTC5_NORM_MIN != 0.60,
        v1.TREND_BTC15_NORM_MIN != 0.50,
        v1.ACCEL_BTC5_NORM_MIN != 0.75,
        v1.CHOP_BTC5_NORM_MAX != 0.45,
        v1.CHOP_BTC15_NORM_MAX != 0.45,
        v1.KALSHI_LAG_ABS_ASK15_MAX != 0.02,
    ]):
        raise RuntimeError("V1 thresholds drifted")


assert_integrity()
