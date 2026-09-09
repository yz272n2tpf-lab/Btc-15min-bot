#!/usr/bin/env python3
"""Research-only market regime tagger for scalp analysis. NO ORDERS.

Purpose:
Classify each scalp sample into simple context buckets so we can learn whether
V6 performs differently in TREND, CHOP, QUIET, or VOLATILE conditions without
changing live qualification logic.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class RegimeInput:
    btc5: Optional[float]
    btc15: Optional[float]
    btc30: Optional[float]
    accel: Optional[float]
    brti5: Optional[float]
    brti15: Optional[float]

@dataclass
class RegimeTag:
    regime: str
    reason: str


def _a(x):
    return 0.0 if x is None else abs(float(x))


def classify_regime(x: RegimeInput) -> RegimeTag:
    b5=_a(x.btc5); b15=_a(x.btc15); b30=_a(x.btc30)
    a=_a(x.accel); r5=_a(x.brti5); r15=_a(x.brti15)

    aligned = (
        x.btc5 is not None and x.btc15 is not None and
        ((x.btc5 > 0 and x.btc15 > 0) or (x.btc5 < 0 and x.btc15 < 0))
    )

    if max(b5,b15,b30,r5,r15) < 6 and a < 4:
        return RegimeTag('QUIET', 'subminute movement is muted')
    if aligned and (b15 >= 20 or b30 >= 25) and (r15 >= 8 or r5 >= 12):
        return RegimeTag('TREND', 'BTC and BRTI are aligned with sustained movement')
    if a >= 18 or max(b5,r5) >= 25:
        return RegimeTag('VOLATILE', 'fast movement/acceleration is elevated')
    return RegimeTag('CHOP', 'mixed or moderate subminute structure')


if __name__ == '__main__':
    demos = [
        RegimeInput(3,4,5,2,2,3),
        RegimeInput(14,28,31,8,13,11),
        RegimeInput(-30,-8,5,22,-27,-4),
        RegimeInput(9,-3,2,6,5,-2),
    ]
    for d in demos:
        t=classify_regime(d)
        print(t.regime, '|', t.reason)
