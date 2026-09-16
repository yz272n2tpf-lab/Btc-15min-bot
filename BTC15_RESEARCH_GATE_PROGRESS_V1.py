#!/usr/bin/env python3
"""
BTC15 research gate progress V1.

PURE REPORTING ONLY | READ ONLY | NO SIGNAL CHANGES | NO ORDERS

Turns the authoritative scoreboard into deterministic frozen-gate progress.
No ETA is guessed. No thresholds are changed. A lane is review-ready only when
all of its predeclared count requirements are satisfied by its own authoritative
sample.
"""
from __future__ import annotations

from typing import Any, Mapping

import BTC15_AUTHORITATIVE_SCOREBOARD_VIEWMODEL_V1 as vm

VERSION = "BTC15_RESEARCH_GATE_PROGRESS_V1"
GATES = vm.GATES


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _i(v: Any) -> int:
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


def _requirement(label: str, current: Any, target: int) -> dict[str, Any]:
    c = _i(current)
    t = max(1, int(target))
    return {
        "label": label,
        "current": c,
        "target": t,
        "remaining": max(0, t - c),
        "satisfied": c >= t,
        "progress": min(1.0, c / t),
    }


def _lane(name: str, requirements: list[dict[str, Any]], source_ready: bool) -> dict[str, Any]:
    all_counts = bool(requirements) and all(r["satisfied"] for r in requirements)
    bottlenecks = [r["label"] for r in requirements if not r["satisfied"]]
    # Count progress is deliberately the minimum capped requirement fraction.
    # It is a checklist-completion measure, NOT probability, accuracy, or ETA.
    count_progress = min((float(r["progress"]) for r in requirements), default=0.0)
    return {
        "lane": name,
        "requirements": requirements,
        "count_requirements_satisfied": all_counts,
        "collector_sample_ready": bool(source_ready),
        "review_ready": bool(all_counts and source_ready),
        "count_progress": count_progress,
        "bottlenecks": bottlenecks,
        "semantics": "FROZEN_COUNT_GATE_PROGRESS_NOT_ACCURACY_OR_ETA",
    }


def build_gate_progress(board: Mapping[str, Any]) -> dict[str, Any]:
    f = _m(board.get("final"))
    e = _m(board.get("early"))
    h = _m(board.get("handoff"))
    x = _m(board.get("early_excursion"))
    r = _m(board.get("flip_risk"))

    lanes = {
        "final": _lane(
            "FINAL V4",
            [
                _requirement("eligible contracts", f.get("eligible_contracts"), GATES["final"]["eligible"]),
                _requirement("settled FINAL locks", f.get("settled_calls"), GATES["final"]["settled"]),
            ],
            bool(f.get("sample_ready")),
        ),
        "early": _lane(
            "EARLY V1",
            [
                _requirement("eligible contracts", e.get("eligible_contracts"), GATES["early"]["eligible"]),
                _requirement("settled EARLY calls", e.get("settled_calls"), GATES["early"]["settled"]),
            ],
            bool(e.get("sample_ready")),
        ),
        "handoff": _lane(
            "EARLY→FINAL HANDOFF V1",
            [
                _requirement("eligible contracts", h.get("eligible_contracts"), GATES["handoff"]["eligible"]),
                _requirement("real EARLY→FINAL handoffs", h.get("handoffs"), GATES["handoff"]["handoffs"]),
                _requirement("settled FINAL locks", h.get("settled_final_locks"), GATES["handoff"]["settled"]),
            ],
            bool(h.get("sample_ready")),
        ),
        "early_excursion": _lane(
            "EARLY EXCURSION V1",
            [
                _requirement("eligible contracts", x.get("eligible_contracts"), GATES["excursion"]["eligible"]),
                _requirement("completed EARLY excursions", x.get("completed"), GATES["excursion"]["completed"]),
            ],
            bool(x.get("sample_ready")),
        ),
        "flip_risk": _lane(
            "FLIP RISK V2",
            [
                _requirement("prediction-complete contracts", r.get("prediction_complete_contracts"), GATES["flip"]["complete"]),
                _requirement("settled predictions", r.get("settled_predictions"), GATES["flip"]["predictions"]),
            ],
            bool(r.get("sample_ready")),
        ),
    }

    ready = [k for k, lane in lanes.items() if lane["review_ready"]]
    waiting = [k for k, lane in lanes.items() if not lane["review_ready"]]
    return {
        "version": VERSION,
        "safety": {
            "read_only": True,
            "reporting_only": True,
            "orders": False,
            "manual_execution_only": True,
            "changes_thresholds": False,
            "guesses_eta": False,
        },
        "lanes": lanes,
        "review_ready_lanes": ready,
        "waiting_lanes": waiting,
        "overall_semantics": "EACH_LANE_KEEPS_ITS_OWN_FROZEN_DENOMINATOR_AND_GATE",
    }


def render_text(progress: Mapping[str, Any]) -> str:
    lines = ["=== BTC15 FROZEN TEST-GATE PROGRESS ===", "No ETA guesses · no threshold changes · no orders"]
    for key in ("final", "early", "handoff", "early_excursion", "flip_risk"):
        lane = _m(_m(progress.get("lanes")).get(key))
        lines.append("")
        lines.append(str(lane.get("lane") or key))
        for req in lane.get("requirements") or []:
            q = _m(req)
            mark = "✓" if q.get("satisfied") else "…"
            lines.append(f"  {mark} {q.get('label')}: {q.get('current',0)}/{q.get('target',0)} · remaining {q.get('remaining',0)}")
        bottlenecks = lane.get("bottlenecks") or []
        lines.append("  Review ready: " + ("YES" if lane.get("review_ready") else "NO"))
        if bottlenecks:
            lines.append("  Waiting on: " + ", ".join(str(x) for x in bottlenecks))
    return "\n".join(lines) + "\n"


__all__ = ["VERSION", "GATES", "build_gate_progress", "render_text"]
