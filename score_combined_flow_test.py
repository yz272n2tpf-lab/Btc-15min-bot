#!/usr/bin/env python3
from __future__ import annotations
import csv, subprocess, sys
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
from pathlib import Path

LIVE=Path("kalshi_live_fair_value_shadow_log.csv")
FLOW=Path("btc_large_flow_shadow_log.csv")
OFFICIAL=Path("kalshi_official_settlement_check.csv")
REFRESH=Path("kalshi_official_settlement_validator.py")
WINDOW_HOURS=24
THRESHOLD=.80
MAX_AGE=90

def pdt(s):
    try:
        s=(s or "").strip().replace("Z","+00:00")
        d=datetime.fromisoformat(s)
        if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except: return None

def num(x):
    try: return float(str(x).strip())
    except: return None

def side(x):
    s=str(x or "").strip().upper()
    if s in ("UP","YES","Y","BUY"): return "UP"
    if s in ("DOWN","NO","N","SELL"): return "DOWN"
    return None

def pct(a,b): return 100*a/b if b else 0

def refresh():
    if REFRESH.exists():
        print("Refreshing official settlements...")
        try:
            r=subprocess.run([sys.executable,str(REFRESH)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=180)
            print("Settlement refresh:", "OK" if r.returncode==0 else "used existing file")
        except:
            print("Settlement refresh: used existing file")

def official_map():
    m={}
    with OFFICIAL.open("r",newline="",encoding="utf-8-sig",errors="replace") as f:
        for row in csv.reader(f):
            if len(row)>=4 and row[0].startswith("KXBTC15M"):
                s=side(row[3])
                if s: m[row[0].strip()]=s
    return m

def load_live():
    out=[]
    with LIVE.open("r",newline="",encoding="utf-8-sig",errors="replace") as f:
        for r in csv.DictReader(f):
            ts=pdt(r.get("timestamp_utc")); t=(r.get("ticker") or "").strip()
            fair=num(r.get("fair_preferred")); sd=side(r.get("preferred_side"))
            if ts and t and fair is not None and sd: out.append((ts,t,fair,sd))
    return sorted(out)

def load_flow():
    out=[]
    with FLOW.open("r",newline="",encoding="utf-8-sig",errors="replace") as f:
        for r in csv.DictReader(f):
            ts=pdt(r.get("timestamp_utc"))
            if ts: out.append((ts,r))
    return sorted(out,key=lambda x:x[0])

def opp_signed(sd,v):
    if v is None: return None
    return v<0 if sd=="UP" else v>0

def opp_pair(sd,up,dn):
    if up is None or dn is None: return None
    return dn>up if sd=="UP" else up>dn

def opp_side(sd,x):
    s=side(x)
    return None if s is None else s!=sd

def votes(sd,r):
    checks={
      "30s":opp_signed(sd,num(r.get("price_change_30s"))),
      "flow":opp_signed(sd,num(r.get("flow_imbalance"))),
      "book":opp_signed(sd,num(r.get("book_imbalance"))),
      "aggr":opp_pair(sd,num(r.get("aggressive_buy_notional")),num(r.get("aggressive_sell_notional"))),
      "largest":opp_side(sd,r.get("largest_trade_side")),
      "zscore":opp_pair(sd,num(r.get("buy_notional_zscore")),num(r.get("sell_notional_zscore"))),
    }
    return sum(v is True for v in checks.values()), sum(v is not None for v in checks.values()), checks

def report(rows,title):
    n=len(rows); c=sum(r["correct"] for r in rows); w=n-c
    print(f"\n=== {title} ===")
    print(f"Calls: {n} | Correct: {c} | Wrong: {w} | Baseline: {pct(c,n):.1f}%")
    for gate in (2,3,4,5):
        warn=[r for r in rows if r["available"]>=4 and r["votes"]>=gate]
        keep=[r for r in rows if r not in warn]
        caught=sum(not r["correct"] for r in warn)
        false=sum(r["correct"] for r in warn)
        kc=sum(r["correct"] for r in keep)
        print(f"{gate}+ votes | warn={len(warn)} | misses caught={caught}/{w} | winners warned={false}/{c} | kept acc={pct(kc,len(keep)):.1f}% | coverage={pct(len(keep),n):.1f}%")

def main():
    print("\n=== ONE-COMMAND COMBINED FLOW TEST ===")
    print("Research only | No bot.py changes | No orders\n")
    refresh()
    live=load_live(); flow=load_flow(); off=official_map()
    end=max(x[0] for x in live); start=end-timedelta(hours=WINDOW_HOURS)
    recent=[x for x in live if x[0]>=start]
    first={}
    for ts,t,fair,sd in recent:
        if fair>=THRESHOLD and t not in first: first[t]=(ts,fair,sd)
    ftimes=[x[0] for x in flow]
    rows=[]
    for t,(ts,fair,sd) in first.items():
        truth=off.get(t)
        if not truth: continue
        i=bisect_right(ftimes,ts)-1
        v=a=0; checks={}
        if i>=0:
            fts,fr=flow[i]
            age=(ts-fts).total_seconds()
            if 0<=age<=MAX_AGE: v,a,checks=votes(sd,fr)
        rows.append(dict(ticker=t,ts=ts,fair=fair,side=sd,truth=truth,correct=sd==truth,votes=v,available=a,checks=checks))
    rows.sort(key=lambda r:r["ts"])
    print(f"Window: last {WINDOW_HOURS}h")
    print(f"Contracts seen: {len(set(x[1] for x in recent))}")
    print(f"First >=80% calls: {len(first)}")
    print(f"Officially settled/scoreable: {len(rows)}")
    report(rows,"FULL 24H SAMPLE")
    report(rows[int(len(rows)*.60):],"CHRONOLOGICAL HOLDOUT - LAST 40%")
    print("\n=== MISSES ===")
    for r in rows:
        if not r["correct"]:
            names=",".join(k for k,v in r["checks"].items() if v is True) or "none"
            print(f"{r['ticker']} | {r['side']}->{r['truth']} | fair={r['fair']:.3f} | votes={r['votes']}/{r['available']} | opposing={names}")
    print("\nDo not install a rule unless the LAST-40% holdout improves too.")
    print("No live rule installed.")

if __name__=="__main__":
    main()
