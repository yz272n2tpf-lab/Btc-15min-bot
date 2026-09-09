#!/usr/bin/env python3
"""Scalp trade-path recorder/scorer V1.

Research-only / signal-only. NO ORDERS.

Purpose
-------
Record the path of an already-qualified scalp so we can evaluate whether the
profit-protection states (HOLD / WATCH / TAKE_PROFIT / EXIT) preserve enough of
the move without cutting expansion scalps too early.

This module does not qualify entries and does not change V6 thresholds.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from scalp_profit_protection_shadow_v1 import ScalpState, assess_scalp


@dataclass
class PathPoint:
    seconds_open: float
    seconds_left: float
    bid: float
    btc5: Optional[float] = None
    btc15: Optional[float] = None
    brti5: Optional[float] = None
    brti15: Optional[float] = None


@dataclass
class PathDecision:
    seconds_open: float
    bid: float
    state: str
    reason: str
    gain: float
    peak_gain: float
    retrace: float


@dataclass
class ScalpPathReport:
    entry: float
    max_bid: float
    max_gain: float
    adverse: float
    first_5c: Optional[float]
    first_10c: Optional[float]
    first_20c: Optional[float]
    first_watch: Optional[float]
    first_take_profit: Optional[float]
    first_exit: Optional[float]
    decision_gain: Optional[float]
    giveback_from_peak_at_decision: Optional[float]
    remaining_upside_after_decision: Optional[float]
    path_style: str
    decisions: List[PathDecision] = field(default_factory=list)


def _first_time(points: List[PathPoint], entry: float, cents: float) -> Optional[float]:
    for p in points:
        if p.bid - entry >= cents:
            return p.seconds_open
    return None


def score_path(entry: float, points: List[PathPoint]) -> ScalpPathReport:
    if not points:
        raise ValueError('points must not be empty')

    peak = points[0].bid
    min_bid = points[0].bid
    decisions: List[PathDecision] = []

    first_watch = None
    first_take = None
    first_exit = None
    chosen_decision_gain = None
    giveback = None
    remaining_upside = None

    all_max_bid = max(p.bid for p in points)

    for p in points:
        peak = max(peak, p.bid)
        min_bid = min(min_bid, p.bid)

        d = assess_scalp(ScalpState(
            entry=entry,
            current_bid=p.bid,
            peak_bid=peak,
            seconds_open=p.seconds_open,
            seconds_left=p.seconds_left,
            btc5=p.btc5,
            btc15=p.btc15,
            brti5=p.brti5,
            brti15=p.brti15,
        ))

        decisions.append(PathDecision(
            seconds_open=p.seconds_open,
            bid=p.bid,
            state=d.state,
            reason=d.reason,
            gain=d.gain,
            peak_gain=d.peak_gain,
            retrace=d.retrace,
        ))

        if d.state == 'WATCH' and first_watch is None:
            first_watch = p.seconds_open
        if d.state == 'TAKE_PROFIT' and first_take is None:
            first_take = p.seconds_open
        if d.state == 'EXIT' and first_exit is None:
            first_exit = p.seconds_open

        # For shadow scoring, TAKE_PROFIT is the first actionable protection cue;
        # if it never occurs, EXIT becomes the modeled decision.
        if chosen_decision_gain is None and d.state in {'TAKE_PROFIT', 'EXIT'}:
            chosen_decision_gain = p.bid - entry
            giveback = peak - p.bid
            remaining_upside = all_max_bid - p.bid

    t10 = _first_time(points, entry, 0.10)
    if t10 is not None and t10 <= 30:
        style = 'BURST'
    elif t10 is not None and t10 <= 180:
        style = 'EXPANSION'
    else:
        style = 'NO_EXPANSION'

    return ScalpPathReport(
        entry=entry,
        max_bid=all_max_bid,
        max_gain=all_max_bid-entry,
        adverse=min_bid-entry,
        first_5c=_first_time(points, entry, 0.05),
        first_10c=t10,
        first_20c=_first_time(points, entry, 0.20),
        first_watch=first_watch,
        first_take_profit=first_take,
        first_exit=first_exit,
        decision_gain=chosen_decision_gain,
        giveback_from_peak_at_decision=giveback,
        remaining_upside_after_decision=remaining_upside,
        path_style=style,
        decisions=decisions,
    )


def compact_report(r: ScalpPathReport) -> str:
    def f(v):
        return 'None' if v is None else ('%.1fs' % v)
    dg = 'None' if r.decision_gain is None else ('%+.3f' % r.decision_gain)
    gb = 'None' if r.giveback_from_peak_at_decision is None else ('%+.3f' % r.giveback_from_peak_at_decision)
    ru = 'None' if r.remaining_upside_after_decision is None else ('%+.3f' % r.remaining_upside_after_decision)
    return (
        'SCALP_PATH | style=%s | entry=%.3f | maxGain=%+.3f | adverse=%+.3f | '
        't5=%s | t10=%s | t20=%s | WATCH=%s | TAKE_PROFIT=%s | EXIT=%s | '
        'decisionGain=%s | giveback=%s | upsideLeft=%s'
    ) % (
        r.path_style, r.entry, r.max_gain, r.adverse,
        f(r.first_5c), f(r.first_10c), f(r.first_20c),
        f(r.first_watch), f(r.first_take_profit), f(r.first_exit),
        dg, gb, ru,
    )


def demo() -> None:
    pts = [
        PathPoint(0, 500, 0.05, btc5=10, btc15=15, brti5=8, brti15=12),
        PathPoint(25, 475, 0.08, btc5=12, btc15=16, brti5=10, brti15=13),
        PathPoint(55, 445, 0.12, btc5=11, btc15=15, brti5=9, brti15=12),
        PathPoint(68, 432, 0.16, btc5=9, btc15=14, brti5=7, brti15=11),
        PathPoint(95, 405, 0.31, btc5=5, btc15=12, brti5=4, brti15=10),
        PathPoint(115, 385, 0.27, btc5=-2, btc15=8, brti5=-1, brti15=7),
        PathPoint(130, 370, 0.23, btc5=-10, btc15=-2, brti5=-7, brti15=-1),
    ]
    print(compact_report(score_path(0.05, pts)))


if __name__ == '__main__':
    demo()
