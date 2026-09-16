#!/usr/bin/env python3
"""BTC15 dashboard poll-session reducer V1.

PURE PRESENTATION | NO NETWORK | NO SIGNAL LOGIC | NO ORDERS

Consumes consecutive already-built mobile view-model snapshots and prevents
healthy same-contract out-of-order SCALP frames from making the UI jump backward.

Critical safety behavior:
- source/fail-closed WAIT is accepted immediately; never keep an old actionable
  scalp card over a stale/unready source;
- contract rollover is accepted immediately;
- FINAL, EARLY, TIMER and FLIP from the newest healthy frame remain current even
  when only the SCALP frame is quarantined;
- impossible same-contract SCALP regressions quarantine only SCALP presentation
  state and its presentation-context metadata;
- no backend signal, threshold, timer, order or lifecycle is changed.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from btc15_scalp_ui_transition_guard_v1 import validate_transition

VERSION = "BTC15_DASHBOARD_SESSION_REDUCER_V1"

SCALP_CONTEXT_KEYS = (
    "scalp_history_slot",
    "scalp_memory_guard",
    "manual_entry_context",
)

FAIL_CLOSED_ACTION_PREFIXES = (
    "WAIT ·",
)
FAIL_CLOSED_PRIMARY_PREFIXES = (
    "NO ACTION · SOURCE NOT READY",
)


@dataclass(frozen=True)
class SessionDecision:
    version: str
    accepted: bool
    contract_rollover: bool
    source_fail_closed_accepted: bool
    scalp_frame_quarantined: bool
    quarantine_reason: str | None
    current_non_scalp_cards_authoritative: bool
    current_timer_authoritative: bool
    previous_scalp_presentation_retained: bool
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


def _display_state_from_scalp(card: Mapping[str, Any]) -> str:
    lifecycle = str(card.get("underlying_lifecycle_state") or "PASS").upper()
    return {
        "PASS": "WAIT",
        "ACTIVE": "ACTIVE",
        "PROTECT": "PROTECT",
        "EXIT": "EXIT",
    }.get(lifecycle, "WAIT")


def _is_source_fail_closed(model: Mapping[str, Any] | None) -> bool:
    card = _scalp(model)
    action = str(card.get("action") or "").upper()
    primary = str(card.get("primary") or "").upper()
    if any(action.startswith(x) for x in FAIL_CLOSED_ACTION_PREFIXES):
        return True
    if any(primary.startswith(x) for x in FAIL_CLOSED_PRIMARY_PREFIXES):
        return True
    # A presentation-integrity failure is not a source failure. It is handled as
    # a SCALP quarantine condition below rather than accepted as WAIT.
    return False


def _transition_snapshot(model: Mapping[str, Any]) -> dict[str, Any]:
    card = _scalp(model)
    return {
        "contract": _contract(model),
        "display_state": _display_state_from_scalp(card),
        "opportunity_index": _int(card.get("opportunity_index")),
        "serial_opportunities_completed": _int(card.get("serial_opportunities_completed")) or 0,
        "scanning_for_next": card.get("scanning_for_next") is True,
        "source": {"fail_closed": _is_source_fail_closed(model)},
    }


def _presentation_integrity_block(model: Mapping[str, Any]) -> str | None:
    integrity = dict(model.get("presentation_integrity") or {})
    if integrity and integrity.get("ok") is False:
        return str(integrity.get("blocked_reason") or "PRESENTATION_INTEGRITY_BLOCK")
    return None


def _replace_scalp_presentation_from_previous(
    current: Mapping[str, Any],
    previous: Mapping[str, Any],
) -> dict[str, Any]:
    out = copy.deepcopy(dict(current))
    prev = dict(previous)

    out.setdefault("cards", {})
    out["cards"]["SCALP_OPPORTUNITY"] = copy.deepcopy(_scalp(prev))

    for key in SCALP_CONTEXT_KEYS:
        if key in prev:
            out[key] = copy.deepcopy(prev[key])
        elif key in out:
            out.pop(key, None)

    # The current frame's contract-level cards stay authoritative. Rollover is
    # false here by construction, but current timer/final/early are never copied
    # from the previous frame.
    return out


def reduce_dashboard_session(
    previous_accepted: Mapping[str, Any] | None,
    current_candidate: Mapping[str, Any],
) -> dict[str, Any]:
    current = copy.deepcopy(dict(current_candidate or {}))
    previous = copy.deepcopy(dict(previous_accepted or {}))

    if not previous:
        decision = SessionDecision(
            VERSION, True, False, _is_source_fail_closed(current), False, None,
            True, True, False,
        )
        current["session_reducer"] = decision.to_dict()
        return current

    prev_contract = _contract(previous)
    cur_contract = _contract(current)
    rollover = bool(prev_contract and cur_contract and prev_contract != cur_contract)
    if rollover:
        decision = SessionDecision(
            VERSION, True, True, _is_source_fail_closed(current), False, None,
            True, True, False,
        )
        current["session_reducer"] = decision.to_dict()
        return current

    # Safety beats smoothness. Never retain an actionable old scalp card over a
    # current source-fail-closed WAIT.
    if _is_source_fail_closed(current):
        decision = SessionDecision(
            VERSION, True, False, True, False, None,
            True, True, False,
        )
        current["session_reducer"] = decision.to_dict()
        return current

    # Recovery from a previously accepted fail-closed frame must be able to
    # resume the current healthy lifecycle without comparing against a stale
    # actionable state that is no longer on screen.
    if _is_source_fail_closed(previous):
        decision = SessionDecision(
            VERSION, True, False, False, False, None,
            True, True, False,
        )
        current["session_reducer"] = decision.to_dict()
        return current

    integrity_block = _presentation_integrity_block(current)
    if integrity_block:
        accepted = _replace_scalp_presentation_from_previous(current, previous)
        decision = SessionDecision(
            VERSION, True, False, False, True, integrity_block,
            True, True, True,
        )
        accepted["session_reducer"] = decision.to_dict()
        return accepted

    transition = validate_transition(
        _transition_snapshot(previous),
        _transition_snapshot(current),
    )
    if not transition.allowed:
        accepted = _replace_scalp_presentation_from_previous(current, previous)
        decision = SessionDecision(
            VERSION, True, False, False, True, transition.reason,
            True, True, True,
        )
        accepted["session_reducer"] = decision.to_dict()
        return accepted

    decision = SessionDecision(
        VERSION, True, False, False, False, None,
        True, True, False,
    )
    current["session_reducer"] = decision.to_dict()
    return current


__all__ = [
    "VERSION",
    "SessionDecision",
    "reduce_dashboard_session",
]
