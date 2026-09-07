#!/usr/bin/env python3
"""
ACCEPTED UNION SCORECARD V1
===========================
Fast checkpoint. NO model rebuild. NO parameter tournament.

Counts ONLY currently accepted/provisionally accepted paths:
1) Locked FINAL tournament rule
2) Locked Tier-1 ENTRY rule
3) Strong scalp candidate from union optimizer holdout

Explicitly EXCLUDES the secondary directional rule because its untouched
holdout accuracy fell to 82.4%.

Uses processed snapshot cache + historical Kalshi candle cache.
Signal-only. No orders. bot.py unchanged.
"""

from pathlib import Path
from zoneinfo import ZoneInfo
import re
import numpy as np
import pandas as pd

CACHE = Path("union_optimizer_processed_snapshot_cache.csv")
CANDLES = Path("kalshi_kxbtc15m_1m_candles_cache.csv")
OUT = Path("accepted_union_scorecard_v1_summary.txt")
DETAIL = Path("accepted_union_scorecard_v1_holdout_detail.csv")

MONTHS = {m:i+1 for i,m in enumerate(
    ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
)}

def parse_start(ticker):
    m=re.search(
        r"KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-",
        str(ticker).upper()
    )
    if not m: return pd.NaT
    yy,mon,dd,hh,mm=m.groups()
    wall=pd.Timestamp(
        year=2000+int(yy),month=MONTHS[mon],day=int(dd),
        hour=int(hh),minute=int(mm)
    )
    close=wall.tz_localize(ZoneInfo("America/New_York")).tz_convert("UTC")
    return close-pd.Timedelta(minutes=15)

def pct(n,d):
    return f"{100*n/d:.1f}%" if d else "N/A"

d=pd.read_csv(CACHE)
d["snapshot_utc"]=pd.to_datetime(d["snapshot_utc"],errors="coerce",utc=True)
numcols=[
    "elapsed","remaining","abs_dist_target","dist_over_range5",
    "preferred_ask","preferred_fair","edge",
    "preferred_side_num","current_side","final_side"
]
for c in numcols:
    d[c]=pd.to_numeric(d[c],errors="coerce")
d=d.dropna(subset=["ticker","snapshot_utc","remaining","preferred_fair"]).copy()

ticks=pd.DataFrame({"ticker":sorted(d["ticker"].unique())})
ticks["start"]=ticks["ticker"].map(parse_start)
ticks=ticks.dropna().sort_values("start").reset_index(drop=True)
mid=len(ticks)//2
valid_ticks=set(ticks.iloc[:mid]["ticker"])
hold_ticks=set(ticks.iloc[mid:]["ticker"])

cand=pd.read_csv(CANDLES)
cand["candle_end_utc"]=pd.to_datetime(
    cand["candle_end_utc"],errors="coerce",utc=True
)
for c in ["yes_ask","yes_bid","no_ask"]:
    cand[c]=pd.to_numeric(cand[c],errors="coerce")
cand["no_bid"]=1.0-cand["yes_ask"]

def tier1_contracts(frame):
    mask=(
        (frame["preferred_ask"]<=.45)
        &(frame["preferred_fair"]>=.75)
        &(frame["edge"]>=.08)
        &(frame["remaining"]>=2)
        &(frame["remaining"]<=10)
        &(frame["abs_dist_target"]>=25)
    )
    return set(frame.loc[mask,"ticker"])

def final_contracts(frame):
    # Exact V4.6 locked FINAL rule.
    required_gap=np.where(frame["remaining"]>6,75.0,50.0)
    mask=(
        (frame["remaining"]<=8)
        &(frame["preferred_fair"]>=.90)
        &(frame["abs_dist_target"]>=required_gap)
        &(frame["dist_over_range5"]>=1.0)
        &(frame["preferred_side_num"].astype(int)==frame["current_side"].astype(int))
    )
    return set(frame.loc[mask,"ticker"])

