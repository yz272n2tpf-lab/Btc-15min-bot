#!/usr/bin/env python3
"""BTC15 dashboard contract-rollover quarantine guard V1.

PURE PRESENTATION | NO SIGNAL LOGIC | NO ORDERS

At a 15-minute contract boundary the new contract view-model is always the only
actionable authority. A prior contract may remain briefly as historical context,
but this guard rewrites it into a muted, explicitly non-actionable record.

It never modifies the new contract's FINAL/EARLY/TIMER/SCALP/FLIP cards and it
never qualifies, suppresses, delays, or changes a signal.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from typing import Any, Mapping

VERSION = "BTC15_DASHBOARD_ROLLOVER_GUARD_V1"

FORBIDDEN_HISTORICAL_ACTION_WORDING = (
    "EXIT NOW",
    "PROTECT PROFITS",
    "ENTRY AVAILABLE",
    "HOLD ·",
)


@dataclass(frozen=True)
class RolloverGuardMeta:
    version: str
    rollover_detected: bool
    previous_contract: str | None
    current_contract: str | None
    current_contract_authoritative: bool
    historical_context_actionable: bool
    signal_filtering: bool = False
    signal_suppression: bool = False
    orders: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _contract(model: Mapping[str, Any] | None) -> str | None:
    raw = str((model or {}).get("contract") or "").strip()
    return raw or None


def _scalp(model: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict((((model or {}).get("cards") or {}).get("SCALP_OPPORTUNITY") or {}))


def _int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def _history_from_previous(previous: Mapping[str, Any]) -> dict[str, Any] | None:
    card = _scalp(previous)
    if not card:
        return None

    lifecycle = str(card.get("underlying_lifecycle_state") or "PASS").upper()
    opp = _int(card.get("opportunity_index"))
    completed = _int(card.get("serial_opportunities_completed")) or 0
    tracking_only = card.get("tracking_only") is True
    manual_path = card.get("manual_entry_path_available") is True
    scanning = card.get("scanning_for_next") is True

    # No actual prior scalp context to retain.
    if opp is None and completed <= 0 and lifecycle == "PASS" and not scanning:
        return None

    n = opp if opp is not None else (completed if completed > 0 else None)
    prefix = f"#{n}" if n is not None else "SCALP"

    if lifecycle == "EXIT" and manual_path and not tracking_only:
        headline = f"{prefix} COMPLETE · PROTECTED EXIT"
        detail = "Previous contract · historical result only."
        terminal_kind = "PROTECTED_EXIT"
    elif tracking_only:
        headline = f"{prefix} ENDED · TRACKING ONLY"
        detail = "Previous contract · no manual position assumed."
        terminal_kind = "TRACKING_ONLY_ENDED"
    elif lifecycle in {"ACTIVE", "PROTECT", "EXIT"}:
        headline = f"{prefix} ENDED · CONTRACT ROLLED"
        detail = "Previous contract · no longer actionable."
        terminal_kind = "ROLLOVER_ENDED"
    elif completed > 0:
        headline = f"#{completed} COMPLETE · PREVIOUS CONTRACT"
        detail = "Historical scalp context only."
        terminal_kind = "COMPLETED_HISTORY"
    else:
        headline = "PREVIOUS CONTRACT · SCALP HISTORY"
        detail = "Historical context only."
        terminal_kind = "HISTORY"

    upper = (headline + " " + detail).upper()
    for forbidden in FORBIDDEN_HISTORICAL_ACTION_WORDING:
        if forbidden in upper:
            raise ValueError(f"historical rollover wording leaked actionable phrase: {forbidden}")

    return {
        "historical_only": True,
        "actionable": False,
        "source_contract": _contract(previous),
        "headline": headline,
        "detail": detail,
        "tone": "muted",
        "terminal_kind": terminal_kind,
        "previous_lifecycle_state": lifecycle,
        "opportunity_index": opp,
        "serial_opportunities_completed": completed,
        "manual_position_assumed": bool(manual_path and not tracking_only),
        "order_action": None,
        "orders": False,
    }


def apply_rollover_guard(
    previous_model: Mapping[str, Any] | None,
    current_model: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a wrapper whose `current` payload is an unchanged deep copy.

    Historical context is created only when both contract IDs are present and
    different. Missing current contract remains fail-closed to the current
    model's own sync/wait presentation and never revives previous actions.
    """
    previous = dict(previous_model or {})
    current = copy.deepcopy(dict(current_model or {}))
    prev_contract = _contract(previous)
    cur_contract = _contract(current)
    rollover = bool(prev_contract and cur_contract and prev_contract != cur_contract)

    history = _history_from_previous(previous) if rollover else None
    meta = RolloverGuardMeta(
        version=VERSION,
        rollover_detected=rollover,
        previous_contract=prev_contract,
        current_contract=cur_contract,
        current_contract_authoritative=bool(cur_contract),
        historical_context_actionable=False,
    )

    return {
        "version": VERSION,
        "current": current,
        "historical_scalp": history,
        "rollover": meta.to_dict(),
        "manual_execution_only": True,
        "order_action": None,
        "orders": False,
    }


__all__ = [
    "VERSION",
    "FORBIDDEN_HISTORICAL_ACTION_WORDING",
    "RolloverGuardMeta",
    "apply_rollover_guard",
]
