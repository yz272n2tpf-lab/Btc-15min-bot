#!/usr/bin/env python3
"""
BTC15 SCALP normalized-momentum tightening research V1.

RESEARCH ONLY | READ ONLY | SIGNAL ONLY | NO ORDERS

Predeclared question
--------------------
Can either of the frozen collector's two explicitly telemetry-only normalized
momentum fields improve the serial SCALP +10c hit rate without materially
sacrificing winners or opportunity coverage?

Only these two fields are tested:
- btc5_norm  = side-aligned BTC 5s move / recent BTC 60s range
- btc15_norm = side-aligned BTC 15s move / recent BTC 60s range

The frozen collector source explicitly marks these fields as telemetry-only and
not used for V1 eligibility. We deliberately DO NOT retest raw btc5/btc15,
btc30, BRTI, acceleration, confirmation persistence, Kalshi price, or time-left.
Those are either already part of the frozen gate, already holdout-tested, or are
outside this research question.

Validation discipline
---------------------
- Same serial lifecycle projection used by the current shadow review.
- Chronological split by contract: first 60% DEVELOPMENT, last 40% HOLDOUT.
- DEVELOPMENT tests only the 10th and 20th percentile floors of each predeclared
  feature; percentile values are computed from DEVELOPMENT only.
- A development nominee must:
    * have >=20 development records,
    * have >=90% feature availability,
    * retain >=90% of +10c winners,
    * retain >=80% of selected opportunities,
    * improve +10c precision by >=3 percentage points.
- HOLDOUT support requires:
    * >=12 holdout records,
    * >=90% feature availability,
    * retain >=90% of holdout +10c winners,
    * retain >=80% of holdout opportunities,
    * improve holdout +10c precision by >=5 percentage points.

Even HOLDOUT support does NOT authorize promotion. It only earns a continued
forward-shadow review. No price filter, fixed time window, stop-loss, order path,
or automatic strategy mutation exists here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import BTC15_SCALP_UNARMED_TERMINAL_HANDOFF_AUDIT_V1 as lifecycle
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_NORMALIZED_MOMENTUM_RESEARCH_V1"
FEATURES = ("btc5_norm", "btc15_norm")
DEV_QUANTILES = (0.10, 0.20)
MIN_DEV_N = 20
MIN_HOLDOUT_N = 12
MIN_FEATURE_AVAILABILITY = 0.90
MIN_WINNER_RETENTION = 0.90
MIN_SELECTED_RETENTION = 0.80
MIN_DEV_PRECISION_LIFT = 0.03
MIN_HOLDOUT_PRECISION_LIFT = 0.05


def _records(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(r) for r in rows]
    projected = lifecycle.audit(rows).get("projected_ladder") or []
    cands = {
        research.cid(c): dict(c)
        for c in forward.forward_candidates(rows)
        if research.cid(c)
    }
    out: list[dict[str, Any]] = []
    for p in projected:
        cid = str(p.get("candidate_id") or "")
        c = cands.get(cid)
        if c is None:
            continue
        out.append({
            "contract": str(p.get("contract") or research.contract(c)),
            "candidate_id": cid,
            "timestamp_utc": str(c.get("timestamp_utc") or ""),
            "plus10": bool(p.get("plus10")),
            "plus20": bool(p.get("plus20")),
            "btc5_norm": research.f(c.get("btc5_norm")),
            "btc15_norm": research.f(c.get("btc15_norm")),
            "entry_price_is_telemetry_only": True,
            "seconds_left_is_telemetry_only": True,
        })
    out.sort(key=lambda r: research.dt(r.get("timestamp_utc")))
    return out


def _contract_split(records: list[Mapping[str, Any]]) -> dict[str, str]:
    first: dict[str, datetime] = {}
    for r in records:
        contract = str(r.get("contract") or "")
        if not contract:
            continue
        t = research.dt(r.get("timestamp_utc"))
        if contract not in first or t < first[contract]:
            first[contract] = t
    ordered = sorted(first, key=lambda c: first[c])
    cut = max(1, min(len(ordered), int(round(len(ordered) * 0.60)))) if ordered else 0
    return {c: ("DEVELOPMENT" if i < cut else "HOLDOUT") for i, c in enumerate(ordered)}


def _baseline(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    xs = [dict(r) for r in records]
    winners = [r for r in xs if r.get("plus10")]
    return {
        "n": len(xs),
        "plus10_n": len(winners),
        "plus10_rate": None if not xs else len(winners) / len(xs),
        "plus20_rate": None if not xs else sum(bool(r.get("plus20")) for r in xs) / len(xs),
    }


def _quantile_floor(values: list[float], q: float) -> float | None:
    xs = sorted(float(x) for x in values)
    if not xs:
        return None
    q = max(0.0, min(1.0, float(q)))
    # Deterministic lower-index empirical quantile; threshold is derived only
    # from DEVELOPMENT feature values and never from HOLDOUT.
    idx = int((len(xs) - 1) * q)
    return xs[idx]


def _cell(records: list[Mapping[str, Any]], feature: str, threshold: float) -> dict[str, Any]:
    xs = [dict(r) for r in records]
    available = [r for r in xs if research.f(r.get(feature)) is not None]
    kept = [r for r in available if float(research.f(r.get(feature))) >= float(threshold)]
    winners = [r for r in xs if r.get("plus10")]
    kept_winners = [r for r in kept if r.get("plus10")]
    base_rate = None if not xs else len(winners) / len(xs)
    kept_rate = None if not kept else len(kept_winners) / len(kept)
    return {
        "feature": feature,
        "threshold": float(threshold),
        "baseline_n": len(xs),
        "available_n": len(available),
        "feature_availability": None if not xs else len(available) / len(xs),
        "n": len(kept),
        "plus10_n": len(kept_winners),
        "plus10_rate": kept_rate,
        "plus20_rate": None if not kept else sum(bool(r.get("plus20")) for r in kept) / len(kept),
        "plus10_winner_retention": None if not winners else len(kept_winners) / len(winners),
        "selected_share_retained": None if not xs else len(kept) / len(xs),
        "plus10_precision_lift": (
            None if kept_rate is None or base_rate is None else kept_rate - base_rate
        ),
    }


def analyze_records(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    records = [dict(r) for r in records]
    split = _contract_split(records)
    dev = [r for r in records if split.get(str(r.get("contract") or "")) == "DEVELOPMENT"]
    hold = [r for r in records if split.get(str(r.get("contract") or "")) == "HOLDOUT"]
    dev_baseline = _baseline(dev)
    hold_baseline = _baseline(hold)

    development_cells: list[dict[str, Any]] = []
    for feature in FEATURES:
        values = [
            float(v) for r in dev
            if (v := research.f(r.get(feature))) is not None
        ]
        for q in DEV_QUANTILES:
            threshold = _quantile_floor(values, q)
            if threshold is None:
                continue
            cell = _cell(dev, feature, threshold)
            cell["development_quantile"] = q
            cell["eligible_for_nomination"] = bool(
                len(dev) >= MIN_DEV_N
                and cell.get("feature_availability") is not None
                and float(cell["feature_availability"]) >= MIN_FEATURE_AVAILABILITY
                and cell.get("plus10_winner_retention") is not None
                and float(cell["plus10_winner_retention"]) >= MIN_WINNER_RETENTION
                and cell.get("selected_share_retained") is not None
                and float(cell["selected_share_retained"]) >= MIN_SELECTED_RETENTION
                and cell.get("plus10_precision_lift") is not None
                and float(cell["plus10_precision_lift"]) >= MIN_DEV_PRECISION_LIFT
            )
            development_cells.append(cell)

    eligible = [c for c in development_cells if c.get("eligible_for_nomination")]
    eligible.sort(
        key=lambda c: (
            float(c.get("plus10_precision_lift") or 0.0),
            float(c.get("plus10_winner_retention") or 0.0),
            float(c.get("selected_share_retained") or 0.0),
            -float(c.get("development_quantile") or 0.0),
        ),
        reverse=True,
    )
    nominee = dict(eligible[0]) if eligible else None

    holdout_nominee = None
    if nominee is not None:
        holdout_nominee = _cell(
            hold,
            str(nominee["feature"]),
            float(nominee["threshold"]),
        )
        holdout_nominee["development_quantile"] = nominee.get("development_quantile")

    holdout_review_ready = bool(
        nominee is not None
        and holdout_nominee is not None
        and len(hold) >= MIN_HOLDOUT_N
        and holdout_nominee.get("feature_availability") is not None
        and float(holdout_nominee["feature_availability"]) >= MIN_FEATURE_AVAILABILITY
    )
    holdout_supports_nominee = bool(
        holdout_review_ready
        and holdout_nominee is not None
        and holdout_nominee.get("plus10_winner_retention") is not None
        and float(holdout_nominee["plus10_winner_retention"]) >= MIN_WINNER_RETENTION
        and holdout_nominee.get("selected_share_retained") is not None
        and float(holdout_nominee["selected_share_retained"]) >= MIN_SELECTED_RETENTION
        and holdout_nominee.get("plus10_precision_lift") is not None
        and float(holdout_nominee["plus10_precision_lift"]) >= MIN_HOLDOUT_PRECISION_LIFT
    )

    return {
        "version": VERSION,
        "research_only": True,
        "orders": False,
        "manual_execution_only": True,
        "features_predeclared": list(FEATURES),
        "development_quantiles_predeclared": list(DEV_QUANTILES),
        "records_n": len(records),
        "development_n": len(dev),
        "holdout_n": len(hold),
        "development_baseline": dev_baseline,
        "holdout_baseline": hold_baseline,
        "development_cells": development_cells,
        "development_nominee": nominee,
        "holdout_nominee": holdout_nominee,
        "holdout_review_ready": holdout_review_ready,
        "holdout_supports_nominee": holdout_supports_nominee,
        "minimum_feature_availability": MIN_FEATURE_AVAILABILITY,
        "minimum_winner_retention": MIN_WINNER_RETENTION,
        "minimum_selected_retention": MIN_SELECTED_RETENTION,
        "minimum_dev_precision_lift": MIN_DEV_PRECISION_LIFT,
        "minimum_holdout_precision_lift": MIN_HOLDOUT_PRECISION_LIFT,
        "entry_price_filter_applied": False,
        "fixed_time_window_applied": False,
        "protected_thresholds_changed": False,
        "stop_loss_rule_selected": False,
        "raw_btc_or_brti_level_filter_applied": False,
        "auto_promote_allowed": False,
        "actionable_now": False,
        "note": (
            "Holdout support earns continued forward-shadow review only. It does not "
            "authorize a strategy change or suppress live candidates."
        ),
    }


def audit(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    out = analyze_records(_records(rows))
    out["source"] = "ENDED_UNARMED_SERIAL_LIFECYCLE_PROJECTION"
    return out


if __name__ == "__main__":
    print(f"{VERSION} | import/use audit(rows) | RESEARCH ONLY | NO ORDERS")
