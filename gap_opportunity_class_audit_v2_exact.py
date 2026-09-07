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

rules=[
    (.05,.05,2),(.08,.05,2),(.10,.05,3),(.12,.08,3),
    (.15,.08,4),(.18,.10,5),(.20,.10,5)
]

grouped={k:g.sort_values("candle_end_utc") for k,g in cand.groupby("contract")}

def temp_move_for_row(r,pt,sl,hz):
    ticker=str(r["ticker"])
    cg=grouped.get(ticker)
    if cg is None or cg.empty:
        return None
    side=str(r["preferred_side"])
    entry=float(r["preferred_ask"])
    t0=pd.Timestamp(r["snapshot_utc"])
    t1=t0+pd.Timedelta(minutes=hz)
    sub=cg[(cg["candle_end_utc"]>t0)&(cg["candle_end_utc"]<=t1)].sort_values("candle_end_utc")
    if sub.empty:
        return None
    bidcol="yes_bid" if side=="UP" else "no_bid"
    target=entry+pt
    stop=entry-sl
    usable=False
    for bid in sub[bidcol].to_numpy():
        if pd.isna(bid):
            continue
        usable=True
        b=float(bid)
        if b<=stop:
            return False
        if b>=target:
            return True
    return False if usable else None

def audit(frame,gset,label):
    print("="*78)
    print(label)
    print("="*78)
    print("Gap contracts:",len(gset))
    print()
    counts={"TEMP_MOVE":0,"DIRECTIONAL_ONLY":0,"NO_REALISTIC_MOVE":0}

    for ticker in sorted(gset):
        g=frame[frame["ticker"]==ticker].sort_values("snapshot_utc")
        best=None

        for _,r in g.iterrows():
            if not (2 <= float(r["remaining"]) <= 14):
                continue
            for pt,sl,hz in rules:
                o=temp_move_for_row(r,pt,sl,hz)
                if o is True:
                    candidate=(pt,sl,hz,float(r["preferred_ask"]),float(r["remaining"]),float(r["preferred_fair"]))
                    if best is None or candidate[0] > best[0]:
                        best=candidate

        if best is not None:
            counts["TEMP_MOVE"]+=1
            pt,sl,hz,ask,left,fair=best
            print(
                f"{ticker} | TEMP_MOVE | up to +{100*pt:.0f}c before -{100*sl:.0f}c stop "
                f"| {hz}m horizon | ask {100*ask:.0f}c | {left:.1f}m left | fair {100*fair:.0f}%"
            )
        else:
            directional=((g["preferred_side_num"].astype(int)==g["final_side"].astype(int))).any()
            if directional:
                counts["DIRECTIONAL_ONLY"]+=1
                print(f"{ticker} | DIRECTIONAL_ONLY | no tested ASK->BID temp move")
            else:
                counts["NO_REALISTIC_MOVE"]+=1
                print(f"{ticker} | NO_REALISTIC_MOVE")

    print("COUNTS:",counts)
    print()
    return counts

print("="*78)
print("GAP OPPORTUNITY-CLASS AUDIT V2 — EXACT ACCEPTED BASELINE")
print("="*78)
print(f"Accepted baseline: validation {len(vunion)}/{len(valid_ticks)} | holdout {len(hunion)}/{len(hold_ticks)}")
print(f"Baseline uncovered: validation {len(valid_ticks)-len(vunion)} | holdout {len(hold_ticks)-len(hunion)}")
print()

audit(valid,set(valid_ticks)-vunion,"VALIDATION GAPS")
audit(hold,set(hold_ticks)-hunion,"UNTOUCHED HOLDOUT GAPS")

print("IMPORTANT: TEMP_MOVE = opportunity feasibility only, NOT a tradable predictor.")
print("Exact accepted FINAL/Tier-1/Scalp baseline preserved.")
print("Holdout not used for selection. No bot logic changed. No orders.")
print("="*78)
