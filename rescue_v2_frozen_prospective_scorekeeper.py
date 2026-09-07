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


# ============================================================
# RESCUE V2 FROZEN PROSPECTIVE SCOREKEEPER
# ============================================================
# Frozen after historical V2 selection.
# Only rows at/after this timestamp are eligible for prospective scoring.
FREEZE_UTC = pd.Timestamp("2026-09-07T15:40:39Z")

# Frozen V2 rule — DO NOT RETUNE IN THIS FILE.
ASK_MAX = .60
FAIR_MIN = .70
EDGE_MIN = .08
MIN_LEFT = 2.0
MAX_LEFT = 12.0
GAP_MIN = 15.0
RANGE_RATIO_MIN = 0.0
PRIOR_SWITCH_MIN = 1
TARGET = .08
STOP = .08
HORIZON_MIN = 3

def accepted_union(frame):
    t1=tier1_contracts(frame)
    fin=final_contracts(frame)
    scalp_pool=frame[~frame["ticker"].isin(t1)].copy()
    sc_calls,_=scalp_contracts(scalp_pool)
    return t1|fin|sc_calls

# Count prior side switches using only past/current information.
x=d.sort_values(["ticker","snapshot_utc"]).copy()
x["prior_switches"]=0
for ticker,g in x.groupby("ticker",sort=False):
    idx=g.index
    s=x.loc[idx,"preferred_side_num"].astype(int)
    x.loc[idx,"prior_switches"]=(s!=s.shift(1)).cumsum().sub(1).clip(lower=0).to_numpy()

# Prospective rows only.
x=x[x["snapshot_utc"]>=FREEZE_UTC].copy()

print("="*96)
print("RESCUE V2 — FROZEN PROSPECTIVE SCOREKEEPER")
print("="*96)
print(f"Freeze UTC: {FREEZE_UTC}")
print("Frozen rule:")
print("  ask<=60c | fair>=70% | edge>=8% | 2-12m left | gap>=$15")
print("  prior switches>=1 | +8c target / -8c stop / 3m horizon")
print()

if x.empty:
    print("NO prospective cache rows yet.")
    print("Railway can keep collecting. No production logic changed. No orders.")
    raise SystemExit(0)

# Keep only contracts not already covered by accepted ladders.
base_union=accepted_union(x)
gap=x[~x["ticker"].isin(base_union)].copy()

mask=(
    (gap["preferred_ask"]<=ASK_MAX)
    &(gap["preferred_fair"]>=FAIR_MIN)
    &(gap["edge"]>=EDGE_MIN)
    &(gap["remaining"]>=MIN_LEFT)
    &(gap["remaining"]<=MAX_LEFT)
    &(gap["abs_dist_target"]>=GAP_MIN)
    &(gap["dist_over_range5"]>=RANGE_RATIO_MIN)
    &(gap["prior_switches"]>=PRIOR_SWITCH_MIN)
)
q=gap.loc[mask].sort_values(["ticker","snapshot_utc"])

grouped={k:g.sort_values("candle_end_utc") for k,g in cand.groupby("contract")}

rows=[]
for ticker,g in q.groupby("ticker",sort=False):
    cg=grouped.get(str(ticker))
    if cg is None or cg.empty:
        continue

    # First frozen-rule call only per contract.
    for _,r in g.iterrows():
        side=str(r["preferred_side"])
        entry=float(r["preferred_ask"])
        t0=pd.Timestamp(r["snapshot_utc"])
        t1=t0+pd.Timedelta(minutes=HORIZON_MIN)
        sub=cg[(cg["candle_end_utc"]>t0)&(cg["candle_end_utc"]<=t1)].copy()
        if sub.empty:
            continue

        bidcol="yes_bid" if side=="UP" else "no_bid"
        result="OPEN"
        exit_bid=np.nan
        for b in sub[bidcol].to_numpy():
            if pd.isna(b):
                continue
            b=float(b)
            if b<=entry-STOP:
                result="LOSS"
                exit_bid=b
                break
            if b>=entry+TARGET:
                result="WIN"
                exit_bid=b
                break

        # If horizon is fully observable and neither target nor stop hit, score as miss.
        horizon_complete = sub["candle_end_utc"].max() >= (t1-pd.Timedelta(seconds=5))
        if result=="OPEN" and horizon_complete:
            result="MISS"

        rows.append({
            "ticker":ticker,
            "signal_utc":t0,
            "side":side,
            "ask_c":round(entry*100,1),
            "fair_pct":round(float(r["preferred_fair"])*100,1),
            "edge_pct":round(float(r["edge"])*100,1),
            "minutes_left":round(float(r["remaining"]),2),
            "gap_dollars":round(float(r["abs_dist_target"]),2),
            "prior_switches":int(r["prior_switches"]),
            "result":result,
            "exit_bid_c":None if pd.isna(exit_bid) else round(exit_bid*100,1),
        })
        break

out=pd.DataFrame(rows)

if out.empty:
    print("No prospective V2 calls have fired yet.")
    print("Railway can keep collecting. Existing accepted ladders remain untouched.")
    raise SystemExit(0)

print(out.to_string(index=False))
print()

closed=out[out["result"].isin(["WIN","LOSS","MISS"])].copy()
wins=int((closed["result"]=="WIN").sum())
losses=int((closed["result"].isin(["LOSS","MISS"])).sum())

print("-"*96)
print(f"FIRED: {len(out)} | CLOSED: {len(closed)} | OPEN: {len(out)-len(closed)}")
if len(closed):
    print(f"WINS: {wins} | LOSSES/MISSES: {losses} | WIN RATE: {100*wins/len(closed):.1f}%")
else:
    print("WIN RATE: N/A — no closed prospective calls yet.")
print()
print("STATUS: SHADOW ONLY. V2 remains unpromoted.")
print("Accepted production ladders unchanged. No orders.")
print("="*96)

out.to_csv("rescue_v2_prospective_results.csv",index=False)
