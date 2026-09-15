#!/usr/bin/env python3
"""
BTC15 authoritative scoreboard V2.

Thin compatibility layer over frozen Scoreboard V1. V2 changes no score math.
It maps the exact native field names emitted by the authoritative live collectors
into V1's frozen presentation semantics.

PURE / OFFLINE / READ ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

import BTC15_AUTHORITATIVE_SCOREBOARD_V1 as v1

VERSION = "BTC15_AUTHORITATIVE_SCOREBOARD_V2"
SCALP_REFERENCE = v1.SCALP_REFERENCE


def _map(v: Any) -> dict[str, Any]:
    return dict(v) if isinstance(v, Mapping) else {}


def _normalized_payload(payload: Mapping[str, Any] | None, kind: str) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return payload
    p = deepcopy(dict(payload))

    # Preserve the collector's native wrapper and normalize only whichever
    # current summary object V1 would read.
    key = None
    for candidate in ("live", "summary", "scorecard", "snapshot"):
        if isinstance(p.get(candidate), Mapping):
            key = candidate
            break
    s = _map(p.get(key)) if key else p

    if kind == "early":
        s.setdefault("settlement_same_side_rate", s.get("settlement_same_side_rate_secondary"))

    elif kind == "handoff":
        s.setdefault("final_calls", s.get("final_locks"))
        s.setdefault("union_coverage", s.get("any_signal_coverage"))
        s.setdefault("side_agreement_rate", s.get("handoff_side_agreement_rate"))
        s.setdefault("avg_handoff_gap_minutes", s.get("avg_early_to_final_gap_minutes"))

    elif kind == "excursion":
        s.setdefault("eligibility_complete_contracts", s.get("eligible_contracts"))
        s.setdefault("completed_excursions", s.get("completed_early_excursions"))
        s.setdefault("plus5_rate", s.get("hit_5c_rate"))
        s.setdefault("plus10_rate", s.get("hit_10c_rate"))
        s.setdefault("plus15_rate", s.get("hit_15c_rate"))
        s.setdefault("plus20_rate", s.get("hit_20c_rate"))

    elif kind == "flip":
        s.setdefault("settled_predictions", s.get("settled_review_predictions"))
        # Passing V2 earns manual review only. It is deliberately NOT converted
        # into user-facing numeric validation here.
        s["numeric_flip_risk_validated"] = False

    if key:
        p[key] = s
        return p
    return s


def combine_scoreboard(
    *,
    final_payload: Mapping[str, Any] | None = None,
    early_payload: Mapping[str, Any] | None = None,
    handoff_payload: Mapping[str, Any] | None = None,
    excursion_payload: Mapping[str, Any] | None = None,
    flip_payload: Mapping[str, Any] | None = None,
    numeric_flip_user_facing_approved: bool = False,
) -> dict[str, Any]:
    board = v1.combine_scoreboard(
        final_payload=_normalized_payload(final_payload, "final"),
        early_payload=_normalized_payload(early_payload, "early"),
        handoff_payload=_normalized_payload(handoff_payload, "handoff"),
        excursion_payload=_normalized_payload(excursion_payload, "excursion"),
        flip_payload=_normalized_payload(flip_payload, "flip"),
        numeric_flip_user_facing_approved=numeric_flip_user_facing_approved,
    )
    board["version"] = VERSION

    # Extra native fields that V1 intentionally did not expose yet. These are
    # presentation-only and keep the same frozen semantics.
    es = v1._summary(_normalized_payload(excursion_payload, "excursion"))
    hs = v1._summary(_normalized_payload(handoff_payload, "handoff"))
    rs = v1._summary(_normalized_payload(flip_payload, "flip"))

    x = board["early_excursion"]
    x.update({
        "ideal_25_35c_n": v1._i(es.get("ideal_25_35c_n")),
        "ideal_25_35c_rate": v1._f(es.get("ideal_25_35c_rate")),
        "avg_entry_minutes_left": v1._f(es.get("avg_entry_minutes_left")),
        "median_entry_minutes_left": v1._f(es.get("median_entry_minutes_left")),
        "final_seen_after_early_n": v1._i(es.get("final_seen_after_early_n")),
        "final_agreement_rate": v1._f(es.get("final_agreement_rate")),
        "settlement_same_side_rate_secondary": v1._f(es.get("settlement_same_side_rate_secondary")),
    })

    h = board["handoff"]
    h.update({
        "early_only_contracts": v1._i(hs.get("early_only_contracts")),
        "final_only_contracts": v1._i(hs.get("final_only_contracts")),
        "no_anchor_contracts": v1._i(hs.get("no_anchor_contracts")),
        "settled_final_locks": v1._i(hs.get("settled_final_locks")),
        "final_accuracy": v1._f(hs.get("final_accuracy")),
        "median_handoff_gap_minutes": v1._f(hs.get("median_early_to_final_gap_minutes")),
    })

    r = board["flip_risk"]
    r.update({
        "settled_complete_contracts": v1._i(rs.get("settled_prediction_complete_contracts")),
        "gate_pass": bool(rs.get("gate_pass")),
        "decision_ready": bool(rs.get("decision_ready")),
        "brier_skill": v1._f(rs.get("brier_skill")),
        "weighted_abs_calibration_error": v1._f(rs.get("weighted_abs_calibration_error")),
        "stay90_actual_stay": v1._f(rs.get("stay90_actual_stay")),
    })
    # Keep numeric display hidden even if gate_pass becomes true. A separate
    # manual display approval is still required by the frozen project contract.
    r["numeric_probability_validated"] = False
    r["user_facing_numeric_allowed"] = False
    r["display_value"] = None
    r["display_status"] = "HIDDEN_UNTIL_VALIDATED"
    return board


def render_text(board: Mapping[str, Any]) -> str:
    return v1.render_text(board)


__all__ = ["VERSION", "SCALP_REFERENCE", "combine_scoreboard", "render_text"]
