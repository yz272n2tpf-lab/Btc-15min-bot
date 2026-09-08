#!/usr/bin/env python3
"""
BTC15 BRTI ROLLOVER TARGET FALLBACK CANDIDATE

Development helper only. Not imported by production and does not place orders.

Purpose:
When Kalshi exposes the new KXBTC15M contract before its numeric floor_strike
metadata is populated, the immediately preceding contract's complete 60/60
BRTI final-window average can serve as a temporary target candidate.

The candidate is deliberately strict:
- Never overrides an official finite Kalshi target.
- Requires a complete 60/60 previous BRTI final window.
- Requires the new contract close to be exactly one 15-minute interval after
  the previous contract close, within a small clock tolerance.
- Refuses stale, incomplete, non-finite, or non-contiguous state.
- Provides a reconciliation check once Kalshi's official target appears.

This file is intentionally standalone so it can be tested without changing
production signal logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Optional, Tuple


CONTRACT_SECONDS = 15 * 60
CONTIGUITY_TOLERANCE_SECONDS = 3.0
OFFICIAL_RECONCILE_TOLERANCE_DOLLARS = 1.00


@dataclass(frozen=True)
class FinalizedBrtiWindow:
    ticker: str
    close_dt: datetime
    final60_avg: float
    final60_count: int
    final60_complete: bool


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def candidate_target(
    official_target,
    new_close_dt: Optional[datetime],
    previous: Optional[FinalizedBrtiWindow],
) -> Tuple[Optional[float], str]:
    """Return (target, source) without ever overriding an official target."""
    if _finite(official_target):
        return float(official_target), "KALSHI_OFFICIAL"

    if previous is None:
        return None, "NO_PREVIOUS_FINALIZED_WINDOW"
    if not previous.final60_complete or previous.final60_count != 60:
        return None, "PREVIOUS_FINAL60_INCOMPLETE"
    if not _finite(previous.final60_avg):
        return None, "PREVIOUS_FINAL60_NONFINITE"
    if new_close_dt is None:
        return None, "NEW_CLOSE_MISSING"

    try:
        delta = (new_close_dt - previous.close_dt).total_seconds()
    except Exception:
        return None, "CLOSE_TIME_COMPARISON_FAILED"

    if abs(delta - CONTRACT_SECONDS) > CONTIGUITY_TOLERANCE_SECONDS:
        return None, "CONTRACT_NOT_CONTIGUOUS"

    return float(previous.final60_avg), "PREVIOUS_COMPLETE_BRTI_FINAL60"


def reconcile_with_official(
    fallback_target,
    official_target,
    tolerance_dollars: float = OFFICIAL_RECONCILE_TOLERANCE_DOLLARS,
) -> Tuple[bool, Optional[float]]:
    """Check a temporary fallback against Kalshi once official metadata exists."""
    if not _finite(fallback_target) or not _finite(official_target):
        return False, None
    delta = abs(float(fallback_target) - float(official_target))
    return delta <= float(tolerance_dollars), delta


if __name__ == "__main__":
    print("BTC15 BRTI rollover target fallback candidate")
    print("DEVELOPMENT ONLY — production unchanged — no orders")
