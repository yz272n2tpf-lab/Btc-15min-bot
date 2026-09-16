#!/usr/bin/env python3
"""BTC15 same-contract scalp completion memory guard V1.

PURE PRESENTATION | NO SIGNAL LOGIC | NO ORDERS

Keeps the just-finished scalp visible as muted historical context while the same
15-minute contract scans for or begins a later opportunity. It does not create a
terminal event. It only memorializes transitions already visible in consecutive
mobile view-model snapshots.

An armed/protected prior scalp is NOT allowed to be treated as completed merely
because a later opportunity appears; that impossible presentation transition is
flagged instead of hidden.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

VERSION = "BTC15_SCALP_MEMORY_GUARD_V1"


@dataclass(frozen=True)
class ScalpMemoryDecision:
    version: str
    same_contract: bool
    progression_detected: bool
    memory: dict[str, Any] | None
    blocked_reason: str | None
    actionable: bool = False
    signal_filtering: bool = False
    signal_suppression: bool = False
    orders: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _contract(model: Mapping[str, Any] | None) -> str | None:
    x = str((model or {}).get("contract") or "").strip()
    return x or None


def _scalp(model: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict((((model or {}).get("cards") or {}).get("SCALP_OPPORTUNITY") or {}))


def _int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def remember_previous_scalp(
    previous_model: Mapping[str, Any] | None,
    current_model: Mapping[str, Any],
) -> ScalpMemoryDecision:
    prev_contract = _contract(previous_model)
    cur_contract = _contract(current_model)
    same_contract = bool(prev_contract and cur_contract and prev_contract == cur_contract)
    if not same_contract:
        return ScalpMemoryDecision(VERSION, False, False, None, None)

    prev = _scalp(previous_model)
    cur = _scalp(current_model)
    if not prev or not cur:
        return ScalpMemoryDecision(VERSION, True, False, None, None)

    prev_opp = _int(prev.get("opportunity_index"))
    cur_opp = _int(cur.get("opportunity_index"))
    prev_completed = _int(prev.get("serial_opportunities_completed")) or 0
    cur_completed = _int(cur.get("serial_opportunities_completed")) or 0
    cur_scanning = cur.get("scanning_for_next") is True

    later_opp = bool(prev_opp is not None and cur_opp is not None and cur_opp > prev_opp)
    count_advanced = cur_completed > prev_completed
    progression = bool(later_opp or count_advanced or cur_scanning)
    if not progression or prev_opp is None:
        return ScalpMemoryDecision(VERSION, True, progression, None, None)

    lifecycle = str(prev.get("underlying_lifecycle_state") or "PASS").upper()
    tracking_only = prev.get("tracking_only") is True
    manual_path = prev.get("manual_entry_path_available") is True

    # Armed/protected winners are not allowed to reset without a real EXIT in the
    # frozen serial lifecycle. Do not fabricate a completion memory.
    if lifecycle == "PROTECT":
        return ScalpMemoryDecision(
            VERSION,
            True,
            True,
            None,
            "ARMED_NO_EXIT_HANDOFF_BLOCKED",
        )

    if lifecycle == "EXIT" and manual_path and not tracking_only:
        headline = f"#{prev_opp} COMPLETE · PROTECTED EXIT"
        detail = f"Historical only · scanning for #{max(prev_opp + 1, cur_opp or prev_opp + 1)}."
        kind = "PROTECTED_EXIT"
        position_assumed = True
    elif tracking_only:
        headline = f"#{prev_opp} ENDED · TRACKING ONLY"
        detail = f"No manual position assumed · scanning for #{max(prev_opp + 1, cur_opp or prev_opp + 1)}."
        kind = "TRACKING_ONLY_ENDED"
        position_assumed = False
    elif lifecycle == "ACTIVE":
        headline = f"#{prev_opp} ENDED · NO PROTECTED EXIT"
        detail = f"Never reached a protected terminal · scanning for #{max(prev_opp + 1, cur_opp or prev_opp + 1)}."
        kind = "ENDED_UNPROTECTED"
        position_assumed = manual_path
    else:
        return ScalpMemoryDecision(VERSION, True, True, None, None)

    memory = {
        "reserved": True,
        "visible": True,
        "historical_only": True,
        "actionable": False,
        "source_contract": prev_contract,
        "headline": headline,
        "detail": detail,
        "tone": "muted",
        "terminal_kind": kind,
        "opportunity_index": prev_opp,
        "serial_opportunities_completed": cur_completed,
        "manual_position_assumed": position_assumed,
        "order_action": None,
        "orders": False,
    }
    return ScalpMemoryDecision(VERSION, True, True, memory, None)


__all__ = ["VERSION", "ScalpMemoryDecision", "remember_previous_scalp"]
