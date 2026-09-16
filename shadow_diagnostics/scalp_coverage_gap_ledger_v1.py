#!/usr/bin/env python3
"""BTC15 scalp true-coverage gap ledger V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

For every fully observed contract, explain whether the selected specialist/core
+ coverage-rescue system covered it and, if not, where the gap occurred.

This is diagnostic only. It does not invent a signal or loosen a threshold.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping

VERSION = "BTC15_SCALP_COVERAGE_GAP_LEDGER_V1"


def finite(v: Any) -> float | None:
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else None
    except Exception:
        return None


def build_ledger(
    scored_rows: Iterable[Mapping[str, Any]],
    selected_rows: Iterable[Mapping[str, Any]],
    denominator_contracts: set[str],
    core_threshold: float,
    rescue_threshold: float,
) -> list[dict[str, Any]]:
    scored_by: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    selected_by: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for r in scored_rows:
        c = str(r.get("contract") or "")
        if c in denominator_contracts:
            scored_by[c].append(r)
    for r in selected_rows:
        c = str(r.get("contract") or "")
        if c in denominator_contracts:
            selected_by[c].append(r)

    out: list[dict[str, Any]] = []
    for contract in sorted(denominator_contracts):
        base = scored_by.get(contract, [])
        selected = selected_by.get(contract, [])
        specialists = [r for r in base if bool(r.get("specialist_union"))]
        quality = [(finite(r.get("quality_prob")), r) for r in base]
        quality = [(p, r) for p, r in quality if p is not None]
        best_p, best = max(quality, key=lambda x: x[0]) if quality else (None, None)
        core_candidates = [
            r for r in specialists
            if finite(r.get("quality_prob")) is not None
            and float(r["quality_prob"]) >= core_threshold
        ]
        affordable_base = [
            r for r in base
            if finite(r.get("entry_ask")) is not None and float(r["entry_ask"]) <= .50
        ]
        affordable_selected = [
            r for r in selected
            if finite(r.get("entry_ask")) is not None and float(r["entry_ask"]) <= .50
        ]

        if selected:
            tiers = {str(r.get("selection_tier") or "") for r in selected}
            coverage_status = "COVERED_CORE" if "CORE" in tiers else "COVERED_RESCUE"
            gap_reason = "NONE"
        elif not base:
            coverage_status = "UNCOVERED"
            gap_reason = "NO_BASELINE_CANDIDATE"
        elif not quality:
            coverage_status = "UNCOVERED"
            gap_reason = "NO_QUALITY_SCORE"
        elif best_p is not None and best_p < rescue_threshold:
            coverage_status = "UNCOVERED"
            gap_reason = "BELOW_RESCUE_THRESHOLD"
        else:
            coverage_status = "UNCOVERED"
            gap_reason = "SELECTOR_INCONSISTENCY_FAIL_CLOSED"

        if affordable_selected:
            affordable_status = "AFFORDABLE_COVERED"
        elif selected:
            affordable_status = "COVERED_ONLY_ABOVE_50C"
        elif affordable_base:
            affordable_status = "AFFORDABLE_CANDIDATE_NOT_SELECTED"
        else:
            affordable_status = "NO_AFFORDABLE_BASELINE_CANDIDATE"

        out.append({
            "contract": contract,
            "coverage_status": coverage_status,
            "gap_reason": gap_reason,
            "affordable_status": affordable_status,
            "baseline_candidate_n": len(base),
            "specialist_candidate_n": len(specialists),
            "core_candidate_n": len(core_candidates),
            "selected_n": len(selected),
            "affordable_baseline_candidate_n": len(affordable_base),
            "affordable_selected_n": len(affordable_selected),
            "best_quality_prob": best_p,
            "best_entry_ask": None if best is None else finite(best.get("entry_ask")),
            "best_primary_lane": None if best is None else str(best.get("primary_lane") or "UNCLASSIFIED"),
            "core_threshold": core_threshold,
            "rescue_threshold": rescue_threshold,
        })
    return out


def summarize(ledger: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(ledger)
    denom = len(rows)
    coverage = Counter(str(r.get("coverage_status") or "") for r in rows)
    gaps = Counter(str(r.get("gap_reason") or "") for r in rows if r.get("gap_reason") != "NONE")
    affordable = Counter(str(r.get("affordable_status") or "") for r in rows)
    covered = sum(v for k, v in coverage.items() if k.startswith("COVERED_"))
    cheap = affordable.get("AFFORDABLE_COVERED", 0)
    return {
        "version": VERSION,
        "orders": False,
        "automatic_promotion": False,
        "true_contract_denominator": denom,
        "covered_contracts": covered,
        "true_contract_coverage": None if not denom else covered / denom,
        "affordable_covered_contracts_le50": cheap,
        "affordable_true_contract_coverage_le50": None if not denom else cheap / denom,
        "coverage_status_counts": dict(coverage),
        "uncovered_gap_reason_counts": dict(gaps),
        "affordable_status_counts": dict(affordable),
    }
