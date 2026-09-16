#!/usr/bin/env python3
"""BTC15 dashboard session payload safety gate V1.

PURE PRESENTATION BOUNDARY | NO NETWORK | NO SIGNAL LOGIC | NO ORDERS

The frontend may render a stateful session-shadow payload only after this gate
checks the frozen app invariants. Any violation produces a fresh fail-closed
WAIT payload instead of attempting to render questionable state.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

VERSION = "BTC15_DASHBOARD_SESSION_PAYLOAD_GATE_V1"
REQUIRED_CARDS = {
    "FINAL_OUTCOME",
    "EARLY_OPPORTUNITY",
    "CONTRACT_TIME_LEFT",
    "SCALP_OPPORTUNITY",
    "FLIP_RISK",
}


@dataclass(frozen=True)
class PayloadGateDecision:
    accepted: bool
    fail_closed: bool
    reason: str
    source_status: str | None
    orders: bool = False
    signal_filtering: bool = False
    signal_suppression: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "fail_closed": self.fail_closed,
            "reason": self.reason,
            "source_status": self.source_status,
            "orders": self.orders,
            "signal_filtering": self.signal_filtering,
            "signal_suppression": self.signal_suppression,
        }


def _safe_fail_closed_dashboard(reason: str) -> dict[str, Any]:
    return {
        "contract": None,
        "card_order": [
            "FINAL_OUTCOME",
            "EARLY_OPPORTUNITY",
            "CONTRACT_TIME_LEFT",
            "SCALP_OPPORTUNITY",
            "FLIP_RISK",
        ],
        "cards": {
            "FINAL_OUTCOME": {"id": "FINAL_OUTCOME", "action": "WAIT · PRESENTATION GATE", "primary": "NO ACTION", "tone": "neutral", "rows": []},
            "EARLY_OPPORTUNITY": {"id": "EARLY_OPPORTUNITY", "action": "WAIT · PRESENTATION GATE", "primary": "NO ACTION", "tone": "neutral", "rows": []},
            "CONTRACT_TIME_LEFT": {"id": "CONTRACT_TIME_LEFT", "primary": "—:—", "visible_timer_count": 1, "tone": "neutral"},
            "SCALP_OPPORTUNITY": {"id": "SCALP_OPPORTUNITY", "action": "WAIT · PRESENTATION GATE", "primary": "NO ACTION · SOURCE NOT READY", "tone": "neutral", "rows": []},
            "FLIP_RISK": {"id": "FLIP_RISK", "primary": "NOT CALIBRATED", "numeric_value": None, "numeric_visible": False, "tone": "neutral"},
        },
        "gate_block_reason": reason,
        "safety": {
            "manual_execution_only": True,
            "manual_position_confirmed": False,
            "numeric_flip_risk_visible": False,
            "watch_warning_thresholds_visible": False,
            "orders": False,
            "order_action": None,
        },
    }


def _violation(payload: Mapping[str, Any]) -> str | None:
    p = dict(payload or {})
    dashboard = dict(p.get("dashboard") or {})
    safety = dict(dashboard.get("safety") or {})
    cards = dict(dashboard.get("cards") or {})

    if p.get("manual_execution_only") is not True:
        return "MANUAL_EXECUTION_FLAG_MISSING"
    if p.get("orders") is not False or p.get("order_action") is not None:
        return "ORDER_CAPABILITY_PRESENT"
    if p.get("production_logic_changed") is not False:
        return "PRODUCTION_LOGIC_CHANGE_MARKER"
    if p.get("signal_thresholds_changed") is not False:
        return "SIGNAL_THRESHOLD_CHANGE_MARKER"
    if p.get("numeric_flip_risk_visible") is not False:
        return "NUMERIC_FLIP_RISK_VISIBLE"
    if p.get("watch_warning_thresholds_visible") is not False:
        return "UNCERTIFIED_WATCH_THRESHOLD_VISIBLE"
    if set(cards) != REQUIRED_CARDS:
        return "CARD_SET_DRIFT"

    timer = dict(cards.get("CONTRACT_TIME_LEFT") or {})
    if timer.get("visible_timer_count") != 1:
        return "CANONICAL_TIMER_COUNT_DRIFT"

    flip = dict(cards.get("FLIP_RISK") or {})
    if flip.get("numeric_visible") is not False or flip.get("numeric_value") is not None:
        return "FLIP_RISK_NUMERIC_LEAK"

    if safety.get("orders") is not False or safety.get("order_action") is not None:
        return "DASHBOARD_ORDER_CAPABILITY_PRESENT"
    if safety.get("manual_position_confirmed") is not False:
        return "MANUAL_POSITION_ASSUMED"

    # When the outer source is fail-closed, the three actionable cards must all
    # remain WAIT. A partial SCALP-only fail-close is allowed when outer ok=True.
    if p.get("ok") is False:
        for card_id in ("FINAL_OUTCOME", "EARLY_OPPORTUNITY", "SCALP_OPPORTUNITY"):
            action = str((cards.get(card_id) or {}).get("action") or "")
            if not action.startswith("WAIT ·"):
                return "OUTER_FAIL_CLOSED_ACTION_LEAK"
    return None


def gate_session_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = copy.deepcopy(dict(payload or {}))
    violation = _violation(raw)
    source_status = str(raw.get("status") or "") or None

    if violation is not None:
        decision = PayloadGateDecision(False, True, violation, source_status)
        return {
            "version": VERSION,
            "gate": decision.to_dict(),
            "dashboard": _safe_fail_closed_dashboard(violation),
            "manual_execution_only": True,
            "order_action": None,
            "orders": False,
        }

    # A correctly constructed upstream fail-closed payload is safe to render as
    # WAIT; accepted does not mean actionable.
    upstream_fail_closed = raw.get("ok") is False
    decision = PayloadGateDecision(
        True,
        upstream_fail_closed,
        "SAFE_FAIL_CLOSED_PAYLOAD" if upstream_fail_closed else "SAFE_SESSION_PAYLOAD",
        source_status,
    )
    return {
        "version": VERSION,
        "gate": decision.to_dict(),
        "dashboard": copy.deepcopy(raw["dashboard"]),
        "manual_execution_only": True,
        "order_action": None,
        "orders": False,
    }


__all__ = ["VERSION", "REQUIRED_CARDS", "PayloadGateDecision", "gate_session_payload"]
