#!/usr/bin/env python3
"""BTC15 mobile dashboard view-model V3 — rollover history quarantine.

PURE PRESENTATION | NO NETWORK | NO ORDERS

V3 wraps the green V2 model. The current contract remains authoritative and its
five core cards are unchanged. V3 adds one fixed scalp-history slot that can
show sanitized prior-contract context after rollover. That history is never
actionable and cannot alter the new contract's signals.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping

import btc15_mobile_dashboard_view_model_v2 as v2
from btc15_dashboard_rollover_guard_v1 import apply_rollover_guard

VERSION = "BTC15_MOBILE_DASHBOARD_VIEW_MODEL_V3"
CARD_ORDER = v2.CARD_ORDER


def _empty_history_slot() -> dict[str, Any]:
    return {
        "reserved": True,
        "visible": False,
        "historical_only": True,
        "actionable": False,
        "source_contract": None,
        "headline": "",
        "detail": "",
        "tone": "muted",
        "terminal_kind": None,
        "order_action": None,
        "orders": False,
    }


def _history_slot(history: Mapping[str, Any] | None) -> dict[str, Any]:
    slot = _empty_history_slot()
    if not history:
        return slot
    h = dict(history)
    slot.update({
        "visible": True,
        "source_contract": h.get("source_contract"),
        "headline": str(h.get("headline") or "PREVIOUS CONTRACT · SCALP HISTORY"),
        "detail": str(h.get("detail") or "Historical context only."),
        "tone": "muted",
        "terminal_kind": h.get("terminal_kind"),
        "opportunity_index": h.get("opportunity_index"),
        "serial_opportunities_completed": h.get("serial_opportunities_completed"),
        "manual_position_assumed": h.get("manual_position_assumed") is True,
    })
    # Safety fields are reasserted instead of trusted from upstream history.
    slot["historical_only"] = True
    slot["actionable"] = False
    slot["order_action"] = None
    slot["orders"] = False
    return slot


def build_mobile_dashboard_view_model(
    combined_state: Mapping[str, Any],
    scalp_ui_state: Mapping[str, Any],
    *,
    previous_model: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    current = v2.build_mobile_dashboard_view_model(combined_state, scalp_ui_state)
    guarded = apply_rollover_guard(previous_model, current)
    out = copy.deepcopy(guarded["current"])
    out["version"] = VERSION
    out["scalp_history_slot"] = _history_slot(guarded.get("historical_scalp"))
    out["rollover"] = copy.deepcopy(guarded["rollover"])
    out["layout"]["scalp_history_slot_reserved"] = True
    out["layout"]["scalp_history_slot_changes_core_card_order"] = False
    out["safety"]["historical_scalp_actionable"] = False
    out["safety"]["historical_scalp_can_change_current_signals"] = False
    return out


# Re-export unchanged builders for convenience.
build_final_card = v2.build_final_card
build_early_card = v2.build_early_card
build_scalp_card = v2.build_scalp_card
build_flip_risk_card = v2.build_flip_risk_card


__all__ = [
    "VERSION",
    "CARD_ORDER",
    "build_mobile_dashboard_view_model",
    "build_final_card",
    "build_early_card",
    "build_scalp_card",
    "build_flip_risk_card",
]
