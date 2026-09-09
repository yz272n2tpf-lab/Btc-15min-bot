#!/usr/bin/env python3
"""Regime-aware scorer for scalp shadow RESULT logs.

Research-only. Parses LEAD_V4 / LEAD_V5 RESULT lines from stdin or a file and
summarizes performance by version/grade, side, entry-price zone, and outcome.
No orders and no production changes.
"""
import argparse,re,statistics,sys
from collections import defaultdict

RESULT_RE=re.compile(
    r"LEAD_V(?P<ver>[45]) RESULT \| (?P<grade>[^|]+) \| (?P<ticker>[^|]+) \| (?P<side>UP|DOWN) \| "
    r"entry (?P<entry>-?\d+(?:\.\d+)?) \| max_exec_gain (?P<gain>[+-]?\d+(?:\.\d+)?) \| "
    r"adverse (?P<adverse>[+-]?\d+(?:\.\d+)?) \| hit10 (?P<hit10>True|False) \| "
    r"to_exec\+5c (?P<t5>None|-?\d+(?:\.\d+)?) \| to_exec\+10c (?P<t10>None|-?\d+(?:\.\d+)?) \| "
    r"kalshi_reprice\+5c (?P<kreprice>None|-?\d+(?:\.\d+)?)"
)

def f(v):
    return None if v == 'None' else float(v)

def zone(entry):
    if entry <= .02:return 'dead<=2c'
    if entry < .07:return '3-6c'
    if entry <= .15:return '7-15c'
    if entry <= .30:return '16-30c'
    return '31-45c+'

def med(vals):
    vals=[x for x in vals if x is not None]
    return statistics.median(vals) if vals else None

def pct(n,d):return 0.0 if not d else 100.0*n/d

def parse(lines):
    rows=[]
    for line in lines:
        m=RESULT_RE.search(line)
        if not m:continue
        g=m.groupdict(); entry=float(g['entry']); gain=float(g['gain']); adv=float(g['adverse'])
        t5,t10,kr=f(g['t5']),f(g['t10']),f(g['kreprice'])
        rows.append({
            'version':'V'+g['ver'],'grade':g['grade'].strip(),'ticker':g['ticker'].strip(),'side':g['side'],
            'entry':entry,'zone':zone(entry),'gain':gain,'adverse':adv,'hit5':t5 is not None,'hit10':g['hit10']=='True',
            't5':t5,'t10':t10,'kr':kr,
            'pre_reprice': (t5 is not None and kr is not None and t5 <= kr)
        })
    return rows

def summarize(rows,keyfn,title):
    groups=defaultdict(list)
    for r in rows:groups[keyfn(r)].append(r)
    print('\n'+title)
    print('='*len(title))
    for k in sorted(groups,key=str):
        rs=groups[k]; n=len(rs); h5=sum(r['hit5'] for r in rs); h10=sum(r['hit10'] for r in rs)
        lead=sum(r['pre_reprice'] for r in rs); lead_den=sum(r['hit5'] and r['kr'] is not None for r in rs)
        print(f"{k}: n={n} contracts={len(set(r['ticker'] for r in rs))} +5c={pct(h5,n):.1f}% +10c={pct(h10,n):.1f}% "
              f"med_entry={med([r['entry'] for r in rs]):.3f} med_gain={med([r['gain'] for r in rs]):+.3f} "
              f"med_adverse={med([r['adverse'] for r in rs]):+.3f} pre_reprice={pct(lead,lead_den):.1f}%")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('file',nargs='?',help='Railway log text file; omit to read stdin')
    a=ap.parse_args()
    lines=open(a.file,encoding='utf-8',errors='ignore') if a.file else sys.stdin
    rows=parse(lines)
    if not rows:
        print('No LEAD_V4/LEAD_V5 RESULT lines found.'); return 1
    print(f'Parsed {len(rows)} result rows across {len(set(r["ticker"] for r in rows))} contracts.')
    summarize(rows,lambda r:(r['version'],r['grade']),'BY VERSION / GRADE')
    summarize(rows,lambda r:(r['version'],r['grade'],r['side']),'BY SIDE')
    summarize(rows,lambda r:(r['version'],r['grade'],r['zone']),'BY ENTRY ZONE')
    return 0

if __name__=='__main__':raise SystemExit(main())
