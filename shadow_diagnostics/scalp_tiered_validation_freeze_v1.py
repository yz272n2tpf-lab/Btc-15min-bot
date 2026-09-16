#!/usr/bin/env python3
"""BTC15 tiered scalp validation-freeze audit V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Instead of demanding one configuration simultaneously maximize precision and
coverage, freeze three distinct validation-selected roles, then report each on
HOLDOUT without retuning:

- PRECISION_CORE: highest +10c conversion with >=40% validation contract coverage.
- BALANCED_90: highest validation coverage among configs with >=90% +10c conversion.
- COVERAGE_FRONTIER: highest validation contract coverage regardless of +10c rate.

The role definitions are fixed here before holdout evaluation. Holdout is
report-only; none of these results auto-promotes a production rule.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np

import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_frontier_v1 as v1
import scalp_specialist_union_frontier_v2 as v2

VERSION = "BTC15_SCALP_TIERED_VALIDATION_FREEZE_V1"
MIN_VALIDATION_N = 12
MIN_VALIDATION_CONTRACTS = 8
PRECISION_CORE_MIN_COVERAGE = 0.40
BALANCED_MIN_PLUS10 = 0.90


def finite(v: Any) -> float | None:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def eligible_rows(frontier: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r0 in frontier:
        r = dict(r0)
        if r.get("error"):
            continue
        if (finite(r.get("n")) or 0) < MIN_VALIDATION_N:
            continue
        if (finite(r.get("covered_contracts")) or 0) < MIN_VALIDATION_CONTRACTS:
            continue
        if finite(r.get("plus10_rate")) is None or finite(r.get("true_contract_coverage")) is None:
            continue
        out.append(r)
    return out


def _common_quality_key(r: Mapping[str, Any]) -> tuple[float, float, float, float]:
    return (
        finite(r.get("affordable_true_contract_coverage_le50")) or 0.0,
        -(finite(r.get("avg_entry_ask_c")) or 999.0),
        finite(r.get("avg_minutes_left")) or 0.0,
        finite(r.get("n")) or 0.0,
    )


def select_roles(frontier: list[Mapping[str, Any]]) -> dict[str, dict[str, Any] | None]:
    rows = eligible_rows(frontier)

    precision_pool = [r for r in rows if (finite(r.get("true_contract_coverage")) or 0.0) >= PRECISION_CORE_MIN_COVERAGE]
    precision = None if not precision_pool else max(
        precision_pool,
        key=lambda r: (
            finite(r.get("plus10_rate")) or 0.0,
            finite(r.get("true_contract_coverage")) or 0.0,
            *_common_quality_key(r),
        ),
    )

    balanced_pool = [r for r in rows if (finite(r.get("plus10_rate")) or 0.0) >= BALANCED_MIN_PLUS10]
    balanced = None if not balanced_pool else max(
        balanced_pool,
        key=lambda r: (
            finite(r.get("true_contract_coverage")) or 0.0,
            finite(r.get("plus10_rate")) or 0.0,
            *_common_quality_key(r),
        ),
    )

    coverage = None if not rows else max(
        rows,
        key=lambda r: (
            finite(r.get("true_contract_coverage")) or 0.0,
            finite(r.get("plus10_rate")) or 0.0,
            *_common_quality_key(r),
        ),
    )

    return {
        "PRECISION_CORE": precision,
        "BALANCED_90": balanced,
        "COVERAGE_FRONTIER": coverage,
    }


def _model_by_name(name: str):
    for model_name, model in q.models():
        if model_name == name:
            return model
    return None


def evaluate_holdout(
    opps: list[dict[str, Any]],
    split: Mapping[str, str],
    config: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    dev = [r for r in opps if split.get(r.get("contract")) == "DEVELOPMENT"]
    hold = [r for r in opps if split.get(r.get("contract")) == "HOLDOUT"]
    hold_contracts = {c for c, s in split.items() if s == "HOLDOUT"}
    if not dev or not hold or not hold_contracts:
        return None, []
    model = _model_by_name(str(config.get("model") or ""))
    if model is None:
        return None, []

    xd = q.to_frame(dev)
    xh = q.to_frame(hold)
    model.fit(xd[q.FEATURES], xd["plus10"].astype(int))
    ph = model.predict_proba(xh[q.FEATURES])[:, 1]
    scored_hold: list[dict[str, Any]] = []
    for r, p in zip(hold, ph):
        x = dict(r)
        x["quality_prob"] = float(p)
        scored_hold.append(x)

    selected = v2.select_core_rescue(
        scored_hold,
        hold_contracts,
        float(config["core_threshold"]),
        float(config["rescue_threshold"]),
    )
    score = v1.score_with_true_coverage(selected, hold_contracts)
    score.update(v2.tier_diagnostics(selected, hold_contracts))
    score.update({
        "model": config.get("model"),
        "core_threshold_frozen_from_validation": config.get("core_threshold"),
        "rescue_threshold_frozen_from_validation": config.get("rescue_threshold"),
        "holdout_is_report_only": True,
        "automatic_promotion": False,
    })
    return score, selected


def audit(
    opps: list[dict[str, Any]],
    split: Mapping[str, str],
    frontier: list[Mapping[str, Any]],
) -> dict[str, Any]:
    roles = select_roles(frontier)
    out: dict[str, Any] = {}
    for role, config in roles.items():
        if config is None:
            out[role] = {"validation_selection": None, "holdout": None}
            continue
        holdout, _ = evaluate_holdout(opps, split, config)
        out[role] = {
            "validation_selection": dict(config),
            "holdout": holdout,
        }
    return {
        "version": VERSION,
        "orders": False,
        "manual_execution_only": True,
        "role_definitions": {
            "PRECISION_CORE": f"maximize validation +10c with coverage >= {PRECISION_CORE_MIN_COVERAGE:.0%}",
            "BALANCED_90": f"maximize validation coverage with +10c >= {BALANCED_MIN_PLUS10:.0%}",
            "COVERAGE_FRONTIER": "maximize validation contract coverage",
        },
        "roles": out,
        "holdout_is_report_only": True,
        "automatic_promotion": False,
        "forward_freeze_required_before_any_promotion": True,
    }
