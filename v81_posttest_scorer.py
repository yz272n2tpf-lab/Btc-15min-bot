#!/usr/bin/env python3
"""V8.1 post-test scorer. Offline/read-only. SIGNAL ONLY. NO ORDERS.

Usage:
  python v81_posttest_scorer.py railway_v81.log

Parses V81 RESULT / CONTRACT / CUMULATIVE lines from a saved Railway log and
prints lane-level hit rates, adverse movement, BRTI health, and a conservative
post-test decision. This file is intentionally isolated from the live test.
"""
from __future__ import annotations
import re, sys
from collections import defaultdict

LANES=("UNIFIED_ULTRA_3_7C","UNIFIED_CHEAP_7_15C","UNIFIED_VALUE_15_30C","UNIFIED_HIGH_30_45C")
LANE_LABELS={
    "UNIFIED_ULTRA_3_7C":"3-7c",
    "UNIFIED_CHEAP_7_15C":"7-15c",
    "UNIFIED_VALUE_15_30C":"15-30c",
    "UNIFIED_HIGH_30_45C":"30-45c",
}
RES=re.compile(r"V81 RESULT \| .*? \| (UP|DOWN) \| (UNIFIED_[A-Z0-9_]+) \| route ([A-Z0-9_]+) \| entry ([0-9.]+) \| max_gain ([+-]?[0-9.]+) \| adverse ([+-]?[0-9.]+) \| pre10 ([+-]?[0-9.]+) \| to5 (None|[0-9.]+) \| to10 (None|[0-9.]+) \| to20 (None|[0-9.]+)")
BRTI=re.compile(r"samples=(\d+).*?primary_ok=(\d+).*?missing=(\d+).*?errors=(\d+).*?timeout=(\d+).*?http=(\d+).*?connection=(\d+).*?other=(\d+)")
START="SCALP V8.1 START | LOCKED SURGICAL SUB30"
HB="V81 HEARTBEAT"

def pct(a,b): return 0.0 if not b else 100.0*a/b

def decision(lane,s):
    n=s['n']; h10=pct(s['h10'],n); h20=pct(s['h20'],n); adv=s['adv']/n if n else 0.0; gain=s['gain']/n if n else 0.0
    if lane=="UNIFIED_CHEAP_7_15C":
        return "REJECTED BY DESIGN" if n==0 else "FAIL: 7-15c should not emit in V8.1"
    if n<3: return "INSUFFICIENT SAMPLE"
    if lane=="UNIFIED_HIGH_30_45C":
        if h10>=75 and adv>=-0.06 and gain>=0.10:return "GRADUATE / PROTECT"
        if h10>=60 and adv>=-0.08:return "HOLD / MORE SAMPLE"
        return "TIGHTEN"
    if lane=="UNIFIED_VALUE_15_30C":
        if h10>=70 and adv>=-0.05 and gain>=0.10:return "GRADUATE"
        if h10>=55 and adv>=-0.07:return "HOLD / MORE SAMPLE"
        return "TIGHTEN"
    if lane=="UNIFIED_ULTRA_3_7C":
        if h10>=65 and adv>=-0.03:return "GRADUATE CAUTIOUSLY"
        if h10>=45 and adv>=-0.05:return "HOLD / MORE SAMPLE"
        return "REJECT OR TIGHTEN"
    return "REVIEW"

def main(path):
    text=open(path,'r',encoding='utf-8',errors='replace').read()
    rows=defaultdict(lambda:dict(n=0,h5=0,h10=0,h20=0,gain=0.0,adv=0.0,pre10=0.0))
    for m in RES.finditer(text):
        _,lane,route,entry,gain,adv,pre,t5,t10,t20=m.groups()
        s=rows[lane]; s['n']+=1; s['h5']+=t5!='None'; s['h10']+=t10!='None'; s['h20']+=t20!='None'; s['gain']+=float(gain); s['adv']+=float(adv); s['pre10']+=float(pre)
    brti=list(BRTI.finditer(text)); b=brti[-1].groups() if brti else None
    print("V8.1 POST-TEST REPORT")
    print("runtime_start=PASS" if START in text else "runtime_start=FAIL")
    print("heartbeat=PASS" if HB in text else "heartbeat=FAIL")
    if b:
        samples,ok,missing,errors,timeout,http,conn,other=map(int,b)
        print(f"brti samples={samples} primary_ok={ok} fresh={pct(ok,samples):.1f}% missing={missing} errors={errors} timeout={timeout} http={http} connection={conn} other={other}")
    else: print("brti=NO SUMMARY FOUND")
    print()
    for lane in LANES:
        s=rows[lane]; n=s['n']
        if n:
            print(f"{LANE_LABELS[lane]:>7} | n={n:2d} | +5c={pct(s['h5'],n):5.1f}% | +10c={pct(s['h10'],n):5.1f}% | +20c={pct(s['h20'],n):5.1f}% | avgGain={s['gain']/n:+.3f} | avgAdv={s['adv']/n:+.3f} | avgPre10={s['pre10']/n:+.3f} | {decision(lane,s)}")
        else:
            print(f"{LANE_LABELS[lane]:>7} | n= 0 | {decision(lane,s)}")
    print("\nGuardrails: scorer is advisory; no live orders, no production changes, and no graduation if runtime integrity/BRTI health failed.")

if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('usage: python v81_posttest_scorer.py <railway-log.txt>')
    main(sys.argv[1])
