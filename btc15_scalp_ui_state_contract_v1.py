#!/usr/bin/env python3
"""BTC15 scalp UI state contract V1.

PURE PRESENTATION | READ ONLY | SIGNAL ONLY | NO ORDERS

This module adapts already-evaluated Combined State Bridge V5 + direct SCALP
state into one stable app-facing payload. It does not qualify a signal, change
thresholds, suppress a frozen signal, fetch data, place orders, or promote any
research rule.

Entry guidance is presentation only:
- 25-35c: IDEAL
- 36-50c: GOOD
- >50c: CAUTION / WAIT FOR PULLBACK
- <25c: BELOW_IDEAL_BAND (shown without upgrading confidence)

The prospective Watch->Exit warning study is not certified, so no numeric or
threshold-derived WATCH warning is surfaced here. The existing frozen 4c EXIT
state may be shown because it already comes from the protected lifecycle.
Numeric Flip Risk also remains hidden until separately certified.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping

VERSION = "BTC15_SCALP_UI_STATE_CONTRACT_V1"

IDEAL_MIN = 0.25
IDEAL_MAX = 0.35
GOOD_MIN = 0.36
GOOD_MAX = 0.50

VALID_LIFECYCLE_STATES = {"PASS", "ACTIVE", "PROTECT", "EXIT"}


def _finite(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def _prob(v: Any) -> float | None:
    x = _finite(v)
    if x is None or not 0.0 <= x <= 1.0:
        return None
    return x


def _cents(v: Any) -> float | None:
    x = _prob(v)
    return None if x is None else round(x * 100.0, 3)


def entry_guidance(entry_ask: Any) -> dict[str, Any]:
    ask = _prob(entry_ask)
    ask_c = _cents(entry_ask)
    if ask is None:
        return {
            "tier": "UNAVAILABLE",
            "label": "WAIT FOR QUALIFIED ENTRY",
            "entry_ask_c": None,
            "within_target_le50": False,
            "ideal_25_35": False,
            "good_36_50": False,
            "presentation_only": True,
        }
    if IDEAL_MIN <= ask <= IDEAL_MAX:
        tier, label = "IDEAL_25_35", "IDEAL ENTRY BAND"
    elif GOOD_MIN <= ask <= GOOD_MAX:
        tier, label = "GOOD_36_50", "GOOD ENTRY BAND"
    elif ask < IDEAL_MIN:
        tier, label = "BELOW_IDEAL_BAND", "BELOW 25c · REVIEW SIGNAL QUALITY"
    else:
        tier, label = "CAUTION_ABOVE_50", "CAUTION · WAIT FOR PULLBACK"
    return {
        "tier": tier,
        "label": label,
        "entry_ask_c": ask_c,
        "within_target_le50": bool(ask <= GOOD_MAX),
        "ideal_25_35": bool(IDEAL_MIN <= ask <= IDEAL_MAX),
        "good_36_50": bool(GOOD_MIN <= ask <= GOOD_MAX),
        "presentation_only": True,
    }


def _display_state(lifecycle_state: str, app_ready: bool) -> str:
    if not app_ready:
        return "WAIT"
    return {
        "PASS": "WAIT",
        "ACTIVE": "ACTIVE",
        "PROTECT": "PROTECT",
        "EXIT": "EXIT",
    }[lifecycle_state]


@dataclass(frozen=True)
class ScalpUIStateContractV1:
    version: str
    contract: str | None
    seconds_left: float | None
    display_state: str
    lifecycle_state: str
    side: str | None
    opportunity_index: int | None
    serial_opportunities_completed: int
    scanning_for_next: bool
    entry_guidance: dict[str, Any]
    entry_ask_c: float | None
    current_bid_c: float | None
    exec_gain_c: float | None
    peak_exec_gain_c: float | None
    giveback_from_peak_c: float | None
    management_message: str
    protection_armed: bool
    pullback_context: bool
    frozen_exit_triggered: bool
    watch_warning: dict[str, Any]
    numeric_flip_risk: dict[str, Any]
    source: dict[str, Any]
    horizon_context: dict[str, Any]
    manual_execution_only: bool = True
    order_action: None = None
    orders: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_scalp_ui_state(
    combined_state: Mapping[str, Any],
    direct_scalp_state: Mapping[str, Any] | None = None,
) -> ScalpUIStateContractV1:
    combined = dict(combined_state or {})
    direct = dict(direct_scalp_state or {})
    scalp = dict(combined.get("scalp") or {})

    lifecycle = str(scalp.get("state") or direct.get("state") or "PASS").upper()
    if lifecycle not in VALID_LIFECYCLE_STATES:
        lifecycle = "PASS"

    aligned = combined.get("scalp_contract_aligned") is True
    fresh = combined.get("scalp_source_fresh") is True
    integration_ready = combined.get("scalp_integration_ready") is True
    app_ready = bool(aligned and fresh and integration_ready)

    entry_ask = scalp.get("entry_ask")
    if entry_ask is None:
        entry_ask = direct.get("entry_price")
    current_bid = scalp.get("current_bid")
    if current_bid is None:
        current_bid = direct.get("current_bid")
    exec_gain = scalp.get("exec_gain")
    if exec_gain is None:
        exec_gain = direct.get("exec_gain")
    peak_gain = scalp.get("peak_exec_gain")
    if peak_gain is None:
        peak_gain = direct.get("peak_exec_gain")

    giveback = _finite(direct.get("giveback_from_peak"))
    if giveback is None:
        p = _finite(peak_gain)
        g = _finite(exec_gain)
        giveback = max(0.0, p - g) if p is not None and g is not None else None

    opportunity_index = direct.get("opportunity_index")
    if opportunity_index is None:
        opportunity_index = combined.get("scalp_opportunity_index")
    try:
        opportunity_index = None if opportunity_index is None else int(opportunity_index)
    except Exception:
        opportunity_index = None

    completed = direct.get("serial_opportunities_completed")
    if completed is None:
        completed = combined.get("scalp_serial_opportunities_completed")
    try:
        completed = int(completed or 0)
    except Exception:
        completed = 0

    scanning = bool(
        direct.get("scanning_for_next") is True
        or combined.get("scalp_scanning_for_next") is True
    )

    protection_armed = bool(
        direct.get("armed") is True
        or lifecycle in {"PROTECT", "EXIT"}
    )
    pullback_context = bool(direct.get("pullback_detected") is True)
    frozen_exit = bool(direct.get("exit_triggered") is True or lifecycle == "EXIT")

    management = str(
        combined.get("scalp_management_message")
        or direct.get("management_message")
        or {
            "PASS": "NO QUALIFIED SCALP",
            "ACTIVE": "SCALP ACTIVE · BUILDING",
            "PROTECT": "PROTECT PROFITS",
            "EXIT": "EXIT / PROTECT PROFITS NOW",
        }[lifecycle]
    )

    source = {
        "app_ready": app_ready,
        "contract_aligned": aligned,
        "source_fresh": fresh,
        "integration_ready": integration_ready,
        "source_age_sec": _finite(combined.get("scalp_source_age_sec")),
        "timer_delta_sec": _finite(combined.get("scalp_timer_delta_sec")),
        "block_reason": combined.get("scalp_block_reason"),
        "fail_closed": not app_ready,
    }

    watch_warning = {
        "visible": False,
        "certified": False,
        "status": "HIDDEN_PENDING_FORWARD_CERTIFICATION",
        "research_thresholds_exposed": False,
        "frozen_exit_remains_visible": frozen_exit,
    }

    numeric_flip_risk = {
        "visible": False,
        "value": None,
        "certified": False,
        "status": "HIDDEN_PENDING_CERTIFICATION",
    }

    horizon_context = {
        "early": dict(combined.get("early") or {}),
        "final": dict(combined.get("final") or {}),
        "headline": combined.get("headline"),
        "context_labels": list(combined.get("context_labels") or ()),
        "blended_accuracy": None,
        "horizons_remain_separate": True,
    }

    return ScalpUIStateContractV1(
        version=VERSION,
        contract=str(combined.get("contract") or direct.get("contract") or "") or None,
        seconds_left=_finite(combined.get("canonical_seconds_left")),
        display_state=_display_state(lifecycle, app_ready),
        lifecycle_state=lifecycle,
        side=scalp.get("side") or direct.get("side"),
        opportunity_index=opportunity_index,
        serial_opportunities_completed=completed,
        scanning_for_next=scanning,
        entry_guidance=entry_guidance(entry_ask),
        entry_ask_c=_cents(entry_ask),
        current_bid_c=_cents(current_bid),
        exec_gain_c=None if _finite(exec_gain) is None else round(float(exec_gain) * 100.0, 3),
        peak_exec_gain_c=None if _finite(peak_gain) is None else round(float(peak_gain) * 100.0, 3),
        giveback_from_peak_c=None if giveback is None else round(giveback * 100.0, 3),
        management_message=management,
        protection_armed=protection_armed,
        pullback_context=pullback_context,
        frozen_exit_triggered=frozen_exit,
        watch_warning=watch_warning,
        numeric_flip_risk=numeric_flip_risk,
        source=source,
        horizon_context=horizon_context,
    )


__all__ = [
    "ScalpUIStateContractV1",
    "build_scalp_ui_state",
    "entry_guidance",
]
