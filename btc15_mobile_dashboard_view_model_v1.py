#!/usr/bin/env python3
"""BTC15 mobile dashboard view-model V1.

PURE PRESENTATION | NO NETWORK | NO ORDERS

Converts the already-evaluated combined dashboard state + scalp UI state into a
stable card model for iPhone/iPad. It follows the frozen app language contract.
It never qualifies/suppresses a signal, changes thresholds, or assumes an order.

Key rule: an internally ACTIVE/PROTECT/EXIT scalp whose original entry was not
an acceptable manual-entry path is rendered as TRACKING ONLY. The underlying
lifecycle remains available for diagnostics, but user-facing PROTECT/EXIT wording
is suppressed when no acceptable manual entry was presented.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

VERSION = "BTC15_MOBILE_DASHBOARD_VIEW_MODEL_V1"
CARD_ORDER = (
    "FINAL_OUTCOME",
    "EARLY_OPPORTUNITY",
    "CONTRACT_TIME_LEFT",
    "SCALP_OPPORTUNITY",
    "FLIP_RISK",
)


def _finite(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def _pct(v: Any) -> str:
    x = _finite(v)
    return "—" if x is None else f"{x * 100:.0f}%"


def _cents(v: Any) -> str:
    x = _finite(v)
    return "—" if x is None else f"{x * 100:.0f}¢"


def _cents_raw(v: Any) -> float | None:
    x = _finite(v)
    return None if x is None else x * 100.0


def _signed_cents(v: Any) -> str:
    x = _finite(v)
    if x is None:
        return "—"
    c = x * 100.0
    return f"{c:+.1f}¢"


def _seconds_text(v: Any) -> str:
    x = _finite(v)
    if x is None:
        return "—:—"
    x = max(0, int(round(x)))
    return f"{x // 60}:{x % 60:02d}"


def _entry_quality_from_prob(v: Any) -> dict[str, Any]:
    x = _finite(v)
    if x is None:
        return {"tier": "UNAVAILABLE", "label": "WAIT", "tone": "neutral", "manual_entry_path": False}
    if .25 <= x <= .35:
        return {"tier": "IDEAL_25_35", "label": "IDEAL ENTRY", "tone": "positive", "manual_entry_path": True}
    if .36 <= x <= .50:
        return {"tier": "GOOD_36_50", "label": "GOOD ENTRY", "tone": "positive", "manual_entry_path": True}
    if x < .25:
        return {"tier": "BELOW_25", "label": "LOW PRICE · CHECK SIGNAL", "tone": "caution", "manual_entry_path": False}
    return {"tier": "ABOVE_50", "label": "DON'T CHASE", "tone": "caution", "manual_entry_path": False}


def _row(label: str, value: str, *, visible: bool = True) -> dict[str, Any]:
    return {"label": label, "value": value, "visible": visible}


def _side_ask(combined: Mapping[str, Any], side: str | None) -> float | None:
    s = str(side or "").upper()
    if s == "UP":
        return _finite(combined.get("up_ask"))
    if s == "DOWN":
        return _finite(combined.get("down_ask"))
    return None


def _source_wait_text(ui: Mapping[str, Any]) -> str:
    source = dict(ui.get("source") or {})
    reason = str(source.get("block_reason") or "").upper()
    if "CONTRACT" in reason or "SYNC" in reason:
        return "WAIT · SYNCING CONTRACT"
    if "STALE" in reason or source.get("source_fresh") is False:
        return "WAIT · SCALP DATA NOT FRESH"
    if source.get("integration_ready") is False:
        return "WAIT · SCALP NOT READY"
    return "WATCHING FOR SCALP"


def build_final_card(combined: Mapping[str, Any]) -> dict[str, Any]:
    f = dict(combined.get("final") or {})
    state = str(f.get("state") or "WATCH").upper()
    side = str(f.get("side") or "").upper() or None
    fair = _finite(f.get("fair"))
    ask = _side_ask(combined, side)
    quality = _entry_quality_from_prob(ask)

    if state == "LOCK" and side in {"UP", "DOWN"}:
        action = f"LOCK · {side}"
        primary = f"{side} {_pct(fair)}"
        subline = "OUTCOME LOCK · ENTRY EXPENSIVE" if quality["tier"] == "ABOVE_50" else quality["label"]
        tone = "lock"
    elif state == "QUALIFIED" and side in {"UP", "DOWN"}:
        action = f"LEAN {side}"
        primary = f"{side} {_pct(fair)}"
        subline = quality["label"]
        tone = "active"
    else:
        action = "FINAL CALL NOT READY"
        primary = "WATCHING FOR CONFIRMATION"
        subline = "WAIT"
        tone = "neutral"

    rows = [
        _row("Confidence", _pct(fair)),
        _row("Kalshi Price", _cents(ask)),
        _row("Entry Quality", quality["label"]),
        _row("Reason", "Waiting for validated evidence." if state == "WATCH" else "Validated outcome state."),
    ]
    return {
        "id": "FINAL_OUTCOME",
        "title": "FINAL OUTCOME",
        "action": action,
        "primary": primary,
        "subline": subline,
        "tone": tone,
        "rows": rows,
        "fixed_row_count": 4,
        "reason_max_lines": 2,
        "time_left_source": "CONTRACT_TIME_LEFT",
    }


def build_early_card(combined: Mapping[str, Any]) -> dict[str, Any]:
    e = dict(combined.get("early") or {})
    state = str(e.get("state") or "PASS").upper()
    side = str(e.get("side") or "").upper() or None
    ask = _finite(e.get("ask"))
    fair = _finite(e.get("fair"))
    edge = _finite(e.get("edge"))
    quality = _entry_quality_from_prob(ask)

    if state == "QUALIFIED" and side in {"UP", "DOWN"}:
        action = f"EARLY {side} OPPORTUNITY"
        primary = quality["label"] if quality["manual_entry_path"] else "TRACKING ONLY · DON'T CHASE"
        tone = quality["tone"]
    else:
        action = "EARLY WATCH"
        primary = "WAITING FOR AN EARLY EDGE"
        tone = "neutral"

    rows = [
        _row("Kalshi Entry", _cents(ask)),
        _row("Model Fair", _pct(fair)),
        _row("Model Edge", _pct(edge)),
        _row("Entry Quality", quality["label"]),
    ]
    return {
        "id": "EARLY_OPPORTUNITY",
        "title": "EARLY OPPORTUNITY",
        "action": action,
        "primary": primary,
        "tone": tone,
        "rows": rows,
        "fixed_row_count": 4,
        "time_left_source": "CONTRACT_TIME_LEFT",
    }


def build_timer_card(combined: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": "CONTRACT_TIME_LEFT",
        "title": "CONTRACT TIME LEFT",
        "primary": _seconds_text(combined.get("canonical_seconds_left")),
        "canonical": True,
        "visible_timer_count": 1,
        "tone": "neutral",
    }


def build_scalp_card(ui_state: Mapping[str, Any]) -> dict[str, Any]:
    ui = dict(ui_state or {})
    source = dict(ui.get("source") or {})
    lifecycle = str(ui.get("lifecycle_state") or "PASS").upper()
    side = str(ui.get("side") or "").upper() or None
    opp = ui.get("opportunity_index")
    completed = int(ui.get("serial_opportunities_completed") or 0)
    scanning = ui.get("scanning_for_next") is True
    guidance = dict(ui.get("entry_guidance") or {})
    tier = str(guidance.get("tier") or "UNAVAILABLE")
    manual_path = tier in {"IDEAL_25_35", "GOOD_36_50"}
    app_ready = source.get("app_ready") is True

    entry_c = _finite(ui.get("entry_ask_c"))
    bid_c = _finite(ui.get("current_bid_c"))
    gain_c = _finite(ui.get("exec_gain_c"))
    peak_c = _finite(ui.get("peak_exec_gain_c"))
    giveback_c = _finite(ui.get("giveback_from_peak_c"))

    tracking_only = bool(app_ready and lifecycle in {"ACTIVE", "PROTECT", "EXIT"} and not manual_path)

    if not app_ready:
        action = _source_wait_text(ui)
        primary = "NO ACTION · SOURCE NOT READY"
        protection = "NO POSITION ASSUMED"
        tone = "neutral"
    elif scanning:
        action = "WATCHING FOR SCALP"
        primary = f"SCANNING FOR #{completed + 1}"
        protection = "WAIT"
        tone = "neutral"
    elif lifecycle == "PASS":
        action = "WATCHING FOR SCALP"
        primary = "WAITING FOR A QUALIFIED MOVE"
        protection = "WAIT"
        tone = "neutral"
    elif tracking_only:
        n = f" #{opp}" if opp is not None else ""
        action = f"{side or 'SCALP'}{n} · TRACKING ONLY"
        primary = "MOVE VALID · NO ENTRY · DON'T CHASE" if tier == "CAUTION_ABOVE_50" else "LOW PRICE · CHECK SIGNAL"
        protection = "MODEL TRACKING ONLY · NO POSITION ASSUMED"
        tone = "caution"
    elif lifecycle == "ACTIVE":
        n = f" #{opp}" if opp is not None else ""
        action = f"{side or 'SCALP'}{n} · ENTRY AVAILABLE"
        primary = "HOLD · MOVE STILL BUILDING"
        protection = "PROTECTION NOT ARMED"
        tone = "positive"
    elif lifecycle == "PROTECT":
        action = "PROTECT PROFITS"
        primary = "MOVE REACHED PROTECTION LEVEL"
        protection = "WATCH FOR GIVEBACK"
        tone = "protect"
    else:  # EXIT
        action = "EXIT NOW · PROTECT PROFITS"
        primary = "VALIDATED GIVEBACK EXIT"
        protection = "PROTECTED EXIT"
        tone = "exit"

    rows = [
        _row("Entry Price", "—" if entry_c is None else f"{entry_c:.0f}¢"),
        _row("Current Sell Price", "—" if bid_c is None else f"{bid_c:.0f}¢"),
        _row("Profit Now", "—" if gain_c is None else f"{gain_c:+.1f}¢"),
        _row("Best Profit", "—" if peak_c is None else f"{peak_c:+.1f}¢"),
        _row("Profit Given Back", "—" if giveback_c is None else f"{giveback_c:.1f}¢"),
        _row("Profit Protection", protection),
    ]
    return {
        "id": "SCALP_OPPORTUNITY",
        "title": "SCALP OPPORTUNITY",
        "action": action,
        "primary": primary,
        "tone": tone,
        "rows": rows,
        "fixed_row_count": 6,
        "time_left_source": "CONTRACT_TIME_LEFT",
        "tracking_only": tracking_only,
        "manual_entry_path_available": manual_path,
        "underlying_lifecycle_state": lifecycle,
        "opportunity_index": opp,
        "serial_opportunities_completed": completed,
        "scanning_for_next": scanning,
    }


def build_flip_risk_card(ui_state: Mapping[str, Any]) -> dict[str, Any]:
    # Numeric values are deliberately absent until separate certification.
    return {
        "id": "FLIP_RISK",
        "title": "FLIP RISK",
        "primary": "NOT CALIBRATED",
        "numeric_value": None,
        "numeric_visible": False,
        "tone": "neutral",
    }


def build_mobile_dashboard_view_model(
    combined_state: Mapping[str, Any],
    scalp_ui_state: Mapping[str, Any],
) -> dict[str, Any]:
    combined = dict(combined_state or {})
    ui = dict(scalp_ui_state or {})
    cards = {
        "FINAL_OUTCOME": build_final_card(combined),
        "EARLY_OPPORTUNITY": build_early_card(combined),
        "CONTRACT_TIME_LEFT": build_timer_card(combined),
        "SCALP_OPPORTUNITY": build_scalp_card(ui),
        "FLIP_RISK": build_flip_risk_card(ui),
    }
    return {
        "version": VERSION,
        "contract": combined.get("contract") or ui.get("contract"),
        "card_order": list(CARD_ORDER),
        "cards": cards,
        "layout": {
            "iphone_columns": 1,
            "ipad_columns": 2,
            "single_canonical_timer": True,
            "reason_max_lines": 2,
            "fixed_card_row_counts": True,
            "raw_price_ticks_do_not_define_tone": True,
        },
        "safety": {
            "manual_execution_only": True,
            "orders": False,
            "order_action": None,
            "numeric_flip_risk_visible": False,
            "watch_warning_thresholds_visible": False,
            "blended_accuracy": None,
        },
    }


__all__ = [
    "build_mobile_dashboard_view_model",
    "build_final_card",
    "build_early_card",
    "build_scalp_card",
    "build_timer_card",
    "build_flip_risk_card",
]
