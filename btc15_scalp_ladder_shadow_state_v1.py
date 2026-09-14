#!/usr/bin/env python3
"""
BTC15 scalp ladder shadow state V1.

PURE / READ ONLY / RESEARCH ONLY / SIGNAL ONLY / NO ORDERS

Builds descriptive secondary/tertiary opportunity telemetry around the frozen
primary scalp. It NEVER changes or replaces the current protected primary state.
Later opportunities are explicitly non-actionable until separately validated.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research

VERSION = "BTC15_SCALP_LADDER_SHADOW_STATE_V1"


def build_shadow_ladder(rows: list[Mapping[str, Any]]) -> dict:
    candidates_by_contract = defaultdict(list)
    paths_by_cid = defaultdict(list)
    snapshots = []
    for row in rows:
        t = research.typ(row)
        if t == "CANDIDATE" and research.contract(row):
            candidates_by_contract[research.contract(row)].append(dict(row))
        elif t == "PATH" and research.cid(row):
            paths_by_cid[research.cid(row)].append(dict(row))
        elif t == "SNAPSHOT" and research.contract(row):
            snapshots.append(dict(row))

    current_contract = None
    if snapshots:
        current_contract = research.contract(max(snapshots, key=lambda r: research.dt(r.get("timestamp_utc"))))
    elif candidates_by_contract:
        current_contract = max(
            candidates_by_contract,
            key=lambda c: max(research.dt(r.get("timestamp_utc")) for r in candidates_by_contract[c]),
        )

    if not current_contract:
        return {
            "version": VERSION,
            "contract": None,
            "primary": None,
            "later_opportunities": [],
            "prearm_failure_telemetry": None,
            "later_opportunities_actionable": False,
            "manual_execution_only": True,
            "orders": False,
        }

    candidates = sorted(candidates_by_contract[current_contract], key=lambda r: research.dt(r.get("timestamp_utc")))
    qualified = [c for c in candidates if research.candidate_qualified(c)]
    if not qualified:
        return {
            "version": VERSION,
            "contract": current_contract,
            "primary": None,
            "later_opportunities": [],
            "prearm_failure_telemetry": None,
            "later_opportunities_actionable": False,
            "manual_execution_only": True,
            "orders": False,
        }

    primary = qualified[0]
    primary_path = research.path_rows_for(primary, paths_by_cid)
    pm = research.measure_path(primary, primary_path)
    primary_rec = {
        "candidate_id": research.cid(primary),
        "side": str(primary.get("side") or "").upper(),
        "entry_ask": research.f(primary.get("entry_ask")),
        "seconds_left": research.f(primary.get("seconds_left")),
        "btc30": research.f(primary.get("btc30")),
        "armed": pm.armed,
        "peak_gain": pm.peak_gain,
        "adverse_gain": pm.adverse_gain,
        "protected_exit_gain": pm.exit_gain,
        "protected_exit_time_utc": pm.exit_time_utc,
    }

    later = []
    if pm.exit_time_utc:
        after = research.dt(pm.exit_time_utc)
        for cand in qualified[1:]:
            if research.dt(cand.get("timestamp_utc")) <= after:
                continue
            cm = research.measure_path(cand, research.path_rows_for(cand, paths_by_cid))
            later.append({
                "candidate_id": research.cid(cand),
                "timestamp_utc": str(cand.get("timestamp_utc") or ""),
                "side": str(cand.get("side") or "").upper(),
                "entry_ask": research.f(cand.get("entry_ask")),
                "seconds_left": research.f(cand.get("seconds_left")),
                "btc30": research.f(cand.get("btc30")),
                "peak_gain": cm.peak_gain,
                "adverse_gain": cm.adverse_gain,
                "armed": cm.armed,
                "protected_exit_gain": cm.exit_gain,
                "research_status": "OBSERVE_ONLY_NOT_VALIDATED",
                "actionable": False,
            })
            # V1 reports all later frozen-qualified candidates descriptively;
            # the offline scorer enforces sequential non-overlap for promotion research.

    failure = None
    if not pm.armed:
        current_gain = None
        current_elapsed = None
        ctime = research.dt(primary.get("timestamp_utc"))
        for row in primary_path:
            g = research.f(row.get("exec_gain"))
            e = research.elapsed(row, ctime)
            if g is not None and e is not None and (current_elapsed is None or e >= current_elapsed):
                current_gain, current_elapsed = g, e
        failure = {
            "armed_plus5": False,
            "current_gain": current_gain,
            "elapsed_sec": current_elapsed,
            "peak_gain": pm.peak_gain,
            "adverse_gain": pm.adverse_gain,
            "status": "OBSERVE_PREARM_FAILURE_ONLY",
            "actionable_cut_rule": False,
        }

    return {
        "version": VERSION,
        "contract": current_contract,
        "primary": primary_rec,
        "later_opportunities": later,
        "prearm_failure_telemetry": failure,
        "later_opportunities_actionable": False,
        "manual_execution_only": True,
        "orders": False,
    }


__all__ = ["VERSION", "build_shadow_ladder"]
