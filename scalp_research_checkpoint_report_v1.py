#!/usr/bin/env python3
"""One-command scalp research checkpoint report V1.

Research-only / signal-only. NO ORDERS.

Purpose
-------
Turn the growing shadow-research outputs into one compact checkpoint so we can
review V5/V6 entry quality, BRTI health, and profit-protection behavior without
manually digging through multiple logs.

This script does not alter qualification logic, thresholds, production files,
or Railway settings.
"""

from pathlib import Path
import re
from collections import Counter

ROOT = Path('.')
LOG_CANDIDATES = [
    ROOT / 'scalp_v6_live.log',
    ROOT / 'v6_live.log',
    ROOT / 'railway_v6.log',
]
PROTECTION_CANDIDATES = [
    ROOT / 'scalp_profit_protection_live.log',
    ROOT / 'scalp_protection_shadow.log',
]
BRTI_CANDIDATES = [
    ROOT / 'brti_health_shadow.log',
    ROOT / 'brti_health.log',
]


def read_first(paths):
    for p in paths:
        if p.exists():
            return p, p.read_text(encoding='utf-8', errors='ignore').splitlines()
    return None, []


def pct(a, b):
    return 0.0 if not b else 100.0 * a / b


def parse_v6(lines):
    results=[]
    rejects=Counter()
    for line in lines:
        if 'LEAD_V6 RESULT' in line:
            d={'raw':line}
            m=re.search(r'\|\s*(V5_BASELINE|V6_QUALIFIED)\s*\|', line)
            d['grade']=m.group(1) if m else 'UNKNOWN'
            m=re.search(r'style\s+(BURST|EXPANSION|NO_EXPANSION)', line)
            d['style']=m.group(1) if m else 'UNKNOWN'
            for key,pat in {
                'gain':r'max_exec_gain\s+([+-]?\d+\.\d+)',
                'adverse':r'adverse\s+([+-]?\d+\.\d+)',
                'entry':r'entry\s+(\d+\.\d+)',
            }.items():
                mm=re.search(pat,line)
                d[key]=float(mm.group(1)) if mm else None
            d['hit10']='hit10 True' in line
            d['hit20']='hit20 True' in line
            results.append(d)
        if 'rejects price=' in line:
            mm=re.search(r'rejects price=(\d+) degraded=(\d+) base=(\d+) high=(\d+)',line)
            if mm:
                rejects['price'] += int(mm.group(1)); rejects['degraded'] += int(mm.group(2))
                rejects['base'] += int(mm.group(3)); rejects['high'] += int(mm.group(4))
    return results,rejects


def summarize_grade(results, grade):
    rs=[r for r in results if r['grade']==grade]
    if not rs:
        return f'{grade}: n=0'
    n=len(rs)
    hit10=sum(r['hit10'] for r in rs)
    hit20=sum(r['hit20'] for r in rs)
    burst=sum(r['style']=='BURST' for r in rs)
    expansion=sum(r['style']=='EXPANSION' for r in rs)
    gains=[r['gain'] for r in rs if r['gain'] is not None]
    adv=[r['adverse'] for r in rs if r['adverse'] is not None]
    entries=[r['entry'] for r in rs if r['entry'] is not None]
    return (
        f'{grade}: n={n} hit10={pct(hit10,n):.1f}% hit20={pct(hit20,n):.1f}% '
        f'burst={pct(burst,n):.1f}% expansion={pct(expansion,n):.1f}% '
        f'avgEntry={(sum(entries)/len(entries)) if entries else 0:.3f} '
        f'avgGain={(sum(gains)/len(gains)) if gains else 0:+.3f} '
        f'avgAdv={(sum(adv)/len(adv)) if adv else 0:+.3f}'
    )


def parse_protection(lines):
    c=Counter()
    givebacks=[]; upside=[]
    for line in lines:
        if 'SCALP_PATH' not in line and 'PROTECTION_RESULT' not in line:
            continue
        for state in ('WATCH','TAKE_PROFIT','EXIT'):
            if state in line:
                c[state]+=1
        m=re.search(r'giveback(?:=|\s)([+-]?\d+\.\d+)',line)
        if m: givebacks.append(float(m.group(1)))
        m=re.search(r'upsideLeft(?:=|\s)([+-]?\d+\.\d+)',line)
        if m: upside.append(float(m.group(1)))
    return c,givebacks,upside


def parse_brti(lines):
    c=Counter()
    for line in lines:
        u=line.upper()
        if 'DEGRADED' in u: c['degraded']+=1
        if 'RECOVER' in u: c['recovered']+=1
        if 'HEALTHY' in u or 'AVAILABLE' in u: c['healthy']+=1
    return c


def main():
    vp,vlines=read_first(LOG_CANDIDATES)
    pp,plines=read_first(PROTECTION_CANDIDATES)
    bp,blines=read_first(BRTI_CANDIDATES)

    results,rejects=parse_v6(vlines)
    pc,gb,up=parse_protection(plines)
    bc=parse_brti(blines)

    print('='*92)
    print('SCALP RESEARCH CHECKPOINT V1 | RESEARCH ONLY | NO ORDERS')
    print('='*92)
    print('V6 source:', vp.name if vp else 'not found locally')
    print(summarize_grade(results,'V5_BASELINE'))
    print(summarize_grade(results,'V6_QUALIFIED'))
    total_rej=sum(rejects.values())
    if total_rej:
        print('Reject mix: price=%d degraded=%d base=%d high=%d' % (
            rejects['price'],rejects['degraded'],rejects['base'],rejects['high']))
    else:
        print('Reject mix: no local reject summary found')

    print('-'*92)
    print('Protection source:', pp.name if pp else 'not found locally')
    print('Protection cues: WATCH=%d TAKE_PROFIT=%d EXIT=%d' % (pc['WATCH'],pc['TAKE_PROFIT'],pc['EXIT']))
    if gb:
        print('Average giveback at actionable cue: %+.3f' % (sum(gb)/len(gb)))
    if up:
        print('Average upside left after actionable cue: %+.3f' % (sum(up)/len(up)))

    print('-'*92)
    print('BRTI source:', bp.name if bp else 'not found locally')
    print('BRTI events: healthy=%d degraded=%d recovered=%d' % (bc['healthy'],bc['degraded'],bc['recovered']))
    print('-'*92)
    print('Use this checkpoint to review evidence only. Do not promote V6 or tune thresholds from this script.')

if __name__ == '__main__':
    main()
