#!/usr/bin/env python3
"""BTC15 time-left guardrail presentation V1.

PURE PRESENTATION | NO SIGNAL FILTERING | NO ORDERS

Converts the already-canonical contract seconds-left value into user-facing late
window context. These bands do not qualify, suppress, re-rank, or exit a signal.
They are display cues only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

VERSION = "BTC15_TIME_LEFT_GUARDRAIL_V1"

CAUTION_5M_SECONDS = 300.0
GUARD_3M_SECONDS = 180.0


def _finite(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except Exception:
        return None
    return x if math.isfinite(x) else None


@dataclass(frozen=True)
class TimeLeftGuardrail:
    version: str
    band: str
    label: str
    detail: str
    tone: str
    seconds_left: float | None
    signal_filtering: bool = False
    signal_suppression: bool = False
    changes_entry_rule: bool = False
    changes_exit_rule: bool = False
    orders: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def time_left_guardrail(seconds_left: Any) -> TimeLeftGuardrail:
    sec = _finite(seconds_left)
    if sec is None:
        return TimeLeftGuardrail(
            VERSION,
            "UNAVAILABLE",
            "TIME CHECK",
            "Waiting for the canonical contract timer.",
            "neutral",
            None,
        )

    sec = max(0.0, sec)
    if sec <= 0.0:
        return TimeLeftGuardrail(
            VERSION,
            "ROLLOVER",
            "NEXT CONTRACT SYNCING",
            "Old-contract actions are no longer current.",
            "caution",
            sec,
        )
    if sec <= GUARD_3M_SECONDS:
        return TimeLeftGuardrail(
            VERSION,
            "GUARD_3M",
            "3M GUARD RAIL",
            "Late contract window · treat new entries with extra caution.",
            "caution",
            sec,
        )
    if sec <= CAUTION_5M_SECONDS:
        return TimeLeftGuardrail(
            VERSION,
            "CAUTION_5M",
            "5M CAUTION",
            "Less time remains for a move to develop or recover.",
            "caution",
            sec,
        )
    return TimeLeftGuardrail(
        VERSION,
        "NORMAL",
        "CONTRACT ACTIVE",
        "Standard timing context.",
        "neutral",
        sec,
    )


__all__ = [
    "VERSION",
    "CAUTION_5M_SECONDS",
    "GUARD_3M_SECONDS",
    "TimeLeftGuardrail",
    "time_left_guardrail",
]
