#!/usr/bin/env python3
"""
KALSHI BTC 15-MIN UNION COVERAGE OPTIMIZER V1
=============================================

Purpose
-------
Keep the locked strong tiers intact and expand ACTIONABLE COVERAGE.

Locked anchors:
1) FINAL tournament winner (do not weaken)
2) Tier-1 ENTRY historical-price winner (do not weaken)

This optimizer searches the contracts NOT already covered by Tier-1 ENTRY for:
- Secondary directional value entries
- Short-horizon scalp opportunities using ACTUAL Kalshi 1-minute bid/ask
- Reversal scalps using ACTUAL Kalshi 1-minute bid/ask

Core metric:
UNION ACTIONABLE COVERAGE = % of contracts with >=1 validated opportunity.

Integrity
---------
- Actual Kalshi historical 1-minute YES bid/ask
- Official settlement labels
- Chronological model/calibration/validation/untouched-holdout split
- Locked Tier-1 rule is not tuned
- New rules are selected on validation only
- Untouched holdout is report-only
- Signal-only; no orders
- bot.py unchanged

Scalp realism
-------------
For a candidate entry:
- BUY at the actual ASK
- EXIT at the actual future BID on the same side
- Profit target must be hit BEFORE a stop-loss is hit
- This accounts for spread and avoids using settlement-only correctness
"""

from pathlib import Path
from zoneinfo import ZoneInfo
import re, warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

CAL = Path("brti_calibration_results.csv")
BTC_CACHE = Path("btc_35d_live_cache.csv")
CANDLE_CACHE = Path("kalshi_kxbtc15m_1m_candles_cache.csv")

SUMMARY = Path("union_coverage_optimizer_v1_summary.txt")
SECONDARY_RESULTS = Path("union_secondary_entry_results.csv")
SCALP_RESULTS = Path("union_scalp_results.csv")
HOLDOUT_DETAIL = Path("union_coverage_holdout_detail.csv")
PROCESSED_CACHE = Path("union_optimizer_processed_snapshot_cache.csv")

MONTHS = {m:i+1 for i,m in enumerate(
    ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
)}

FEATURES = [
    "elapsed","remaining","current_side",
    "dist_target","abs_dist_target","dist_target_pct",
    "move_from_start","move_from_start_pct",
    "move1","move2","move3","move5",
    "support1","support2","support3","support5",
    "range5","vol5",
    "dist_per_min_remaining","dist_over_range5",
]

def parse_contract_times(ticker):
    m = re.search(
        r"KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-",
        str(ticker).upper(),
    )
    if not m:
        return pd.NaT, pd.NaT
    yy, mon, dd, hh, mm = m.groups()
    wall = pd.Timestamp(
        year=2000+int(yy), month=MONTHS[mon], day=int(dd),
        hour=int(hh), minute=int(mm),
    )
    close_utc = wall.tz_localize(
        ZoneInfo("America/New_York")
    ).tz_convert("UTC")
    return close_utc-pd.Timedelta(minutes=15), close_utc

def load_btc():
    try:
        d = pd.read_csv(BTC_CACHE, index_col="Datetime", parse_dates=True)
    except Exception:
        d = pd.read_csv(BTC_CACHE)
        ts = next(
            (c for c in ["Datetime","datetime","timestamp","Timestamp","time","Time"]
             if c in d.columns), d.columns[0]
        )
        d[ts] = pd.to_datetime(d[ts], errors="coerce", utc=True)
        d = d.dropna(subset=[ts]).set_index(ts)

    idx = pd.to_datetime(d.index, errors="coerce", utc=True)
    ok = ~pd.isna(idx)
    d = d.loc[ok].copy()
    d.index = idx[ok]
    rename={}
    for want in ["Open","High","Low","Close","Volume"]:
        for c in d.columns:
            if str(c).lower()==want.lower():
                rename[c]=want
                break
    d=d.rename(columns=rename)
    d=d[~d.index.duplicated(keep="last")].sort_index()
    return d

def price_at_or_before(data, ts):
    i=data.index.searchsorted(ts,side="right")-1
    if i<0:
        return np.nan,pd.NaT
    ti=data.index[i]
    if ts-ti>pd.Timedelta(minutes=2):
        return np.nan,pd.NaT
    return float(data.iloc[i]["Close"]),ti

