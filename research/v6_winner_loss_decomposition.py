#!/usr/bin/env python3
"""Research-only V6 winner/loss decomposition.

Parses LEAD_V6 CANDIDATE / RESULT / CONTRACT_SUMMARY log lines from stdin or a
text file and produces a compact evidence table for V7 design.

NO ORDERS. Does not alter qualification rules or production behavior.

Usage:
    python research/v6_winner_loss_decomposition.py railway.log
    cat railway.log | python research/v6_winner_loss_decomposition.py
"""

from __future__ import annotations
import re
import sys
from collections import defaultdict
from statistics import mean

CAND = re.compile(
    r"LEAD_V6 CANDIDATE \| (?P<grade>[^|]+) \| (?P<ticker>[^|]+) \| (?P<side>UP|DOWN) \| zone (?P<zone>[^|]+) \| ask (?P<ask>[0-9.]+) \| "
    r"btc5 (?P<btc5>[+-]?[0-9.]+) \| btc15 (?P<btc15>[+-]?[0-9.]+) \| btc30 (?P<btc30>N/A|[+-]?[0-9.]+) \| "
    r"accel (?P<accel>[+-]?[0-9.]+) \| brti5 (?P<brti5>N/A|[+-]?[0-9.]+) \| brti15 (?P<brti15>N/A|[+-]?[0-9.]+) .* left (?P<left>[0-9.]+)s"
)
RES = re.compile(
    r"LEAD_V6 RESULT \| (?P<grade>[^|]+) \| (?P<ticker>[^|]+) \| (?P<side>UP|DOWN) \| zone (?P<zone>[^|]+) \| style (?P<style>[^|]+) \| "
    r"entry (?P<entry>[0-9.]+) \| max_exec_gain (?P<gain>[+-]?[0-9.]+) \| adverse (?P<adverse>[+-]?[0-9.]+) \| hit10 (?P<hit10>True|False) \| hit20 (?P<hit20>True|False) \| "
    r"to_exec\+5c (?P<t5>None|[0-9.]+) \| to_exec\+10c (?P<t10>None|[0-9.]+) \| to_exec\+20c (?P<t20>None|[0-9.]+)"
)


def f(v):
    return None if v in (None, 'N/A', 'None') else float(v)


def load_lines():
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8', errors='ignore') as fh:
            return fh.readlines()
    return sys.stdin.readlines()


def avg(rows, key):
    vals=[r[key] for r in rows if r.get(key) is not None]
    return mean(vals) if vals else None


def pct(n,d):
    return 0.0 if not d else 100.0*n/d


def fmt(v, digits=2):
    return 'N/A' if v is None else f'{v:.{digits}f}'


def main():
    candidates=[]
    results=[]
    for line in load_lines():
        m=CAND.search(line)
        if m:
            d=m.groupdict()
            d.update({
                'ask':float(d['ask']),'btc5':float(d['btc5']),'btc15':float(d['btc15']),
                'btc30':f(d['btc30']),'accel':float(d['accel']),'brti5':f(d['brti5']),
                'brti15':f(d['brti15']),'left':float(d['left'])
            })
            candidates.append(d)
            continue
        m=RES.search(line)
        if m:
            d=m.groupdict()
            d.update({
                'entry':float(d['entry']),'gain':float(d['gain']),'adverse':float(d['adverse']),
                'hit10':d['hit10']=='True','hit20':d['hit20']=='True',
                't5':f(d['t5']),'t10':f(d['t10']),'t20':f(d['t20'])
            })
            results.append(d)

    # Focus V6 only; candidate/result pairing is FIFO by ticker/side/entry.
    c6=[c for c in candidates if c['grade'].strip()=='V6_QUALIFIED']
    r6=[r for r in results if r['grade'].strip()=='V6_QUALIFIED']
    queues=defaultdict(list)
    for c in c6:
        queues[(c['ticker'],c['side'],round(c['ask'],3))].append(c)
    paired=[]
    for r in r6:
        key=(r['ticker'],r['side'],round(r['entry'],3))
        c=queues[key].pop(0) if queues[key] else {}
        paired.append({**c, **r})

    wins=[x for x in paired if x['hit10']]
    misses=[x for x in paired if not x['hit10']]
    bursts=[x for x in paired if x['style']=='BURST']
    expansions=[x for x in paired if x['style']=='EXPANSION']

    print('V6 WINNER/LOSS DECOMPOSITION')
    print(f'scored={len(paired)} hit10={pct(len(wins),len(paired)):.1f}% misses={len(misses)}')
    print(f'burst={len(bursts)} expansion={len(expansions)} no_expansion={sum(x["style"]=="NO_EXPANSION" for x in paired)}')

    for label, rows in [('WIN +10c',wins),('MISS <10c',misses)]:
        print('\n'+label)
        print('n=%d entry=%s left_s=%s btc5=%s btc15=%s btc30=%s accel=%s brti5=%s brti15=%s gain=%s adverse=%s' % (
            len(rows),fmt(avg(rows,'entry'),3),fmt(avg(rows,'left'),0),fmt(avg(rows,'btc5')),fmt(avg(rows,'btc15')),
            fmt(avg(rows,'btc30')),fmt(avg(rows,'accel')),fmt(avg(rows,'brti5')),fmt(avg(rows,'brti15')),
            fmt(avg(rows,'gain'),3),fmt(avg(rows,'adverse'),3)))

    print('\nENTRY ZONES')
    bands=[('7-15c',.07,.15),('15-25c',.15,.25),('25-30c',.25,.30),('31-45c',.30,.451)]
    for name,lo,hi in bands:
        rows=[x for x in paired if lo <= x['entry'] < hi]
        print(f'{name}: n={len(rows)} hit10={pct(sum(x["hit10"] for x in rows),len(rows)):.1f}% avgGain={fmt(avg(rows,"gain"),3)} avgAdv={fmt(avg(rows,"adverse"),3)}')

    print('\nTIME-LEFT BANDS')
    tbands=[('>10m',600,10**9),('7-10m',420,600),('4-7m',240,420),('<4m',0,240)]
    for name,lo,hi in tbands:
        rows=[x for x in paired if x.get('left') is not None and lo <= x['left'] < hi]
        print(f'{name}: n={len(rows)} hit10={pct(sum(x["hit10"] for x in rows),len(rows)):.1f}% avgGain={fmt(avg(rows,"gain"),3)} avgAdv={fmt(avg(rows,"adverse"),3)}')

    print('\nFAILURE FLAGS')
    if misses:
        print(f'miss avg adverse={fmt(avg(misses,"adverse"),3)} vs win avg adverse={fmt(avg(wins,"adverse"),3)}')
        low_acc=[x for x in misses if x.get('accel') is not None and x['accel'] < 10]
        weak_brti=[x for x in misses if x.get('brti5') is not None and x['brti5'] < 15]
        late=[x for x in misses if x.get('left') is not None and x['left'] < 240]
        print(f'misses accel<10={len(low_acc)}/{len(misses)} brti5<15={len(weak_brti)}/{len(misses)} left<4m={len(late)}/{len(misses)}')

    # V5 rejected ultra-cheap candidates are proxies for the sub-7c reversal audit.
    cheap=[c for c in candidates if c['grade'].strip()=='V5_BASELINE' and c['ask'] < .07]
    print('\nSUB-7C AUDIT INPUT')
    print(f'v5_baseline_candidates_below_7c={len(cheap)}')
    if cheap:
        print('These need outcome pairing/replay before any V7 ultra-cheap reversal rule is enabled.')

    print('\nV7 RULE: no threshold changes from this script; use it to identify repeatable separation first.')

if __name__=='__main__':
    main()
