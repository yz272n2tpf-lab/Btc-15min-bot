#!/usr/bin/env python3
"""
BTC15 failed-prearm SCALP reset tournament V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Problem under test:
A selected scalp that has not yet reached the protected +5c arm point has no
validated close/reset rule. If it eventually fails, the serial ladder can stay
blocked and later qualified scalps in the same 15-minute contract may never be
shown.

V1 does NOT choose or promote a stop. It evaluates a fixed grid of hypothetical
pre-arm release rules on ALL completed primary scalps, not only the eventual
losers. This is critical because a too-aggressive rule could cut a slow winner
that would later reach +5c.

For each rule V1 measures:
1) how often the release would trigger before +5c arms;
2) false abort rate: triggered primaries that later recover to +5c;
3) opportunity recovery: later qualified candidates exposed after the release;
4) whether those later candidates subsequently reach +10c.

The grid is descriptive only. A rule cannot be promoted by this module.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_FAILED_PREARM_RESET_TOURNAMENT_V1"
ADVERSE_LEVELS = (0.03, 0.05, 0.07, 0.10)
MIN_ELAPSED = (10.0, 20.0, 30.0, 45.0, 60.0)


def _paths(rows: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if research.typ(r) == "PATH" and research.cid(r):
            out[research.cid(r)].append(dict(r))
    return out


def _done(rows: list[Mapping[str, Any]]) -> set[str]:
    return forward.completed_ids([dict(r) for r in rows])


def _timeline(candidate: Mapping[str, Any], path_rows: list[Mapping[str, Any]]) -> list[tuple[float, float, datetime]]:
    ctime = research.dt(candidate.get("timestamp_utc"))
    out: list[tuple[float, float, datetime]] = []
    for r in path_rows:
        e = research.elapsed(r, ctime)
        g = research.f(r.get("exec_gain"))
        if e is None or g is None:
            continue
        t = research.dt(r.get("timestamp_utc"))
        if t == datetime.min.replace(tzinfo=timezone.utc):
            t = ctime + timedelta(seconds=e)
        out.append((float(e), float(g), t))
    out.sort(key=lambda x: x[0])
    return out


def _first_qualified_by_contract(rows: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in forward.forward_candidates([dict(r) for r in rows]):
        if research.candidate_qualified(c):
            by_contract[research.contract(c)].append(dict(c))
    out: dict[str, dict[str, Any]] = {}
    for contract, cs in by_contract.items():
        cs.sort(key=lambda x: research.dt(x.get("timestamp_utc")))
        if cs:
            out[contract] = cs[0]
    return out


def _next_candidate_after(
    contract: str,
    after: datetime,
    candidates: list[Mapping[str, Any]],
    exclude_id: str,
) -> dict[str, Any] | None:
    xs = [
        dict(c) for c in candidates
        if research.contract(c) == contract
        and research.cid(c) != exclude_id
        and research.candidate_qualified(c)
        and research.dt(c.get("timestamp_utc")) > after
    ]
    xs.sort(key=lambda x: research.dt(x.get("timestamp_utc")))
    return xs[0] if xs else None


def _release_before_arm(
    tl: list[tuple[float, float, datetime]],
    adverse: float,
    min_elapsed: float,
) -> tuple[int, float, float, datetime] | None:
    """Return first hypothetical release only if it occurs before +5c arms."""
    running_peak = None
    for i, (e, gain, ts) in enumerate(tl):
        running_peak = gain if running_peak is None else max(running_peak, gain)
        if running_peak >= research.SCALP_ARM_GAIN - 1e-12:
            return None
        if e >= min_elapsed and gain <= -adverse + 1e-12:
            return i, e, gain, ts
    return None


def audit(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Evaluate the fixed release grid without selecting a live rule."""
    rows = [dict(r) for r in rows]
    done = _done(rows)
    paths = _paths(rows)
    candidates = [dict(c) for c in forward.forward_candidates(rows) if research.candidate_qualified(c)]
    primaries = _first_qualified_by_contract(rows)

    completed_primaries: list[dict[str, Any]] = []
    failed_full_path: list[dict[str, Any]] = []
    for _contract, primary in primaries.items():
        cid = research.cid(primary)
        if cid not in done:
            continue
        completed_primaries.append(primary)
        pm = research.measure_path(primary, research.path_rows_for(primary, paths))
        if not pm.armed:
            failed_full_path.append(primary)

    cells: dict[str, dict[str, Any]] = {}
    for adverse in ADVERSE_LEVELS:
        for min_elapsed in MIN_ELAPSED:
            key = f"-{adverse*100:g}c_after_{min_elapsed:g}s"
            cell = {
                "rule": key,
                "adverse_cents": adverse * 100.0,
                "min_elapsed_sec": min_elapsed,
                "completed_primary_n": len(completed_primaries),
                "full_path_failed_primary_n": len(failed_full_path),
                "triggered_before_arm_n": 0,
                "original_later_recovers_plus5_n": 0,
                "later_candidate_available_n": 0,
                "later_candidate_completed_n": 0,
                "later_candidate_plus10_n": 0,
                "trigger_exit_gains": [],
                "handoff_candidate_ids": [],
                "actionable_now": False,
                "rule_selected": False,
                "orders": False,
            }

            for primary in completed_primaries:
                cid = research.cid(primary)
                contract = research.contract(primary)
                tl = _timeline(primary, research.path_rows_for(primary, paths))
                hit = _release_before_arm(tl, adverse, min_elapsed)
                if hit is None:
                    continue
                i, _e, gain, trigger_time = hit
                cell["triggered_before_arm_n"] += 1
                cell["trigger_exit_gains"].append(gain)

                # False abort = the same primary would later recover to +5c.
                future_gains = [x[1] for x in tl[i + 1:]]
                if future_gains and max(future_gains) >= research.SCALP_ARM_GAIN - 1e-12:
                    cell["original_later_recovers_plus5_n"] += 1

                nxt = _next_candidate_after(contract, trigger_time, candidates, cid)
                if nxt is None:
                    continue
                cell["later_candidate_available_n"] += 1
                nid = research.cid(nxt)
                cell["handoff_candidate_ids"].append(nid)
                if nid not in done:
                    continue
                cell["later_candidate_completed_n"] += 1
                npm = research.measure_path(nxt, research.path_rows_for(nxt, paths))
                if npm.peak_gain is not None and npm.peak_gain >= 0.10 - 1e-12:
                    cell["later_candidate_plus10_n"] += 1

            trig = cell["triggered_before_arm_n"]
            completed_next = cell["later_candidate_completed_n"]
            cell["false_abort_recovery_rate"] = None if not trig else cell["original_later_recovers_plus5_n"] / trig
            cell["later_candidate_plus10_rate"] = None if not completed_next else cell["later_candidate_plus10_n"] / completed_next
            gains = cell.pop("trigger_exit_gains")
            cell["avg_release_gain"] = None if not gains else sum(gains) / len(gains)
            cells[key] = cell

    return {
        "version": VERSION,
        "research_only": True,
        "orders": False,
        "manual_execution_only": True,
        "completed_primary_n": len(completed_primaries),
        "failed_prearm_primary_n": len(failed_full_path),
        "failed_primary_candidate_ids": [research.cid(x) for x in failed_full_path],
        "grid": cells,
        "rule_selected": False,
        "auto_promote_allowed": False,
        "minimum_sample_rule_not_invented": True,
        "note": "Descriptive tournament only; do not change live scalp close/reset behavior from this output alone.",
    }


if __name__ == "__main__":
    print(f"{VERSION} | import/use audit(rows) | RESEARCH ONLY | NO ORDERS")
