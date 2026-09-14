#!/usr/bin/env python3
"""
BTC15 protected FINAL BRTI authority semantics V1.

PURE / NO NETWORK / NO ORDERS

Mirrors the existing V4.10 live safety semantics so a future resilient fetch
layer can be tested independently from the protected FINAL model:
- BRTI age <= 5 seconds
- BRTI must be more than $11 away from the exact Kalshi target
- BRTI side must be UP or DOWN
- protected fair-preferred side must agree with BRTI side before FINAL authority

No model threshold is selected here.
"""
from __future__ import annotations

from dataclasses import dataclass

MAX_AGE_SEC = 5.0
WAIT_DOLLARS = 11.0


@dataclass(frozen=True)
class FinalBrtiAuthority:
    ready: bool
    agrees_with_fair: bool
    value: float | None
    age_sec: float | None
    target: float | None
    gap: float | None
    side: str | None
    fair_side: str | None


def evaluate_final_brti_authority(
    *,
    value: float | None,
    age_sec: float | None,
    target: float | None,
    fair_side: str | None,
    max_age_sec: float = MAX_AGE_SEC,
    wait_dollars: float = WAIT_DOLLARS,
) -> FinalBrtiAuthority:
    side = None
    gap = None
    ready = False

    fair = None if fair_side is None else str(fair_side).strip().upper()
    if fair not in {"UP", "DOWN"}:
        fair = None

    try:
        v = None if value is None else float(value)
        age = None if age_sec is None else float(age_sec)
        tgt = None if target is None else float(target)
        if v is not None and age is not None and tgt is not None:
            gap = v - tgt
            side = "UP" if gap > 0 else "DOWN" if gap < 0 else None
            ready = bool(
                age <= float(max_age_sec)
                and abs(gap) > float(wait_dollars)
                and side in {"UP", "DOWN"}
            )
    except (TypeError, ValueError, OverflowError):
        v = None
        age = None
        tgt = None
        gap = None
        side = None
        ready = False

    agrees = bool(ready and fair is not None and fair == side)
    return FinalBrtiAuthority(
        ready=ready,
        agrees_with_fair=agrees,
        value=v,
        age_sec=age,
        target=tgt,
        gap=gap,
        side=side,
        fair_side=fair,
    )


__all__ = [
    "MAX_AGE_SEC",
    "WAIT_DOLLARS",
    "FinalBrtiAuthority",
    "evaluate_final_brti_authority",
]
