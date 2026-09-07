#!/usr/bin/env python3
from pathlib import Path
import csv, math
from datetime import datetime, timezone, timedelta

ROOT=Path(".")
WINDOW_HOURS=9
FILES={
"live":ROOT/"kalshi_two_output_live_log_v4_13.csv",
"unified":ROOT/"kalshi_subminute_unified_v1_1.csv",
"scalp":ROOT/"kalshi_true_scalp_forward_shadow_v1.csv",
"profit":ROOT/"kalshi_profit_protection_forward_shadow_v1.csv",
"brti":ROOT/"kalshi_direct_brti_parity_v1.csv",
"final_protect":ROOT/"kalshi_final_position_protection_shadow_v1.csv",
}

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
    if not s: return None
    for v in (s,s.replace("Z","+00:00")):
        try:
            d=datetime.fromisoformat(v)
            if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc)
        except: pass
    return None

def rows_in_window(h,rows,start,end):
    tc=find_col(h,["timestamp_utc","timestamp","entry_timestamp_utc","exit_timestamp_utc","source_timestamp_utc","time_utc"])
    if tc is None: return []
    out=[]
    for r in rows:
        if len(r)<=tc: continue
        d=parse_dt(r[tc])
        if d and start<=d<=end: out.append(r)
    return out

def contracts(h,rows):
    cc=find_col(h,["contract","ticker"])
    if cc is None:return set()
    return {r[cc].strip() for r in rows if len(r)>cc and r[cc].strip()}

def num(x):
    try:return float(x)
    except:return math.nan

def boolish(x):
    return str(x).strip().lower() in {"1","true","yes","y"}

uh,ur=read_csv(FILES["unified"])
if not uh:
    print("STOP: unified log missing/empty:",FILES["unified"].name); raise SystemExit(2)
utc=find_col(uh,["timestamp_utc","timestamp"])
udts=[parse_dt(r[utc]) for r in ur if utc is not None and len(r)>utc and parse_dt(r[utc])]
if not udts:
    print("STOP: no usable timestamps in unified log."); raise SystemExit(2)
end=max(udts); start=end-timedelta(hours=WINDOW_HOURS)

print("="*82)
print("BTC15 OVERNIGHT FINAL CONFIRMATION AUDIT V1")
print("="*82)
print("Window UTC:",start.isoformat(),"->",end.isoformat())
print()

summaries={}
for k,p in FILES.items():
    h,rows=read_csv(p)
    if not h:
        print(f"{k.upper():13s}: MISSING/EMPTY | {p.name}")
        summaries[k]={"rows":0,"contracts":0}; continue
    wr=rows_in_window(h,rows,start,end)
    cs=contracts(h,wr)
    summaries[k]={"rows":len(wr),"contracts":len(cs)}
    print(f"{k.upper():13s}: rows {len(wr):6d} | contracts {len(cs):3d} | {p.name}")
print()

uw=rows_in_window(uh,ur,start,end)
ud=sorted([parse_dt(r[utc]) for r in uw if len(r)>utc and parse_dt(r[utc])])
gaps20=[]; gaps60=[]
for a,b in zip(ud,ud[1:]):
    sec=(b-a).total_seconds()
    if sec>20:gaps20.append(sec)
    if sec>60:gaps60.append(sec)
span_hours=(ud[-1]-ud[0]).total_seconds()/3600 if len(ud)>=2 else 0
ucontracts=len(contracts(uh,uw))
print("UNIFIED LOG HEALTH")
print(f"  observed saved span: {span_hours:.2f}h")
print(f"  rows: {len(ud):,}")
print(f"  contracts: {ucontracts}")
print(f"  gaps >20s: {len(gaps20)}")
print(f"  gaps >60s: {len(gaps60)}")
if gaps20: print(f"  largest gap: {max(gaps20):.1f}s")
print()

bh,br=read_csv(FILES["brti"]); ready_pct=None
if bh:
    bw=rows_in_window(bh,br,start,end)
    ac=find_col(bh,["age","age_seconds","brti_age"])
    rc=find_col(bh,["ready","brti_ready"])
    ages=[num(r[ac]) for r in bw if ac is not None and len(r)>ac and math.isfinite(num(r[ac]))]
    ready=[boolish(r[rc]) for r in bw if rc is not None and len(r)>rc]
    print("DIRECT BRTI HEALTH")
    if ages: print(f"  age avg/max: {sum(ages)/len(ages):.2f}s / {max(ages):.2f}s")
    if ready:
        ready_pct=sum(ready)/len(ready)
        print(f"  ready TRUE: {sum(ready)}/{len(ready)} = {100*ready_pct:.1f}%")
    print()

for label,key in [("PRIMARY SCALP FORWARD","scalp"),("PROFIT PROTECTION","profit"),("FINAL POSITION-PROTECTION SHADOW","final_protect")]:
    h,rows=read_csv(FILES[key])
    if h:
        wr=rows_in_window(h,rows,start,end)
        print(label)
        print(f"  rows: {len(wr)}")
        print(f"  contracts: {len(contracts(h,wr))}")
        print()

brti_rows=summaries.get("brti",{}).get("rows",0)
reasons=[]; hard_fail=False
if span_hours<5: reasons.append("saved span under 5h")
if ucontracts<15: reasons.append("fewer than 15 contracts observed")
if brti_rows==0: hard_fail=True; reasons.append("no BRTI rows")
if ready_pct is not None and ready_pct<0.98:
    hard_fail=True; reasons.append(f"BRTI ready below 98% ({100*ready_pct:.1f}%)")
if len(gaps60)>5: reasons.append(f"{len(gaps60)} logging gaps >60s")

print("="*82)
if not hard_fail and span_hours>=5 and ucontracts>=15 and (ready_pct is None or ready_pct>=0.98):
    print("FINAL CONFIRMATION RESULT: PASS")
    print("Locked integrated core showed sustained overnight operation across many rollovers.")
    if reasons: print("WATCH ITEMS:", "; ".join(reasons))
    print("CORE STATUS: PRODUCTION-READY CANDIDATE")
    print("NEXT: score FINAL position-protection shadow, then begin server/storage/dashboard deployment.")
else:
    print("FINAL CONFIRMATION RESULT: REVIEW")
    print("Reasons:", "; ".join(reasons) if reasons else "insufficient evidence")
    print("Do not restart yet; inspect only flagged item(s).")
print("="*82)
