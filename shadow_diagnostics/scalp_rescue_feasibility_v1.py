#!/usr/bin/env python3
"""BTC15 coverage-rescue feasibility audit V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

This module takes the existing raw-baseline coverage-gap ledger and answers the
next development question without changing the baseline: which mechanical gap
classes actually contain recoverable executable movement?

All +5/+10/+20 fields here are hindsight labels used only for development. They
are never causal inputs and this report cannot promote a live rule.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

VERSION = "BTC15_SCALP_RESCUE_FEASIBILITY_V1"


def _rate(n: int, d: int) -> float | None:
    return None if d <= 0 else n / d


def summarize(ledger: list[Mapping[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in ledger:
        groups[str(row.get("reason") or "UNKNOWN")].append(row)

    by_reason: dict[str, dict[str, Any]] = {}
    for reason in sorted(groups):
        rows = groups[reason]
        n = len(rows)
        complete = sum(int((r.get("complete_candidate_paths") or 0) > 0) for r in rows)
        p5 = sum(bool(r.get("hindsight_any_plus5")) for r in rows)
        p10 = sum(bool(r.get("hindsight_any_plus10")) for r in rows)
        p20 = sum(bool(r.get("hindsight_any_plus20")) for r in rows)
        early10 = sum(bool(r.get("hindsight_early_plus10")) for r in rows)
        affordable10 = sum(bool(r.get("hindsight_affordable_plus10")) for r in rows)
        early_affordable10 = sum(bool(r.get("hindsight_early_affordable_plus10")) for r in rows)
        nonbaseline10 = sum(bool(r.get("hindsight_nonbaseline_plus10")) for r in rows)
        peaks = [float(r["best_hindsight_peak_c"]) for r in rows if r.get("best_hindsight_peak_c") is not None]
        by_reason[reason] = {
            "contracts": n,
            "with_complete_candidate_path": complete,
            "with_hindsight_plus5": p5,
            "with_hindsight_plus10": p10,
            "with_hindsight_plus20": p20,
            "with_hindsight_early_plus10": early10,
            "with_hindsight_affordable_plus10": affordable10,
            "with_hindsight_early_affordable_plus10": early_affordable10,
            "with_hindsight_nonbaseline_plus10": nonbaseline10,
            "hindsight_plus10_share": _rate(p10, n),
            "hindsight_early_affordable_plus10_share": _rate(early_affordable10, n),
            "best_hindsight_peak_c_max": None if not peaks else max(peaks),
            "hindsight_only_not_signal": True,
        }

    return {
        "version": VERSION,
        "contracts": len(ledger),
        "by_reason": by_reason,
        "orders": False,
        "automatic_promotion": False,
        "hindsight_labels_are_development_only": True,
        "forward_freeze_required": True,
    }
