#!/usr/bin/env python3
"""
BTC15 cross-service combined dashboard payload V2.

PURE COMPOSITION | SIGNAL ONLY | NO ORDERS

Combines:
1. one protected main-bot snapshot row (EARLY + FINAL + canonical timer/target/quotes),
2. one read-only generalized-SCALP /state payload,
3. the frozen side-effect-free integration composer.

It never recalculates protected EARLY/FINAL thresholds and never retunes SCALP.
Contract mismatch fails closed for SCALP instead of mixing two 15-minute markets.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from btc15_protected_module_adapter_v1 import (
    early_state_from_snapshot,
    final_state_from_snapshot,
)
from btc15_signal_integration_v1 import ScalpState, compose_contract_state

VALID_SCALP_STATES = {"PASS", "ACTIVE", "PROTECT", "EXIT"}


def _float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _side(value: Any) -> str | None:
    if value is None:
        return None
    x = str(value).strip().upper()
    return x if x in {"UP", "DOWN"} else None


def _seconds_left(snapshot: Mapping[str, Any]) -> float | None:
    v = _float(snapshot.get("seconds_left"))
    if v is not None:
        return max(0.0, v)
    m = _float(snapshot.get("time_left_min"))
    return None if m is None else max(0.0, 60.0 * m)


def scalp_state_from_bridge(payload: Mapping[str, Any] | None) -> ScalpState:
    if not payload:
        return ScalpState("PASS").normalized()
    state = str(payload.get("state") or "PASS").strip().upper()
    if state not in VALID_SCALP_STATES:
        state = "PASS"
    side = _side(payload.get("side"))
    if state != "PASS" and side is None:
        # Fail closed: actionable state without a side is malformed.
        state = "PASS"
    return ScalpState(
        state=state,
        side=side,
        entry_ask=_float(payload.get("entry_price")),
        current_bid=_float(payload.get("current_bid")),
        peak_exec_gain=_float(payload.get("peak_exec_gain")),
        exec_gain=_float(payload.get("exec_gain")),
        seconds_left=_float(payload.get("entry_seconds_left")),
    ).normalized()


@dataclass(frozen=True)
class CrossServiceDashboardPayload:
    contract: str
    canonical_seconds_left: float | None
    kalshi_target: float | None
    up_bid: float | None
    up_ask: float | None
    down_bid: float | None
    down_ask: float | None
    headline: str
    early: dict
    final: dict
    scalp: dict
    actionable_paths: tuple[str, ...]
    context_labels: tuple[str, ...]
    union_actionable: bool
    scalp_management_message: str
    scalp_contract_aligned: bool
    scalp_timer_delta_sec: float | None
    manual_execution_only: bool = True
    numeric_flip_risk_validated: bool = False
    order_action: None = None

    def to_dict(self) -> dict:
        return asdict(self)


def compose_cross_service_payload(
    snapshot: Mapping[str, Any],
    scalp_payload: Mapping[str, Any] | None,
) -> CrossServiceDashboardPayload:
    contract = str(snapshot.get("contract") or "").strip()
    if not contract:
        raise ValueError("protected snapshot contract is required")

    canonical_left = _seconds_left(snapshot)
    scalp_contract = str((scalp_payload or {}).get("contract") or "").strip()
    aligned = bool(scalp_contract and scalp_contract == contract)

    if aligned:
        scalp = scalp_state_from_bridge(scalp_payload)
        message = str((scalp_payload or {}).get("management_message") or "").strip()
        if not message:
            message = {
                "PASS": "NO QUALIFIED SCALP",
                "ACTIVE": "SCALP ACTIVE · BUILDING",
                "PROTECT": "PROTECT PROFITS",
                "EXIT": "EXIT / PROTECT PROFITS NOW",
            }[scalp.state]
        scalp_left = _float((scalp_payload or {}).get("contract_seconds_left"))
        timer_delta = (
            abs(canonical_left - scalp_left)
            if canonical_left is not None and scalp_left is not None
            else None
        )
    else:
        # Never blend a scalp from the preceding/following contract into the
        # current protected EARLY/FINAL timeline.
        scalp = ScalpState("PASS").normalized()
        message = "SCALP WAIT · CONTRACT SYNC"
        timer_delta = None

    early = early_state_from_snapshot(snapshot)
    final = final_state_from_snapshot(snapshot)
    combined = compose_contract_state(contract, early=early, final=final, scalp=scalp)

    return CrossServiceDashboardPayload(
        contract=contract,
        canonical_seconds_left=canonical_left,
        kalshi_target=_float(snapshot.get("kalshi_target")),
        up_bid=_float(snapshot.get("up_bid")),
        up_ask=_float(snapshot.get("up_ask")),
        down_bid=_float(snapshot.get("down_bid")),
        down_ask=_float(snapshot.get("down_ask")),
        headline=combined.headline,
        early=asdict(early),
        final=asdict(final),
        scalp=asdict(scalp),
        actionable_paths=combined.actionable_paths,
        context_labels=combined.context_labels,
        union_actionable=combined.union_actionable,
        scalp_management_message=message,
        scalp_contract_aligned=aligned,
        scalp_timer_delta_sec=timer_delta,
    )


__all__ = [
    "CrossServiceDashboardPayload",
    "scalp_state_from_bridge",
    "compose_cross_service_payload",
]
