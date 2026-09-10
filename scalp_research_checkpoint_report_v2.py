#!/usr/bin/env python3
"""One-command scalp research checkpoint report V2.

Research-only / signal-only. NO ORDERS.

V2 adds regression-safe V6 scoring semantics:
- de-duplicate repeated RESULT log lines
- count +5c from to_exec+5c rather than rounded max gain
- count +10c from the explicit hit10 flag
- report +10c reached within 30 seconds
- de-duplicate cumulative reject counters by taking the max per contract
"""

from pathlib import Path
import re
from collections import Counter, defaultdict

ROOT = Path('.')
LOG_CANDIDATES = [
    ROOT / 'scalp_v6_live.log',
    ROOT / 'v6_live.log',
    ROOT / 'railway_v6.log',
]


def read_first(paths):
    for p in paths:
        if p.exists():
            return p, p.read_text(encoding='utf-8', errors='ignore').splitlines()
    return None, []


def pct(a, b):
    return 0.0 if not b else 100.0 * a / b


def _float(line, pattern):
    m = re.search(pattern, line)
    return float(m.group(1)) if m else None


def _seconds_or_none(line, label):
    m = re.search(rf'{re.escape(label)}\s+([^\s|]+)', line)
    if not m or m.group(1) == 'None':
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _result_identity(line):
    """Normalize wrapper prefixes while preserving the actual RESULT payload."""
    idx = line.find('LEAD_V6 RESULT')
    return line[idx:].strip() if idx >= 0 else line.strip()


def parse_v6(lines):
    results = []
    seen_results = set()
    rejects_by_contract = defaultdict(Counter)
    fallback_reject_max = Counter()

    for line in lines:
        if 'LEAD_V6 RESULT' in line:
            identity = _result_identity(line)
            if identity in seen_results:
                continue
            seen_results.add(identity)

            d = {'raw': line}
            m = re.search(r'\|\s*(V5_BASELINE|V6_QUALIFIED)\s*\|', line)
            d['grade'] = m.group(1) if m else 'UNKNOWN'
            m = re.search(r'style\s+(BURST|EXPANSION|NO_EXPANSION)', line)
            d['style'] = m.group(1) if m else 'UNKNOWN'
            d['gain'] = _float(line, r'max_exec_gain\s+([+-]?\d+\.\d+)')
            d['adverse'] = _float(line, r'adverse\s+([+-]?\d+\.\d+)')
            d['entry'] = _float(line, r'entry\s+(\d+\.\d+)')
            d['hit10'] = 'hit10 True' in line
            d['hit20'] = 'hit20 True' in line
            d['to5'] = _seconds_or_none(line, 'to_exec+5c')
            d['to10'] = _seconds_or_none(line, 'to_exec+10c')
            d['hit5'] = d['to5'] is not None
            d['hit10_30s'] = d['hit10'] and d['to10'] is not None and d['to10'] <= 30.0
            results.append(d)

        if 'rejects price=' in line:
            mm = re.search(r'rejects price=(\d+) degraded=(\d+) base=(\d+) high=(\d+)', line)
            if not mm:
                continue
            vals = dict(zip(('price', 'degraded', 'base', 'high'), map(int, mm.groups())))
            cm = re.search(r'LEAD_V6\s+(?:MIDCONTRACT|CUMULATIVE|SUMMARY)\s*\|\s*([^|]+?)\s*\|', line)
            if cm:
                contract = cm.group(1).strip()
                for key, value in vals.items():
                    rejects_by_contract[contract][key] = max(rejects_by_contract[contract][key], value)
            else:
                for key, value in vals.items():
                    fallback_reject_max[key] = max(fallback_reject_max[key], value)

    rejects = Counter()
    if rejects_by_contract:
        for counts in rejects_by_contract.values():
            rejects.update(counts)
    else:
        rejects.update(fallback_reject_max)

    return results, rejects


def summarize_grade(results, grade):
    rs = [r for r in results if r['grade'] == grade]
    if not rs:
        return f'{grade}: n=0'
    n = len(rs)
    hit5 = sum(r['hit5'] for r in rs)
    hit10 = sum(r['hit10'] for r in rs)
    hit20 = sum(r['hit20'] for r in rs)
    hit10_30 = sum(r['hit10_30s'] for r in rs)
    burst = sum(r['style'] == 'BURST' for r in rs)
    expansion = sum(r['style'] == 'EXPANSION' for r in rs)
    gains = [r['gain'] for r in rs if r['gain'] is not None]
    adv = [r['adverse'] for r in rs if r['adverse'] is not None]
    entries = [r['entry'] for r in rs if r['entry'] is not None]
    return (
        f'{grade}: n={n} hit5={pct(hit5,n):.1f}% hit10={pct(hit10,n):.1f}% '
        f'hit10_30s={pct(hit10_30,n):.1f}% hit20={pct(hit20,n):.1f}% '
        f'burst={pct(burst,n):.1f}% expansion={pct(expansion,n):.1f}% '
        f'avgEntry={(sum(entries)/len(entries)) if entries else 0:.3f} '
        f'avgGain={(sum(gains)/len(gains)) if gains else 0:+.3f} '
        f'avgAdv={(sum(adv)/len(adv)) if adv else 0:+.3f}'
    )


def main():
    vp, vlines = read_first(LOG_CANDIDATES)
    results, rejects = parse_v6(vlines)

    print('=' * 92)
    print('SCALP RESEARCH CHECKPOINT V2 | RESEARCH ONLY | NO ORDERS')
    print('=' * 92)
    print('V6 source:', vp.name if vp else 'not found locally')
    print(summarize_grade(results, 'V5_BASELINE'))
    print(summarize_grade(results, 'V6_QUALIFIED'))
    total_rej = sum(rejects.values())
    if total_rej:
        print('Reject mix (deduped cumulative maxima): price=%d degraded=%d base=%d high=%d' % (
            rejects['price'], rejects['degraded'], rejects['base'], rejects['high']))
    else:
        print('Reject mix: no local reject summary found')
    print('-' * 92)
    print('Evidence only. Do not promote V6 or tune frozen qualification thresholds from this script.')


if __name__ == '__main__':
    main()
