#!/usr/bin/env python3
"""
BTC15 SCALP sub-10c outcome taxonomy V1.

DESCRIPTIVE RESEARCH ONLY | READ ONLY | SIGNAL ONLY | NO ORDERS

Purpose
-------
The frozen blueprint reports +10c as a meaningful-move target, but +10c is not a
trade-entry gate and the review gate deliberately never defined "every scalp must
hit +10c" as acceptance. This audit decomposes the opportunities that finish
below +10c so we know whether they are:
- never-armed moves that stayed below +5c,
- smaller +5c-to-<10c moves that armed protection and later hit the existing
  protected EXIT,
- smaller +5c-to-<10c moves that armed protection but never produced a validated
  4c-giveback EXIT during the observed path.

No entry rule, price filter, time rule, protection threshold, or order behavior
is changed. The audit does NOT relabel +5c as a validated trading success; it
only reports observed path structure.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from typing import Any, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import BTC15_SCALP_UNARMED_TERMINAL_HANDOFF_AUDIT_V1 as lifecycle
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_SUB10_OUTCOME_TAXONOMY_V1"


def _median(xs):
    vals = [float(x) for x in xs if x is not None]
    return statistics.median(vals) if vals else None


def _peak_band(peak: float | None) -> str:
    if peak is None:
        return "NO_PATH_VALUE"
    if peak < 0.05 - 1e-12:
        return "LT_5C"
    if peak < 0.08 - 1e-12:
        return "5_TO_LT_8C"
    if peak < 0.10 - 1e-12:
        return "8_TO_LT_10C"
    if peak < 0.15 - 1e-12:
        return "10_TO_LT_15C"
    return "15C_PLUS"


def _classification(peak: float | None, terminal_kind: str) -> str:
    if peak is not None and peak >= 0.10 - 1e-12:
        return "PLUS10_OR_BETTER"
    if peak is None or peak < 0.05 - 1e-12:
        return "UNARMED_SUB5"
    if terminal_kind == "PROTECTED_EXIT":
        return "ARMED_SUB10_PROTECTED_EXIT"
    return "ARMED_SUB10_NO_VALIDATED_EXIT"


def summarize_records(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    xs = [dict(r) for r in records]
    for r in xs:
        peak = research.f(r.get("peak_gain"))
        r["peak_band"] = _peak_band(peak)
        r["classification"] = _classification(peak, str(r.get("terminal_kind") or ""))

    counts = Counter(str(r.get("classification") or "") for r in xs)
    bands = Counter(str(r.get("peak_band") or "") for r in xs)
    plus5 = [r for r in xs if research.f(r.get("peak_gain")) is not None and float(r["peak_gain"]) >= 0.05 - 1e-12]
    plus10 = [r for r in xs if research.f(r.get("peak_gain")) is not None and float(r["peak_gain"]) >= 0.10 - 1e-12]
    sub10 = [r for r in xs if r.get("classification") != "PLUS10_OR_BETTER"]
    protected_sub10 = [r for r in xs if r.get("classification") == "ARMED_SUB10_PROTECTED_EXIT"]
    positive_exit_sub10 = [
        r for r in protected_sub10
        if research.f(r.get("protected_exit_gain")) is not None
        and float(r["protected_exit_gain"]) > 0
    ]

    category_stats = {}
    for category in sorted(counts):
        rows = [r for r in xs if r.get("classification") == category]
        category_stats[category] = {
            "n": len(rows),
            "median_peak_gain": _median(r.get("peak_gain") for r in rows),
            "median_adverse_gain": _median(r.get("adverse_gain") for r in rows),
            "median_protected_exit_gain": _median(r.get("protected_exit_gain") for r in rows),
        }

    return {
        "version": VERSION,
        "research_only": True,
        "orders": False,
        "manual_execution_only": True,
        "n": len(xs),
        "plus5_n": len(plus5),
        "plus5_rate": None if not xs else len(plus5) / len(xs),
        "plus10_n": len(plus10),
        "plus10_rate": None if not xs else len(plus10) / len(xs),
        "sub10_n": len(sub10),
        "unarmed_sub5_n": counts.get("UNARMED_SUB5", 0),
        "armed_sub10_n": counts.get("ARMED_SUB10_PROTECTED_EXIT", 0) + counts.get("ARMED_SUB10_NO_VALIDATED_EXIT", 0),
        "armed_sub10_protected_exit_n": counts.get("ARMED_SUB10_PROTECTED_EXIT", 0),
        "armed_sub10_no_validated_exit_n": counts.get("ARMED_SUB10_NO_VALIDATED_EXIT", 0),
        "positive_protected_exit_sub10_n": len(positive_exit_sub10),
        "positive_protected_exit_sub10_rate_among_protected_sub10": (
            None if not protected_sub10 else len(positive_exit_sub10) / len(protected_sub10)
        ),
        "peak_band_counts": dict(sorted(bands.items())),
        "classification_counts": dict(sorted(counts.items())),
        "category_stats": category_stats,
        "records": xs,
        "plus10_is_reporting_target_not_entry_gate": True,
        "plus5_is_not_reclassified_as_validated_trade_success": True,
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
    paths: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if research.typ(r) == "PATH" and research.cid(r):
            paths[research.cid(r)].append(dict(r))

    records = []
    for p in projected:
        cid = str(p.get("candidate_id") or "")
        c = candidates.get(cid)
        if c is None:
            continue
        pm = research.measure_path(c, research.path_rows_for(c, paths))
        records.append({
            "contract": str(p.get("contract") or research.contract(c)),
            "candidate_id": cid,
            "opportunity_index": int(p.get("opportunity_index") or 0),
            "terminal_kind": str(p.get("terminal_kind") or ""),
            "peak_gain": pm.peak_gain,
            "adverse_gain": pm.adverse_gain,
            "protected_exit_gain": pm.exit_gain,
            "entry_price_is_telemetry_only": True,
        })
    out = summarize_records(records)
    out["source"] = "ENDED_UNARMED_SERIAL_LIFECYCLE_PROJECTION"
    return out


if __name__ == "__main__":
    print(f"{VERSION} | import/use audit(rows) | DESCRIPTIVE ONLY | NO ORDERS")
