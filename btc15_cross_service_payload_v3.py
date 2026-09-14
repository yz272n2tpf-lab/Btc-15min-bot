#!/usr/bin/env python3
"""
BTC15 cross-service combined dashboard payload V3.

PURE COMPOSITION | SIGNAL ONLY | NO ORDERS

V3 keeps the V2 contract/timer/module-preservation rules and additionally
requires the generalized SCALP V4 source to be fresh before any ACTIVE,
PROTECT, or EXIT state may compose into the protected main dashboard timeline.
No protected trading threshold is changed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

import btc15_cross_service_payload_v2 as v2
from btc15_protected_module_adapter_v1 import early_state_from_snapshot, final_state_from_snapshot
from btc15_signal_integration_v1 import ScalpState, compose_contract_state


@dataclass(frozen=True)
class CrossServiceDashboardPayloadV3:
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
    scalp_source_fresh: bool
    scalp_source_age_sec: float | None
    scalp_integration_ready: bool
    scalp_block_reason: str | None
    scalp_timer_delta_sec: float | None
    manual_execution_only: bool = True
    numeric_flip_risk_validated: bool = False
    order_action: None = None

    def to_dict(self) -> dict:
        return asdict(self)


def compose_cross_service_payload(
    snapshot: Mapping[str, Any],
    scalp_payload: Mapping[str, Any] | None,
) -> CrossServiceDashboardPayloadV3:
    contract = str(snapshot.get("contract") or "").strip()
    if not contract:
        raise ValueError("protected snapshot contract is required")

    canonical_left = v2._seconds_left(snapshot)
    raw = scalp_payload or {}
    scalp_contract = str(raw.get("contract") or "").strip()
    aligned = bool(scalp_contract and scalp_contract == contract)
    source_fresh = bool(raw.get("source_fresh") is True)
    integration_ready = bool(raw.get("integration_ready") is True)
    source_age = v2._float(raw.get("source_event_age_sec"))

    scalp_left = v2._float(raw.get("contract_seconds_left"))
    timer_delta = (
        abs(canonical_left - scalp_left)
        if aligned and canonical_left is not None and scalp_left is not None
        else None
    )

    block_reason = None
    if not aligned:
        scalp = ScalpState("PASS").normalized()
        message = "SCALP WAIT · CONTRACT SYNC"
        block_reason = "CONTRACT_MISMATCH"
    elif not source_fresh or not integration_ready:
        # Fail closed on a stale/unready cross-service source. The raw bridge
        # state remains available at its own endpoint for diagnostics, but it
        # cannot become actionable on the protected dashboard timeline.
        scalp = ScalpState("PASS").normalized()
        message = "SCALP WAIT · STALE SOURCE" if not source_fresh else "SCALP WAIT · SOURCE NOT READY"
        block_reason = str(raw.get("integration_block_reason") or (
            "SCALP_SOURCE_STALE" if not source_fresh else "SCALP_SOURCE_NOT_READY"
        ))
    else:
        scalp = v2.scalp_state_from_bridge(raw)
        message = str(raw.get("management_message") or "").strip()
        if not message:
            message = {
                "PASS": "NO QUALIFIED SCALP",
                "ACTIVE": "SCALP ACTIVE · BUILDING",
                "PROTECT": "PROTECT PROFITS",
                "EXIT": "EXIT / PROTECT PROFITS NOW",
            }[scalp.state]

    early = early_state_from_snapshot(snapshot)
    final = final_state_from_snapshot(snapshot)
    combined = compose_contract_state(contract, early=early, final=final, scalp=scalp)

    return CrossServiceDashboardPayloadV3(
        contract=contract,
        canonical_seconds_left=canonical_left,
        kalshi_target=v2._float(snapshot.get("kalshi_target")),
        up_bid=v2._float(snapshot.get("up_bid")),
        up_ask=v2._float(snapshot.get("up_ask")),
        down_bid=v2._float(snapshot.get("down_bid")),
        down_ask=v2._float(snapshot.get("down_ask")),
        headline=combined.headline,
        early=asdict(early),
        final=asdict(final),
        scalp=asdict(scalp),
        actionable_paths=combined.actionable_paths,
        context_labels=combined.context_labels,
        union_actionable=combined.union_actionable,
        scalp_management_message=message,
        scalp_contract_aligned=aligned,
        scalp_source_fresh=source_fresh,
        scalp_source_age_sec=source_age,
        scalp_integration_ready=integration_ready,
        scalp_block_reason=block_reason,
        scalp_timer_delta_sec=timer_delta,
    )


__all__ = ["CrossServiceDashboardPayloadV3", "compose_cross_service_payload"]
