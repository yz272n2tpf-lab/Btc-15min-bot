#!/usr/bin/env python3
"""BTC15 dashboard visual stability guard V1.

PURE PRESENTATION | NO NETWORK | NO ORDERS

Classifies view-model updates as semantic changes vs value-only ticks. The UI can
update numeric text continuously without blinking/recoloring cards when the
meaning has not changed. It also validates fixed card order/row counts so reason
or telemetry changes cannot silently change the dashboard geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import btc15_mobile_dashboard_view_model_v1 as vm

VERSION = "BTC15_DASHBOARD_VISUAL_STABILITY_GUARD_V1"


@dataclass(frozen=True)
class VisualUpdateDecision:
    semantic_changed: bool
    value_only_update: bool
    animate_emphasis: bool
    geometry_valid: bool
    reason: str
    manual_execution_only: bool = True
    orders: bool = False


def _card(model: Mapping[str, Any], card_id: str) -> dict[str, Any]:
    return dict((model.get("cards") or {}).get(card_id) or {})


def _row_values(card: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple(
        (str(r.get("label") or ""), r.get("value"))
        for r in (card.get("rows") or [])
        if isinstance(r, Mapping)
    )


def semantic_signature(model: Mapping[str, Any]) -> tuple[Any, ...]:
    """Meaning-only signature; intentionally excludes raw numeric values/reasons."""
    final = _card(model, "FINAL_OUTCOME")
    early = _card(model, "EARLY_OPPORTUNITY")
    scalp = _card(model, "SCALP_OPPORTUNITY")
    flip = _card(model, "FLIP_RISK")
    timer = _card(model, "CONTRACT_TIME_LEFT")
    return (
        model.get("contract"),
        tuple(model.get("card_order") or ()),
        final.get("action"), final.get("tone"), final.get("subline"),
        early.get("action"), early.get("tone"), early.get("primary"),
        scalp.get("action"), scalp.get("tone"), scalp.get("tracking_only"),
        scalp.get("underlying_lifecycle_state"), scalp.get("opportunity_index"),
        scalp.get("serial_opportunities_completed"), scalp.get("scanning_for_next"),
        flip.get("primary"), flip.get("numeric_visible"),
        timer.get("canonical"),
    )


def value_signature(model: Mapping[str, Any]) -> tuple[Any, ...]:
    """Numeric/text values that may tick without changing semantic presentation."""
    return (
        _card(model, "CONTRACT_TIME_LEFT").get("primary"),
        _row_values(_card(model, "FINAL_OUTCOME")),
        _row_values(_card(model, "EARLY_OPPORTUNITY")),
        _row_values(_card(model, "SCALP_OPPORTUNITY")),
    )


def validate_geometry(model: Mapping[str, Any]) -> tuple[bool, str]:
    order = list(model.get("card_order") or [])
    if order != list(vm.CARD_ORDER):
        return False, "CARD_ORDER_DRIFT"
    cards = dict(model.get("cards") or {})
    for card_id in vm.CARD_ORDER:
        if card_id not in cards:
            return False, f"MISSING_CARD:{card_id}"
    expected_rows = {
        "FINAL_OUTCOME": 4,
        "EARLY_OPPORTUNITY": 4,
        "SCALP_OPPORTUNITY": 6,
    }
    for card_id, expected in expected_rows.items():
        card = dict(cards.get(card_id) or {})
        rows = list(card.get("rows") or [])
        if int(card.get("fixed_row_count") or -1) != expected or len(rows) != expected:
            return False, f"ROW_COUNT_DRIFT:{card_id}"
    timer = dict(cards.get("CONTRACT_TIME_LEFT") or {})
    if timer.get("visible_timer_count") != 1 or timer.get("canonical") is not True:
        return False, "CANONICAL_TIMER_DRIFT"
    if (model.get("layout") or {}).get("single_canonical_timer") is not True:
        return False, "LAYOUT_TIMER_DRIFT"
    return True, "GEOMETRY_STABLE"


def decide_visual_update(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> VisualUpdateDecision:
    geometry_valid, geometry_reason = validate_geometry(current)
    if not geometry_valid:
        return VisualUpdateDecision(
            semantic_changed=False,
            value_only_update=False,
            animate_emphasis=False,
            geometry_valid=False,
            reason=geometry_reason,
        )
    if not previous:
        return VisualUpdateDecision(
            semantic_changed=True,
            value_only_update=False,
            animate_emphasis=False,
            geometry_valid=True,
            reason="INITIAL_RENDER",
        )
    prev_geometry, _ = validate_geometry(previous)
    if not prev_geometry:
        return VisualUpdateDecision(
            semantic_changed=True,
            value_only_update=False,
            animate_emphasis=False,
            geometry_valid=True,
            reason="RECOVERED_FROM_INVALID_PREVIOUS_GEOMETRY",
        )

    semantic_changed = semantic_signature(previous) != semantic_signature(current)
    values_changed = value_signature(previous) != value_signature(current)
    value_only = bool(values_changed and not semantic_changed)
    if semantic_changed:
        reason = "SEMANTIC_STATE_CHANGE"
    elif value_only:
        reason = "VALUE_TICK_NO_SEMANTIC_CHANGE"
    else:
        reason = "NO_VISIBLE_CHANGE"
    return VisualUpdateDecision(
        semantic_changed=semantic_changed,
        value_only_update=value_only,
        animate_emphasis=semantic_changed,
        geometry_valid=True,
        reason=reason,
    )


__all__ = [
    "VisualUpdateDecision",
    "semantic_signature",
    "value_signature",
    "validate_geometry",
    "decide_visual_update",
]
