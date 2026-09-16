#!/usr/bin/env python3
"""BTC15 mobile dashboard view-model V2 — canonical time guardrails.

PURE PRESENTATION | NO NETWORK | NO ORDERS

V2 wraps the already-green V1 card model and augments only the single canonical
timer card with display-only 5m / 3m / rollover context. It does not qualify,
suppress, re-rank, enter, protect, or exit a signal.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping

import btc15_mobile_dashboard_view_model_v1 as v1
from btc15_time_left_guardrail_v1 import time_left_guardrail

VERSION = "BTC15_MOBILE_DASHBOARD_VIEW_MODEL_V2"
CARD_ORDER = v1.CARD_ORDER


def build_mobile_dashboard_view_model(
    combined_state: Mapping[str, Any],
    scalp_ui_state: Mapping[str, Any],
) -> dict[str, Any]:
    out = copy.deepcopy(v1.build_mobile_dashboard_view_model(combined_state, scalp_ui_state))
    guard = time_left_guardrail(combined_state.get("canonical_seconds_left"))
    timer = dict(out["cards"]["CONTRACT_TIME_LEFT"])
    timer.update({
        "guardrail_band": guard.band,
        "status_label": guard.label,
        "status_detail": guard.detail,
        "tone": guard.tone,
        "presentation_only": True,
        "signal_filtering": False,
        "signal_suppression": False,
        "changes_entry_rule": False,
        "changes_exit_rule": False,
    })
    out["cards"]["CONTRACT_TIME_LEFT"] = timer
    out["version"] = VERSION
    out["safety"]["time_guardrail_signal_filtering"] = False
    out["safety"]["time_guardrail_signal_suppression"] = False
    return out


# Re-export the unchanged V1 builders for callers that need individual cards.
build_final_card = v1.build_final_card
build_early_card = v1.build_early_card
build_scalp_card = v1.build_scalp_card
build_flip_risk_card = v1.build_flip_risk_card
build_timer_card_v1 = v1.build_timer_card


__all__ = [
    "VERSION",
    "CARD_ORDER",
    "build_mobile_dashboard_view_model",
    "build_final_card",
    "build_early_card",
    "build_scalp_card",
    "build_flip_risk_card",
    "build_timer_card_v1",
]
