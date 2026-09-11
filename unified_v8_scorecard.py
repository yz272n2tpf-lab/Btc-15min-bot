#!/usr/bin/env python3
"""Offline analyzer for Unified V8 Railway logs.

Safe/non-invasive: reads exported/pasted logs only. It never imports the live
collector, never calls Kalshi/BRTI, and never places orders.

Usage:
  python unified_v8_scorecard.py railway.log
  cat railway.log | python unified_v8_scorecard.py -
"""
from __future__ import annotations
import re, sys, statistics

RESULT = re.compile(
    r"UNIFIED_V8 RESULT \| (?P<ticker>[^|]+) \| (?P<side>UP|DOWN) \| zone (?P<zone>[^|]+) \| style (?P<style>[^|]+) \| entry (?P<entry>[0-9.]+) \| max_gain (?P<gain>[+-][0-9.]+) \| adverse (?P<adv>[+-][0-9.]+) \| to\+5c (?P<t5>[^|]+) \| to\+10c (?P<t10>[^|]+) \| to\+20c (?P<t20>[^|\n]+)"
)
BRTI = re.compile(r"BRTI_RESILIENCE \| samples=(?P<samples>\d+) \| primary_ok=(?P<ok>\d+) \((?P<pct>[0-9.]+)%\).*?errors=(?P<errors>\d+).*?http=(?P<http>\d+)")
ZONES = ["UNIFIED_ULTRA_3_7C","UNIFIED_CHEAP_7_15C","UNIFIED_VALUE_15_30C","UNIFIED_HIGH_30_45C"]

def num(v):
    v=v.strip()
    return None if v in {"None","N/A"} else float(v)

def p(v): return f"{100*v:.1f}%"
def cents(v): return f"{100*v:+.1f}c"
def med(xs): return statistics.median(xs) if xs else None

def decision(rows):
    n=len(rows)
    if n < 8:
        return "MORE_DATA", "fewer than 8 completed signals"
    h5=sum(r['t5'] is not None for r in rows)/n
    h10=sum(r['t10'] is not None for r in rows)/n
    adv=[r['adv'] for r in rows]
    bad=sum(a <= -0.15 for a in adv)/n
    avg_adv=sum(adv)/n
    if h5 >= .85 and h10 >= .70 and bad <= .10 and avg_adv >= -.08:
        return "FREEZE_CANDIDATE", "strong expansion precision with controlled adverse movement"
    if h5 >= .70 and h10 >= .50 and bad <= .20:
        return "TIGHTEN", "edge present, but quality/adverse control still needs tightening"
    return "REJECT_OR_REWORK", "forward results do not yet justify graduation"

def summarize(rows):
    n=len(rows)
    if not n:return None
    hit5=sum(r['t5'] is not None for r in rows)
    hit10=sum(r['t10'] is not None for r in rows)
    hit20=sum(r['t20'] is not None for r in rows)
    burst=sum(r['t10'] is not None and r['t10']<=30 for r in rows)
    expand=sum(r['t10'] is not None and r['t10']<=120 for r in rows)
    return {
        'n':n,'hit5':hit5/n,'hit10':hit10/n,'hit20':hit20/n,
        'burst10':burst/n,'expand10':expand/n,
        'avg_gain':sum(r['gain'] for r in rows)/n,
        'avg_adv':sum(r['adv'] for r in rows)/n,
        'median_entry':med([r['entry'] for r in rows]),
        'median_t10':med([r['t10'] for r in rows if r['t10'] is not None]),
        'bad15':sum(r['adv']<=-.15 for r in rows)/n,
    }

def show(label, rows):
    s=summarize(rows)
    if not s:
        print(f"{label}: n=0")
        return
    med_t10='N/A' if s['median_t10'] is None else f"{s['median_t10']:.1f}s"
    print(
        f"{label}: n={s['n']} | +5c {p(s['hit5'])} | +10c {p(s['hit10'])} | +20c {p(s['hit20'])} | "
        f"<=30s +10c {p(s['burst10'])} | <=120s +10c {p(s['expand10'])} | avgGain {cents(s['avg_gain'])} | "
        f"avgAdv {cents(s['avg_adv'])} | badAdv<=-15c {p(s['bad15'])} | medianEntry {100*s['median_entry']:.1f}c | medianTo+10c {med_t10}"
    )

def main():
    src=sys.stdin.read() if len(sys.argv)<2 or sys.argv[1]=='-' else open(sys.argv[1],encoding='utf-8').read()
    rows=[]
    for m in RESULT.finditer(src):
        d=m.groupdict(); rows.append({
            'ticker':d['ticker'].strip(),'side':d['side'],'zone':d['zone'].strip(),'style':d['style'].strip(),
            'entry':float(d['entry']),'gain':float(d['gain']),'adv':float(d['adv']),
            't5':num(d['t5']),'t10':num(d['t10']),'t20':num(d['t20'])
        })
    print("UNIFIED V8 FORWARD SCORECARD")
    print("="*72)
    show("ALL", rows)
    for z in ZONES: show(z, [r for r in rows if r['zone']==z])
    show("UP", [r for r in rows if r['side']=='UP'])
    show("DOWN", [r for r in rows if r['side']=='DOWN'])
    bursts=[r for r in rows if r['t10'] is not None and r['t10']<=30]
    slow=[r for r in rows if r['t10'] is not None and 30<r['t10']<=180]
    show("BURST <=30s", bursts); show("EXPANSION 30-180s", slow)
    if rows:
        worst=sorted(rows,key=lambda r:r['adv'])[:5]
        print("\nWORST ADVERSE MOVES")
        for r in worst:
            print(f"{r['ticker']} {r['side']} {r['zone']} entry={100*r['entry']:.1f}c gain={cents(r['gain'])} adverse={cents(r['adv'])} t10={r['t10']}")
    br=list(BRTI.finditer(src))
    if br:
        d=br[-1].groupdict(); print(f"\nBRTI LAST SNAPSHOT: samples={d['samples']} primary_ok={d['ok']} ({d['pct']}%) errors={d['errors']} http={d['http']}")
    dec,why=decision(rows)
    print(f"\nDECISION GATE: {dec} — {why}")
    if not any(r['zone']=="UNIFIED_ULTRA_3_7C" for r in rows): print("NOTE: no completed 3-7c evidence yet.")
    if not any(r['zone']=="UNIFIED_CHEAP_7_15C" for r in rows): print("NOTE: no completed 7-15c evidence yet.")

if __name__=='__main__': main()
