#!/usr/bin/env python3
"""BTC15 multi-objective scalp Pareto frontier V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Purpose
-------
Keep every validation configuration that is not strictly dominated across the
project's simultaneous goals instead of collapsing the search to one scalar
"winner" too early.

Objectives
----------
Maximize:
- executable +10c conversion rate
- true fully-observed contract coverage
- affordable <=50c true contract coverage
- average minutes remaining at entry (earlier is better)

Minimize:
- average executable entry ask in cents

This module does not fit models, change thresholds, promote a rule, or place
orders. It only audits rows already produced by the validation frontier.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

VERSION = "BTC15_SCALP_MULTIOBJECTIVE_PARETO_V1"

MAXIMIZE = (
    "plus10_rate",
    "true_contract_coverage",
    "affordable_true_contract_coverage_le50",
    "avg_minutes_left",
)
MINIMIZE = ("avg_entry_ask_c",)


def finite(v: Any) -> float | None:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def eligible(row: Mapping[str, Any], min_n: int = 1) -> bool:
    if row.get("error"):
        return False
    n = finite(row.get("n"))
    if n is None or n < min_n:
        return False
    required = MAXIMIZE + MINIMIZE
    return all(finite(row.get(k)) is not None for k in required)


def dominates(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    """True when a is at least as good on every objective and better on one."""
    weak = True
    strict = False
    for key in MAXIMIZE:
        av = finite(a.get(key)); bv = finite(b.get(key))
        if av is None or bv is None:
            return False
        if av < bv:
            weak = False
            break
        if av > bv:
            strict = True
    if not weak:
        return False
    for key in MINIMIZE:
        av = finite(a.get(key)); bv = finite(b.get(key))
        if av is None or bv is None:
            return False
        if av > bv:
            return False
        if av < bv:
            strict = True
    return strict


def pareto_frontier(rows: Iterable[Mapping[str, Any]], min_n: int = 1) -> list[dict[str, Any]]:
    candidates = [dict(r) for r in rows if eligible(r, min_n=min_n)]
    out: list[dict[str, Any]] = []
    for i, row in enumerate(candidates):
        if any(i != j and dominates(other, row) for j, other in enumerate(candidates)):
            continue
        x = dict(row)
        x["pareto_non_dominated"] = True
        out.append(x)
    out.sort(
        key=lambda r: (
            -(finite(r.get("plus10_rate")) or 0.0),
            -(finite(r.get("true_contract_coverage")) or 0.0),
            -(finite(r.get("affordable_true_contract_coverage_le50")) or 0.0),
            finite(r.get("avg_entry_ask_c")) or float("inf"),
            -(finite(r.get("avg_minutes_left")) or 0.0),
        )
    )
    return out


def summarize(frontier_rows: Iterable[Mapping[str, Any]], min_n: int = 1) -> dict[str, Any]:
    rows = [dict(r) for r in frontier_rows]
    p = pareto_frontier(rows, min_n=min_n)
    return {
        "version": VERSION,
        "orders": False,
        "manual_execution_only": True,
        "automatic_promotion": False,
        "objective_direction": {
            "maximize": list(MAXIMIZE),
            "minimize": list(MINIMIZE),
        },
        "input_rows": len(rows),
        "eligible_rows": sum(eligible(r, min_n=min_n) for r in rows),
        "pareto_rows": len(p),
        "pareto_frontier": p,
        "note": "Non-dominated validation configurations only; this report does not select a production rule.",
    }
