#!/usr/bin/env python3
import csv, math
from collections import defaultdict
from datetime import datetime, timezone
UFILE="kalshi_subminute_unified_v1_1.csv"
SFILE="kalshi_true_scalp_forward_shadow_v1.csv"
START=datetime.fromisoformat("2026-09-06T04:00:00+00:00")
END=datetime.fromisoformat("2026-09-06T18:00:00+00:00")
def n(x):
    try:return float(str(x).strip())
    except:return math.nan
def t(x):
    try:
        d=datetime.fromisoformat(str(x).strip().replace("Z","+00:00"))
        if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except:return None
def side(x):
    s=str(x or "").strip().upper()
    if s in {"UP","YES","Y","HIGHER","ABOVE","TRUE","1"}:return "UP"
    if s in {"DOWN","NO","N","LOWER","BELOW","FALSE","0"}:return "DOWN"
    return ""
def p(x):
    v=n(x)
    return v/100 if math.isfinite(v) and v>1.5 else v
def yes(x):return str(x).strip().lower() in {"1","true","yes","y"}
def rows(path):
    with open(path,newline="",encoding="utf-8-sig",errors="ignore") as f:return list(csv.DictReader(f))
u=[]
for r in rows(UFILE):
    z=t(r.get("timestamp_utc"))
    if z and START<=z<=END:u.append(r)
contracts=sorted({str(r.get("contract","")).strip() for r in u if str(r.get("contract","")).strip()})
def pref(r):
    ps=side(r.get("side")); sf=p(r.get("side_fair")); pf=p(r.get("preferred_fair"))
    return ps if yes(r.get("preferred_side_match")) or (ps and math.isfinite(sf) and math.isfinite(pf) and abs(sf-pf)<1e-9) else ""
F={};E={}
for r in u:
    c=str(r.get("contract","")).strip()
    if not c:continue
    pf=p(r.get("preferred_fair")); ml=n(r.get("minutes_left")); gap=n(r.get("btc_gap")); ps=pref(r)
    if c not in F:
        ratio=n(r.get("dist_over_range5")); target=side(r.get("current_target_side")); need=75 if math.isfinite(ml) and ml>6 else 50
        if math.isfinite(pf) and pf>=.90 and math.isfinite(ml) and ml<=8 and math.isfinite(gap) and abs(gap)>=need and math.isfinite(ratio) and ratio>=1 and ps and ps==target:
            F[c]=(t(r.get("timestamp_utc")),ml)
    if c not in E:
        ask=p(r.get("side_ask")); edge=n(r.get("edge_vs_ask"))
        if math.isfinite(edge) and abs(edge)>1.5:edge/=100
        if ps and math.isfinite(ask) and ask<=.45 and math.isfinite(pf) and pf>=.75 and math.isfinite(edge) and edge>=.08 and math.isfinite(ml) and 2<=ml<=10 and math.isfinite(gap) and abs(gap)>=25:
            E[c]=(t(r.get("timestamp_utc")),ml)
S={}
try:srows=rows(SFILE)
except FileNotFoundError:srows=[]
for r in srows:
    c=str(r.get("contract") or r.get("ticker") or "").strip()
    if not c or c not in contracts or c in S:continue
    z=t(r.get("entry_timestamp_utc") or r.get("timestamp_utc") or r.get("signal_timestamp_utc"))
    if z and not START<=z<=END:continue
    S[c]=(z,math.nan)
f=set(F);e=set(E);s=set(S);union=f|e|s;dead=set(contracts)-union
pct=lambda a,b:100*a/b if b else 0
print("="*72)
print("SEP 6 THREE-LADDER UNION COVERAGE")
print("="*72)
print("Observed contracts:",len(contracts))
print(f"FINAL:            {len(f)}/{len(contracts)} = {pct(len(f),len(contracts)):.1f}%")
print(f"EARLY / TIER-1:   {len(e)}/{len(contracts)} = {pct(len(e),len(contracts)):.1f}%")
print(f"SCALP / REVERSAL: {len(s)}/{len(contracts)} = {pct(len(s),len(contracts)):.1f}%")
print("-"*72)
print(f"UNION ANY LADDER: {len(union)}/{len(contracts)} = {pct(len(union),len(contracts)):.1f}%")
print(f"NO ACTIONABLE:    {len(dead)}/{len(contracts)} = {pct(len(dead),len(contracts)):.1f}%")
print()
print("OVERLAP | FINAL+EARLY",len(f&e),"| FINAL+SCALP",len(f&s),"| EARLY+SCALP",len(e&s),"| ALL 3",len(f&e&s))
first=defaultdict(int)
for c in union:
    q=[]
    for name,d in [("EARLY",E),("SCALP",S),("FINAL",F)]:
        if c in d and d[c][0]:q.append((d[c][0],name))
    first[min(q)[1] if q else "UNKNOWN_TIME"]+=1
print("FIRST LADDER | EARLY",first["EARLY"],"| SCALP",first["SCALP"],"| FINAL",first["FINAL"],"| UNKNOWN",first["UNKNOWN_TIME"])
print()
print("UNCOVERED CONTRACTS")
if dead:
    for c in sorted(dead):print(" ",c)
else:print(" NONE")
print("="*72)
print("READ-ONLY. NO BOT CHANGES. NO ORDERS.")
