#!/usr/bin/env python3
"""Research-only regime performance aggregator for V6 scalp work.

Purpose
-------
Aggregate completed scalp observations by market regime so we can compare
TREND / VOLATILE / CHOP / QUIET performance without changing V6 qualification.

Signal-only. NO ORDERS. Production untouched.

Expected CSV columns (minimum):
regime,grade,entry,max_gain,adverse,t5,t10,t20,style

The script is intentionally tolerant of missing optional fields and is designed
for checkpoint/replay analysis rather than live strategy changes.
"""

from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path


def fnum(v):
    try:
        return float(v)
    except Exception:
        return math.nan


def truthy_time(v):
    x = fnum(v)
    return math.isfinite(x)


def new_bucket():
    return {
        'n': 0,
        'entry_sum': 0.0,
        'gain_sum': 0.0,
        'adverse_sum': 0.0,
        'hit5': 0,
        'hit10': 0,
        'hit20': 0,
        'burst': 0,
        'expansion': 0,
        'no_expansion': 0,
    }


def add(bucket, row):
    bucket['n'] += 1
    entry = fnum(row.get('entry'))
    gain = fnum(row.get('max_gain'))
    adverse = fnum(row.get('adverse'))
    if math.isfinite(entry): bucket['entry_sum'] += entry
    if math.isfinite(gain): bucket['gain_sum'] += gain
    if math.isfinite(adverse): bucket['adverse_sum'] += adverse
    if truthy_time(row.get('t5')) or (math.isfinite(gain) and gain >= 0.05): bucket['hit5'] += 1
    if truthy_time(row.get('t10')) or (math.isfinite(gain) and gain >= 0.10): bucket['hit10'] += 1
    if truthy_time(row.get('t20')) or (math.isfinite(gain) and gain >= 0.20): bucket['hit20'] += 1
    style = str(row.get('style', '')).strip().upper()
    if style == 'BURST': bucket['burst'] += 1
    elif style == 'EXPANSION': bucket['expansion'] += 1
    else: bucket['no_expansion'] += 1


def pct(x, n):
    return 0.0 if not n else 100.0 * x / n


def fmt(name, b):
    n = b['n']
    if not n:
        return f'{name}: n=0'
    return (
        f'{name}: n={n} | hit5={pct(b["hit5"],n):.1f}% | '
        f'hit10={pct(b["hit10"],n):.1f}% | hit20={pct(b["hit20"],n):.1f}% | '
        f'burst={pct(b["burst"],n):.1f}% | expansion={pct(b["expansion"],n):.1f}% | '
        f'avgEntry={b["entry_sum"]/n:.3f} | avgGain={b["gain_sum"]/n:+.3f} | '
        f'avgAdverse={b["adverse_sum"]/n:+.3f}'
    )


def main(path: str) -> int:
    p = Path(path)
    if not p.exists():
        print(f'REGIME_REPORT | missing file: {p}')
        return 2

    by_regime = defaultdict(new_bucket)
    by_regime_grade = defaultdict(new_bucket)
    total = new_bucket()

    with p.open(newline='', encoding='utf-8-sig', errors='ignore') as f:
        for row in csv.DictReader(f):
            regime = str(row.get('regime', 'UNKNOWN')).strip().upper() or 'UNKNOWN'
            grade = str(row.get('grade', 'UNKNOWN')).strip().upper() or 'UNKNOWN'
            add(total, row)
            add(by_regime[regime], row)
            add(by_regime_grade[(regime, grade)], row)

    print('SCALP REGIME PERFORMANCE REPORT | RESEARCH ONLY')
    print(fmt('ALL', total))
    for regime in ('TREND', 'VOLATILE', 'CHOP', 'QUIET', 'UNKNOWN'):
        if regime in by_regime:
            print(fmt(regime, by_regime[regime]))
            grades = sorted(g for (r, g) in by_regime_grade if r == regime)
            for grade in grades:
                print('  ' + fmt(f'{regime}/{grade}', by_regime_grade[(regime, grade)]))

    if total['n']:
        ranked = sorted(by_regime.items(), key=lambda kv: (
            pct(kv[1]['hit10'], kv[1]['n']),
            kv[1]['gain_sum'] / kv[1]['n'] if kv[1]['n'] else -999,
        ), reverse=True)
        print('REGIME_RANK_BY_HIT10 | ' + ' > '.join(
            f'{name}({pct(b["hit10"],b["n"]):.1f}%,n={b["n"]})' for name,b in ranked
        ))

    return 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python scalp_regime_performance_report_v1.py <completed_scalps.csv>')
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
