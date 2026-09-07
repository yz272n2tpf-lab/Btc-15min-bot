#!/usr/bin/env python3
from __future__ import annotations
import csv, subprocess, sys
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from pathlib import Path

LIVE = Path('kalshi_live_fair_value_shadow_log.csv')
FLOW = Path('btc_large_flow_shadow_log.csv')
OFFICIAL = Path('kalshi_official_settlement_check.csv')
REFRESH = Path('kalshi_official_settlement_validator.py')
WINDOW_HOURS = 24
THRESHOLD = 0.80
FLOW_LOOKBACK_SECONDS = 90

def dtparse(s):
    s=(s or '').strip()
    if not s: return None
    try:
        if s.endswith('Z'): s=s[:-1]+'+00:00'
        d=datetime.fromisoformat(s)
        if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception: return None

def fnum(x):
    try: return float(str(x).strip())
    except Exception: return None

def side(x):
    s=str(x or '').strip().upper()
    if s in ('UP','YES','Y'): return 'UP'
    if s in ('DOWN','NO','N'): return 'DOWN'
    return None

def pct(a,b): return 100*a/b if b else 0.0

def refresh():
    if REFRESH.exists():
        print('Refreshing official settlements...')
        try:
            p=subprocess.run([sys.executable,str(REFRESH)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=180)
            print('Settlement refresh:', 'OK' if p.returncode==0 else 'used existing file')
        except Exception:
            print('Settlement refresh: used existing file')

def read_live():
    out=[]
    with LIVE.open('r',newline='',encoding='utf-8-sig',errors='replace') as f:
        for r in csv.DictReader(f):
            ts=dtparse(r.get('timestamp_utc')); ticker=(r.get('ticker') or '').strip(); fair=fnum(r.get('fair_preferred')); sd=side(r.get('preferred_side'))
            if ts and ticker and fair is not None and sd: out.append((ts,ticker,fair,sd))
    return out

def read_flow():
    out=[]
    with FLOW.open('r',newline='',encoding='utf-8-sig',errors='replace') as f:
        for r in csv.DictReader(f):
            ts=dtparse(r.get('timestamp_utc')); move=fnum(r.get('price_change_30s'))
            if ts and move is not None: out.append((ts,move))
    out.sort(); return out

def read_official():
    off={}
    with OFFICIAL.open('r',newline='',encoding='utf-8-sig',errors='replace') as f:
        for row in csv.reader(f):
            if len(row)>=4 and row[0].startswith('KXBTC15M'):
                sd=side(row[3])
                if sd: off[row[0].strip()]=sd
    return off

def main():
    print('\n=== ONE-COMMAND BTC 15M FLOW REPORT ===')
    print('Research only. No bot.py changes. No orders.\n')
    refresh()
    for p in (LIVE,FLOW,OFFICIAL):
        if not p.exists():
            print('Missing:',p); return
    live=read_live(); flow=read_flow(); official=read_official()
    if not live or not flow:
        print('Not enough usable data yet.'); return
    end=max(x[0] for x in live); start=end-timedelta(hours=WINDOW_HOURS)
    recent=[x for x in live if x[0]>=start]
    first={}
    for ts,ticker,fair,sd in sorted(recent):
        if fair>=THRESHOLD and ticker not in first: first[ticker]=(ts,fair,sd)
    scored=[]
    for ticker,(ts,fair,sd) in first.items():
        truth=official.get(ticker)
        if truth: scored.append((ticker,ts,fair,sd,truth,sd==truth))
    times=[x[0] for x in flow]; warned=[]; kept=[]
    for row in scored:
        ticker,call_ts,fair,sd,truth,correct=row; i=bisect_right(times,call_ts)-1; warning=False; move=None
        if i>=0:
            fts,move=flow[i]; age=(call_ts-fts).total_seconds()
            if 0<=age<=FLOW_LOOKBACK_SECONDS:
                warning=(sd=='UP' and move<0) or (sd=='DOWN' and move>0)
        rec=(ticker,call_ts,fair,sd,truth,correct,warning,move)
        (warned if warning else kept).append(rec)
    total=len(scored); correct=sum(r[5] for r in scored); wrong=total-correct
    caught=sum(1 for r in warned if not r[5]); false_warn=sum(1 for r in warned if r[5]); kept_correct=sum(1 for r in kept if r[5])
    print(f'Window: last {WINDOW_HOURS}h of collected data')
    print(f'Contracts seen: {len(set(x[1] for x in recent))}')
    print(f'First >=80% calls: {len(first)}')
    print(f'Officially settled/scoreable: {total}\n')
    print('BASELINE')
    print(f'Correct: {correct}')
    print(f'Wrong: {wrong}')
    print(f'Accuracy: {pct(correct,total):.1f}%\n')
    print('30-SECOND OPPOSING-MOVE WARNING')
    print(f'Misses caught: {caught}/{wrong}')
    print(f'Winners wrongly warned: {false_warn}/{correct}\n')
    print('IF WARNED CALLS WERE SKIPPED')
    print(f'Calls kept: {len(kept)}')
    print(f'Correct: {kept_correct}')
    print(f'Wrong: {len(kept)-kept_correct}')
    print(f'Accuracy: {pct(kept_correct,len(kept)):.1f}%')
    print(f'Coverage: {pct(len(kept),total):.1f}%\n')
    print('MISSES')
    for r in sorted([r for r in warned+kept if not r[5]], key=lambda x:x[1]):
        mv='n/a' if r[7] is None else f'{r[7]:+.2f}'
        print(f"{r[0]} | {r[3]}->{r[4]} | fair={r[2]:.3f} | 30s={mv} | {'WARN' if r[6] else 'NO WARN'}")

if __name__=='__main__': main()