# Strong scalp candidate:
# ask <=70c, fair >=52%, edge >=0, 3-10m left, gap >=$50,
# +8c target / -10c stop / 5m horizon.
def scalp_contracts(frame):
    eligible=frame[
        (frame["preferred_ask"]<=.70)
        &(frame["preferred_fair"]>=.52)
        &(frame["edge"]>=0)
        &(frame["remaining"]>=3)
        &(frame["remaining"]<=10)
        &(frame["abs_dist_target"]>=50)
    ].sort_values(["ticker","elapsed"])

    calls=set()
    wins=set()
    grouped={k:g.sort_values("candle_end_utc") for k,g in cand.groupby("contract")}

    for ticker,g in eligible.groupby("ticker",sort=False):
        cg=grouped.get(ticker)
        if cg is None or cg.empty:
            continue
        for _,r in g.iterrows():
            side=r["preferred_side"]
            entry=float(r["preferred_ask"])
            t0=pd.Timestamp(r["snapshot_utc"])
            t1=t0+pd.Timedelta(minutes=5)
            sub=cg[
                (cg["candle_end_utc"]>t0)
                &(cg["candle_end_utc"]<=t1)
            ].sort_values("candle_end_utc")
            if sub.empty:
                continue
            bidcol="yes_bid" if side=="UP" else "no_bid"
            target=entry+.08
            stop=entry-.10
            usable=False
            win=False
            for bid in sub[bidcol].to_numpy():
                if pd.isna(bid):
                    continue
                usable=True
                b=float(bid)
                if b<=stop:
                    win=False
                    break
                if b>=target:
                    win=True
                    break
            if usable:
                # The first valid signal is an actionable call whether it wins
                # or loses. Coverage counts calls; win rate is reported separately.
                calls.add(ticker)
                if win:
                    wins.add(ticker)
                break
    return calls,wins

def score_split(name,tickset):
    frame=d[d["ticker"].isin(tickset)].copy()
    t1=tier1_contracts(frame)
    fin=final_contracts(frame)

    # To preserve independent-path accounting, evaluate scalp on all contracts
    # not already covered by Tier-1; FINAL is allowed to overlap and is unioned.
    scalp_pool=frame[~frame["ticker"].isin(t1)].copy()
    sc_calls,sc_wins=scalp_contracts(scalp_pool)

    union=t1|fin|sc_calls
    scalp_wr=(len(sc_wins)/len(sc_calls)) if sc_calls else np.nan

    print(f"\n{name}")
    print(f"Contracts: {len(tickset)}")
    print(f"Tier-1 entry: {len(t1)} ({pct(len(t1),len(tickset))})")
    print(f"Locked FINAL: {len(fin)} ({pct(len(fin),len(tickset))})")
    print(
        f"Strong scalp: {len(sc_calls)} ({pct(len(sc_calls),len(tickset))}) | "
        f"win rate {100*scalp_wr:.1f}%" if sc_calls else "Strong scalp: 0"
    )
    print(f"ACCEPTED UNION: {len(union)}/{len(tickset)} ({pct(len(union),len(tickset))})")

    return t1,fin,sc_calls,sc_wins,union


def first_rows(frame, mask):
    q=frame.loc[mask].sort_values(["ticker","elapsed","snapshot_utc"]).copy()
    if q.empty:
        return q
    return q.groupby("ticker",as_index=False).first()

def accepted_sets(tickset):
    frame=d[d["ticker"].isin(tickset)].copy()
    t1=tier1_contracts(frame)
    fin=final_contracts(frame)
    scalp_pool=frame[~frame["ticker"].isin(t1)].copy()
    sc_calls,sc_wins=scalp_contracts(scalp_pool)
    return frame,t1,fin,sc_calls,sc_wins,(t1|fin|sc_calls)

valid,vt1,vfin,vsc,vwins,vunion=accepted_sets(valid_ticks)
hold,ht1,hfin,hsc,hwins,hunion=accepted_sets(hold_ticks)

# Search only VALIDATION gaps. Holdout is report-only.
vgaps=valid[~valid["ticker"].isin(vunion)].copy()
hgaps=hold[~hold["ticker"].isin(hunion)].copy()

# Focused "Earlier Early" extension:
# Preserve Tier-1; test only 10-14m-left opportunities on still-uncovered contracts.
asks=[.40,.45,.50]
fairs=[.75,.80,.85]
edges=[.05,.08,.10]
gaps=[25,50,75]
mins=[10,11,12]
maxs=[13,14]

