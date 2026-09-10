#!/usr/bin/env python3
"""Research-only utilities for the split V7 scalp ladder.

Does NOT place orders and does NOT change live V7 qualification thresholds.
Provides:
- lane/price-zone scoring summaries
- KEEP/TIGHTEN/REJECT recommendations
- app-facing SCALP WATCH/ENTRY/HOLD/TAKE PROFIT/EXIT translation
- BRTI reliability diagnostics
"""
from dataclasses import dataclass, asdict
from typing import Optional, Iterable, Dict, List


@dataclass
class Outcome:
    lane: str
    zone: str
    entry: float
    max_gain: float
    adverse: float
    to5: Optional[float] = None
    to10: Optional[float] = None
    to20: Optional[float] = None


def price_bucket(entry: float) -> str:
    if entry < 0.03: return 'LT_3C'
    if entry <= 0.07: return '3_7C'
    if entry <= 0.15: return '8_15C'
    if entry <= 0.30: return '16_30C'
    if entry <= 0.45: return '31_45C'
    return 'GT_45C'


def summarize(outcomes: Iterable[Outcome]) -> Dict[str, float]:
    rows = list(outcomes)
    n = len(rows)
    if not n:
        return {'n': 0}
    hit5 = sum(r.to5 is not None for r in rows)
    hit10 = sum(r.to10 is not None for r in rows)
    hit20 = sum(r.to20 is not None for r in rows)
    burst10 = sum(r.to10 is not None and r.to10 <= 30 for r in rows)
    expand10 = sum(r.to10 is not None and r.to10 <= 120 for r in rows)
    return {
        'n': n,
        'hit5_pct': 100.0 * hit5 / n,
        'hit10_pct': 100.0 * hit10 / n,
        'burst10_pct': 100.0 * burst10 / n,
        'expand10_pct': 100.0 * expand10 / n,
        'hit20_pct': 100.0 * hit20 / n,
        'avg_gain': sum(r.max_gain for r in rows) / n,
        'avg_adverse': sum(r.adverse for r in rows) / n,
    }


def split_summary(outcomes: Iterable[Outcome]) -> Dict[str, Dict[str, float]]:
    rows = list(outcomes)
    groups: Dict[str, List[Outcome]] = {}
    for r in rows:
        keys = [
            f'LANE:{r.lane}',
            f'PRICE:{price_bucket(r.entry)}',
            f'LANE_PRICE:{r.lane}:{price_bucket(r.entry)}',
            f'ZONE:{r.zone}',
        ]
        for k in keys:
            groups.setdefault(k, []).append(r)
    return {k: summarize(v) for k, v in groups.items()}


def recommendation(stats: Dict[str, float], min_sample: int = 12) -> str:
    n = int(stats.get('n', 0))
    if n < min_sample:
        return 'MORE_DATA'
    hit10 = stats.get('hit10_pct', 0.0)
    gain = stats.get('avg_gain', 0.0)
    adverse = abs(stats.get('avg_adverse', 0.0))
    if hit10 >= 65.0 and gain >= 0.15 and adverse <= 0.07:
        return 'KEEP'
    if hit10 >= 50.0 and gain >= 0.10 and adverse <= 0.10:
        return 'TIGHTEN'
    return 'REJECT'


def decision_report(outcomes: Iterable[Outcome]) -> Dict[str, Dict[str, object]]:
    report = {}
    for k, stats in split_summary(outcomes).items():
        report[k] = {'stats': stats, 'decision': recommendation(stats)}
    return report


@dataclass
class AppSignal:
    state: str
    side: str
    lane: str
    entry: Optional[float]
    signal_strength: int
    flip_risk: str
    reason: str


def app_state(*, side: str, lane: str, qualified: bool, entry: Optional[float],
              max_gain: float = 0.0, adverse: float = 0.0,
              evidence_score: float = 0.0, reversal_risk: float = 0.0) -> AppSignal:
    if not qualified:
        state = 'SCALP WATCH'
    elif max_gain >= 0.30 or max_gain >= max(0.10, (entry or 0.0) * 1.5):
        state = 'TAKE PROFIT'
    elif adverse <= -0.10 or reversal_risk >= 0.70:
        state = 'EXIT'
    elif max_gain >= 0.05:
        state = 'HOLD'
    else:
        state = 'ENTRY'

    strength = max(0, min(100, int(round(evidence_score * 100))))
    if reversal_risk < 0.25:
        flip = 'LOW'
    elif reversal_risk < 0.50:
        flip = 'MODERATE'
    else:
        flip = 'HIGH'

    reason = f'{lane} lane; evidence {strength}%; reversal risk {int(reversal_risk*100)}%'
    return AppSignal(state, side, lane, entry, strength, flip, reason)


@dataclass
class BrtiHealth:
    samples: int
    fresh_ok: int
    retry_recovered: int
    errors: int

    @property
    def fresh_pct(self) -> float:
        return 0.0 if self.samples <= 0 else 100.0 * self.fresh_ok / self.samples

    @property
    def error_pct(self) -> float:
        return 0.0 if self.samples <= 0 else 100.0 * self.errors / self.samples

    def status(self) -> str:
        p = self.fresh_pct
        if p >= 97.0: return 'HEALTHY'
        if p >= 94.0: return 'DEGRADED_BUT_USABLE'
        return 'UNRELIABLE'

    def compact(self) -> str:
        return ('BRTI_HEALTH | samples=%d | fresh=%.1f%% | retry_recovered=%d | '
                'errors=%d (%.1f%%) | status=%s') % (
                    self.samples, self.fresh_pct, self.retry_recovered,
                    self.errors, self.error_pct, self.status())


def brti_health(samples: int, fresh_ok: int, retry_recovered: int, errors: int) -> Dict[str, object]:
    h = BrtiHealth(samples, fresh_ok, retry_recovered, errors)
    return {**asdict(h), 'fresh_pct': h.fresh_pct, 'error_pct': h.error_pct, 'status': h.status()}


if __name__ == '__main__':
    # Tiny smoke test only; no external calls and no orders.
    demo = [
        Outcome('MOMENTUM_EXPANSION','MOMENTUM_PREFERRED_7_30C',0.19,0.55,-0.01,12,72,72),
        Outcome('MOMENTUM_EXPANSION','MOMENTUM_PREFERRED_7_30C',0.26,0.48,-0.02,44,44,119),
    ]
    print(decision_report(demo))
    print(BrtiHealth(1187,1143,704,44).compact())
