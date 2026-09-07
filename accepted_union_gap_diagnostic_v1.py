#!/usr/bin/env python3
import pandas as pd
import numpy as np
from pathlib import Path

DETAIL=Path("accepted_union_scorecard_v1_holdout_detail.csv")
CACHE=Path("union_optimizer_processed_snapshot_cache.csv")

for p in (DETAIL,CACHE):
    if not p.exists():
        raise SystemExit(f"MISSING: {p}")

d=pd.read_csv(CACHE)
h=pd.read_csv(DETAIL)

for c in ["elapsed","remaining","abs_dist_target","dist_over_range5","preferred_ask","preferred_fair","edge"]:
    if c in d.columns:
        d[c]=pd.to_numeric(d[c],errors="coerce")
d["snapshot_utc"]=pd.to_datetime(d["snapshot_utc"],errors="coerce",utc=True)

for c in ["accepted_actionable","tier1_entry","locked_final","strong_scalp"]:
    if c in h.columns:
        h[c]=h[c].astype(str).str.strip().str.lower().isin(["true","1","yes","y"])

gaps=set(h.loc[~h["accepted_actionable"],"ticker"].astype(str))
x=d[d["ticker"].astype(str).isin(gaps)].copy()

print("="*78)
print("ACCEPTED-UNION GAP DIAGNOSTIC — READ ONLY")
print("="*78)
print("Uncovered contracts:",len(gaps))
print()

rows=[]
for t in sorted(gaps):
    g=x[x["ticker"].astype(str)==t].sort_values("snapshot_utc")
    if g.empty:
        rows.append(dict(ticker=t,rows=0))
        continue
    rows.append({
        "ticker":t,
        "rows":len(g),
        "peak_fair":g["preferred_fair"].max(),
        "best_ask":g["preferred_ask"].min(),
        "peak_edge":g["edge"].max(),
        "peak_gap":g["abs_dist_target"].max(),
        "peak_ratio":g["dist_over_range5"].max(),
        "first_75_left": (g.loc[g["preferred_fair"]>=.75,"remaining"].iloc[0] if (g["preferred_fair"]>=.75).any() else np.nan),
        "ask_at_75": (g.loc[g["preferred_fair"]>=.75,"preferred_ask"].iloc[0] if (g["preferred_fair"]>=.75).any() else np.nan),
    })

out=pd.DataFrame(rows)

def pct(v): return "—" if pd.isna(v) else f"{100*v:.1f}%"
def cents(v): return "—" if pd.isna(v) else f"{100*v:.1f}c"
def num(v): return "—" if pd.isna(v) else f"{v:.2f}"

for _,r in out.iterrows():
    print(r["ticker"])
    if int(r.get("rows",0))==0:
        print("  no cache rows")
        continue
    print("  peak fair",pct(r["peak_fair"]),"| best ask",cents(r["best_ask"]),"| peak edge",pct(r["peak_edge"]),"| peak gap",f"${r['peak_gap']:.0f}","| peak range ratio",num(r["peak_ratio"]))
    print("  first >=75% fair with",("—" if pd.isna(r["first_75_left"]) else f"{r['first_75_left']:.2f}m left"),"| ask then",cents(r["ask_at_75"]))

print()
print("GROUP COUNTS")
print("Reached >=75% fair:",int((out["peak_fair"]>=.75).sum()),"/",len(out))
print("Reached >=70% fair:",int((out["peak_fair"]>=.70).sum()),"/",len(out))
print("Ever ask <=45c:",int((out["best_ask"]<=.45).sum()),"/",len(out))
print("Ever gap >=$25:",int((out["peak_gap"]>=25).sum()),"/",len(out))
print("Ever gap >=$50:",int((out["peak_gap"]>=50).sum()),"/",len(out))
print("Ever range ratio >=1.0:",int((out["peak_ratio"]>=1.0).sum()),"/",len(out))
print()
print("No bot logic changed. No thresholds changed. No orders.")
print("="*78)
out.to_csv("accepted_union_gap_diagnostic_v1.csv",index=False)
