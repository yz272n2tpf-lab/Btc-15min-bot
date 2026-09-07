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
    return frame,t1,fin,sc_calls,sc_wins,(t1|fin|sc_calls)

valid,vt1,vfin,vsc,vwins,vunion=accepted_sets(valid_ticks)
hold,ht1,hfin,hsc,hwins,hunion=accepted_sets(hold_ticks)

def morph(frame, union, label):
    gaps=frame[~frame["ticker"].isin(union)].copy()
    print("="*78)
    print(label)
    print("="*78)
    print("Gap contracts:", gaps["ticker"].nunique())
    print()

    summary=[]
    for ticker,g in gaps.groupby("ticker"):
        g=g.sort_values("snapshot_utc").copy()
        if g.empty: continue

        strong75=g[g["preferred_fair"]>=.75]
        cheap45=g[g["preferred_ask"]<=.45]
        cheap50=g[g["preferred_ask"]<=.50]
        joint45=g[(g["preferred_fair"]>=.75)&(g["preferred_ask"]<=.45)]
        joint50=g[(g["preferred_fair"]>=.75)&(g["preferred_ask"]<=.50)]
        edge8=g[g["edge"]>=.08]
        gap25=g[g["abs_dist_target"]>=25]

        side_switches=(g["preferred_side_num"].astype(float).diff().abs()>0).sum()

        summary.append({
            "ticker":ticker,
            "rows":len(g),
            "peak_fair":g["preferred_fair"].max(),
            "best_ask":g["preferred_ask"].min(),
            "peak_edge":g["edge"].max(),
            "peak_gap":g["abs_dist_target"].max(),
            "strong75":len(strong75)>0,
            "cheap45":len(cheap45)>0,
            "cheap50":len(cheap50)>0,
            "joint45":len(joint45)>0,
            "joint50":len(joint50)>0,
            "edge8":len(edge8)>0,
            "gap25":len(gap25)>0,
            "side_switches":int(side_switches),
            "first75_left": strong75.iloc[0]["remaining"] if len(strong75) else float("nan"),
            "first45_left": cheap45.iloc[0]["remaining"] if len(cheap45) else float("nan"),
            "first50_left": cheap50.iloc[0]["remaining"] if len(cheap50) else float("nan"),
        })

    s=pd.DataFrame(summary)
    if s.empty:
        print("No gap rows.")
        return s

    n=len(s)
    print("EVER OCCURRED")
    print(f"fair >=75%:          {int(s.strong75.sum())}/{n}")
    print(f"ask <=45c:           {int(s.cheap45.sum())}/{n}")
    print(f"ask <=50c:           {int(s.cheap50.sum())}/{n}")
    print(f"fair>=75 & ask<=45:  {int(s.joint45.sum())}/{n}")
    print(f"fair>=75 & ask<=50:  {int(s.joint50.sum())}/{n}")
    print(f"edge >=8%:           {int(s.edge8.sum())}/{n}")
    print(f"gap >=$25:           {int(s.gap25.sum())}/{n}")
    print(f"any side switch:     {int((s.side_switches>0).sum())}/{n}")
    print()

    print("PER-CONTRACT SNAPSHOT")
    for _,r in s.iterrows():
        print(
            f"{r.ticker} | peak fair {100*r.peak_fair:.1f}% | best ask {100*r.best_ask:.0f}c "
            f"| edge {100*r.peak_edge:.1f}% | gap ${r.peak_gap:.0f} | switches {int(r.side_switches)}"
        )
    print()
    return s

sv=morph(valid,vunion,"VALIDATION GAP MORPHOLOGY")
sh=morph(hold,hunion,"UNTOUCHED HOLDOUT GAP MORPHOLOGY")

print("="*78)
print("READ-ONLY DIAGNOSTIC. NO BOT LOGIC CHANGED. NO ORDERS.")
print("="*78)

sv.to_csv("validation_gap_morphology_v1.csv",index=False)
sh.to_csv("holdout_gap_morphology_v1.csv",index=False)
