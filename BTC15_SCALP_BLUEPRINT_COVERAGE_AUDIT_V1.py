#!/usr/bin/env python3
"""
BTC15 SCALP blueprint opportunity coverage audit V1.

RESEARCH ONLY | READ ONLY | SIGNAL ONLY | NO ORDERS

Audits whether the serial scalp ladder is doing what the confirmed blueprint
requires after each completed scalp: reset, then take the next frozen-qualified
setup in the same 15-minute contract. This does NOT treat every overlapping raw
candidate as a missed trade; candidates that appear while a prior scalp is still
being managed are classified as overlap. Candidates after an unarmed primary
with no validated EXIT are classified as blocked-by-failed-prearm, which is the
known gap being researched separately.

Kalshi entry price is telemetry only here. It never suppresses a candidate.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_BLUEPRINT_COVERAGE_AUDIT_V1"


def _done_ids(rows: list[Mapping[str, Any]]) -> set[str]:
    return {
        research.cid(r)
        for r in rows
        if research.typ(r) == "RESULT" and research.cid(r)
    }


def _paths(rows: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if research.typ(r) == "PATH" and research.cid(r):
            out[research.cid(r)].append(dict(r))
    return out


def audit(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Classify every forward frozen-qualified candidate by serial-ladder role."""
    done = _done_ids(rows)
    paths = _paths(rows)
    selected = forward.build_serial_opportunities(list(rows))
    selected_by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in selected:
        selected_by_contract[str(s.get("contract") or "")].append(s)

    by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in forward.forward_candidates(list(rows)):
        if research.candidate_qualified(c):
            by_contract[research.contract(c)].append(c)

    records: list[dict[str, Any]] = []
    for contract, cands in by_contract.items():
        cands = sorted(cands, key=lambda x: research.dt(x.get("timestamp_utc")))
        chosen = sorted(selected_by_contract.get(contract, []), key=lambda x: int(x.get("opportunity_index") or 0))
        chosen_by_id = {str(x.get("candidate_id") or ""): x for x in chosen}

        active_until = datetime.min.replace(tzinfo=timezone.utc)
        hard_block_time: datetime | None = None
        hard_block_cid: str | None = None

        for c in cands:
            cid = research.cid(c)
            ts = research.dt(c.get("timestamp_utc"))
            rec: dict[str, Any] = {
                "contract": contract,
                "candidate_id": cid,
                "timestamp_utc": str(c.get("timestamp_utc") or ""),
                "side": str(c.get("side") or "").strip().upper(),
                "entry_ask": research.f(c.get("entry_ask")),
                "price_band": forward.price_band(research.f(c.get("entry_ask"))),
                "price_is_telemetry_only": True,
                "completed": cid in done,
            }

            if cid in chosen_by_id:
                s = chosen_by_id[cid]
                rec.update({
                    "classification": "SELECTED_SERIAL_SCALP",
                    "opportunity_index": int(s.get("opportunity_index") or 0),
                    "meaningful_10c": bool(s.get("meaningful_10c")),
                    "protected_exit_time_utc": s.get("protected_exit_time_utc"),
                    "armed_plus5": bool(s.get("armed_plus5")),
                })
                exit_raw = s.get("protected_exit_time_utc")
                if exit_raw:
                    active_until = research.dt(exit_raw)
                else:
                    # No validated reset exists after this point yet.
                    hard_block_time = ts
                    hard_block_cid = cid
                records.append(rec)
                continue

            if hard_block_time is not None and ts > hard_block_time:
                rec.update({
                    "classification": "BLOCKED_BY_FAILED_PREARM_NO_EXIT",
                    "blocked_by_candidate_id": hard_block_cid,
                })
            elif ts <= active_until:
                rec["classification"] = "OVERLAP_WHILE_PRIOR_SCALP_ACTIVE"
            elif cid not in done:
                rec["classification"] = "AWAITING_RESULT"
            else:
                # A completed, qualified candidate after a prior exit that was
                # not selected is a true implementation/coverage defect.
                rec["classification"] = "POST_EXIT_MISSED_QUALIFIED"
            records.append(rec)

    counts = Counter(r["classification"] for r in records)
    selected_rows = [r for r in records if r["classification"] == "SELECTED_SERIAL_SCALP"]
    true_misses = counts.get("POST_EXIT_MISSED_QUALIFIED", 0)
    eligible_after_reset = len(selected_rows) + true_misses
    reset_selection_rate = (
        None if eligible_after_reset == 0 else len(selected_rows) / eligible_after_reset
    )

    return {
        "version": VERSION,
        "research_only": True,
        "orders": False,
        "manual_execution_only": True,
        "price_is_telemetry_only": True,
        "qualified_forward_candidates": len(records),
        "selected_serial_scalps": len(selected_rows),
        "meaningful_10c_selected": sum(bool(r.get("meaningful_10c")) for r in selected_rows),
        "max_serial_index": max((int(r.get("opportunity_index") or 0) for r in selected_rows), default=0),
        "classification_counts": dict(sorted(counts.items())),
        "post_exit_reset_selection_rate": reset_selection_rate,
        "post_exit_missed_qualified": true_misses,
        "failed_prearm_blocked_candidates": counts.get("BLOCKED_BY_FAILED_PREARM_NO_EXIT", 0),
        "records": records,
        "actionable_now": False,
    }


def gate(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Read-only coverage gate; does not freeze or promote strategy rules."""
    misses = int(summary.get("post_exit_missed_qualified") or 0)
    max_idx = int(summary.get("max_serial_index") or 0)
    return {
        "coverage_logic_pass": misses == 0 and max_idx >= 2,
        "no_post_exit_misses": misses == 0,
        "multi_scalp_reset_observed": max_idx >= 2,
        "failed_prearm_gap_observed": int(summary.get("failed_prearm_blocked_candidates") or 0) > 0,
        "freeze_allowed": False,
        "actionable_now": False,
        "orders": False,
    }
