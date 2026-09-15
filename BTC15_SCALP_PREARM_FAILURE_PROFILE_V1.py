#!/usr/bin/env python3
"""
BTC15 SCALP never-armed pre-entry failure profile V1.

HYPOTHESIS GENERATION ONLY | READ ONLY | SIGNAL ONLY | NO ORDERS

Compares frozen pre-entry telemetry for three observed path groups:
- PLUS10_OR_BETTER: peak executable move >= +10c
- ARMED_SUB10: peak >= +5c and < +10c
- UNARMED_SUB5: peak < +5c

This module SELECTS NO FEATURE AND NO THRESHOLD. It deliberately uses the full
current research sample only to generate hypotheses about the remaining false
starts. Any future rule inspired by this output must be frozen before a NEW
future forward cutoff and validated on data that does not exist yet.

Kalshi entry price and seconds-left are excluded from the profiled fields so this
cannot quietly become a price filter or fixed-time window study.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import BTC15_SCALP_UNARMED_TERMINAL_HANDOFF_AUDIT_V1 as lifecycle
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_PREARM_FAILURE_PROFILE_V1"
FIELDS = (
    "btc5",
    "btc15",
    "btc30",
    "brti5",
    "brti15",
    "accel",
    "btc5_norm",
    "btc15_norm",
    "recent_btc_range60",
    "confirm_count",
    "ask5",
    "ask15",
)


def _group(peak: float | None) -> str:
    if peak is not None and peak >= 0.10 - 1e-12:
        return "PLUS10_OR_BETTER"
    if peak is not None and peak >= 0.05 - 1e-12:
        return "ARMED_SUB10"
    return "UNARMED_SUB5"


def _summary(values: list[float]) -> dict[str, Any]:
    xs = sorted(float(x) for x in values)
    if not xs:
        return {"n": 0, "median": None, "mean": None, "min": None, "max": None}
    return {
        "n": len(xs),
        "median": statistics.median(xs),
        "mean": statistics.fmean(xs),
        "min": xs[0],
        "max": xs[-1],
    }


def summarize_records(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    xs = [dict(r) for r in records]
    groups = ("PLUS10_OR_BETTER", "ARMED_SUB10", "UNARMED_SUB5")
    counts = {g: sum(str(r.get("group") or "") == g for r in xs) for g in groups}
    field_profiles: dict[str, Any] = {}

    for field in FIELDS:
        per_group = {}
        for g in groups:
            vals = [
                float(v) for r in xs
                if str(r.get("group") or "") == g
                and (v := research.f(r.get(field))) is not None
            ]
            per_group[g] = _summary(vals)
        win_med = per_group["PLUS10_OR_BETTER"].get("median")
        fail_med = per_group["UNARMED_SUB5"].get("median")
        armed_med = per_group["ARMED_SUB10"].get("median")
        field_profiles[field] = {
            "groups": per_group,
            "unarmed_minus_plus10_median": (
                None if win_med is None or fail_med is None else float(fail_med) - float(win_med)
            ),
            "armed_sub10_minus_plus10_median": (
                None if win_med is None or armed_med is None else float(armed_med) - float(win_med)
            ),
        }

    return {
        "version": VERSION,
        "research_only": True,
        "orders": False,
        "manual_execution_only": True,
        "records_n": len(xs),
        "group_counts": counts,
        "fields_predeclared": list(FIELDS),
        "field_profiles": field_profiles,
        "hypothesis_generation_only": True,
        "feature_selected": False,
        "threshold_selected": False,
        "existing_holdout_reused_for_next_rule": False,
        "new_future_holdout_required": True,
        "entry_price_filter_applied": False,
        "fixed_time_window_applied": False,
        "protected_thresholds_changed": False,
        "stop_loss_rule_selected": False,
        "auto_promote_allowed": False,
        "actionable_now": False,
    }


def audit(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(r) for r in rows]
    projected = lifecycle.audit(rows).get("projected_ladder") or []
    candidates = {
        research.cid(c): dict(c)
        for c in forward.forward_candidates(rows)
        if research.cid(c)
    }
    records = []
    for p in projected:
        cid = str(p.get("candidate_id") or "")
        c = candidates.get(cid)
        if c is None:
            continue
        peak = research.f(p.get("peak_gain"))
        rec = {
            "contract": str(p.get("contract") or research.contract(c)),
            "candidate_id": cid,
            "opportunity_index": int(p.get("opportunity_index") or 0),
            "group": _group(peak),
        }
        for field in FIELDS:
            rec[field] = research.f(c.get(field))
        records.append(rec)
    out = summarize_records(records)
    out["source"] = "ENDED_UNARMED_SERIAL_LIFECYCLE_PROJECTION"
    return out


if __name__ == "__main__":
    print(f"{VERSION} | import/use audit(rows) | HYPOTHESIS GENERATION ONLY | NO ORDERS")
