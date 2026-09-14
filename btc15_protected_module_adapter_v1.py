#!/usr/bin/env python3
"""
BTC15 protected-module runtime adapter V1.

PURE ADAPTER / NO NETWORK / NO ORDERS

Purpose
-------
Translate already-protected EARLY / FINAL snapshot outputs plus the frozen
SCALP event tape into the side-effect-free integration composer without
changing any protected thresholds.

Important:
- EARLY qualification is read from the protected V3 tournament-ready output.
- FINAL LOCK is read only from the protected V4.6 tournament-winner FINAL CALL.
- SCALP eligibility remains the frozen seconds_left>=120 + btc30>=15 rule.
- SCALP management remains +5c arm / 4c giveback.
- PROTECT is a presentation state once the validated +5c arm has fired.
- EXIT is the validated 4c giveback trigger from running executable peak.
- Once EXIT triggers, it is latched for that primary signal; recovery later in
  the same path cannot resurrect an already-exited trade.
- No price eligibility filter is introduced for SCALP.
- No order-placement code exists.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from btc15_signal_integration_v1 import (
    EarlyState,
    FinalState,
    ScalpState,
    compose_contract_state,
)

SCALP_MIN_SECONDS_LEFT = 120.0
SCALP_MIN_BTC30 = 15.0
SCALP_ARM_GAIN = 0.05
SCALP_GIVEBACK = 0.04


def _float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _side(value: Any) -> str | None:
    if value is None:
        return None
    x = str(value).strip().upper()
    return x if x in {"UP", "DOWN"} else None


def _seconds_left_from_snapshot(row: Mapping[str, Any]) -> float | None:
    seconds = _float(row.get("seconds_left"))
    if seconds is not None:
        return max(0.0, seconds)
    minutes = _float(row.get("time_left_min"))
    if minutes is not None:
        return max(0.0, minutes * 60.0)
    return None


def early_state_from_snapshot(row: Mapping[str, Any]) -> EarlyState:
    """Adapt the protected V3 EARLY output without recomputing its thresholds."""
    side = _side(row.get("fair_preferred_side") or row.get("opportunity_side"))
    ask = _float(row.get("preferred_kalshi_ask"))
    fair = _float(row.get("fair_preferred"))
    edge = _float(row.get("fair_edge_vs_ask"))
    seconds_left = _seconds_left_from_snapshot(row)

    qualified = (
        _bool(row.get("entry_tournament_ready"))
        and str(row.get("opportunity_status") or "").strip().upper() == "OPPORTUNITY"
        and side in {"UP", "DOWN"}
    )

    return EarlyState(
        state="QUALIFIED" if qualified else "PASS",
        side=side,
        ask=ask,
        fair=fair,
        edge=edge,
        seconds_left=seconds_left,
    ).normalized()


def final_state_from_snapshot(row: Mapping[str, Any]) -> FinalState:
    """Adapt only the protected V4.6 tournament-winner FINAL authority."""
    status = str(row.get("final_status") or "").strip().upper()
    source = str(row.get("final_call_source") or "").strip().upper()
    side = _side(row.get("final_side") or row.get("expected_final_outcome"))
    fair = _float(row.get("final_confidence"))
    seconds_left = _seconds_left_from_snapshot(row)

    locked = (
        status == "FINAL CALL"
        and source == "TOURNAMENT WINNER"
        and side in {"UP", "DOWN"}
        and fair is not None
        and fair >= 0.90
    )

    # When not locked, preserve only directional context as WATCH. No fallback
    # path is allowed to fabricate a protected FINAL call.
    return FinalState(
        state="LOCK" if locked else "WATCH",
        side=side,
        fair=fair if locked else None,
        seconds_left=seconds_left,
    ).normalized()


def _path_for_candidate(
    candidate: Mapping[str, Any],
    path_rows: Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    cid = str(candidate.get("candidate_id") or "").strip()
    rows = []
    for row in path_rows:
        row_cid = str(row.get("candidate_id") or "").strip()
        if cid and row_cid and row_cid != cid:
            continue
        rows.append(row)

    def key(row: Mapping[str, Any]) -> tuple[int, float]:
        elapsed = _float(row.get("elapsed_sec"))
        if elapsed is not None:
            return (0, elapsed)
        return (1, 0.0)

    return sorted(rows, key=key)


def scalp_state_from_events(
    candidate: Mapping[str, Any] | None,
    path_rows: Iterable[Mapping[str, Any]] = (),
) -> ScalpState:
    """
    Adapt the frozen generalized scalp challenger and management path.

    ACTIVE: frozen challenger qualified, +5c arm not yet reached.
    PROTECT: +5c arm reached; profit protection is now visibly armed.
    EXIT: first chronological >=4c giveback after arming. EXIT latches.
    PASS: no frozen qualified challenger.

    Chronology intentionally matches the frozen forward scorer: after EXIT, a
    later market recovery cannot turn the same primary signal back into an
    active/protect state unless a separately validated re-entry path is added.
    """
    if not candidate:
        return ScalpState("PASS").normalized()

    side = _side(candidate.get("side"))
    seconds_left = _float(candidate.get("seconds_left"))
    btc30 = _float(candidate.get("btc30"))
    entry_ask = _float(candidate.get("entry_ask"))

    qualified = bool(
        side in {"UP", "DOWN"}
        and seconds_left is not None
        and seconds_left >= SCALP_MIN_SECONDS_LEFT
        and btc30 is not None
        and btc30 >= SCALP_MIN_BTC30
    )

    if not qualified:
        return ScalpState(
            state="PASS",
            side=side,
            entry_ask=entry_ask,
            seconds_left=seconds_left,
        ).normalized()

    rows = _path_for_candidate(candidate, path_rows)
    running_peak: float | None = None
    armed = False
    last_gain: float | None = None
    exit_gain: float | None = None
    exit_peak: float | None = None

    for row in rows:
        gain = _float(row.get("exec_gain"))
        if gain is None:
            continue
        last_gain = gain
        running_peak = gain if running_peak is None else max(running_peak, gain)
        armed = armed or running_peak >= SCALP_ARM_GAIN

        if armed and running_peak - gain >= (SCALP_GIVEBACK - 1e-12):
            exit_gain = gain
            exit_peak = running_peak
            break

    if exit_gain is not None:
        state = "EXIT"
        display_gain = exit_gain
        peak_gain = exit_peak
    else:
        state = "PROTECT" if armed else "ACTIVE"
        display_gain = last_gain
        peak_gain = running_peak

    current_bid = None
    if entry_ask is not None and display_gain is not None:
        current_bid = min(1.0, max(0.0, entry_ask + display_gain))

    return ScalpState(
        state=state,
        side=side,
        entry_ask=entry_ask,
        current_bid=current_bid,
        peak_exec_gain=peak_gain,
        exec_gain=display_gain,
        seconds_left=seconds_left,
    ).normalized()


@dataclass(frozen=True)
class DashboardPayload:
    contract: str
    canonical_seconds_left: float | None
    kalshi_target: float | None
    up_ask: float | None
    down_ask: float | None
    headline: str
    scalp_management_message: str
    combined: dict
    manual_execution_only: bool = True
    numeric_flip_risk_validated: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def compose_dashboard_payload(
    snapshot_row: Mapping[str, Any],
    *,
    scalp_candidate: Mapping[str, Any] | None = None,
    scalp_path_rows: Iterable[Mapping[str, Any]] = (),
) -> DashboardPayload:
    """Build one dashboard-facing payload on one canonical contract timeline."""
    contract = str(snapshot_row.get("contract") or "").strip()
    if not contract:
        raise ValueError("snapshot contract is required")

    if scalp_candidate:
        scalp_contract = str(scalp_candidate.get("contract") or "").strip()
        if scalp_contract and scalp_contract != contract:
            raise ValueError(
                f"contract mismatch: snapshot={contract} scalp={scalp_contract}"
            )

    early = early_state_from_snapshot(snapshot_row)
    final = final_state_from_snapshot(snapshot_row)
    scalp = scalp_state_from_events(scalp_candidate, scalp_path_rows)
    combined = compose_contract_state(
        contract,
        early=early,
        final=final,
        scalp=scalp,
    )

    management = {
        "PASS": "NO SCALP ACTION",
        "ACTIVE": "SCALP ACTIVE",
        "PROTECT": "PROTECT PROFITS",
        "EXIT": "EXIT / PROTECT PROFITS NOW",
    }[scalp.state]

    return DashboardPayload(
        contract=contract,
        canonical_seconds_left=_seconds_left_from_snapshot(snapshot_row),
        kalshi_target=_float(snapshot_row.get("kalshi_target")),
        up_ask=_float(snapshot_row.get("up_ask")),
        down_ask=_float(snapshot_row.get("down_ask")),
        headline=combined.headline,
        scalp_management_message=management,
        combined=combined.to_dict(),
    )


__all__ = [
    "SCALP_MIN_SECONDS_LEFT",
    "SCALP_MIN_BTC30",
    "SCALP_ARM_GAIN",
    "SCALP_GIVEBACK",
    "DashboardPayload",
    "early_state_from_snapshot",
    "final_state_from_snapshot",
    "scalp_state_from_events",
    "compose_dashboard_payload",
]
