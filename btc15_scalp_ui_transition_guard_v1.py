#!/usr/bin/env python3
"""BTC15 scalp UI transition guard V1.

PURE PRESENTATION GUARD | NO SIGNAL LOGIC | NO ORDERS

Rejects impossible same-contract UI regressions caused by stale/out-of-order
presentation payloads. It never changes the underlying detector or lifecycle.
Contract rollover resets are allowed. Source-fail-closed WAIT is always allowed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

VERSION = "BTC15_SCALP_UI_TRANSITION_GUARD_V1"

STATE_RANK = {
    "WAIT": 0,
    "ACTIVE": 1,
    "PROTECT": 2,
    "EXIT": 3,
}


@dataclass(frozen=True)
class TransitionDecision:
    allowed: bool
    reason: str
    previous_state: str | None
    next_state: str | None
    manual_execution_only: bool = True
    orders: bool = False


def _state(x: Mapping[str, Any] | None) -> str | None:
    if not x:
        return None
    s = str(x.get("display_state") or "").upper()
    return s if s in STATE_RANK else None


def _int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def _fail_closed(x: Mapping[str, Any] | None) -> bool:
    return bool(((x or {}).get("source") or {}).get("fail_closed") is True)


def validate_transition(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> TransitionDecision:
    prev = dict(previous or {})
    cur = dict(current or {})
    ps = _state(prev)
    cs = _state(cur)

    if cs is None:
        return TransitionDecision(False, "INVALID_NEXT_DISPLAY_STATE", ps, cs)

    if not prev:
        return TransitionDecision(True, "INITIAL_STATE", ps, cs)

    prev_contract = str(prev.get("contract") or "")
    cur_contract = str(cur.get("contract") or "")
    if prev_contract != cur_contract:
        return TransitionDecision(True, "CONTRACT_ROLLOVER", ps, cs)

    if _fail_closed(cur):
        return TransitionDecision(True, "SOURCE_FAIL_CLOSED_WAIT_ALLOWED", ps, cs)

    prev_completed = _int(prev.get("serial_opportunities_completed")) or 0
    cur_completed = _int(cur.get("serial_opportunities_completed")) or 0
    if cur_completed < prev_completed:
        return TransitionDecision(False, "SERIAL_COMPLETED_COUNT_REGRESSION", ps, cs)

    prev_opp = _int(prev.get("opportunity_index"))
    cur_opp = _int(cur.get("opportunity_index"))
    if prev_opp is not None and cur_opp is not None and cur_opp < prev_opp:
        return TransitionDecision(False, "OPPORTUNITY_INDEX_REGRESSION", ps, cs)

    # A later serial opportunity is a new lifecycle, so ACTIVE is allowed after
    # a prior EXIT/WAIT when the opportunity index increases.
    later_opp = bool(
        prev_opp is not None
        and cur_opp is not None
        and cur_opp > prev_opp
    )
    if later_opp:
        return TransitionDecision(True, "LATER_SERIAL_OPPORTUNITY", ps, cs)

    # Scanning for the next opportunity after a terminal state may legitimately
    # show WAIT while the serial counter remains monotonic.
    if cs == "WAIT" and cur.get("scanning_for_next") is True:
        return TransitionDecision(True, "SCANNING_FOR_NEXT", ps, cs)

    if ps is None:
        return TransitionDecision(True, "PREVIOUS_STATE_UNAVAILABLE", ps, cs)

    if STATE_RANK[cs] < STATE_RANK[ps]:
        return TransitionDecision(False, "SAME_OPPORTUNITY_STATE_REGRESSION", ps, cs)

    return TransitionDecision(True, "MONOTONIC_SAME_OPPORTUNITY", ps, cs)


__all__ = ["TransitionDecision", "validate_transition", "VERSION"]
