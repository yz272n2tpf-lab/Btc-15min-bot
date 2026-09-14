#!/usr/bin/env python3
"""
BTC15 combined signal integration/state-composition V1.

PURE / SIDE-EFFECT FREE | SIGNAL ONLY | NO ORDERS

This module composes already-evaluated EARLY, FINAL and SCALP module states.
It never qualifies a trading rule, changes a threshold, calls a network, reads a
secret, or places an order.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional, Tuple

VALID_SIDES = {"UP", "DOWN"}
EARLY_STATES = {"PASS", "QUALIFIED"}
FINAL_STATES = {"WATCH", "QUALIFIED", "LOCK"}
SCALP_STATES = {"PASS", "ACTIVE", "PROTECT", "EXIT"}

FINAL_ACTIONABLE = {"QUALIFIED", "LOCK"}
SCALP_ACTIONABLE = {"ACTIVE", "PROTECT", "EXIT"}


def _side(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    x = str(value).upper()
    if x not in VALID_SIDES:
        raise ValueError(f"invalid side: {value!r}")
    return x


def _prob(value: Optional[float], name: str) -> Optional[float]:
    if value is None:
        return None
    x = float(value)
    if not 0.0 <= x <= 1.0:
        raise ValueError(f"{name} must be within [0, 1], got {x}")
    return x


@dataclass(frozen=True)
class EarlyState:
    state: str = "PASS"
    side: Optional[str] = None
    ask: Optional[float] = None
    fair: Optional[float] = None
    edge: Optional[float] = None
    seconds_left: Optional[float] = None

    def normalized(self) -> "EarlyState":
        state = str(self.state).upper()
        if state not in EARLY_STATES:
            raise ValueError(f"invalid EARLY state: {self.state!r}")
        side = _side(self.side)
        if state == "QUALIFIED" and side is None:
            raise ValueError("EARLY QUALIFIED requires side")
        return EarlyState(
            state=state,
            side=side,
            ask=_prob(self.ask, "early.ask"),
            fair=_prob(self.fair, "early.fair"),
            edge=None if self.edge is None else float(self.edge),
            seconds_left=None if self.seconds_left is None else float(self.seconds_left),
        )


@dataclass(frozen=True)
class FinalState:
    state: str = "WATCH"
    side: Optional[str] = None
    fair: Optional[float] = None
    seconds_left: Optional[float] = None

    def normalized(self) -> "FinalState":
        state = str(self.state).upper()
        if state not in FINAL_STATES:
            raise ValueError(f"invalid FINAL state: {self.state!r}")
        side = _side(self.side)
        if state in FINAL_ACTIONABLE and side is None:
            raise ValueError(f"FINAL {state} requires side")
        return FinalState(
            state=state,
            side=side,
            fair=_prob(self.fair, "final.fair"),
            seconds_left=None if self.seconds_left is None else float(self.seconds_left),
        )


@dataclass(frozen=True)
class ScalpState:
    state: str = "PASS"
    side: Optional[str] = None
    entry_ask: Optional[float] = None
    current_bid: Optional[float] = None
    peak_exec_gain: Optional[float] = None
    exec_gain: Optional[float] = None
    seconds_left: Optional[float] = None

    def normalized(self) -> "ScalpState":
        state = str(self.state).upper()
        if state not in SCALP_STATES:
            raise ValueError(f"invalid SCALP state: {self.state!r}")
        side = _side(self.side)
        if state in SCALP_ACTIONABLE and side is None:
            raise ValueError(f"SCALP {state} requires side")
        return ScalpState(
            state=state,
            side=side,
            entry_ask=_prob(self.entry_ask, "scalp.entry_ask"),
            current_bid=_prob(self.current_bid, "scalp.current_bid"),
            peak_exec_gain=None if self.peak_exec_gain is None else float(self.peak_exec_gain),
            exec_gain=None if self.exec_gain is None else float(self.exec_gain),
            seconds_left=None if self.seconds_left is None else float(self.seconds_left),
        )


@dataclass(frozen=True)
class CombinedContractState:
    contract: str
    early: EarlyState
    final: FinalState
    scalp: ScalpState
    headline: str
    actionable_paths: Tuple[str, ...]
    union_actionable: bool
    context_labels: Tuple[str, ...]
    manual_execution_only: bool = True
    numeric_flip_risk_validated: bool = False

    def to_dict(self) -> dict:
        # Deliberately contains no order-placement field and no numeric flip-risk field.
        return asdict(self)


def _headline(early: EarlyState, final: FinalState, scalp: ScalpState) -> str:
    if scalp.state == "EXIT":
        return "SCALP_EXIT"
    if scalp.state == "PROTECT":
        return "SCALP_PROTECT"
    if final.state == "LOCK":
        return "FINAL_LOCK"
    if final.state == "QUALIFIED":
        return "FINAL_QUALIFIED"
    if early.state == "QUALIFIED":
        return "EARLY_QUALIFIED"
    if scalp.state == "ACTIVE":
        return "SCALP_ACTIVE"
    if final.state == "WATCH":
        return "FINAL_WATCH"
    return "PASS"


def compose_contract_state(
    contract: str,
    *,
    early: EarlyState | None = None,
    final: FinalState | None = None,
    scalp: ScalpState | None = None,
) -> CombinedContractState:
    e = (early or EarlyState()).normalized()
    f = (final or FinalState()).normalized()
    s = (scalp or ScalpState()).normalized()

    paths = []
    sides = []

    if e.state == "QUALIFIED":
        paths.append("EARLY")
        sides.append(e.side)
    if f.state in FINAL_ACTIONABLE:
        paths.append("FINAL")
        sides.append(f.side)
    if s.state in SCALP_ACTIONABLE:
        paths.append("SCALP")
        sides.append(s.side)

    labels = []
    if s.state in SCALP_ACTIONABLE and f.state in FINAL_ACTIONABLE and s.side != f.side:
        labels.append("COUNTERTREND_SCALP")
    if e.state == "QUALIFIED" and f.state in FINAL_ACTIONABLE and e.side != f.side:
        labels.append("EARLY_FINAL_DIVERGENCE")

    if len(paths) >= 2:
        if len(set(sides)) == 1:
            labels.append("ALIGNED")
        else:
            labels.append("MIXED_HORIZONS")

    return CombinedContractState(
        contract=str(contract),
        early=e,
        final=f,
        scalp=s,
        headline=_headline(e, f, s),
        actionable_paths=tuple(paths),
        union_actionable=bool(paths),
        context_labels=tuple(labels),
    )


__all__ = [
    "EarlyState",
    "FinalState",
    "ScalpState",
    "CombinedContractState",
    "compose_contract_state",
]
