#!/usr/bin/env python3
"""
BTC15 SCALP +10c opportunity accounting audit V2.

RESEARCH ONLY | READ ONLY | SIGNAL ONLY | NO ORDERS

Goal: explain every completed frozen-qualified candidate that later moved +10c
without confusing raw/overlapping candidates with true serial-ladder misses.

Each completed +10c candidate is assigned exactly one existing coverage class:
- SELECTED_SERIAL_SCALP
- OVERLAP_WHILE_PRIOR_SCALP_ACTIVE
- BLOCKED_BY_FAILED_PREARM_NO_EXIT
- POST_EXIT_MISSED_QUALIFIED

No new entry, exit, price, or management rule is created. Entry price remains
telemetry only. The frozen +5c arm / 4c giveback protection is untouched.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Mapping

import BTC15_SCALP_BLUEPRINT_COVERAGE_AUDIT_V1 as coverage
import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_10C_ACCOUNTING_AUDIT_V2"
CLASSES = (
    "SELECTED_SERIAL_SCALP",
    "OVERLAP_WHILE_PRIOR_SCALP_ACTIVE",
    "BLOCKED_BY_FAILED_PREARM_NO_EXIT",
    "POST_EXIT_MISSED_QUALIFIED",
)


def _paths(rows: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if research.typ(r) == "PATH" and research.cid(r):
            out[research.cid(r)].append(dict(r))
    return out


def audit(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(r) for r in rows]
    cov = coverage.audit(rows)
    class_by_id = {
        str(r.get("candidate_id") or ""): str(r.get("classification") or "")
        for r in cov.get("records", [])
        if r.get("candidate_id")
    }
    done = {
        research.cid(r) for r in rows
        if research.typ(r) == "RESULT" and research.cid(r)
    }
    paths = _paths(rows)

    plus10_records: list[dict[str, Any]] = []
    for c in forward.forward_candidates(rows):
        if not research.candidate_qualified(c):
            continue
        cid = research.cid(c)
        if not cid or cid not in done:
            continue
        pm = research.measure_path(c, research.path_rows_for(c, paths))
        if pm.peak_gain is None or pm.peak_gain < 0.10 - 1e-12:
            continue
        cls = class_by_id.get(cid, "UNACCOUNTED")
        plus10_records.append({
            "contract": research.contract(c),
            "candidate_id": cid,
            "classification": cls,
            "side": str(c.get("side") or "").strip().upper(),
            "entry_ask": research.f(c.get("entry_ask")),
            "peak_gain": pm.peak_gain,
            "entry_price_is_telemetry_only": True,
        })

    counts = Counter(r["classification"] for r in plus10_records)
    recognized_n = sum(counts.get(k, 0) for k in CLASSES)
    total_n = len(plus10_records)
    unaccounted_n = total_n - recognized_n
    selected_n = counts.get("SELECTED_SERIAL_SCALP", 0)
    overlap_n = counts.get("OVERLAP_WHILE_PRIOR_SCALP_ACTIVE", 0)
    blocked_n = counts.get("BLOCKED_BY_FAILED_PREARM_NO_EXIT", 0)
    true_missed_n = counts.get("POST_EXIT_MISSED_QUALIFIED", 0)

    return {
        "version": VERSION,
        "research_only": True,
        "orders": False,
        "manual_execution_only": True,
        "entry_price_filter_applied": False,
        "price_is_telemetry_only": True,
        "protected_thresholds_changed": False,
        "completed_frozen_qualified_plus10_n": total_n,
        "selected_plus10_n": selected_n,
        "overlap_plus10_n": overlap_n,
        "blocked_failed_prearm_plus10_n": blocked_n,
        "true_post_exit_missed_plus10_n": true_missed_n,
        "unaccounted_plus10_n": unaccounted_n,
        "accounting_identity_ok": (
            total_n == selected_n + overlap_n + blocked_n + true_missed_n
            and unaccounted_n == 0
        ),
        "selected_share_of_all_plus10": None if not total_n else selected_n / total_n,
        "recoverable_gap_share": None if not total_n else (blocked_n + true_missed_n) / total_n,
        "classification_counts": dict(sorted(counts.items())),
        "records": plus10_records,
        "auto_promote_allowed": False,
        "note": (
            "Overlap is not counted as a serial-ladder miss. Failed-prearm blockage "
            "is a lifecycle gap under separate validation. Only POST_EXIT_MISSED_QUALIFIED "
            "is a true normal-reset coverage defect."
        ),
    }


def gate(summary: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "accounting_pass": summary.get("accounting_identity_ok") is True,
        "normal_reset_plus10_coverage_pass": int(summary.get("true_post_exit_missed_plus10_n") or 0) == 0,
        "failed_prearm_gap_present": int(summary.get("blocked_failed_prearm_plus10_n") or 0) > 0,
        "freeze_allowed": False,
        "orders": False,
    }


if __name__ == "__main__":
    print(f"{VERSION} | import/use audit(rows) | RESEARCH ONLY | NO ORDERS")
