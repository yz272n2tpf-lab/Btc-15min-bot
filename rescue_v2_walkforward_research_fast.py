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
# RESCUE V2 RESEARCH — WALK-FORWARD, HISTORICAL ONLY
# ============================================================
# IMPORTANT:
# - The prior historical holdout has already been inspected and is therefore
#   retired from "untouched holdout" status.
# - V2 development may use the full historical cache.
# - The already-viewed Railway Rescue-V1 sample is NEVER used to select V2.
# - V2 must later pass genuinely fresh Railway contracts before promotion.
# - Accepted production ladders are untouched.

def accepted_union(frame):
    t1=tier1_contracts(frame)
    fin=final_contracts(frame)
    scalp_pool=frame[~frame["ticker"].isin(t1)].copy()
    sc_calls,_=scalp_contracts(scalp_pool)
    return t1|fin|sc_calls

hist_union=accepted_union(d)
gap=d[~d["ticker"].isin(hist_union)].copy()
gap=gap.sort_values(["snapshot_utc","ticker"]).reset_index(drop=True)

# Count prior preferred-side changes using only information available BEFORE entry.
gap["prior_switches"]=0
for ticker,g in gap.groupby("ticker",sort=False):
    idx=g.sort_values("snapshot_utc").index
    s=gap.loc[idx,"preferred_side_num"].astype(int)
    gap.loc[idx,"prior_switches"]=(s!=s.shift(1)).cumsum().sub(1).clip(lower=0).to_numpy()

grouped_cand={k:g.sort_values("candle_end_utc") for k,g in cand.groupby("contract")}

def outcome(r,pt,sl,hz):
    cg=grouped_cand.get(str(r["ticker"]))
    if cg is None or cg.empty:
        return np.nan
    side=str(r["preferred_side"])
    entry=float(r["preferred_ask"])
    t0=pd.Timestamp(r["snapshot_utc"])
    t1=t0+pd.Timedelta(minutes=hz)
    sub=cg[(cg["candle_end_utc"]>t0)&(cg["candle_end_utc"]<=t1)]
    if sub.empty:
        return np.nan
    bidcol="yes_bid" if side=="UP" else "no_bid"
    for b in sub[bidcol].to_numpy():
        if pd.isna(b):
            continue
        b=float(b)
        if b<=entry-sl:
            return 0.0
        if b>=entry+pt:
            return 1.0
    return 0.0

# Keep the research grid intentionally small and interpretable.
# This is NOT a giant threshold hunt.
exit_rules=[
    (.08,.05,2),
    (.08,.08,3),
    (.10,.08,3),
]

ask_caps=[.45,.50,.55,.60]
fair_floors=[.65,.70,.75]
edge_floors=[.08,.12,.16,.20]
max_lefts=[6,8,10,12]
gap_floors=[0,15,25,40]
range_floors=[0,.50,1.00]
switch_floors=[0,1]

# Precompute outcome once per exit geometry for speed.
for pt,sl,hz in exit_rules:
    col=f"o_{int(pt*100)}_{int(sl*100)}_{hz}"
    gap[col]=gap.apply(lambda r: outcome(r,pt,sl,hz),axis=1)

# Chronological 4-block walk-forward on CONTRACTS.
ticks=(gap[["ticker","snapshot_utc"]]
       .groupby("ticker",as_index=False)["snapshot_utc"].min()
       .sort_values("snapshot_utc"))
tick_blocks=np.array_split(ticks["ticker"].to_numpy(),4)

def first_calls(frame,p,outcol):
    m=(
        (frame["preferred_ask"]<=p["ask"])
        &(frame["preferred_fair"]>=p["fair"])
        &(frame["edge"]>=p["edge"])
        &(frame["remaining"]>=2)
        &(frame["remaining"]<=p["mx"])
        &(frame["abs_dist_target"]>=p["gap"])
        &(frame["dist_over_range5"]>=p["rr"])
        &(frame["prior_switches"]>=p["sw"])
        &frame[outcol].notna()
    )
    q=frame.loc[m].sort_values(["ticker","snapshot_utc"])
    if q.empty:
        return q
    return q.groupby("ticker",as_index=False).first()