rows=[]
for ask in asks:
  for fair in fairs:
    for edge in edges:
      for gap in gaps:
        for mn in mins:
          for mx in maxs:
            if mn>mx: continue
            m=(
              (vgaps["preferred_ask"]<=ask)
              &(vgaps["preferred_fair"]>=fair)
              &(vgaps["edge"]>=edge)
              &(vgaps["remaining"]>=mn)
              &(vgaps["remaining"]<=mx)
              &(vgaps["abs_dist_target"]>=gap)
            )
            first=first_rows(vgaps,m)
            if first.empty: continue
            correct=(first["preferred_side_num"].astype(int)==first["final_side"].astype(int))
            rows.append({
              "ask":ask,"fair":fair,"edge":edge,"gap":gap,"min_left":mn,"max_left":mx,
              "calls":len(first),"accuracy":float(correct.mean()),
              "avg_ask":float(first["preferred_ask"].mean()),
              "avg_left":float(first["remaining"].mean())
            })

r=pd.DataFrame(rows)
print("="*78)
print("EARLY EXTENSION GAP STUDY V1 — VALIDATION SELECT / HOLDOUT REPORT")
print("="*78)
print(f"Accepted union baseline: validation {len(vunion)}/{len(valid_ticks)} | holdout {len(hunion)}/{len(hold_ticks)}")
print(f"Still uncovered: validation {len(valid_ticks)-len(vunion)} | holdout {len(hold_ticks)-len(hunion)}")
print()

if r.empty:
    print("No validation-gap Early extension candidates fired.")
    raise SystemExit(0)

# Quality first. Require >=90% validation accuracy and >=5 calls if available.
eligible=r[(r["accuracy"]>=.90)&(r["calls"]>=5)].copy()
if eligible.empty:
    eligible=r[r["calls"]>=3].copy()
    quality_note="NO candidate cleared >=90% with >=5 validation calls."
else:
    quality_note="Winner selected ONLY among >=90% accuracy / >=5-call validation candidates."

eligible=eligible.sort_values(
    ["accuracy","calls","avg_ask","avg_left"],
    ascending=[False,False,True,False]
).reset_index(drop=True)
w=eligible.iloc[0]

print("SELECTION:",quality_note)
print(
    f"Winner: ask<={100*w['ask']:.0f}c | fair>={100*w['fair']:.0f}% | edge>={100*w['edge']:.0f}% | "
    f"gap>=${w['gap']:.0f} | {w['min_left']:.0f}-{w['max_left']:.0f}m left"
)
print(
    f"VALIDATION GAPS: {int(w['calls'])} calls | accuracy {100*w['accuracy']:.1f}% | "
    f"avg ask {100*w['avg_ask']:.1f}c | avg {w['avg_left']:.2f}m left"
)

hm=(
  (hgaps["preferred_ask"]<=w["ask"])
  &(hgaps["preferred_fair"]>=w["fair"])
  &(hgaps["edge"]>=w["edge"])
  &(hgaps["remaining"]>=w["min_left"])
  &(hgaps["remaining"]<=w["max_left"])
  &(hgaps["abs_dist_target"]>=w["gap"])
)
hf=first_rows(hgaps,hm)

if hf.empty:
    print("UNTOUCHED HOLDOUT GAPS: 0 calls")
    added=set()
else:
    hc=(hf["preferred_side_num"].astype(int)==hf["final_side"].astype(int))
    added=set(hf["ticker"])
    print(
      f"UNTOUCHED HOLDOUT GAPS: {len(hf)} calls | {int(hc.sum())}/{len(hf)} correct = {100*hc.mean():.1f}% | "
      f"avg ask {100*hf['preferred_ask'].mean():.1f}c | avg {hf['remaining'].mean():.2f}m left"
    )

new_union=hunion|added
print(f"NEW HOLDOUT UNION IF ADDED: {len(new_union)}/{len(hold_ticks)} = {100*len(new_union)/len(hold_ticks):.1f}%")
print(f"Remaining uncovered: {len(hold_ticks)-len(new_union)}")
print()
print("INTEGRITY: accepted FINAL/Tier-1/Scalp unchanged; holdout not used for selection; no orders.")
print("="*78)
