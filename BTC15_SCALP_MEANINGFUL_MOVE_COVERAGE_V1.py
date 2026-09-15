#!/usr/bin/env python3
"""
BTC15 SCALP meaningful-move coverage audit V1.

RESEARCH ONLY | READ ONLY | SIGNAL ONLY | NO ORDERS

The user's scalp objective is not merely to emit candidates; it is to surface
as many distinct, serially actionable 10c+ moves as possible during each
15-minute contract. This audit therefore scores every completed
frozen-qualified candidate by its observed executable peak and combines that
with the existing serial-ladder coverage classification.

Important:
- +10c is a reporting/coverage target, NOT an entry-price gate.
- Kalshi entry price remains telemetry only.
- Overlapping candidates are reported separately and are NOT automatically
  treated as missed serial trades.
- Blocked-by-failed-prearm candidates are separated from true post-exit misses.
- No threshold is tuned or promoted by this module.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping

import BTC15_SCALP_BLUEPRINT_COVERAGE_AUDIT_V1 as coverage
import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import BTC15_SCALP_UNARMED_TERMINAL_HANDOFF_AUDIT_V1 as handoff

VERSION = "BTC15_SCALP_MEANINGFUL_MOVE_COVERAGE_V1"


def _paths(rows: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if research.typ(r) == "PATH" and research.cid(r):
            out[research.cid(r)].append(dict(r))
    return out


def audit(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(r) for r in rows]
    cov = coverage.audit(rows)
    lifecycle = handoff.audit(rows)
    paths = _paths(rows)

    records: list[dict[str, Any]] = []
    for rec in cov.get("records") or []:
        x = dict(rec)
        cid = str(x.get("candidate_id") or "")
        candidate = next(
            (
                r for r in rows
                if research.typ(r) == "CANDIDATE" and research.cid(r) == cid
            ),
            None,
        )
        pm = None
        if candidate is not None and x.get("completed"):
            pm = research.measure_path(candidate, research.path_rows_for(candidate, paths))
        peak = None if pm is None else pm.peak_gain
        x["peak_gain"] = peak
        x["meaningful_10c"] = bool(peak is not None and peak >= 0.10 - 1e-12)
        x["meaningful_20c"] = bool(peak is not None and peak >= 0.20 - 1e-12)
        x["entry_price_is_telemetry_only"] = True
        records.append(x)

    completed = [r for r in records if r.get("completed")]
    meaningful10 = [r for r in completed if r.get("meaningful_10c")]
    meaningful20 = [r for r in completed if r.get("meaningful_20c")]
    selected = [r for r in completed if r.get("classification") == "SELECTED_SERIAL_SCALP"]
    selected10 = [r for r in selected if r.get("meaningful_10c")]
    selected_sub10 = [r for r in selected if not r.get("meaningful_10c")]

    cls10 = Counter(str(r.get("classification") or "") for r in meaningful10)
    cls20 = Counter(str(r.get("classification") or "") for r in meaningful20)

    # Serially addressable 10c moves exclude overlaps by definition. Overlaps
    # are still reported so a future parallel/re-entry design can study them.
    serial_addressable10 = [
        r for r in meaningful10
        if r.get("classification") != "OVERLAP_WHILE_PRIOR_SCALP_ACTIVE"
    ]
    baseline_captured10 = [
        r for r in serial_addressable10
        if r.get("classification") == "SELECTED_SERIAL_SCALP"
    ]

    projected_ids = {
        str(r.get("candidate_id") or "")
        for r in lifecycle.get("projected_ladder") or []
    }
    projected_captured10 = [r for r in serial_addressable10 if str(r.get("candidate_id") or "") in projected_ids]

    return {
        "version": VERSION,
        "research_only": True,
        "orders": False,
        "manual_execution_only": True,
        "entry_price_filter_applied": False,
        "price_is_telemetry_only": True,
        "completed_frozen_qualified_candidates": len(completed),
        "completed_meaningful_10c_candidates": len(meaningful10),
        "completed_meaningful_20c_candidates": len(meaningful20),
        "selected_serial_scalps": len(selected),
        "selected_meaningful_10c": len(selected10),
        "selected_sub10": len(selected_sub10),
        "selected_10c_precision": None if not selected else len(selected10) / len(selected),
        "meaningful_10c_by_classification": dict(sorted(cls10.items())),
        "meaningful_20c_by_classification": dict(sorted(cls20.items())),
        "overlap_meaningful_10c": cls10.get("OVERLAP_WHILE_PRIOR_SCALP_ACTIVE", 0),
        "blocked_prearm_meaningful_10c": cls10.get("BLOCKED_BY_FAILED_PREARM_NO_EXIT", 0),
        "true_post_exit_missed_meaningful_10c": cls10.get("POST_EXIT_MISSED_QUALIFIED", 0),
        "serial_addressable_meaningful_10c": len(serial_addressable10),
        "baseline_serial_captured_meaningful_10c": len(baseline_captured10),
        "baseline_serial_10c_capture_rate": (
            None if not serial_addressable10 else len(baseline_captured10) / len(serial_addressable10)
        ),
        "projected_unarmed_lifecycle_captured_meaningful_10c": len(projected_captured10),
        "projected_unarmed_lifecycle_10c_capture_rate": (
            None if not serial_addressable10 else len(projected_captured10) / len(serial_addressable10)
        ),
        "projected_additional_10c_captured": max(0, len(projected_captured10) - len(baseline_captured10)),
        "ended_unarmed_n": lifecycle.get("ended_unarmed_n"),
        "post_unarmed_later_plus10_n": lifecycle.get("post_unarmed_later_plus10_n"),
        "records": records,
        "auto_promote_allowed": False,
        "note": (
            "Coverage decomposition only. Do not add a price filter, stop-loss, "
            "or new qualification threshold from this output alone."
        ),
    }


if __name__ == "__main__":
    print(f"{VERSION} | import/use audit(rows) | RESEARCH ONLY | NO ORDERS")
