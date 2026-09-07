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

vg=valid[~valid["ticker"].isin(vunion)].copy()
hg=hold[~hold["ticker"].isin(hunion)].copy()

def pullback_calls(frame, setup_fair, entry_ask, entry_fair, edge_min, gap_min, min_delay, max_delay):
    picks=[]
    for ticker,g in frame.groupby("ticker"):
        g=g.sort_values("snapshot_utc").copy()
        if g.empty: continue

        setups=g[
            (g["preferred_fair"]>=setup_fair)
            &(g["remaining"]>=2)
            &(g["remaining"]<=14)
        ]
        if setups.empty: continue

        for _,s in setups.iterrows():
            t0=s["snapshot_utc"]
            side0=int(s["preferred_side_num"])
            q=g[
                (g["snapshot_utc"]>=t0+pd.Timedelta(seconds=min_delay))
                &(g["snapshot_utc"]<=t0+pd.Timedelta(seconds=max_delay))
                &(g["preferred_ask"]<=entry_ask)
                &(g["preferred_fair"]>=entry_fair)
                &(g["edge"]>=edge_min)
                &(g["abs_dist_target"]>=gap_min)
                &(g["remaining"]>=2)
            ].copy()
            if q.empty: continue
            q=q[q["preferred_side_num"].astype(int)==side0]
            if q.empty: continue

            r=q.iloc[0].copy()
            r["setup_time"]=t0
            r["setup_fair"]=s["preferred_fair"]
            r["delay_sec"]=(r["snapshot_utc"]-t0).total_seconds()
            r["correct"]=int(r["preferred_side_num"])==int(r["final_side"])
            picks.append(r)
            break
    return pd.DataFrame(picks)

setup_fairs=[.75,.80,.85]
entry_asks=[.40,.45,.50]
entry_fairs=[.65,.70,.75]
edges=[.05,.08]
gaps=[25,50]
windows=[(30,180),(30,300),(60,360)]

rows=[]
for sf in setup_fairs:
  for ea in entry_asks:
    for ef in entry_fairs:
      for ed in edges:
        for gp in gaps:
          for mn,mx in windows:
            q=pullback_calls(vg,sf,ea,ef,ed,gp,mn,mx)
            if q.empty: continue
            rows.append({
                "setup_fair":sf,"entry_ask":ea,"entry_fair":ef,"edge":ed,"gap":gp,
                "min_delay":mn,"max_delay":mx,
                "calls":len(q),"accuracy":float(q["correct"].mean()),
                "avg_ask":float(q["preferred_ask"].mean()),
                "avg_left":float(q["remaining"].mean()),
                "avg_delay":float(q["delay_sec"].mean()),
            })

res=pd.DataFrame(rows)
print("="*78)
print("EARLY PULLBACK / RE-ENTRY GAP STUDY V1")
print("VALIDATION SELECT / UNTOUCHED HOLDOUT REPORT")
print("="*78)
print(f"Baseline union: validation {len(vunion)}/{len(valid_ticks)} | holdout {len(hunion)}/{len(hold_ticks)}")
print(f"Uncovered: validation {len(valid_ticks)-len(vunion)} | holdout {len(hold_ticks)-len(hunion)}")
print()

if res.empty:
    print("RESULT: No pullback/re-entry candidates fired on validation gaps.")
    print("No bot logic changed. No orders.")
    raise SystemExit(0)

eligible=res[(res["calls"]>=3)&(res["accuracy"]>=.90)].copy()
if eligible.empty:
    print("RESULT: No pullback/re-entry candidate cleared >=3 validation calls AND >=90% accuracy.")
    best=res.sort_values(["accuracy","calls","avg_ask"],ascending=[False,False,True]).head(5)
    print()
    print("Best validation-only candidates for diagnosis:")
    for _,w in best.iterrows():
        print(
            f"  {int(w.calls)} calls | {100*w.accuracy:.1f}% | "
            f"setup fair>={100*w.setup_fair:.0f}% -> ask<={100*w.entry_ask:.0f}c "
            f"fair>={100*w.entry_fair:.0f}% edge>={100*w.edge:.0f}% gap>=${w.gap:.0f} "
            f"| delay {int(w.min_delay)}-{int(w.max_delay)}s"
        )
    print()
    print("No holdout selection performed. Branch should not be promoted.")
    print("No bot logic changed. No orders.")
    raise SystemExit(0)

eligible=eligible.sort_values(
    ["accuracy","calls","avg_ask","avg_left"],
    ascending=[False,False,True,False]
).reset_index(drop=True)
w=eligible.iloc[0]

print(
    f"VALIDATION WINNER: {int(w.calls)} calls | {100*w.accuracy:.1f}% | "
    f"avg ask {100*w.avg_ask:.1f}c | avg {w.avg_left:.2f}m left | avg wait {w.avg_delay:.0f}s"
)
print(
    f"Rule: setup fair>={100*w.setup_fair:.0f}% then within {int(w.min_delay)}-{int(w.max_delay)}s "
    f"same-side ask<={100*w.entry_ask:.0f}c | fair>={100*w.entry_fair:.0f}% | "
    f"edge>={100*w.edge:.0f}% | gap>=${w.gap:.0f}"
)

hq=pullback_calls(hg,w.setup_fair,w.entry_ask,w.entry_fair,w.edge,w.gap,int(w.min_delay),int(w.max_delay))
if hq.empty:
    print("UNTOUCHED HOLDOUT GAPS: 0 calls")
    added=set()
else:
    added=set(hq["ticker"].astype(str))
    wins=int(hq["correct"].sum())
    print(
        f"UNTOUCHED HOLDOUT GAPS: {len(hq)} calls | {wins}/{len(hq)} = {100*hq.correct.mean():.1f}% | "
        f"avg ask {100*hq.preferred_ask.mean():.1f}c | avg {hq.remaining.mean():.2f}m left | "
        f"avg wait {hq.delay_sec.mean():.0f}s"
    )

new_union=hunion|added
print(f"NEW HOLDOUT UNION IF ADDED: {len(new_union)}/{len(hold_ticks)} = {100*len(new_union)/len(hold_ticks):.1f}%")
print(f"Remaining uncovered: {len(hold_ticks)-len(new_union)}")
print()
print("INTEGRITY: validation-only selection; holdout report-only; accepted ladders unchanged.")
print("No bot logic changed. No orders.")
print("="*78)
