#!/usr/bin/env python3
"""Research-only scalp test gate evaluator.

NO ORDERS. NO production changes. NO threshold changes.

Purpose
-------
Turn accumulated V6 research metrics into one compact checkpoint so we do not
manually debate incomplete test runs. This script only evaluates evidence that
is supplied to it; it does not alter V6 or any trading behavior.

The gate is intentionally conservative:
- INSUFFICIENT_DATA until enough V6 samples exist
- REVIEW when data is large enough but mixed
- PROMISING only when multiple quality dimensions are healthy

The constants below are research review gates, not trading thresholds.
"""

from dataclasses import dataclass


@dataclass
class ResearchMetrics:
    n: int
    hit5_pct: float
    hit10_pct: float
    hit20_pct: float
    burst10_pct: float
    expand10_pct: float
    avg_gain_c: float
    avg_adverse_c: float
    degraded_pct: float = 0.0


@dataclass
class GateResult:
    state: str
    reasons: list[str]


MIN_SAMPLES = 30
TARGET_HIT10 = 70.0
TARGET_EXPAND10 = 75.0
TARGET_HIT5 = 80.0
MAX_AVG_ADVERSE_C = 6.0
MAX_DEGRADED_PCT = 20.0


def evaluate(m: ResearchMetrics) -> GateResult:
    reasons: list[str] = []

    if m.n < MIN_SAMPLES:
        reasons.append(f'need {MIN_SAMPLES - m.n} more V6 samples')
        return GateResult('INSUFFICIENT_DATA', reasons)

    good = 0
    checks = 5

    if m.hit5_pct >= TARGET_HIT5:
        good += 1
    else:
        reasons.append(f'hit5 {m.hit5_pct:.1f}% < {TARGET_HIT5:.1f}%')

    if m.hit10_pct >= TARGET_HIT10:
        good += 1
    else:
        reasons.append(f'hit10 {m.hit10_pct:.1f}% < {TARGET_HIT10:.1f}%')

    if m.expand10_pct >= TARGET_EXPAND10:
        good += 1
    else:
        reasons.append(f'expand10 {m.expand10_pct:.1f}% < {TARGET_EXPAND10:.1f}%')

    if m.avg_adverse_c <= MAX_AVG_ADVERSE_C:
        good += 1
    else:
        reasons.append(f'avg adverse {m.avg_adverse_c:.1f}c > {MAX_AVG_ADVERSE_C:.1f}c')

    if m.degraded_pct <= MAX_DEGRADED_PCT:
        good += 1
    else:
        reasons.append(f'degraded data {m.degraded_pct:.1f}% > {MAX_DEGRADED_PCT:.1f}%')

    if good == checks:
        return GateResult('PROMISING', ['all research review gates passed'])
    if good >= 3:
        return GateResult('REVIEW', reasons or ['mixed result'])
    return GateResult('NOT_READY', reasons or ['too many review gates missed'])


def compact(m: ResearchMetrics) -> str:
    g = evaluate(m)
    why = '; '.join(g.reasons)
    return (
        f'SCALP_TEST_GATE | {g.state} | n={m.n} | hit5={m.hit5_pct:.1f}% | '
        f'hit10={m.hit10_pct:.1f}% | hit20={m.hit20_pct:.1f}% | '
        f'burst10={m.burst10_pct:.1f}% | expand10={m.expand10_pct:.1f}% | '
        f'avgGain={m.avg_gain_c:.1f}c | avgAdv={m.avg_adverse_c:.1f}c | '
        f'degraded={m.degraded_pct:.1f}% | {why}'
    )


if __name__ == '__main__':
    # Example only; replace with actual research summary values when invoked.
    sample = ResearchMetrics(
        n=12,
        hit5_pct=83.3,
        hit10_pct=66.7,
        hit20_pct=41.7,
        burst10_pct=25.0,
        expand10_pct=66.7,
        avg_gain_c=14.2,
        avg_adverse_c=3.8,
        degraded_pct=10.0,
    )
    print(compact(sample))
