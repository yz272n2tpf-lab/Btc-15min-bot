#!/usr/bin/env python3
"""
BTC15 scalp management presentation V1.

PURE PRESENTATION | SIGNAL ONLY | NO ORDERS

This module does NOT change frozen SCALP entry or exit thresholds. It converts
an already-derived SCALP state into clear user-facing guidance:

- before +5c arm: SCALP ACTIVE
- +5c arm reached and still at running peak: PROTECTION ARMED / WINNER RUNNING
- any observed pullback after arm but before frozen 4c EXIT: PROTECT PROFITS / PULLBACK DETECTED
- frozen 4c giveback reached: EXIT / PROTECT PROFITS NOW

The pullback warning uses no tuned magnitude threshold: any positive giveback
visible in the event tape after the validated +5c arm can surface a warning.
"""
from __future__ import annotations

from dataclasses import dataclass

EPS = 1e-12


@dataclass(frozen=True)
class ScalpManagementPresentation:
    state: str
    message: str
    protection_armed: bool
    pullback_detected: bool
    exit_now: bool
    giveback_from_peak: float | None
    manual_execution_only: bool = True


def management_presentation(
    *,
    state: str,
    peak_exec_gain: float | None,
    exec_gain: float | None,
    arm_gain: float = 0.05,
    exit_giveback: float = 0.04,
) -> ScalpManagementPresentation:
    state = str(state or "PASS").upper()
    peak = None if peak_exec_gain is None else float(peak_exec_gain)
    current = None if exec_gain is None else float(exec_gain)
    giveback = (
        max(0.0, peak - current)
        if peak is not None and current is not None
        else None
    )
    armed = bool(peak is not None and peak >= float(arm_gain) - EPS)
    pullback = bool(armed and giveback is not None and giveback > EPS)
    exit_now = bool(state == "EXIT" or (armed and giveback is not None and giveback >= float(exit_giveback) - EPS))

    if exit_now:
        message = "EXIT / PROTECT PROFITS NOW"
        state_out = "EXIT"
    elif armed and pullback:
        message = "PROTECT PROFITS · PULLBACK DETECTED"
        state_out = "PROTECT"
    elif armed:
        message = "PROTECTION ARMED · WINNER RUNNING"
        state_out = "PROTECT"
    elif state == "PASS":
        message = "NO QUALIFIED SCALP"
        state_out = "PASS"
    else:
        message = "SCALP ACTIVE · BUILDING"
        state_out = "ACTIVE"

    return ScalpManagementPresentation(
        state=state_out,
        message=message,
        protection_armed=armed,
        pullback_detected=pullback,
        exit_now=exit_now,
        giveback_from_peak=giveback,
    )


__all__ = ["ScalpManagementPresentation", "management_presentation"]
