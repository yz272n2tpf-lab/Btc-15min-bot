#!/usr/bin/env python3
"""
BTC15 authoritative scoreboard V1.

PURE / OFFLINE / READ ONLY | SIGNAL ONLY | MANUAL EXECUTION ONLY | NO ORDERS

Purpose
-------
Combine already-authoritative collector snapshots into one consistent scoreboard
without recomputing any model, changing thresholds, or inventing union coverage.

Important separations
---------------------
- FINAL directional accuracy is FINAL only.
- SCALP +10c is a movement-rate metric, never FINAL accuracy.
- EARLY settlement same-side rate is secondary context, not FINAL accuracy.
- Overall/union coverage is NOT CERTIFIED unless an authoritative common-universe
  source explicitly provides it. Separate EARLY and FINAL coverages are never added.
- Numeric Flip Risk is hidden unless its own future collector is sample-ready AND
  explicitly validated for user-facing numeric presentation by a later manual review.
"""
from __future__ import annotations

from typing import Any, Mapping

VERSION = "BTC15_AUTHORITATIVE_SCOREBOARD_V1"

SCALP_REFERENCE = {
    "label": "FROZEN_SCALP_REFERENCE",
    "completed_serial_opportunities": 115,
    "plus10_move_rate": 0.774,
    "protected_exits": 70,
    "first_4c_crossing_correct_rate": 1.0,
    "fresh_reference_opportunities": 61,
    "fresh_reference_contracts": 33,
    "fresh_plus10_move_rate": 0.820,
    "metric_semantics": "SCALP_MOVEMENT_RATE_NOT_FINAL_ACCURACY",
}


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _f(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _rate(n: int, d: int) -> float | None:
    return n / d if d else None


def _summary(payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    p = _m(payload)
    for key in ("live", "summary", "scorecard", "snapshot"):
        q = p.get(key)
        if isinstance(q, Mapping):
            return q
    return p


def _watchdog(payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    p = _m(payload)
    for key in ("watchdog", "runtime", "health"):
        q = p.get(key)
        if isinstance(q, Mapping):
            return q
    return {}


def _assert_safe(name: str, payload: Mapping[str, Any] | None) -> None:
    p = _m(payload)
    s = _summary(payload)
    for q in (p, s):
        if q.get("orders") is True:
            raise ValueError(f"{name}: orders=True is forbidden")
        if q.get("manual_execution_only") is False:
            raise ValueError(f"{name}: manual_execution_only=False is forbidden")
        if q.get("production_behavior_changed") is True:
            raise ValueError(f"{name}: production_behavior_changed=True")


def _source(name: str, payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping) or not payload:
        return {"name": name, "connected": False, "status": "NOT CONNECTED"}
    _assert_safe(name, payload)
    p, s, w = _m(payload), _summary(payload), _watchdog(payload)
    return {
        "name": name,
        "connected": True,
        "version": p.get("version") or s.get("version"),
        "status": s.get("status") or p.get("status") or "CONNECTED",
        "sample_ready": bool(s.get("sample_ready") or s.get("ready")),
        "watchdog_healthy": w.get("healthy"),
        "watchdog_restarts": w.get("observer_restarts", w.get("restarts")),
    }


def combine_scoreboard(
    *,
    final_payload: Mapping[str, Any] | None = None,
    early_payload: Mapping[str, Any] | None = None,
    handoff_payload: Mapping[str, Any] | None = None,
    excursion_payload: Mapping[str, Any] | None = None,
    flip_payload: Mapping[str, Any] | None = None,
    numeric_flip_user_facing_approved: bool = False,
) -> dict[str, Any]:
    for name, p in (
        ("FINAL", final_payload), ("EARLY", early_payload),
        ("HANDOFF", handoff_payload), ("EARLY_EXCURSION", excursion_payload),
        ("FLIP_RISK", flip_payload),
    ):
        if p is not None:
            _assert_safe(name, p)

    fs, es, hs, xs, rs = map(_summary, (
        final_payload, early_payload, handoff_payload, excursion_payload, flip_payload
    ))

    final_eligible = _i(fs.get("eligibility_complete_contracts"))
    final_calls = _i(fs.get("lock_calls", fs.get("final_calls")))
    final_settled = _i(fs.get("settled_lock_calls", fs.get("settled_final_calls")))
    final_accuracy = _f(fs.get("qualified_accuracy", fs.get("final_accuracy")))
    final_coverage = _f(fs.get("final_only_coverage"))
    if final_coverage is None:
        final_coverage = _rate(final_calls, final_eligible)

    early_eligible = _i(es.get("eligibility_complete_contracts"))
    early_calls = _i(es.get("early_calls"))
    early_settled = _i(es.get("settled_early_calls"))
    early_coverage = _f(es.get("early_only_coverage"))
    if early_coverage is None:
        early_coverage = _rate(early_calls, early_eligible)

    handoff_eligible = _i(hs.get("eligibility_complete_contracts"))
    handoff_early = _i(hs.get("early_calls", hs.get("early_n")))
    handoff_final = _i(hs.get("final_calls", hs.get("final_n")))
    handoffs = _i(hs.get("handoffs", hs.get("both_n")))
    handoff_union = _f(hs.get("union_coverage", hs.get("any_anchor_coverage")))
    handoff_dual = _f(hs.get("dual_anchor_coverage"))

    excursion_eligible = _i(xs.get("eligibility_complete_contracts", xs.get("eligible_contracts")))
    excursion_calls = _i(xs.get("early_calls"))
    excursion_complete = _i(xs.get("completed_excursions", xs.get("complete")))

    flip_complete = _i(rs.get("prediction_complete_contracts", rs.get("complete_contracts", rs.get("complete"))))
    flip_settled_preds = _i(rs.get("settled_predictions", rs.get("settled_preds")))
    flip_ready = bool(rs.get("sample_ready") or rs.get("ready"))
    flip_validated = bool(rs.get("numeric_flip_risk_validated"))
    show_numeric_flip = bool(flip_ready and flip_validated and numeric_flip_user_facing_approved)

    return {
        "version": VERSION,
        "safety": {
            "read_only": True,
            "signal_only": True,
            "manual_execution_only": True,
            "orders": False,
            "production_behavior_changed": False,
        },
        "sources": {
            "final": _source("FINAL", final_payload),
            "early": _source("EARLY", early_payload),
            "handoff": _source("HANDOFF", handoff_payload),
            "early_excursion": _source("EARLY_EXCURSION", excursion_payload),
            "flip_risk": _source("FLIP_RISK", flip_payload),
        },
        "final": {
            "eligible_contracts": final_eligible,
            "calls": final_calls,
            "settled_calls": final_settled,
            "directional_accuracy": final_accuracy,
            "final_only_coverage": final_coverage,
            "avg_minutes_left": _f(fs.get("avg_minutes_left")),
            "median_minutes_left": _f(fs.get("median_minutes_left")),
            "avg_locked_side_ask": _f(fs.get("avg_preferred_ask")),
            "median_locked_side_ask": _f(fs.get("median_preferred_ask")),
            "ask_le_50c_n": _i(fs.get("ask_le_50c_n")),
            "ask_le_50c_rate": _f(fs.get("ask_le_50c_rate")),
            "sample_ready": bool(fs.get("sample_ready") or fs.get("ready")),
            "metric_semantics": "FINAL_DIRECTIONAL_ACCURACY_AND_FINAL_ONLY_COVERAGE",
        },
        "early": {
            "eligible_contracts": early_eligible,
            "calls": early_calls,
            "settled_calls": early_settled,
            "early_only_coverage": early_coverage,
            "avg_entry_ask": _f(es.get("avg_ask", es.get("avg_entry_ask"))),
            "median_entry_ask": _f(es.get("median_ask", es.get("median_entry_ask"))),
            "ideal_25_35c_n": _i(es.get("ideal_25_35c_n", es.get("ask_25_35c_n"))),
            "ask_le_50c_n": _i(es.get("ask_le_50c_n")),
            "avg_minutes_left": _f(es.get("avg_minutes_left")),
            "median_minutes_left": _f(es.get("median_minutes_left")),
            "avg_fair": _f(es.get("avg_fair")),
            "avg_edge": _f(es.get("avg_edge")),
            "settlement_same_side_rate_secondary": _f(es.get("settlement_same_side_rate", es.get("same_side_rate"))),
            "sample_ready": bool(es.get("sample_ready") or es.get("ready")),
            "metric_semantics": "EARLY_ENTRY_QUALITY; SETTLEMENT_SIDE_RATE_IS_SECONDARY",
        },
        "scalp": dict(SCALP_REFERENCE),
        "early_excursion": {
            "eligible_contracts": excursion_eligible,
            "calls": excursion_calls,
            "completed": excursion_complete,
            "coverage": _f(xs.get("early_coverage", xs.get("coverage"))),
            "avg_entry_ask": _f(xs.get("avg_entry_ask", xs.get("avg_ask"))),
            "median_entry_ask": _f(xs.get("median_entry_ask", xs.get("median_ask"))),
            "avg_mfe": _f(xs.get("avg_mfe")),
            "median_mfe": _f(xs.get("median_mfe")),
            "avg_mae": _f(xs.get("avg_mae")),
            "median_mae": _f(xs.get("median_mae")),
            "plus5_rate": _f(xs.get("plus5_rate")),
            "plus10_rate": _f(xs.get("plus10_rate")),
            "plus15_rate": _f(xs.get("plus15_rate")),
            "plus20_rate": _f(xs.get("plus20_rate")),
            "sample_ready": bool(xs.get("sample_ready") or xs.get("ready")),
            "metric_semantics": "BID_BASED_TRADABLE_EXCURSION_FROM_PROTECTED_EARLY_ENTRY",
        },
        "handoff": {
            "eligible_contracts": handoff_eligible,
            "early_calls": handoff_early,
            "final_calls": handoff_final,
            "handoffs": handoffs,
            "any_anchor_coverage": handoff_union,
            "dual_anchor_coverage": handoff_dual,
            "side_agreement_rate": _f(hs.get("side_agreement_rate", hs.get("agreement_rate"))),
            "avg_handoff_gap_minutes": _f(hs.get("avg_handoff_gap_minutes", hs.get("avg_handoff_gap"))),
            "sample_ready": bool(hs.get("sample_ready") or hs.get("ready")),
            "metric_semantics": "COMMON_UNIVERSE_TWO_SIGNAL_WORKFLOW_ONLY",
        },
        "flip_risk": {
            "prediction_complete_contracts": flip_complete,
            "settled_predictions": flip_settled_preds,
            "sample_ready": flip_ready,
            "numeric_probability_validated": flip_validated,
            "user_facing_numeric_allowed": show_numeric_flip,
            "display_value": _f(rs.get("current_flip_risk")) if show_numeric_flip else None,
            "display_status": "VALIDATED" if show_numeric_flip else "HIDDEN_UNTIL_VALIDATED",
        },
        "overall": {
            "certified_union_coverage": handoff_union if bool(hs.get("sample_ready") or hs.get("ready")) else None,
            "certified_union_status": "CERTIFIED_FROM_COMMON_UNIVERSE" if bool(hs.get("sample_ready") or hs.get("ready")) else "NOT CERTIFIED",
            "system_accuracy": None,
            "system_accuracy_status": "NOT A VALID SINGLE METRIC",
        },
    }


def _pct(v: Any) -> str:
    x = _f(v)
    return "—" if x is None else f"{100*x:.1f}%"


def _cents(v: Any) -> str:
    x = _f(v)
    return "—" if x is None else f"{100*x:.1f}c"


def _mins(v: Any) -> str:
    x = _f(v)
    return "—" if x is None else f"{x:.2f}m"


def render_text(board: Mapping[str, Any]) -> str:
    f, e, s = _m(board.get("final")), _m(board.get("early")), _m(board.get("scalp"))
    x, h, r, o = (_m(board.get("early_excursion")), _m(board.get("handoff")),
                  _m(board.get("flip_risk")), _m(board.get("overall")))
    lines = [
        "=== ONE-COMMAND BTC 15M AUTHORITATIVE SCOREBOARD ===",
        "Read only. Signal only. Manual execution. No orders.",
        "",
        "FINAL",
        f"  Accuracy: {_pct(f.get('directional_accuracy'))} ({f.get('settled_calls',0)} settled)",
        f"  Coverage: {_pct(f.get('final_only_coverage'))} ({f.get('calls',0)}/{f.get('eligible_contracts',0)})",
        f"  Timing: avg {_mins(f.get('avg_minutes_left'))} | median {_mins(f.get('median_minutes_left'))}",
        f"  Locked ask: avg {_cents(f.get('avg_locked_side_ask'))} | median {_cents(f.get('median_locked_side_ask'))} | <=50c {f.get('ask_le_50c_n',0)}",
        "",
        "EARLY",
        f"  Coverage: {_pct(e.get('early_only_coverage'))} ({e.get('calls',0)}/{e.get('eligible_contracts',0)})",
        f"  Entry ask: avg {_cents(e.get('avg_entry_ask'))} | median {_cents(e.get('median_entry_ask'))}",
        f"  Ideal 25-35c: {e.get('ideal_25_35c_n',0)} | <=50c: {e.get('ask_le_50c_n',0)}",
        f"  Settlement-side rate: {_pct(e.get('settlement_same_side_rate_secondary'))} (secondary only)",
        "",
        "SCALP",
        f"  Frozen +10c move rate: {_pct(s.get('plus10_move_rate'))} on {s.get('completed_serial_opportunities',0)} opportunities",
        f"  Fresh reference +10c move rate: {_pct(s.get('fresh_plus10_move_rate'))} on {s.get('fresh_reference_opportunities',0)} opportunities",
        "  Label: movement rate, NOT FINAL accuracy",
        "",
        "EARLY EXCURSION",
        f"  Completed: {x.get('completed',0)}/{x.get('calls',0)} calls | MFE avg {_cents(x.get('avg_mfe'))} | MAE avg {_cents(x.get('avg_mae'))}",
        f"  +5/+10/+15/+20: {_pct(x.get('plus5_rate'))} / {_pct(x.get('plus10_rate'))} / {_pct(x.get('plus15_rate'))} / {_pct(x.get('plus20_rate'))}",
        "",
        "EARLY -> FINAL HANDOFF",
        f"  Common-universe any-anchor coverage: {_pct(h.get('any_anchor_coverage'))}",
        f"  Dual-anchor coverage: {_pct(h.get('dual_anchor_coverage'))} | handoffs={h.get('handoffs',0)}",
        f"  Side agreement: {_pct(h.get('side_agreement_rate'))} | avg gap {_mins(h.get('avg_handoff_gap_minutes'))}",
        "",
        "FLIP RISK",
        f"  Future sample: {r.get('prediction_complete_contracts',0)} complete contracts / {r.get('settled_predictions',0)} settled predictions",
        f"  Numeric display: {r.get('display_status','HIDDEN_UNTIL_VALIDATED')}",
        "",
        "SYSTEM",
        f"  >=90% union-coverage claim: {o.get('certified_union_status','NOT CERTIFIED')}",
        "  Single blended system accuracy: NOT A VALID SINGLE METRIC",
    ]
    return "\n".join(lines) + "\n"


__all__ = ["VERSION", "SCALP_REFERENCE", "combine_scoreboard", "render_text"]
