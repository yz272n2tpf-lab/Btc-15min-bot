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


def accepted_sets(tickset):
    frame=d[d["ticker"].isin(tickset)].copy()
    t1=tier1_contracts(frame)
    fin=final_contracts(frame)
    scalp_pool=frame[~frame["ticker"].isin(t1)].copy()
    sc_calls,sc_wins=scalp_contracts(scalp_pool)
    return frame,(t1|fin|sc_calls)

valid,vunion=accepted_sets(valid_ticks)
hold,hunion=accepted_sets(hold_ticks)
vg=valid[~valid["ticker"].isin(vunion)].copy().sort_values(["ticker","snapshot_utc"]).reset_index(drop=True)
hg=hold[~hold["ticker"].isin(hunion)].copy().sort_values(["ticker","snapshot_utc"]).reset_index(drop=True)

grouped_cand={k:g.sort_values("candle_end_utc") for k,g in cand.groupby("contract")}

exit_rules=[(pt,sl,hz)
    for pt in [.08,.10,.12,.15,.18,.20]
    for sl in [.05,.08,.10]
    for hz in [2,3,4,5]
]

def future_outcome(r,pt,sl,hz):
    cg=grouped_cand.get(str(r["ticker"]))
    if cg is None or cg.empty: return np.nan
    side=str(r["preferred_side"])
    entry=float(r["preferred_ask"])
    t0=pd.Timestamp(r["snapshot_utc"])
    t1=t0+pd.Timedelta(minutes=hz)
    sub=cg[(cg["candle_end_utc"]>t0)&(cg["candle_end_utc"]<=t1)]
    if sub.empty: return np.nan
    bidcol="yes_bid" if side=="UP" else "no_bid"
    seen=False
    for b in sub[bidcol].to_numpy():
        if pd.isna(b): continue
        seen=True
        b=float(b)
        if b<=entry-sl: return 0.0
        if b>=entry+pt: return 1.0
    return 0.0 if seen else np.nan

def add_outcomes(frame):
    x=frame.copy()
    for j,(pt,sl,hz) in enumerate(exit_rules):
        x[f"_o{j}"]=[future_outcome(r,pt,sl,hz) for _,r in x.iterrows()]
    return x

print("="*78)
print("FAST GAP RESCUE SCALP TOURNAMENT V2")
print("="*78)
print(f"Accepted baseline: validation {len(vunion)}/{len(valid_ticks)} | holdout {len(hunion)}/{len(hold_ticks)}")
print(f"Baseline gaps: validation {len(valid_ticks)-len(vunion)} | holdout {len(hold_ticks)-len(hunion)}")
print("Precomputing future outcomes once on gap rows...")

vg=add_outcomes(vg)
hg=add_outcomes(hg)

entry_filters=[]
for ask in [.45,.50,.55,.60,.70,.80]:
 for fair in [.50,.55,.60,.65,.70,.75,.80]:
  for edge in [0,.03,.05,.08]:
   for mn in [2,3,5,7,9]:
    for mx in [10,12,14]:
     if mn>mx: continue
     for gap in [0,25,50]:
      entry_filters.append((ask,fair,edge,mn,mx,gap))

def first_calls(frame, mask, ocol):
    q=frame.loc[mask,["ticker","preferred_ask","remaining",ocol]].copy()
    q=q.dropna(subset=[ocol])
    if q.empty: return None
    q=q.groupby("ticker",sort=False).first().reset_index()
    if q.empty: return None
    return {
        "calls":len(q),
        "win":float(q[ocol].mean()),
        "avg_ask":float(q["preferred_ask"].mean()),
        "avg_left":float(q["remaining"].mean()),
        "tickers":set(q["ticker"].astype(str)),
    }

best=None
tested=0
for ask,fair,edge,mn,mx,gap in entry_filters:
    mask=(
        (vg["preferred_ask"]<=ask)
        &(vg["preferred_fair"]>=fair)
        &(vg["edge"]>=edge)
        &(vg["remaining"]>=mn)
        &(vg["remaining"]<=mx)
        &(vg["abs_dist_target"]>=gap)
    )
    if not mask.any(): continue
    for j,(pt,sl,hz) in enumerate(exit_rules):
        tested+=1
        s=first_calls(vg,mask,f"_o{j}")
        if s is None or s["calls"]<4 or s["win"]<.90:
            continue
        cand=(s["win"],s["calls"],-s["avg_ask"],s["avg_left"],
              ask,fair,edge,mn,mx,gap,j,s)
        if best is None or cand[:4] > best[:4]:
            best=cand

print(f"Fast combinations checked: {tested:,}")

if best is None:
    print("RESULT: No rescue-scalp rule cleared >=4 validation calls AND >=90% win rate.")
    print("No holdout selection performed. Accepted ladders unchanged. No orders.")
    raise SystemExit(0)

_,_,_,_,ask,fair,edge,mn,mx,gap,j,sv=best
pt,sl,hz=exit_rules[j]

hmask=(
    (hg["preferred_ask"]<=ask)
    &(hg["preferred_fair"]>=fair)
    &(hg["edge"]>=edge)
    &(hg["remaining"]>=mn)
    &(hg["remaining"]<=mx)
    &(hg["abs_dist_target"]>=gap)
)
sh=first_calls(hg,hmask,f"_o{j}")

print()
print(f"VALIDATION WINNER: {sv['calls']} calls | {100*sv['win']:.1f}% win | avg ask {100*sv['avg_ask']:.1f}c | avg {sv['avg_left']:.2f}m left")
print(f"RULE: ask<={100*ask:.0f}c | fair>={100*fair:.0f}% | edge>={100*edge:.0f}% | {mn}-{mx}m left | gap>=${gap} | +{100*pt:.0f}c/-{100*sl:.0f}c | {hz}m horizon")

if sh is None:
    print("UNTOUCHED HOLDOUT: 0 calls")
    added=set()
else:
    print(f"UNTOUCHED HOLDOUT: {sh['calls']} calls | {100*sh['win']:.1f}% win | avg ask {100*sh['avg_ask']:.1f}c | avg {sh['avg_left']:.2f}m left")
    added=sh["tickers"]

new_union=hunion|added
print(f"NEW HOLDOUT UNION IF ADDED: {len(new_union)}/{len(hold_ticks)} = {100*len(new_union)/len(hold_ticks):.1f}%")
print(f"Remaining uncovered: {len(hold_ticks)-len(new_union)}")
print()
print("INTEGRITY: selected on validation gaps only; untouched holdout report-only.")
print("Accepted FINAL/Tier-1/Strong Scalp unchanged. No orders.")
print("="*78)
