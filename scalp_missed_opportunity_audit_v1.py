#!/usr/bin/env python3
"""V6 missed-opportunity audit V1.

Research-only / signal-only. NO ORDERS.

Purpose
-------
Score rejected V6 setups after the fact so we can tell whether the filter is
protecting us or becoming too strict. This module does NOT alter qualification.

For each rejected setup, record:
- rejection reason
- entry ask
- max executable bid gain over 3 minutes
- adverse move
- time to +5c/+10c/+20c if reached
- whether the rejection later became a material missed opportunity

This is intentionally independent from V6 entry logic.
"""

from dataclasses import dataclass
from typing import Optional, List

HORIZON_SECONDS = 180.0
MISS_10C = 0.10
MISS_20C = 0.20


@dataclass
class RejectedCandidate:
    ticker: str
    side: str
    reason: str
    ts: float
    entry_ask: float


@dataclass
class AuditPoint:
    ts: float
    bid: float


@dataclass
class MissedOpportunityReport:
    ticker: str
    side: str
    reason: str
    entry_ask: float
    max_gain: float
    adverse: float
    t5: Optional[float]
    t10: Optional[float]
    t20: Optional[float]
    classification: str


def _first_hit(points: List[AuditPoint], start_ts: float, entry: float, delta: float) -> Optional[float]:
    for p in points:
        if p.ts - start_ts > HORIZON_SECONDS:
            break
        if p.bid - entry >= delta:
            return round(p.ts - start_ts, 1)
    return None


def score_rejection(c: RejectedCandidate, points: List[AuditPoint]) -> MissedOpportunityReport:
    active = [p for p in points if 0 <= p.ts - c.ts <= HORIZON_SECONDS]
    if not active:
        return MissedOpportunityReport(c.ticker,c.side,c.reason,c.entry_ask,0.0,0.0,None,None,None,'NO_FOLLOWUP_DATA')

    max_bid = max(p.bid for p in active)
    min_bid = min(p.bid for p in active)
    max_gain = max_bid - c.entry_ask
    adverse = min_bid - c.entry_ask
    t5 = _first_hit(active, c.ts, c.entry_ask, 0.05)
    t10 = _first_hit(active, c.ts, c.entry_ask, 0.10)
    t20 = _first_hit(active, c.ts, c.entry_ask, 0.20)

    if max_gain >= MISS_20C:
        cls = 'MATERIAL_MISS_20C'
    elif max_gain >= MISS_10C:
        cls = 'MATERIAL_MISS_10C'
    elif max_gain >= 0.05:
        cls = 'SMALL_MISS_5C'
    else:
        cls = 'GOOD_REJECT'

    return MissedOpportunityReport(
        c.ticker,c.side,c.reason,c.entry_ask,max_gain,adverse,t5,t10,t20,cls
    )


def compact(r: MissedOpportunityReport) -> str:
    def f(v): return 'None' if v is None else f'{v:.1f}s'
    return (
        f'MISSED_OPP | {r.ticker} | {r.side} | reason={r.reason} | entry={r.entry_ask:.3f} | '
        f'class={r.classification} | maxGain={r.max_gain:+.3f} | adverse={r.adverse:+.3f} | '
        f't5={f(r.t5)} | t10={f(r.t10)} | t20={f(r.t20)}'
    )


def summarize(reports: List[MissedOpportunityReport]) -> str:
    if not reports:
        return 'MISSED_OPP_SUMMARY | n=0'
    n=len(reports)
    good=sum(r.classification=='GOOD_REJECT' for r in reports)
    small=sum(r.classification=='SMALL_MISS_5C' for r in reports)
    m10=sum(r.classification=='MATERIAL_MISS_10C' for r in reports)
    m20=sum(r.classification=='MATERIAL_MISS_20C' for r in reports)
    return (
        f'MISSED_OPP_SUMMARY | n={n} | goodReject={100*good/n:.1f}% | '
        f'smallMiss5={100*small/n:.1f}% | miss10={100*m10/n:.1f}% | miss20={100*m20/n:.1f}%'
    )


if __name__ == '__main__':
    c=RejectedCandidate('DEMO','DOWN','DATA_DEGRADED',1000.0,0.05)
    pts=[AuditPoint(1000,0.04),AuditPoint(1030,0.08),AuditPoint(1068,0.16),AuditPoint(1095,0.31)]
    r=score_rejection(c,pts)
    print(compact(r))
    print(summarize([r]))
