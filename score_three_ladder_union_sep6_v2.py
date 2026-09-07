#!/usr/bin/env python3
import csv, math
from collections import defaultdict
from datetime import datetime, timezone

UFILE="kalshi_subminute_unified_v1_1.csv"
SFILE="kalshi_scalp_shadow_events_v1.csv"

START=datetime.fromisoformat("2026-09-06T04:00:00+00:00")
END=datetime.fromisoformat("2026-09-06T18:00:00+00:00")

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

u=[]
for r in read(UFILE):
    t=parse_dt(r.get("timestamp_utc"))
    if t and START<=t<=END:
        u.append(r)

contracts=sorted({str(r.get("contract","")).strip() for r in u if str(r.get("contract","")).strip()})

# ---- FINAL production winner ----
F={}
for r in u:
    c=str(r.get("contract","")).strip()
    if not c or c in F: continue
    pf=prob(r.get("preferred_fair"))
    ml=num(r.get("minutes_left"))
    gap=num(r.get("btc_gap"))
    ratio=num(r.get("dist_over_range5"))
    ps=side(r.get("preferred_fair_side"))
    if not ps and boolish(r.get("preferred_side_match")):
        ps=side(r.get("side"))
    target=side(r.get("current_target_side"))
    need=75 if math.isfinite(ml) and ml>6 else 50
    if (math.isfinite(pf) and pf>=.90 and math.isfinite(ml) and ml<=8
        and math.isfinite(gap) and abs(gap)>=need
        and math.isfinite(ratio) and ratio>=1.0
        and ps and ps==target):
        F[c]=(parse_dt(r.get("timestamp_utc")),ml)

# ---- EARLY / TIER-1 locked rule ----
E={}
for r in u:
    c=str(r.get("contract","")).strip()
    if not c or c in E: continue

    ps=side(r.get("preferred_fair_side"))
    row_side=side(r.get("side"))
    if not ps and boolish(r.get("preferred_side_match")):
        ps=row_side
    # This CSV has side-specific rows. Only use the preferred-side row.
    if not ps or row_side!=ps:
        continue

    ask=prob(r.get("side_ask"))
    pf=prob(r.get("preferred_fair"))
    edge=num(r.get("preferred_edge"))
    if math.isfinite(edge) and abs(edge)>1.5:
        edge/=100.0
    ml=num(r.get("minutes_left"))
    gap=num(r.get("btc_gap"))

    if (math.isfinite(ask) and ask<=.45
        and math.isfinite(pf) and pf>=.75
        and math.isfinite(edge) and edge>=.08
        and math.isfinite(ml) and 2<=ml<=10
        and math.isfinite(gap) and abs(gap)>=25):
        E[c]=(parse_dt(r.get("timestamp_utc")),ml,ask)

# ---- SCALP / REVERSAL actual forward shadow events ----
S={}
scalp_signal_rows=0
try:
    srows=read(SFILE)
except FileNotFoundError:
    srows=[]

for r in srows:
    c=str(r.get("contract") or r.get("ticker") or "").strip()
    if not c or c not in contracts: continue
    t=parse_dt(r.get("entry_timestamp_utc") or r.get("timestamp_utc") or r.get("signal_timestamp_utc"))
    if t and not (START<=t<=END): continue
    scalp_signal_rows+=1
    if c not in S:
        ml=num(r.get("minutes_left"))
        if not math.isfinite(ml):
            sec=num(r.get("seconds_left"))
            ml=sec/60.0 if math.isfinite(sec) else math.nan
        S[c]=(t,ml)

f=set(F); e=set(E); s=set(S); union=f|e|s; dead=set(contracts)-union
pct=lambda a,b:100*a/b if b else 0.0

print("="*76)
print("SEP 6 — CORRECTED THREE-LADDER UNION COVERAGE")
print("="*76)
print("Observed contracts:",len(contracts))
print(f"FINAL:             {len(f)}/{len(contracts)} = {pct(len(f),len(contracts)):.1f}%")
print(f"EARLY / TIER-1:    {len(e)}/{len(contracts)} = {pct(len(e),len(contracts)):.1f}%")
print(f"SCALP / REVERSAL:  {len(s)}/{len(contracts)} = {pct(len(s),len(contracts)):.1f}%")
print(f"Scalp signal rows: {scalp_signal_rows}")
print("-"*76)
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
    for c in sorted(dead):print(" ",c)
else:
    print(" NONE — every observed contract had >=1 ladder opportunity.")
print("="*76)
print("READ-ONLY AUDIT. NO BOT LOGIC CHANGED. NO ORDERS.")
