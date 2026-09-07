#!/usr/bin/env python3
import csv, math
from collections import defaultdict
from datetime import datetime, timezone

UFILE="kalshi_subminute_unified_v1_1.csv"
SFILE="kalshi_true_scalp_forward_shadow_v1.csv"
BASE_SCALP_ROWS=17

def num(x):
    try:return float(str(x).strip())
    except:return math.nan

def parse_dt(x):
    try:
        d=datetime.fromisoformat(str(x).strip().replace("Z","+00:00"))
        if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except:return None

def side(x):
    s=str(x or "").strip().upper()
    if s in {"UP","YES","Y","HIGHER","ABOVE","TRUE","1"}: return "UP"
    if s in {"DOWN","NO","N","LOWER","BELOW","FALSE","0"}: return "DOWN"
    return ""

def prob(x):
    v=num(x)
    if math.isfinite(v) and v>1.5:v/=100.0
    return v

def boolish(x):
    return str(x or "").strip().lower() in {"1","true","yes","y"}

def read(path):
    with open(path,newline="",encoding="utf-8-sig",errors="ignore") as f:
        return list(csv.DictReader(f))

# Exact fresh scalp block used by the V4.13 scorecard.
all_scalp=read(SFILE)
fresh_scalp=all_scalp[BASE_SCALP_ROWS:]
if not fresh_scalp:
    raise SystemExit("No fresh scalp rows after baseline 17.")

scalp_times=[parse_dt(r.get("signal_timestamp_utc")) for r in fresh_scalp]
scalp_times=[t for t in scalp_times if t is not None]
if not scalp_times:
    raise SystemExit("No usable signal_timestamp_utc values in fresh scalp block.")

START=min(scalp_times)
END=max(scalp_times)

# Align unified data to the exact scalp window.
u=[]
for r in read(UFILE):
    t=parse_dt(r.get("timestamp_utc"))
    if t and START<=t<=END:
        u.append(r)

contracts=sorted({str(r.get("contract","")).strip() for r in u if str(r.get("contract","")).strip()})

# FINAL
F={}
for r in u:
    c=str(r.get("contract","")).strip()
    if not c or c in F: continue
    pf=prob(r.get("preferred_fair")); ml=num(r.get("minutes_left")); gap=num(r.get("btc_gap"))
    ratio=num(r.get("dist_over_range5")); ps=side(r.get("preferred_fair_side"))
    if not ps and boolish(r.get("preferred_side_match")): ps=side(r.get("side"))
    target=side(r.get("current_target_side")); need=75 if math.isfinite(ml) and ml>6 else 50
    if (math.isfinite(pf) and pf>=.90 and math.isfinite(ml) and ml<=8
        and math.isfinite(gap) and abs(gap)>=need
        and math.isfinite(ratio) and ratio>=1.0
        and ps and ps==target):
        F[c]=(parse_dt(r.get("timestamp_utc")),ml)

# EARLY / TIER-1
E={}
for r in u:
    c=str(r.get("contract","")).strip()
    if not c or c in E: continue
    ps=side(r.get("preferred_fair_side")); row_side=side(r.get("side"))
    if not ps and boolish(r.get("preferred_side_match")): ps=row_side
    if not ps or row_side!=ps: continue
    ask=prob(r.get("side_ask")); pf=prob(r.get("preferred_fair"))
    edge=num(r.get("preferred_edge"))
    if math.isfinite(edge) and abs(edge)>1.5: edge/=100.0
    ml=num(r.get("minutes_left")); gap=num(r.get("btc_gap"))
    if (math.isfinite(ask) and ask<=.45
        and math.isfinite(pf) and pf>=.75
        and math.isfinite(edge) and edge>=.08
        and math.isfinite(ml) and 2<=ml<=10
        and math.isfinite(gap) and abs(gap)>=25):
        E[c]=(parse_dt(r.get("timestamp_utc")),ml,ask)

# SCALP / REVERSAL: exact fresh block, intersected to same aligned unified cohort.
S={}
for r in fresh_scalp:
    c=str(r.get("contract") or r.get("ticker") or "").strip()
    if not c or c not in contracts: continue
    t=parse_dt(r.get("signal_timestamp_utc"))
    if c not in S:
        ml=num(r.get("minutes_left"))
        if not math.isfinite(ml):
            sec=num(r.get("seconds_left"))
            ml=sec/60.0 if math.isfinite(sec) else math.nan
        S[c]=(t,ml)

f,e,s=set(F),set(E),set(S)
union=f|e|s
dead=set(contracts)-union
pct=lambda a,b:100*a/b if b else 0.0
fresh_contracts={str(r.get("contract") or r.get("ticker") or "").strip()
                 for r in fresh_scalp if str(r.get("contract") or r.get("ticker") or "").strip()}

print("="*78)
print("ALIGNED THREE-LADDER UNION TEST")
print("="*78)
print("Window UTC:", START.isoformat(), "->", END.isoformat())
print("Observed unified contracts:",len(contracts))
print("Fresh scalp rows:",len(fresh_scalp))
print("Fresh scalp unique contracts overall:",len(fresh_contracts))
print(f"FINAL:             {len(f)}/{len(contracts)} = {pct(len(f),len(contracts)):.1f}%")
print(f"EARLY / TIER-1:    {len(e)}/{len(contracts)} = {pct(len(e),len(contracts)):.1f}%")
print(f"SCALP / REVERSAL:  {len(s)}/{len(contracts)} = {pct(len(s),len(contracts)):.1f}%")
print("-"*78)
print(f"UNION ANY LADDER:  {len(union)}/{len(contracts)} = {pct(len(union),len(contracts)):.1f}%")
print(f"NO ACTIONABLE:     {len(dead)}/{len(contracts)} = {pct(len(dead),len(contracts)):.1f}%")
print()
print("OVERLAP")
print("FINAL + EARLY:",len(f&e))
print("FINAL + SCALP:",len(f&s))
print("EARLY + SCALP:",len(e&s))
print("ALL THREE:",len(f&e&s))
print()

first=defaultdict(int)
for c in union:
    q=[]
    for name,d in [("EARLY",E),("SCALP",S),("FINAL",F)]:
        if c in d and d[c][0] is not None:q.append((d[c][0],name))
    first[min(q)[1] if q else "UNKNOWN"]+=1

print("FIRST ACTIONABLE LADDER")
for k in ["EARLY","SCALP","FINAL","UNKNOWN"]:
    print(f"{k:10s}: {first[k]}")
print()
print("UNCOVERED CONTRACTS")
if dead:
    for c in sorted(dead): print(" ",c)
else:
    print(" NONE — every observed contract had >=1 ladder opportunity.")
print("="*78)
print("READ-ONLY TEST. NO BOT LOGIC CHANGED. NO ORDERS.")
