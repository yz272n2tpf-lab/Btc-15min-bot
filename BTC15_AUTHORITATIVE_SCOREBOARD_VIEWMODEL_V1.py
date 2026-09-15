#!/usr/bin/env python3
"""
BTC15 authoritative scoreboard view model V1.

PURE PRESENTATION ONLY | READ ONLY | NO SIGNAL CHANGES | NO ORDERS

Turns the frozen authoritative scoreboard payload into compact app-ready cards.
It adds no strategy judgments and never exposes numeric Flip Risk.
"""
from __future__ import annotations

from typing import Any, Mapping

VERSION = "BTC15_AUTHORITATIVE_SCOREBOARD_VIEWMODEL_V1"

GATES = {
    "final": {"eligible": 30, "settled": 12},
    "early": {"eligible": 30, "settled": 12},
    "handoff": {"eligible": 30, "handoffs": 10, "settled": 12},
    "excursion": {"eligible": 30, "completed": 10},
    "flip": {"complete": 30, "predictions": 240},
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


def pct(v: Any) -> str:
    x = _f(v)
    return "—" if x is None else f"{100*x:.1f}%"


def cents(v: Any) -> str:
    x = _f(v)
    return "—" if x is None else f"{100*x:.1f}¢"


def minutes(v: Any) -> str:
    x = _f(v)
    return "—" if x is None else f"{x:.2f}m"


def _source_connected(board: Mapping[str, Any], key: str) -> bool:
    return bool(_m(_m(board.get("sources")).get(key)).get("connected"))


def build_viewmodel(board: Mapping[str, Any]) -> dict[str, Any]:
    f = _m(board.get("final"))
    e = _m(board.get("early"))
    s = _m(board.get("scalp"))
    x = _m(board.get("early_excursion"))
    h = _m(board.get("handoff"))
    r = _m(board.get("flip_risk"))
    o = _m(board.get("overall"))

    final_eligible, final_settled = _i(f.get("eligible_contracts")), _i(f.get("settled_calls"))
    early_eligible, early_settled = _i(e.get("eligible_contracts")), _i(e.get("settled_calls"))
    hand_eligible, handoffs = _i(h.get("eligible_contracts")), _i(h.get("handoffs"))
    hand_settled = _i(h.get("settled_final_locks"))
    exc_eligible, exc_completed = _i(x.get("eligible_contracts")), _i(x.get("completed"))
    flip_complete, flip_preds = _i(r.get("prediction_complete_contracts")), _i(r.get("settled_predictions"))

    return {
        "version": VERSION,
        "safety": {
            "presentation_only": True,
            "orders": False,
            "manual_execution_only": True,
            "numeric_flip_risk_hidden": True,
            "blended_system_accuracy_forbidden": True,
        },
        "cards": {
            "final": {
                "title": "FINAL OUTCOME",
                "connected": _source_connected(board, "final"),
                "accuracy": pct(f.get("directional_accuracy")),
                "coverage": pct(f.get("final_only_coverage")),
                "avg_time_left": minutes(f.get("avg_minutes_left")),
                "avg_kalshi_price": cents(f.get("avg_locked_side_ask")),
                "cheap_entries_le50": _i(f.get("ask_le_50c_n")),
                "sample_progress": f"{final_eligible}/{GATES['final']['eligible']} eligible · {final_settled}/{GATES['final']['settled']} settled locks",
                "sample_ready": bool(f.get("sample_ready")),
                "note": "Directional accuracy and entry price are separate.",
            },
            "early": {
                "title": "EARLY OPPORTUNITY",
                "connected": _source_connected(board, "early"),
                "coverage": pct(e.get("early_only_coverage")),
                "avg_entry_price": cents(e.get("avg_entry_ask")),
                "avg_time_left": minutes(e.get("avg_minutes_left")),
                "ideal_entries_25_35": _i(e.get("ideal_25_35c_n")),
                "cheap_entries_le50": _i(e.get("ask_le_50c_n")),
                "sample_progress": f"{early_eligible}/{GATES['early']['eligible']} eligible · {early_settled}/{GATES['early']['settled']} settled EARLY calls",
                "sample_ready": bool(e.get("sample_ready")),
                "note": "Settlement-side rate is secondary, not FINAL accuracy.",
            },
            "scalp": {
                "title": "SCALP / REVERSAL",
                "plus10_move_rate": pct(s.get("plus10_move_rate")),
                "opportunities": _i(s.get("completed_serial_opportunities")),
                "fresh_plus10_reference": pct(s.get("fresh_plus10_move_rate")),
                "note": "Price-movement metric, not FINAL accuracy.",
            },
            "early_excursion": {
                "title": "EARLY TRADE UTILITY",
                "connected": _source_connected(board, "early_excursion"),
                "avg_entry_price": cents(x.get("avg_entry_ask")),
                "avg_best_move": cents(x.get("avg_mfe")),
                "avg_worst_move": cents(x.get("avg_mae")),
                "plus5": pct(x.get("plus5_rate")),
                "plus10": pct(x.get("plus10_rate")),
                "plus15": pct(x.get("plus15_rate")),
                "plus20": pct(x.get("plus20_rate")),
                "sample_progress": f"{exc_eligible}/{GATES['excursion']['eligible']} eligible · {exc_completed}/{GATES['excursion']['completed']} completed EARLY opportunities",
                "sample_ready": bool(x.get("sample_ready")),
                "note": "Uses later same-side Kalshi BID minus protected EARLY ask.",
            },
            "handoff": {
                "title": "EARLY → FINAL",
                "connected": _source_connected(board, "handoff"),
                "any_anchor_coverage": pct(h.get("any_anchor_coverage")),
                "dual_anchor_coverage": pct(h.get("dual_anchor_coverage")),
                "side_agreement": pct(h.get("side_agreement_rate")),
                "avg_gap": minutes(h.get("avg_handoff_gap_minutes")),
                "sample_progress": f"{hand_eligible}/{GATES['handoff']['eligible']} eligible · {handoffs}/{GATES['handoff']['handoffs']} handoffs · {hand_settled}/{GATES['handoff']['settled']} settled FINAL locks",
                "sample_ready": bool(h.get("sample_ready")),
                "note": "Only this common-universe lane may certify union coverage.",
            },
            "flip_risk": {
                "title": "FLIP RISK",
                "connected": _source_connected(board, "flip_risk"),
                "value": None,
                "display": "NOT CALIBRATED",
                "sample_progress": f"{flip_complete}/{GATES['flip']['complete']} complete contracts · {flip_preds}/{GATES['flip']['predictions']} settled predictions",
                "sample_ready": bool(r.get("sample_ready")),
                "note": "Numeric risk remains hidden until validation and manual display approval.",
            },
            "system": {
                "title": "SYSTEM STATUS",
                "union_coverage": pct(o.get("certified_union_coverage")),
                "union_status": o.get("certified_union_status", "NOT CERTIFIED"),
                "blended_accuracy": None,
                "note": "No single blended system-accuracy percentage is valid.",
            },
        },
    }


__all__ = ["VERSION", "GATES", "build_viewmodel", "pct", "cents", "minutes"]
