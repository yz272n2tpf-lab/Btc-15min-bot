#!/usr/bin/env python3
"""Research-only V7 freeze gate for the BTC 15m scalp ladder.

Purpose:
- turn grouped V7 metrics into a deterministic FREEZE / TIGHTEN / MORE_DATA decision
- keep momentum/expansion and ultra-cheap reversal lanes independent
- prevent one spectacular winner from graduating a weak lane
- never place orders or alter production behavior
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class LaneMetrics:
    name: str
    n: int
    hit5: float
    hit10: float
    hit20: float
    avg_gain: float
    avg_adverse: float
    preferred_entry_share: float = 0.0
    brti_clean_rate: Optional[float] = None


@dataclass
class GateResult:
    lane: str
    decision: str
    reason: str


MIN_SAMPLE = 24
MIN_HIT5 = 0.65
MIN_HIT10 = 0.55
MIN_HIT20 = 0.30
MAX_AVG_ADVERSE = 0.07
MIN_AVG_GAIN = 0.12
MIN_PREF_SHARE = 0.50
MIN_BRTI_CLEAN = 0.94

# Reversal lane is intentionally stricter on sample interpretation because cheap
# contracts can create huge but infrequent outliers.
REV_MIN_SAMPLE = 18
REV_MIN_HIT10 = 0.50
REV_MIN_AVG_GAIN = 0.15


def evaluate_lane(m: LaneMetrics) -> GateResult:
    if m.name == 'ULTRA_CHEAP_REVERSAL':
        min_sample = REV_MIN_SAMPLE
        min_hit10 = REV_MIN_HIT10
        min_avg_gain = REV_MIN_AVG_GAIN
    else:
        min_sample = MIN_SAMPLE
        min_hit10 = MIN_HIT10
        min_avg_gain = MIN_AVG_GAIN

    if m.n < min_sample:
        return GateResult(m.name, 'MORE_DATA', f'n={m.n} < required {min_sample}')

    failures = []
    if m.hit5 < MIN_HIT5:
        failures.append(f'hit5 {m.hit5:.1%} < {MIN_HIT5:.0%}')
    if m.hit10 < min_hit10:
        failures.append(f'hit10 {m.hit10:.1%} < {min_hit10:.0%}')
    if m.hit20 < MIN_HIT20:
        failures.append(f'hit20 {m.hit20:.1%} < {MIN_HIT20:.0%}')
    if m.avg_gain < min_avg_gain:
        failures.append(f'avg_gain {m.avg_gain:.3f} < {min_avg_gain:.3f}')
    if abs(min(0.0, m.avg_adverse)) > MAX_AVG_ADVERSE:
        failures.append(f'avg_adverse {m.avg_adverse:.3f} worse than -{MAX_AVG_ADVERSE:.3f}')
    if m.name == 'MOMENTUM_EXPANSION' and m.preferred_entry_share < MIN_PREF_SHARE:
        failures.append(f'preferred_entry_share {m.preferred_entry_share:.1%} < {MIN_PREF_SHARE:.0%}')
    if m.brti_clean_rate is not None and m.brti_clean_rate < MIN_BRTI_CLEAN:
        failures.append(f'brti_clean_rate {m.brti_clean_rate:.1%} < {MIN_BRTI_CLEAN:.0%}')

    if not failures:
        return GateResult(m.name, 'FREEZE', 'all graduation gates passed')

    # If upside remains materially positive, preserve the lane but tighten it.
    if m.hit10 >= 0.45 and m.avg_gain >= 0.08:
        return GateResult(m.name, 'TIGHTEN', '; '.join(failures))

    return GateResult(m.name, 'REJECT', '; '.join(failures))


def final_architecture(momentum: GateResult, reversal: GateResult) -> str:
    if momentum.decision == 'FREEZE' and reversal.decision == 'FREEZE':
        return 'FREEZE_SPLIT_LADDER'
    if momentum.decision == 'FREEZE' and reversal.decision in {'MORE_DATA', 'REJECT'}:
        return 'FREEZE_MOMENTUM_ONLY_KEEP_REVERSAL_RESEARCH'
    if momentum.decision in {'TIGHTEN', 'MORE_DATA'} or reversal.decision in {'TIGHTEN', 'MORE_DATA'}:
        return 'FOCUSED_REFINEMENT_ONLY'
    return 'DO_NOT_GRADUATE'


def _self_test() -> None:
    good = LaneMetrics('MOMENTUM_EXPANSION', 30, .72, .63, .37, .19, -.05, .74, .963)
    thin = LaneMetrics('ULTRA_CHEAP_REVERSAL', 4, .75, .50, .50, .22, -.04, 1.0, .963)
    bad = LaneMetrics('MOMENTUM_EXPANSION', 30, .50, .33, .10, .05, -.11, .30, .90)
    assert evaluate_lane(good).decision == 'FREEZE'
    assert evaluate_lane(thin).decision == 'MORE_DATA'
    assert evaluate_lane(bad).decision == 'REJECT'
    print('V7_FREEZE_GATE_SELF_TEST | PASS')


if __name__ == '__main__':
    _self_test()
