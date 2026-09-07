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

hold,hunion=accepted_sets(hold_ticks)
hg=hold[~hold["ticker"].isin(hunion)].copy().sort_values(["ticker","snapshot_utc"])

# Frozen rescue rule selected on validation only.
ASK=.60
FAIR=.65
EDGE=.00
MIN_LEFT=2
MAX_LEFT=12
GAP=0
PT=.08
SL=.05
HZ=2

candles={k:g.sort_values("candle_end_utc") for k,g in cand.groupby("contract")}

def outcome(r):
    cg=candles.get(str(r["ticker"]))
    if cg is None or cg.empty:
        return None
    side=str(r["preferred_side"])
    entry=float(r["preferred_ask"])
    t0=pd.Timestamp(r["snapshot_utc"])
    t1=t0+pd.Timedelta(minutes=HZ)
    sub=cg[(cg["candle_end_utc"]>t0)&(cg["candle_end_utc"]<=t1)]
    if sub.empty:
        return None
    bidcol="yes_bid" if side=="UP" else "no_bid"
    for b in sub[bidcol]:
        if pd.isna(b):
            continue
        b=float(b)
        if b<=entry-SL:
            return 0
        if b>=entry+PT:
            return 1
    return 0

mask=(
    (hg["preferred_ask"]<=ASK)
    &(hg["preferred_fair"]>=FAIR)
    &(hg["edge"]>=EDGE)
    &(hg["remaining"]>=MIN_LEFT)
    &(hg["remaining"]<=MAX_LEFT)
    &(hg["abs_dist_target"]>=GAP)
)

q=hg[mask].sort_values(["ticker","snapshot_utc"])

rows=[]
for ticker,g in q.groupby("ticker"):
    for _,r in g.iterrows():
        o=outcome(r)
        if o is None:
            continue
        rr=r.copy()
        rr["win"]=int(o)
        rows.append(rr)
        break

calls=pd.DataFrame(rows)

def prior_switches(ticker, ts):
    g=hg[(hg["ticker"]==ticker)&(hg["snapshot_utc"]<=ts)].sort_values("snapshot_utc")
    if g.empty:
        return 0
    s=g["preferred_side_num"].astype(int)
    return max(0,int((s!=s.shift(1)).sum())-1)

print("="*86)
print("RESCUE-SCALP HOLDOUT DIAGNOSTIC V2 — FIXED RULE ONLY")
print("="*86)
print(f"Accepted holdout baseline: {len(hunion)}/{len(hold_ticks)}")
print(f"Frozen rescue rule: ask<=60c | fair>=65% | 2-12m left | +8c/-5c | 2m horizon")
print()

if calls.empty:
    raise SystemExit("No frozen-rule holdout calls found.")

out=[]
for _,r in calls.iterrows():
    out.append({
        "ticker":str(r["ticker"]),
        "win":int(r["win"]),
        "ask_c":100*float(r["preferred_ask"]),
        "fair_pct":100*float(r["preferred_fair"]),
        "edge_pct":100*float(r["edge"]),
        "minutes_left":float(r["remaining"]),
        "gap_dollars":float(r["abs_dist_target"]),
        "range_ratio":float(r["dist_over_range5"]),
        "switches":prior_switches(str(r["ticker"]),pd.Timestamp(r["snapshot_utc"])),
        "side":str(r["preferred_side"]),
    })

o=pd.DataFrame(out)

for label,val in [("WINS",1),("LOSSES",0)]:
    g=o[o["win"]==val]
    print(label)
    print("-"*86)
    print(
        f"n={len(g)} | avg ask {g.ask_c.mean():.1f}c | avg fair {g.fair_pct.mean():.1f}% | "
        f"avg edge {g.edge_pct.mean():.1f}% | avg time {g.minutes_left.mean():.2f}m | "
        f"avg gap ${g.gap_dollars.mean():.0f} | avg ratio {g.range_ratio.mean():.2f} | "
        f"avg switches {g.switches.mean():.2f}"
    )
    for _,x in g.iterrows():
        print(
            f"{x.ticker} | ask {x.ask_c:.0f}c | fair {x.fair_pct:.0f}% | edge {x.edge_pct:.0f}% | "
            f"{x.minutes_left:.1f}m | gap ${x.gap_dollars:.0f} | ratio {x.range_ratio:.2f} | "
            f"switches {int(x.switches)} | {x.side}"
        )
    print()

print("DIFFERENCES (wins avg - losses avg)")
print("-"*86)
for c in ["ask_c","fair_pct","edge_pct","minutes_left","gap_dollars","range_ratio","switches"]:
    w=o.loc[o.win==1,c]
    l=o.loc[o.win==0,c]
    print(f"{c:18s}: {w.mean()-l.mean():+8.2f}")

print()
print(f"Frozen rule holdout: {int(o.win.sum())}/{len(o)} = {100*o.win.mean():.1f}%")
print("No retuning. No bot logic changed. No orders.")
print("="*86)

o.to_csv("rescue_scalp_holdout_diagnostic_v2.csv",index=False)