def build_snapshot(data,start,target,final_side,elapsed):
    cut=start+pd.Timedelta(minutes=float(elapsed))
    pstart,_=price_at_or_before(data,start)
    vals=[price_at_or_before(data,cut-pd.Timedelta(minutes=m)) for m in [0,1,2,3,5]]
    if pd.isna(pstart) or any(pd.isna(v[0]) for v in vals):
        return None
    p0,p1,p2,p3,p5=[v[0] for v in vals]
    w=data.loc[(data.index>cut-pd.Timedelta(minutes=5))&(data.index<=cut)]
    if len(w)<3:
        return None
    closes=w["Close"].dropna()
    if len(closes)<2:
        return None

    current_side=int(p0>=target)
    sign=1.0 if current_side==1 else -1.0
    dist=p0-target
    abs_dist=abs(dist)
    remaining=max(0.0,15.0-float(elapsed))
    range5=float(w["High"].max()-w["Low"].min())
    move1,move2,move3,move5=p0-p1,p0-p2,p0-p3,p0-p5
    return {
        "elapsed":float(elapsed),
        "remaining":remaining,
        "current_side":current_side,
        "dist_target":float(dist),
        "abs_dist_target":float(abs_dist),
        "dist_target_pct":float(dist/target),
        "move_from_start":float(p0-pstart),
        "move_from_start_pct":float((p0-pstart)/pstart),
        "move1":float(move1),"move2":float(move2),
        "move3":float(move3),"move5":float(move5),
        "support1":float(move1*sign),"support2":float(move2*sign),
        "support3":float(move3*sign),"support5":float(move5*sign),
        "range5":range5,
        "vol5":float(closes.pct_change().std(ddof=0)),
        "dist_per_min_remaining":float(abs_dist/max(remaining,.25)),
        "dist_over_range5":float(abs_dist/max(range5,1.0)),
        "final_side":int(final_side),
        "flip":int(int(final_side)!=current_side),
        "snapshot_utc":cut,
    }

def load_candles():
    c=pd.read_csv(CANDLE_CACHE)
    c["candle_end_utc"]=pd.to_datetime(c["candle_end_utc"],errors="coerce",utc=True)
    for col in ["yes_ask","yes_bid","no_ask"]:
        c[col]=pd.to_numeric(c[col],errors="coerce")
    # derive NO bid from YES ask
    c["no_bid"]=1.0-c["yes_ask"]
    return c.dropna(subset=["contract","candle_end_utc"]).sort_values(
        ["contract","candle_end_utc"]
    )

def add_fair(hist,rf,sigmoid):
    d=hist.copy()
    raw=rf.predict_proba(d[FEATURES])[:,1]
    flip=sigmoid.predict_proba(raw.reshape(-1,1))[:,1]
    flip=np.clip(flip,.001,.999)
    d["fair_up"]=np.where(d["current_side"]==1,1-flip,flip)
    d["fair_down"]=1-d["fair_up"]
    d["preferred_side_num"]=np.where(d["fair_up"]>=d["fair_down"],1,0)
    d["preferred_side"]=np.where(d["preferred_side_num"]==1,"UP","DOWN")
    d["preferred_fair"]=np.maximum(d["fair_up"],d["fair_down"])
    return d

def align_prices(test,candles):
    parts=[]
    for ticker,g in test.groupby("ticker",sort=False):
        cg=candles[candles["contract"]==ticker].copy()
        if cg.empty:
            continue
        gg=g.copy()
        gg["snapshot_utc"]=pd.to_datetime(
            gg["snapshot_utc"],errors="coerce",utc=True
        ).astype("datetime64[ns, UTC]")
        cg["candle_end_utc"]=pd.to_datetime(
            cg["candle_end_utc"],errors="coerce",utc=True
        ).astype("datetime64[ns, UTC]")
        gg=gg.dropna(subset=["snapshot_utc"]).sort_values("snapshot_utc")
        cg=cg.dropna(subset=["candle_end_utc"]).sort_values("candle_end_utc")
        m=pd.merge_asof(
            gg,
            cg[["candle_end_utc","yes_ask","yes_bid","no_ask","no_bid"]],
            left_on="snapshot_utc",right_on="candle_end_utc",
            direction="backward",tolerance=pd.Timedelta(seconds=90),
        )
        parts.append(m)
    if not parts:
        raise SystemExit("No aligned Kalshi price data")
    d=pd.concat(parts,ignore_index=True)
    d["preferred_ask"]=np.where(
        d["preferred_side_num"]==1,d["yes_ask"],d["no_ask"]
    )
    d["preferred_bid"]=np.where(
        d["preferred_side_num"]==1,d["yes_bid"],d["no_bid"]
    )
    d["edge"]=d["preferred_fair"]-d["preferred_ask"]
    return d[d["preferred_ask"].between(.001,.999)].copy()

def locked_tier1_mask(d):
    # Exact V3 Tier-1 winner
    return (
        (d["preferred_ask"]<=.45)
        &(d["preferred_fair"]>=.75)
        &(d["edge"]>=.08)
        &(d["remaining"]>=2.0)
        &(d["remaining"]<=10.0)
        &(d["abs_dist_target"]>=25.0)
    )

