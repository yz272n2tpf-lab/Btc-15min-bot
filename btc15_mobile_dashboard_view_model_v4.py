#!/usr/bin/env python3
"""BTC15 mobile dashboard view-model V4 — persistent scalp memory slot.

PURE PRESENTATION | NO NETWORK | NO ORDERS

V4 wraps V3. Rollover history remains authoritative on contract changes. Within
the same contract, V4 may reuse the reserved scalp-history slot to show a just-
finished scalp while scanning for or running a later opportunity.

Current five core cards are never changed by this memory layer.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping

import btc15_mobile_dashboard_view_model_v3 as v3
from btc15_scalp_memory_guard_v1 import remember_previous_scalp

VERSION = "BTC15_MOBILE_DASHBOARD_VIEW_MODEL_V4"
CARD_ORDER = v3.CARD_ORDER


def build_mobile_dashboard_view_model(
    combined_state: Mapping[str, Any],
    scalp_ui_state: Mapping[str, Any],
    *,
    previous_model: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    out = v3.build_mobile_dashboard_view_model(
        combined_state,
        scalp_ui_state,
        previous_model=previous_model,
    )

    decision = remember_previous_scalp(previous_model, out)
    out = copy.deepcopy(out)
    out["version"] = VERSION
    out["scalp_memory_guard"] = decision.to_dict()

    # Contract rollover history already filled by V3 takes precedence. Otherwise
    # same-contract completion memory may use the same fixed reserved slot.
    if not out["rollover"]["rollover_detected"] and decision.memory:
        out["scalp_history_slot"] = copy.deepcopy(decision.memory)
        out["scalp_history_slot"]["reserved"] = True
        out["scalp_history_slot"]["historical_only"] = True
        out["scalp_history_slot"]["actionable"] = False
        out["scalp_history_slot"]["order_action"] = None
        out["scalp_history_slot"]["orders"] = False

    out["presentation_integrity"] = {
        "ok": decision.blocked_reason is None,
        "blocked_reason": decision.blocked_reason,
        "armed_no_exit_handoff_blocked": decision.blocked_reason == "ARMED_NO_EXIT_HANDOFF_BLOCKED",
        "changes_current_signal_cards": False,
        "orders": False,
    }
    out["safety"]["scalp_memory_actionable"] = False
    out["safety"]["scalp_memory_changes_current_signals"] = False
    return out


# Re-export unchanged card builders.
build_final_card = v3.build_final_card
build_early_card = v3.build_early_card
build_scalp_card = v3.build_scalp_card
build_flip_risk_card = v3.build_flip_risk_card


__all__ = [
    "VERSION",
    "CARD_ORDER",
    "build_mobile_dashboard_view_model",
    "build_final_card",
    "build_early_card",
    "build_scalp_card",
    "build_flip_risk_card",
]
