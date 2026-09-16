#!/usr/bin/env python3
"""BTC15 mobile dashboard view-model V5 — manual-entry context continuity.

PURE PRESENTATION | NO NETWORK | NO ORDERS

V5 wraps V4 and makes same-opportunity entry-context wording sticky:
- TRACKING ONLY remains no-position for that scalp opportunity;
- an acceptable entry path remains eligible for normal ACTIVE/PROTECT/EXIT
  wording through later missing/transient entry telemetry;
- new contract or new opportunity resets from the new opportunity.

This does NOT confirm that the user actually placed a manual trade.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping

import btc15_mobile_dashboard_view_model_v4 as v4
from btc15_manual_entry_context_guard_v1 import (
    apply_manual_entry_context_to_scalp_card,
    resolve_manual_entry_context,
)

VERSION = "BTC15_MOBILE_DASHBOARD_VIEW_MODEL_V5"
CARD_ORDER = v4.CARD_ORDER


def build_mobile_dashboard_view_model(
    combined_state: Mapping[str, Any],
    scalp_ui_state: Mapping[str, Any],
    *,
    previous_model: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    out = v4.build_mobile_dashboard_view_model(
        combined_state,
        scalp_ui_state,
        previous_model=previous_model,
    )
    context = resolve_manual_entry_context(previous_model, out)

    out = copy.deepcopy(out)
    out["version"] = VERSION
    out["manual_entry_context"] = context.to_dict()
    out["cards"]["SCALP_OPPORTUNITY"] = apply_manual_entry_context_to_scalp_card(
        out["cards"]["SCALP_OPPORTUNITY"],
        context,
    )
    out["safety"]["manual_position_confirmed"] = False
    out["safety"]["manual_entry_context_signal_filtering"] = False
    out["safety"]["manual_entry_context_signal_suppression"] = False
    out["safety"]["manual_entry_context_changes_underlying_lifecycle"] = False
    return out


# Re-export unchanged card builders for static callers.
build_final_card = v4.build_final_card
build_early_card = v4.build_early_card
build_scalp_card = v4.build_scalp_card
build_flip_risk_card = v4.build_flip_risk_card


__all__ = [
    "VERSION",
    "CARD_ORDER",
    "build_mobile_dashboard_view_model",
    "build_final_card",
    "build_early_card",
    "build_scalp_card",
    "build_flip_risk_card",
]