def score_secondary(frame,p):
    mask=(
        (frame["preferred_ask"]<=p["ask_max"])
        &(frame["preferred_fair"]>=p["fair_min"])
        &(frame["edge"]>=p["edge_min"])
        &(frame["remaining"]>=p["min_tl"])
        &(frame["remaining"]<=p["max_tl"])
        &(frame["abs_dist_target"]>=p["min_gap"])
        &(frame["dist_over_range5"]>=p["min_ratio"])
    )
    q=frame[mask].sort_values(["ticker","elapsed"])
    if q.empty:
        return None,pd.DataFrame()
    first=q.groupby("ticker",as_index=False).first()
    first["correct"]=first["preferred_side_num"].astype(int)==first["final_side"].astype(int)
    return {
        **p,
        "calls":len(first),
        "contracts":frame["ticker"].nunique(),
        "coverage":len(first)/max(frame["ticker"].nunique(),1),
        "accuracy":float(first["correct"].mean()),
        "avg_ask":float(first["preferred_ask"].mean()),
        "avg_time_left":float(first["remaining"].mean()),
    },first

def future_scalp_outcome(row,candles,profit_target,stop_loss,horizon):
    ticker=row["ticker"]
    side=row["preferred_side"]
    entry=float(row["preferred_ask"])
    t0=pd.Timestamp(row["snapshot_utc"])
    t1=t0+pd.Timedelta(minutes=int(horizon))
    cg=candles[
        (candles["contract"]==ticker)
        &(candles["candle_end_utc"]>t0)
        &(candles["candle_end_utc"]<=t1)
    ].sort_values("candle_end_utc")
    if cg.empty:
        return None
    bid_col="yes_bid" if side=="UP" else "no_bid"
    asks_col="yes_ask" if side=="UP" else "no_ask"

    target=entry+profit_target
    stop=entry-stop_loss
    for _,c in cg.iterrows():
        bid=c[bid_col]
        ask=c[asks_col]
        if pd.isna(bid) or pd.isna(ask):
            continue
        # Stop uses bid too, because that's the executable exit.
        if float(bid)<=stop:
            return False
        if float(bid)>=target:
            return True
    return False

def score_scalp(frame,candles,p):
    mask=(
        (frame["preferred_ask"]<=p["ask_max"])
        &(frame["preferred_fair"]>=p["fair_min"])
        &(frame["edge"]>=p["edge_min"])
        &(frame["remaining"]>=p["min_tl"])
        &(frame["remaining"]<=p["max_tl"])
        &(frame["abs_dist_target"]>=p["min_gap"])
    )
    q=frame[mask].sort_values(["ticker","elapsed"])
    if q.empty:
        return None,pd.DataFrame()

    picked=[]
    for ticker,g in q.groupby("ticker",sort=False):
        for _,r in g.iterrows():
            out=future_scalp_outcome(
                r,candles,p["profit_target"],p["stop_loss"],p["horizon"]
            )
            if out is None:
                continue
            rr=r.copy()
            rr["scalp_win"]=bool(out)
            picked.append(rr)
            break

    if not picked:
        return None,pd.DataFrame()
    first=pd.DataFrame(picked)
    return {
        **p,
        "calls":len(first),
        "contracts":frame["ticker"].nunique(),
        "coverage":len(first)/max(frame["ticker"].nunique(),1),
        "accuracy":float(first["scalp_win"].mean()),
        "avg_ask":float(first["preferred_ask"].mean()),
        "avg_time_left":float(first["remaining"].mean()),
    },first


