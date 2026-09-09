#!/usr/bin/env python3
"""Scalp lead-edge analyzer V1.

Research-only / signal-only. NO ORDERS.

Purpose
-------
Measure whether a qualified scalp signal is actually early relative to Kalshi
repricing, instead of only measuring eventual profit.

For each signal, record the signal timestamp and entry ask, then feed subsequent
Kalshi bid/ask observations. The analyzer reports:
- time from signal to +5c/+10c/+20c executable bid gain
- time from signal to +5c/+10c ask reprice
- lead margin between the signal and Kalshi's visible repricing
- whether the move was already underway at signal time
- whether the signal was EARLY, ON_TIME, LATE, or NO_MOVE

This module does not alter V6 qualification thresholds.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class QuotePoint:
    seconds_after_signal: float
    bid: Optional[float]
    ask: Optional[float]


@dataclass
class LeadEdgeReport:
    entry_ask: float
    first_bid_5c: Optional[float]
    first_bid_10c: Optional[float]
    first_bid_20c: Optional[float]
    first_ask_5c: Optional[float]
    first_ask_10c: Optional[float]
    max_exec_gain: float
    max_ask_reprice: float
    signal_class: str
    lead_margin_5c: Optional[float]
    lead_margin_10c: Optional[float]


def _first(points: List[QuotePoint], fn) -> Optional[float]:
    for p in points:
        if fn(p):
            return p.seconds_after_signal
    return None


def analyze_lead(entry_ask: float, points: List[QuotePoint]) -> LeadEdgeReport:
    if not points:
        raise ValueError('points must not be empty')

    bid5 = _first(points, lambda p: p.bid is not None and p.bid - entry_ask >= 0.05)
    bid10 = _first(points, lambda p: p.bid is not None and p.bid - entry_ask >= 0.10)
    bid20 = _first(points, lambda p: p.bid is not None and p.bid - entry_ask >= 0.20)
    ask5 = _first(points, lambda p: p.ask is not None and p.ask - entry_ask >= 0.05)
    ask10 = _first(points, lambda p: p.ask is not None and p.ask - entry_ask >= 0.10)

    bids = [p.bid for p in points if p.bid is not None]
    asks = [p.ask for p in points if p.ask is not None]
    max_exec = (max(bids) - entry_ask) if bids else 0.0
    max_ask = (max(asks) - entry_ask) if asks else 0.0

    # Lead margin is how many seconds the signal existed before the visible ask
    # repriced by the same amount. Positive is desirable.
    lead5 = ask5 if ask5 is not None else None
    lead10 = ask10 if ask10 is not None else None

    # Classify timing independently of eventual profitability.
    if max_exec < 0.05:
        timing = 'NO_MOVE'
    elif bid5 is not None and bid5 <= 2.0:
        timing = 'LATE'
    elif ask5 is not None and ask5 <= 3.0:
        timing = 'ON_TIME'
    elif ask5 is not None and ask5 > 3.0:
        timing = 'EARLY'
    else:
        # Executable gain happened but ask did not visibly reprice enough in the
        # observed window; treat as early but unconfirmed by ask ladder.
        timing = 'EARLY_UNCONFIRMED'

    return LeadEdgeReport(
        entry_ask=entry_ask,
        first_bid_5c=bid5,
        first_bid_10c=bid10,
        first_bid_20c=bid20,
        first_ask_5c=ask5,
        first_ask_10c=ask10,
        max_exec_gain=max_exec,
        max_ask_reprice=max_ask,
        signal_class=timing,
        lead_margin_5c=lead5,
        lead_margin_10c=lead10,
    )


def compact(r: LeadEdgeReport) -> str:
    def t(v):
        return 'None' if v is None else f'{v:.1f}s'
    return (
        'SCALP_LEAD_EDGE | class=%s | entry=%.3f | maxExec=%+.3f | maxAsk=%+.3f | '
        'bid+5=%s | bid+10=%s | bid+20=%s | ask+5=%s | ask+10=%s | lead5=%s | lead10=%s'
    ) % (
        r.signal_class, r.entry_ask, r.max_exec_gain, r.max_ask_reprice,
        t(r.first_bid_5c), t(r.first_bid_10c), t(r.first_bid_20c),
        t(r.first_ask_5c), t(r.first_ask_10c), t(r.lead_margin_5c), t(r.lead_margin_10c)
    )


def demo() -> None:
    pts = [
        QuotePoint(0, 0.04, 0.05),
        QuotePoint(8, 0.06, 0.07),
        QuotePoint(22, 0.10, 0.11),
        QuotePoint(68, 0.16, 0.18),
        QuotePoint(95, 0.29, 0.31),
    ]
    print(compact(analyze_lead(0.05, pts)))


if __name__ == '__main__':
    demo()
