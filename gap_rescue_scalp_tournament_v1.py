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
vg=valid[~valid["ticker"].isin(vunion)].copy()
hg=hold[~hold["ticker"].isin(hunion)].copy()

CANDLE_CACHE=Path("union_optimizer_1m_candle_cache.csv")
if not CANDLE_CACHE.exists():
    raise SystemExit("MISSING: union_optimizer_1m_candle_cache.csv")

cand=pd.read_csv(CANDLE_CACHE)
cand["candle_end_utc"]=pd.to_datetime(cand["candle_end_utc"],errors="coerce",utc=True)
for c in ["yes_ask","yes_bid","no_ask"]:
    cand[c]=pd.to_numeric(cand[c],errors="coerce")
cand["no_bid"]=1.0-cand["yes_ask"]
groups={k:g.sort_values("candle_end_utc") for k,g in cand.groupby("contract")}

def outcome(r,pt,sl,hz):
    cg=groups.get(str(r["ticker"]))
    if cg is None: return None
    side=str(r["preferred_side"])
    entry=float(r["preferred_ask"])
    t0=pd.Timestamp(r["snapshot_utc"])
    sub=cg[(cg["candle_end_utc"]>t0)&(cg["candle_end_utc"]<=t0+pd.Timedelta(minutes=hz))]
    if sub.empty: return None
    bidcol="yes_bid" if side=="UP" else "no_bid"
    seen=False
    for b in sub[bidcol]:
        if pd.isna(b): continue
        seen=True; b=float(b)
        if b<=entry-sl: return 0
        if b>=entry+pt: return 1
    return 0 if seen else None

def score(frame,p):
    q=frame[
      (frame["preferred_ask"]<=p["ask"])
      &(frame["preferred_fair"]>=p["fair"])
      &(frame["edge"]>=p["edge"])
      &(frame["remaining"]>=p["mn"])
      &(frame["remaining"]<=p["mx"])
      &(frame["abs_dist_target"]>=p["gap"])
    ].sort_values(["ticker","snapshot_utc"])
    rows=[]
    for t,g in q.groupby("ticker"):
        for _,r in g.iterrows():
            o=outcome(r,p["pt"],p["sl"],p["hz"])
            if o is None: continue
            rr=r.copy(); rr["win"]=o; rows.append(rr); break
    if not rows: return None,pd.DataFrame()
    c=pd.DataFrame(rows)
    return dict(**p,calls=len(c),win=float(c["win"].mean()),
                avg_ask=float(c["preferred_ask"].mean()),
                avg_left=float(c["remaining"].mean())),c

grid=[]
for ask in [.45,.50,.55,.60,.70,.80]:
 for fair in [.50,.55,.60,.65,.70,.75]:
  for edge in [0,.03,.05,.08]:
   for mn in [2,3,5,7,9]:
    for mx in [10,12,14]:
     if mn>mx: continue
     for gap in [0,25,50]:
      for pt in [.08,.10,.12,.15,.18,.20]:
       for sl in [.05,.08,.10]:
        for hz in [2,3,4,5]:
         s,_=score(vg,dict(ask=ask,fair=fair,edge=edge,mn=mn,mx=mx,gap=gap,pt=pt,sl=sl,hz=hz))
         if s: grid.append(s)

res=pd.DataFrame(grid)
print("="*78)
print("GAP RESCUE SCALP TOURNAMENT V1")
print("="*78)
print(f"Baseline: validation {len(vunion)}/{len(valid_ticks)} | holdout {len(hunion)}/{len(hold_ticks)}")
print(f"Gaps: validation {len(valid_ticks)-len(vunion)} | holdout {len(hold_ticks)-len(hunion)}")

eligible=res[(res["calls"]>=4)&(res["win"]>=.90)].copy()
if eligible.empty:
    print("NO RULE cleared >=4 validation calls and >=90% win rate.")
    raise SystemExit(0)

eligible=eligible.sort_values(["win","calls","avg_ask","avg_left"],
                              ascending=[False,False,True,False]).reset_index(drop=True)
w=eligible.iloc[0].to_dict()
sv,svc=score(vg,w)
sh,shc=score(hg,w)

print(f"VALIDATION: {sv['calls']} calls | {100*sv['win']:.1f}% | avg ask {100*sv['avg_ask']:.1f}c | avg {sv['avg_left']:.2f}m left")
print(f"RULE: ask<={100*w['ask']:.0f}c fair>={100*w['fair']:.0f}% edge>={100*w['edge']:.0f}% {w['mn']:.0f}-{w['mx']:.0f}m gap>=${w['gap']:.0f} +{100*w['pt']:.0f}c/-{100*w['sl']:.0f}c {int(w['hz'])}m")
if sh is None:
    print("HOLDOUT: 0 calls")
    added=set()
else:
    print(f"HOLDOUT: {sh['calls']} calls | {100*sh['win']:.1f}% | avg ask {100*sh['avg_ask']:.1f}c | avg {sh['avg_left']:.2f}m left")
    added=set(shc["ticker"].astype(str))
print(f"NEW HOLDOUT UNION IF ADDED: {len(hunion|added)}/{len(hold_ticks)} = {100*len(hunion|added)/len(hold_ticks):.1f}%")
print("No bot logic changed. Holdout report-only. No orders.")
