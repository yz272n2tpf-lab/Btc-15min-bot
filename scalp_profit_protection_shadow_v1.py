#!/usr/bin/env python3
"""Scalp profit-protection decision engine V1.

Research-only / signal-only. NO ORDERS.

Purpose:
Translate an active scalp's live path into HOLD / WATCH / TAKE_PROFIT / EXIT
research states without changing entry qualification. This module is intentionally
standalone so it can be validated before being wired into V6.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class ScalpState:
    entry: float
    current_bid: float
    peak_bid: float
    seconds_open: float
    seconds_left: float
    btc5: Optional[float] = None
    btc15: Optional[float] = None
    brti5: Optional[float] = None
    brti15: Optional[float] = None

@dataclass
class ProtectionDecision:
    state: str
    reason: str
    gain: float
    peak_gain: float
    retrace: float


def _opposed(v: Optional[float], threshold: float) -> bool:
    return v is not None and v <= threshold


def assess_scalp(state: ScalpState) -> ProtectionDecision:
    """Return a research-only protection state for an already-open scalp.

    Rules are deliberately conservative and are NOT production thresholds.
    They are a first shadow hypothesis to score against realized max gain.
    """
    gain = state.current_bid - state.entry
    peak_gain = state.peak_bid - state.entry
    retrace = state.peak_bid - state.current_bid

    momentum_reversal = (
        _opposed(state.btc5, -8.0) and
        (state.brti5 is None or _opposed(state.brti5, -5.0))
    )
    momentum_soft = (
        _opposed(state.btc5, 0.0) or
        _opposed(state.btc15, 0.0) or
        _opposed(state.brti5, 0.0)
    )

    # No meaningful expansion yet: stay patient unless the move is already failing.
    if peak_gain < 0.05:
        if gain <= -0.05 or momentum_reversal:
            return ProtectionDecision('EXIT', 'entry failed before expansion', gain, peak_gain, retrace)
        return ProtectionDecision('HOLD', 'expansion not established yet', gain, peak_gain, retrace)

    # Strong profit has been achieved. A large give-back or momentum reversal is an exit cue.
    if peak_gain >= 0.20:
        if retrace >= 0.10 or momentum_reversal:
            return ProtectionDecision('EXIT', 'large give-back after strong expansion', gain, peak_gain, retrace)
        if retrace >= 0.05 or momentum_soft or state.seconds_left <= 60:
            return ProtectionDecision('TAKE_PROFIT', 'protect a strong expansion', gain, peak_gain, retrace)
        return ProtectionDecision('HOLD', 'strong expansion still intact', gain, peak_gain, retrace)

    # Mid-profit zone: protect more aggressively as the move matures.
    if peak_gain >= 0.10:
        if retrace >= 0.08 or momentum_reversal:
            return ProtectionDecision('EXIT', 'mid-profit move is reversing', gain, peak_gain, retrace)
        if retrace >= 0.04 or momentum_soft:
            return ProtectionDecision('WATCH', 'momentum weakening after +10c expansion', gain, peak_gain, retrace)
        return ProtectionDecision('HOLD', 'expansion structure intact', gain, peak_gain, retrace)

    # Early +5c to +10c zone: keep room for a 1-3 minute expansion scalp.
    if retrace >= 0.05 or momentum_reversal:
        return ProtectionDecision('WATCH', 'early expansion is losing structure', gain, peak_gain, retrace)
    return ProtectionDecision('HOLD', 'allow early expansion room', gain, peak_gain, retrace)


def demo() -> None:
    cases = [
        ScalpState(0.05,0.06,0.06,20,500,btc5=12,btc15=20,brti5=10,brti15=15),
        ScalpState(0.05,0.16,0.17,70,430,btc5=8,btc15=18,brti5=7,brti15=12),
        ScalpState(0.05,0.25,0.31,95,405,btc5=-2,btc15=10,brti5=-1,brti15=8),
        ScalpState(0.05,0.19,0.31,110,390,btc5=-12,btc15=-3,brti5=-8,brti15=-2),
    ]
    for c in cases:
        d=assess_scalp(c)
        print(f'{d.state:11s} gain={d.gain:+.3f} peak={d.peak_gain:+.3f} retrace={d.retrace:+.3f} | {d.reason}')

if __name__ == '__main__':
    demo()
