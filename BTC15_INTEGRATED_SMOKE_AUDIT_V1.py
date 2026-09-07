#!/usr/bin/env python3
from pathlib import Path
import csv, math
from datetime import datetime, timezone, timedelta

ROOT=Path(".")
FILES={
"live":ROOT/"kalshi_two_output_live_log_v4_13.csv",
"unified":ROOT/"kalshi_subminute_unified_v1_1.csv",
"scalp":ROOT/"kalshi_true_scalp_forward_shadow_v1.csv",
"profit":ROOT/"kalshi_profit_protection_forward_shadow_v1.csv",
"brti":ROOT/"kalshi_direct_brti_parity_v1.csv",
}
WINDOW=40

def read_csv(p):
    if not p.exists(): return [],[]
    with p.open(newline="",encoding="utf-8-sig",errors="ignore") as f:
        rows=list(csv.reader(f))
    return (rows[0],rows[1:]) if rows else ([],[])

def find_col(h,names):
    low=[x.lower() for x in h]
    for n in names:
        if n.lower() in low: return low.index(n.lower())
    for i,x in enumerate(low):
        for n in names:
            if n.lower() in x: return i
    return None

def parse_dt(s):
    s=str(s).strip()
    for v in (s,s.replace("Z","+00:00")):
        try:
            d=datetime.fromisoformat(v)
            if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc)
        except: pass
    return None

def recent(h,rows):
    tc=find_col(h,["timestamp_utc","timestamp","entry_timestamp_utc","exit_timestamp_utc","time_utc"])
    if tc is None: return rows,None
    ds=[parse_dt(r[tc]) for r in rows if len(r)>tc and parse_dt(r[tc])]
    if not ds: return rows,None
    latest=max(ds); cutoff=latest-timedelta(minutes=WINDOW)
    out=[r for r in rows if len(r)>tc and parse_dt(r[tc]) and parse_dt(r[tc])>=cutoff]
    return out,latest

def contracts(h,rows):
    cc=find_col(h,["contract","ticker"])
    if cc is None:return set()
    return {r[cc].strip() for r in rows if len(r)>cc and r[cc].strip()}

def num(x):
    try:return float(x)
    except:return math.nan

def boolish(x): return str(x).strip().lower() in {"1","true","yes","y"}

print("="*78)
print("BTC15 INTEGRATED SMOKE AUDIT V1")
print("="*78)
status={}
for k,p in FILES.items():
    h,rows=read_csv(p)
    if not h:
        print(f"{k.upper():8s}: MISSING/EMPTY | {p.name}")
        status[k]=False; continue
    rr,latest=recent(h,rows)
    cs=contracts(h,rr)
    print(f"{k.upper():8s}: recent rows {len(rr):5d} | contracts {len(cs):2d} | {p.name}")
    if latest: print("          latest UTC:",latest.isoformat())
    status[k]=len(rr)>0
print()

h,rows=read_csv(FILES["unified"])
if h:
    rr,_=recent(h,rows)
    tc=find_col(h,["timestamp_utc","timestamp"])
    ds=sorted([parse_dt(r[tc]) for r in rr if tc is not None and len(r)>tc and parse_dt(r[tc])])
    gaps=[(b-a).total_seconds() for a,b in zip(ds,ds[1:]) if (b-a).total_seconds()>20]
    print("UNIFIED 5s CADENCE")
    print("  recent rows:",len(ds))
    print("  gaps >20s:",len(gaps))
    if gaps: print("  largest gap:",f"{max(gaps):.1f}s")
    print()

h,rows=read_csv(FILES["brti"])
if h:
    rr,_=recent(h,rows)
    ac=find_col(h,["age","age_seconds","brti_age"])
    rc=find_col(h,["ready","brti_ready"])
    ages=[num(r[ac]) for r in rr if ac is not None and len(r)>ac and math.isfinite(num(r[ac]))]
    ready=[boolish(r[rc]) for r in rr if rc is not None and len(r)>rc]
    print("DIRECT BRTI HEALTH")
    if ages: print(f"  age avg/max: {sum(ages)/len(ages):.2f}s / {max(ages):.2f}s")
    if ready: print(f"  ready TRUE: {sum(ready)}/{len(ready)} = {100*sum(ready)/len(ready):.1f}%")
    print()

h,rows=read_csv(FILES["scalp"])
if h:
    rr,_=recent(h,rows)
    print("PRIMARY SCALP FORWARD")
    print("  recent rows/signals:",len(rr))
    print("  recent contracts:",len(contracts(h,rr)))
    print()

h,rows=read_csv(FILES["profit"])
if h:
    rr,_=recent(h,rows)
    print("PROFIT PROTECTION")
    print("  recent rows/exits:",len(rr))
    print()

rollover=False
for k in ("live","unified"):
    h,rows=read_csv(FILES[k])
    if h:
        rr,_=recent(h,rows)
        if len(contracts(h,rr))>=2: rollover=True

print("="*78)
if status.get("unified") and status.get("brti") and rollover:
    print("SMOKE RESULT: PASS")
    print("Core logging active; BRTI log active; rollover observed.")
    print("NEXT: final confirmation gate.")
elif status.get("unified") and status.get("brti"):
    print("SMOKE RESULT: PARTIAL")
    print("Core logs active, but this audit window did not prove a rollover.")
else:
    print("SMOKE RESULT: FAIL/INCOMPLETE")
    print("Inspect only the missing/inactive component shown above.")
print("="*78)