rows=[]
for pt,sl,hz in exit_rules:
    outcol=f"o_{int(pt*100)}_{int(sl*100)}_{hz}"
    for ask in ask_caps:
      for fair in fair_floors:
       for edge in edge_floors:
        for mx in max_lefts:
         for gf in gap_floors:
          for rr in range_floors:
           for sw in switch_floors:
            p=dict(ask=ask,fair=fair,edge=edge,mx=mx,gap=gf,rr=rr,sw=sw)
            fold_acc=[]
            fold_calls=[]
            for block in tick_blocks:
                f=gap[gap["ticker"].isin(set(block))]
                c=first_calls(f,p,outcol)
                n=len(c)
                fold_calls.append(n)
                fold_acc.append(float(c[outcol].mean()) if n else np.nan)

            allc=first_calls(gap,p,outcol)
            n=len(allc)
            if n<8:
                continue

            valid_acc=[x for x in fold_acc if not np.isnan(x)]
            nonempty=sum(nf>0 for nf in fold_calls)
            worst=min(valid_acc) if valid_acc else 0
            overall=float(allc[outcol].mean())

            # Stability-first ranking. Require presence in >=3 chronological blocks.
            if nonempty < 3:
                continue

            rows.append(dict(
                ask=ask,fair=fair,edge=edge,mx=mx,gap=gf,rr=rr,sw=sw,
                pt=pt,sl=sl,hz=hz,calls=n,acc=overall,worst=worst,
                nonempty=nonempty,
                f1_calls=fold_calls[0],f1_acc=fold_acc[0],
                f2_calls=fold_calls[1],f2_acc=fold_acc[1],
                f3_calls=fold_calls[2],f3_acc=fold_acc[2],
                f4_calls=fold_calls[3],f4_acc=fold_acc[3],
            ))

res=pd.DataFrame(rows)
if res.empty:
    raise SystemExit("No V2 candidates met minimum sample/stability requirements.")

# Prefer rules that survive every block, then worst-block accuracy,
# then overall accuracy, then more calls, then lower ask cap.
res["four_blocks"]=(res["nonempty"]==4).astype(int)
res=res.sort_values(
    ["four_blocks","worst","acc","calls","ask"],
    ascending=[False,False,False,False,True]
).reset_index(drop=True)

print("="*100)
print("RESCUE V2 — HISTORICAL WALK-FORWARD RESEARCH")
print("="*100)
print(f"Historical contracts: {d.ticker.nunique()}")
print(f"Already accepted by existing ladders: {len(hist_union)}")
print(f"Historical uncovered gap pool: {gap.ticker.nunique()}")
print()
print("Railway Rescue-V1 results are NOT used anywhere in this search.")
print("Prior historical holdout is retired from untouched status because we already inspected it.")
print("Fresh Railway contracts will be required for any V2 promotion.")
print()

show=res.head(15).copy()
for i,r in show.iterrows():
    print(
        f"#{i+1:02d} | acc {100*r.acc:5.1f}% | worst {100*r.worst:5.1f}% | "
        f"calls {int(r.calls):2d} | ask<={int(r.ask*100):2d}c fair>={int(r.fair*100):2d}% "
        f"edge>={int(r.edge*100):2d}% maxleft<={int(r.mx):2d}m gap>=${int(r.gap):2d} "
        f"rr>={r.rr:.2f} switches>={int(r.sw)} | "
        f"+{int(r.pt*100)}c/-{int(r.sl*100)}c {int(r.hz)}m | "
        f"folds "
        f"{int(r.f1_calls)}/{('NA' if pd.isna(r.f1_acc) else f'{100*r.f1_acc:.0f}%')} "
        f"{int(r.f2_calls)}/{('NA' if pd.isna(r.f2_acc) else f'{100*r.f2_acc:.0f}%')} "
        f"{int(r.f3_calls)}/{('NA' if pd.isna(r.f3_acc) else f'{100*r.f3_acc:.0f}%')} "
        f"{int(r.f4_calls)}/{('NA' if pd.isna(r.f4_acc) else f'{100*r.f4_acc:.0f}%')}"
    )

winner=res.iloc[0]
print()
print("-"*100)
print("PROVISIONAL V2 RESEARCH WINNER — NOT PROMOTED")
print("-"*100)
print(
    f"ask <= {winner.ask*100:.0f}c | fair >= {winner.fair*100:.0f}% | "
    f"edge >= {winner.edge*100:.0f}% | 2-{winner.mx:.0f}m left | "
    f"gap >= ${winner.gap:.0f} | range ratio >= {winner.rr:.2f} | "
    f"prior switches >= {winner.sw:.0f}"
)
print(
    f"Exit: +{winner.pt*100:.0f}c / -{winner.sl*100:.0f}c / {winner.hz:.0f}m | "
    f"historical {winner.calls:.0f} calls at {winner.acc*100:.1f}% | "
    f"worst chronological block {winner.worst*100:.1f}%"
)
print()
print("STATUS: RESEARCH ONLY. Existing accepted ladders untouched. No orders.")
print("NEXT GATE: freeze this winner, then score ONLY genuinely fresh Railway contracts.")
print("="*100)

res.to_csv("rescue_v2_walkforward_all_candidates.csv",index=False)
show.to_csv("rescue_v2_walkforward_top15.csv",index=False)