def main():
    if not CACHE.exists():
        raise SystemExit("MISSING processed cache: "+str(CACHE))
    if not CANDLE_CACHE.exists():
        raise SystemExit("MISSING candle cache: "+str(CANDLE_CACHE))

    d=pd.read_csv(CACHE)
    d["snapshot_utc"]=pd.to_datetime(d["snapshot_utc"],errors="coerce",utc=True)
    numcols=[
        "elapsed","remaining","abs_dist_target","dist_over_range5",
        "preferred_ask","preferred_fair","edge","preferred_side_num",
        "current_side","final_side"
    ]
    for c in numcols:
        if c in d.columns:
            d[c]=pd.to_numeric(d[c],errors="coerce")
    d=d.dropna(subset=["ticker","snapshot_utc","remaining","preferred_fair"]).copy()

    ticks=pd.DataFrame({"ticker":sorted(d["ticker"].unique())})
    ticks["start"]=ticks["ticker"].map(parse_start)
    ticks=ticks.dropna().sort_values("start").reset_index(drop=True)
    mid=len(ticks)//2
    valid_ticks=set(ticks.iloc[:mid]["ticker"])
    hold_ticks=set(ticks.iloc[mid:]["ticker"])

    candles=load_candles()

    # Reproduce accepted baseline from the current scorecard semantics.
    def t1(frame):
        return set(frame.loc[
            (frame["preferred_ask"]<=.45)
            &(frame["preferred_fair"]>=.75)
            &(frame["edge"]>=.08)
            &(frame["remaining"]>=2)
            &(frame["remaining"]<=10)
            &(frame["abs_dist_target"]>=25),
            "ticker"
        ])

    def locked_final(frame):
        m=(
            (frame["preferred_fair"]>=.90)
            &(frame["remaining"]<=8)
            &(frame["dist_over_range5"]>=1.0)
            &(frame["preferred_side_num"]==frame["current_side"])
            &(
                ((frame["remaining"]>6)&(frame["abs_dist_target"]>=75))
                |((frame["remaining"]<=6)&(frame["abs_dist_target"]>=50))
            )
        )
        return set(frame.loc[m,"ticker"])

    # Accepted strong scalp rule from scorecard.
    def strong_scalp(frame):
        p=dict(ask_max=.70,fair_min=.52,edge_min=.00,min_tl=3.,max_tl=14.,min_gap=0.)
        pt,sl,hz=.08,.05,5
        calls=[]
        for ticker,g in frame.groupby("ticker"):
            g=g.sort_values("snapshot_utc")
            q=g[
                (g["preferred_ask"]<=p["ask_max"])
                &(g["preferred_fair"]>=p["fair_min"])
                &(g["edge"]>=p["edge_min"])
                &(g["remaining"]>=p["min_tl"])
                &(g["remaining"]<=p["max_tl"])
                &(g["abs_dist_target"]>=p["min_gap"])
            ]
            for _,r in q.iterrows():
                o=future_scalp_outcome(r,candles,pt,sl,hz)
                if o is None: continue
                calls.append((ticker,o))
                break
        return set(t for t,o in calls)

    def gaps(tickset):
        f=d[d["ticker"].isin(tickset)].copy()
        a=t1(f); b=locked_final(f)
        # mirror accepted scorecard: scalp excludes Tier-1-covered contracts
        c=strong_scalp(f[~f["ticker"].isin(a)].copy())
        return f, set(tickset)-(a|b|c)

    valid,vg=gaps(valid_ticks)
    hold,hg=gaps(hold_ticks)

    print("="*78)
    print("GAP OPPORTUNITY-CLASS AUDIT V1 — READ ONLY")
    print("="*78)
    print(f"Baseline uncovered: validation {len(vg)} | holdout {len(hg)}")
    print()

    # Diagnostic only: for each gap, ask whether ANY realistic 1m ASK->future BID
    # temporary move existed. This is NOT a candidate selector and NOT union coverage.
    rules=[
        (.05,.05,2),(.08,.05,2),(.10,.05,3),(.12,.08,3),
        (.15,.08,4),(.18,.10,5),(.20,.10,5)
    ]

    def audit(frame,gset,label):
        print(label)
        print("-"*78)
        counts={"TEMP_MOVE":0,"DIRECTIONAL_ONLY":0,"NO_REALISTIC_MOVE":0}
        for ticker in sorted(gset):
            g=frame[frame["ticker"]==ticker].sort_values("snapshot_utc")
            any_move=False
            best=None
            for _,r in g.iterrows():
                if not (2<=r["remaining"]<=14): continue
                for pt,sl,hz in rules:
                    o=future_scalp_outcome(r,candles,pt,sl,hz)
                    if o is None: continue
                    if o==1:
                        any_move=True
                        score=pt
                        if best is None or score>best[0]:
                            best=(score,pt,sl,hz,r["preferred_ask"],r["remaining"],r["preferred_fair"])
            final_correct=((g["preferred_side_num"].astype(int)==g["final_side"].astype(int))).any()
            if any_move:
                cls="TEMP_MOVE"; counts[cls]+=1
                _,pt,sl,hz,ask,left,fair=best
                print(f"{ticker} | TEMP_MOVE | up to +{100*pt:.0f}c before -{100*sl:.0f}c stop | {hz}m horizon | ask {100*ask:.0f}c | {left:.1f}m left | fair {100*fair:.0f}%")
            elif final_correct:
                cls="DIRECTIONAL_ONLY"; counts[cls]+=1
                print(f"{ticker} | DIRECTIONAL_ONLY | preferred side was eventually correct somewhere, but no tested ASK->BID move qualified")
            else:
                cls="NO_REALISTIC_MOVE"; counts[cls]+=1
                print(f"{ticker} | NO_REALISTIC_MOVE | no tested ASK->BID move and no correct preferred-side snapshot")
        print("COUNTS:",counts)
        print()
        return counts

    audit(valid,vg,"VALIDATION GAPS")
    audit(hold,hg,"UNTOUCHED HOLDOUT GAPS")

    print("IMPORTANT: TEMP_MOVE is opportunity feasibility, NOT a tradable predictor.")
    print("No threshold selected. Holdout not used for selection. No bot logic changed. No orders.")
    print("="*78)

if __name__=="__main__":
    main()
