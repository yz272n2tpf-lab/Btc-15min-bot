#!/usr/bin/env python3
"""Parse Railway-exported scalp shadow logs and score BROAD/V3/V4 results. Research-only."""
import re,sys,statistics as st
from collections import defaultdict

PAT=re.compile(r"LEAD_V4 RESULT \| (?P<grade>[^|]+) \| (?P<contract>[^|]+) \| (?P<side>UP|DOWN) \| entry (?P<entry>-?\d+(?:\.\d+)?) \| max_exec_gain (?P<gain>[+-]?\d+(?:\.\d+)?) \| adverse (?P<adv>[+-]?\d+(?:\.\d+)?) \| hit10 (?P<hit10>True|False) \| to_exec\+5c (?P<t5>None|\d+(?:\.\d+)?) \| to_exec\+10c (?P<t10>None|\d+(?:\.\d+)?) \| kalshi_reprice\+5c (?P<kr>None|\d+(?:\.\d+)?)")

def f(v): return None if v=='None' else float(v)

def med(xs): return None if not xs else st.median(xs)
def pct(xs,p):
    if not xs:return None
    s=sorted(xs); i=(len(s)-1)*p; lo=int(i); hi=min(lo+1,len(s)-1); w=i-lo
    return s[lo]*(1-w)+s[hi]*w

def score(rows):
    n=len(rows); contracts=len(set(r['contract'] for r in rows))
    entries=[r['entry'] for r in rows]; gains=[r['gain'] for r in rows]; adv=[abs(min(0,r['adv'])) for r in rows]
    hit5=[r for r in rows if r['t5'] is not None]; hit10=[r for r in rows if r['hit10']]
    t5=[r['t5'] for r in hit5]; t10=[r['t10'] for r in hit10 if r['t10'] is not None]; kr=[r['kr'] for r in rows if r['kr'] is not None]
    lead=[r for r in hit5 if r['kr'] is not None and r['t5'] is not None and r['t5']<=r['kr']]
    return {
      'n':n,'contracts':contracts,'hit5':len(hit5)/n if n else 0,'hit10':len(hit10)/n if n else 0,
      'entry_med':med(entries),'gain_med':med(gains),'adv_med':med(adv),'adv_p90':pct(adv,.9),
      't5_med':med(t5),'t10_med':med(t10),'kr_med':med(kr),
      'lead_share':len(lead)/len(hit5) if hit5 else 0,
    }

def fmt(x): return 'NA' if x is None else f'{x:.3f}'

def main(path):
    groups=defaultdict(list)
    with open(path,'r',errors='ignore') as fh:
        for line in fh:
            m=PAT.search(line)
            if not m:continue
            d=m.groupdict(); d.update(entry=float(d['entry']),gain=float(d['gain']),adv=float(d['adv']),hit10=d['hit10']=='True',t5=f(d['t5']),t10=f(d['t10']),kr=f(d['kr']))
            groups[(d['grade'],d['side'])].append(d); groups[(d['grade'],'ALL')].append(d)
    for key in sorted(groups):
        s=score(groups[key]); print(f"{key[0]:13s} {key[1]:4s} n={s['n']:3d} contracts={s['contracts']:2d} hit5={s['hit5']:.1%} hit10={s['hit10']:.1%} entry_med={fmt(s['entry_med'])} adv_med={fmt(s['adv_med'])} adv_p90={fmt(s['adv_p90'])} gain_med={fmt(s['gain_med'])} t5_med={fmt(s['t5_med'])} t10_med={fmt(s['t10_med'])} lead_share={s['lead_share']:.1%}")

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: python score_scalp_shadow_logs_v1.py railway_logs.txt')
    main(sys.argv[1])
