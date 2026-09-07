#!/usr/bin/env python3
"""
BTC15 EARLY-PERSISTENCE META-MODEL V1
=====================================

Goal
----
Build a DEDICATED early-entry persistence/reversal-risk model.

This is not another fair/edge threshold search.
The base target-aware fair model remains unchanged.

Question learned by this meta-model:
    "When a cheap early setup exists, is this setup structurally likely
     to persist to the official Kalshi settlement instead of reversing?"

Training / validation integrity
-------------------------------
OLD PRICED DATA ONLY:
- brti_calibration_results.csv
- btc_35d_live_cache.csv
- kalshi_kxbtc15m_1m_candles_cache.csv

Old priced contracts are split chronologically:
- first 70% meta-train
- next 15% meta-validation
- last 15% old holdout

FRESH 250-CONTRACT DATA:
- fresh_oos_market_manifest.csv
- fresh_oos_candles_cache.csv

The fresh block is NEVER used to train the fair model, train the meta-model,
or select the meta threshold. It is report-only at the very end.

Base cheap-candidate pool
-------------------------
A snapshot is eligible for meta-scoring when:
- preferred ask <= 50c
- preferred fair >= 65%
- edge >= 5%
- 4-10 minutes left
- abs strike gap >= $15

This broad pool deliberately contains good and bad setups so the meta-model
can learn reversal risk rather than merely re-create the old threshold rule.

Meta features
-------------
- preferred_fair
- preferred_ask
- edge
- remaining
- abs_dist_target
- dist_over_range5
- range5
- vol5
- support1/2/3/5
- move1/2/3/5
- dist_per_min_remaining
- current-side agreement
- fair-side vs current-side
- normalized ask/fair relationship

Selection
---------
Meta probability threshold is selected on OLD VALIDATION ONLY.

Primary objective:
- validation accuracy >= 93% if feasible
- at least 12 validation calls
Then rank by:
- coverage
- avg ask (lower better)
- avg time left (higher better)

Fresh acceptance readout
------------------------
Reports:
- accuracy
- calls / coverage
- avg & median ask
- % <=40c
- % 20-40c
- avg/median time left
- comparison with P40 / P45 / old Tier1 / locked FINAL

No orders. Does not modify bot.py.
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
OLD_CANDLES = Path("kalshi_kxbtc15m_1m_candles_cache.csv")
FRESH_MANIFEST = Path("fresh_oos_market_manifest.csv")
FRESH_CANDLES = Path("fresh_oos_candles_cache.csv")

SUMMARY = Path("early_persistence_meta_summary.txt")
OLD_CALLS = Path("early_persistence_old_holdout_calls.csv")
FRESH_CALLS = Path("early_persistence_fresh_calls.csv")
VAL_GRID = Path("early_persistence_validation_thresholds.csv")

MONTHS = {m:i+1 for i,m in enumerate(
    ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
)}

BASE_FEATURES = [
    "elapsed","remaining","current_side",
    "dist_target","abs_dist_target","dist_target_pct",
    "move_from_start","move_from_start_pct",
    "move1","move2","move3","move5",
    "support1","support2","support3","support5",
    "range5","vol5",
    "dist_per_min_remaining","dist_over_range5",
]

META_FEATURES = [
    "preferred_fair",
    "preferred_ask",
    "edge",
    "remaining",
    "abs_dist_target",
    "dist_over_range5",
    "range5",
    "vol5",
    "support1","support2","support3","support5",
    "move1","move2","move3","move5",
    "dist_per_min_remaining",
    "preferred_agrees_current",
    "fair_minus_ask_ratio",
    "gap_per_range",
]

def parse_contract_times(ticker):
    m = re.search(
        r"KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-",
        str(ticker).upper()
    )
    if not m:
        return pd.NaT, pd.NaT
    yy,mon,dd,hh,mm = m.groups()
    wall = pd.Timestamp(
        year=2000+int(yy), month=MONTHS[mon], day=int(dd),
        hour=int(hh), minute=int(mm)
    )
    close_utc = wall.tz_localize(
        ZoneInfo("America/New_York")
    ).tz_convert("UTC")
    return close_utc-pd.Timedelta(minutes=15), close_utc

def load_btc():
    d = pd.read_csv(BTC_CACHE)
    ts_col = next(
        (c for c in ["Datetime","datetime","timestamp","Timestamp","time","Time"]
         if c in d.columns),
        d.columns[0]
    )
    d[ts_col] = pd.to_datetime(d[ts_col], errors="coerce", utc=True)
    d = d.dropna(subset=[ts_col]).set_index(ts_col)
    rename={}
    for want in ["Open","High","Low","Close","Volume"]:
        for c in d.columns:
            if str(c).lower()==want.lower():
                rename[c]=want
                break
    d=d.rename(columns=rename)
    d=d[~d.index.duplicated(keep="last")].sort_index()
    return d

def price_at_or_before(data,ts):
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
    vals=[price_at_or_before(data,cut-pd.Timedelta(minutes=m))
          for m in [0,1,2,3,5]]
    if pd.isna(pstart) or any(pd.isna(v[0]) for v in vals):
        return None
    p0,p1,p2,p3,p5=[v[0] for v in vals]
    w=data.loc[
        (data.index>cut-pd.Timedelta(minutes=5))
        & (data.index<=cut)
    ]
    if len(w)<3:
        return None
    closes=w["Close"].dropna()
    if len(closes)<2:
        return None

    current_side=int(p0>=target)
    sign=1. if current_side==1 else -1.
    dist=p0-target
    abs_dist=abs(dist)
    remaining=max(0.,15.-float(elapsed))
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

def load_old_contracts():
    cal=pd.read_csv(CAL)
    cal["target_brti"]=pd.to_numeric(cal["target_brti"],errors="coerce")
    cal["final_brti"]=pd.to_numeric(cal["final_brti"],errors="coerce")
    cal=cal.dropna(subset=["target_brti","final_brti"]).copy()
    cal["final_side"]=(cal["final_brti"]>=cal["target_brti"]).astype(int)
    parsed=cal["ticker"].apply(parse_contract_times)
    cal["start"]=[x[0] for x in parsed]
    cal["close"]=[x[1] for x in parsed]
    return cal.dropna(subset=["start","close"]).sort_values("start").reset_index(drop=True)

def load_fresh_contracts():
    f=pd.read_csv(FRESH_MANIFEST)
    for c in ["start","close"]:
        f[c]=pd.to_datetime(f[c],errors="coerce",utc=True)
    f["target"]=pd.to_numeric(f["target"],errors="coerce")
    f["final_side"]=pd.to_numeric(f["final_side"],errors="coerce").astype(int)
    return f.dropna(subset=["start","close","target"]).sort_values("start").reset_index(drop=True)

def load_candles(path):
    c=pd.read_csv(path)
    c["candle_end_utc"]=pd.to_datetime(
        c["candle_end_utc"],errors="coerce",utc=True
    )
    for col in ["yes_ask","yes_bid","no_ask"]:
        if col in c.columns:
            c[col]=pd.to_numeric(c[col],errors="coerce")
    return c.dropna(subset=["candle_end_utc"])

def train_base_fair(old,btc):
    rows=[]
    for _,r in old.iterrows():
        for elapsed in range(1,15):
            s=build_snapshot(
                btc,r["start"],r["target_brti"],r["final_side"],elapsed
            )
            if s is not None:
                s["ticker"]=r["ticker"]
                s["start"]=r["start"]
                rows.append(s)
    hist=pd.DataFrame(rows)
    cov=hist.groupby("ticker")["elapsed"].nunique()
    keep=set(cov[cov>=10].index)
    hist=hist[hist["ticker"].isin(keep)].copy()

    contracts=(
        hist[["ticker","start"]].drop_duplicates()
        .sort_values("start").reset_index(drop=True)
    )
    n=len(contracts)
    i1,i2=int(n*.50),int(n*.70)
    model_c=set(contracts.iloc[:i1]["ticker"])
    calib_c=set(contracts.iloc[i1:i2]["ticker"])

    rf_train=hist[hist["ticker"].isin(model_c)]
    calset=hist[hist["ticker"].isin(calib_c)]

    rf=RandomForestClassifier(
        n_estimators=900,max_depth=9,min_samples_leaf=12,
        class_weight="balanced",random_state=42,n_jobs=-1
    )
    rf.fit(rf_train[BASE_FEATURES],rf_train["flip"])

    raw=rf.predict_proba(calset[BASE_FEATURES])[:,1]
    sig=LogisticRegression(
        solver="lbfgs",C=1.0,max_iter=1000,random_state=42
    )
    sig.fit(raw.reshape(-1,1),calset["flip"].astype(int))
    return rf,sig

def build_features(contracts,btc,rf,sig,old=True):
    rows=[]
    for _,r in contracts.iterrows():
        target=float(r["target_brti"] if old else r["target"])
        for elapsed in range(1,15):
            s=build_snapshot(
                btc,r["start"],target,int(r["final_side"]),elapsed
            )
            if s is not None:
                s["ticker"]=r["ticker"]
                s["start"]=r["start"]
                rows.append(s)
    x=pd.DataFrame(rows)
    raw=rf.predict_proba(x[BASE_FEATURES])[:,1]
    flip=sig.predict_proba(raw.reshape(-1,1))[:,1]
    flip=np.clip(flip,.001,.999)
    x["fair_up"]=np.where(x["current_side"]==1,1-flip,flip)
    x["fair_down"]=1-x["fair_up"]
    x["preferred_side_num"]=np.where(
        x["fair_up"]>=x["fair_down"],1,0
    )
    x["preferred_side"]=np.where(
        x["preferred_side_num"]==1,"UP","DOWN"
    )
    x["preferred_fair"]=np.maximum(x["fair_up"],x["fair_down"])
    return x

def align_prices(features,candles):
    parts=[]
    for ticker,g in features.groupby("ticker",sort=False):
        cg=candles[candles["contract"]==ticker].copy()
        if cg.empty:
            continue
        gg=g.copy().sort_values("snapshot_utc")
        cg=cg.sort_values("candle_end_utc")
        gg["snapshot_utc"]=pd.to_datetime(gg["snapshot_utc"],utc=True)
        m=pd.merge_asof(
            gg,
            cg[["candle_end_utc","yes_ask","yes_bid","no_ask"]],
            left_on="snapshot_utc",right_on="candle_end_utc",
            direction="backward",tolerance=pd.Timedelta(seconds=90)
        )
        parts.append(m)
    d=pd.concat(parts,ignore_index=True)
    d["preferred_ask"]=np.where(
        d["preferred_side_num"]==1,d["yes_ask"],d["no_ask"]
    )
    d["edge"]=d["preferred_fair"]-d["preferred_ask"]
    d=d[
        d["preferred_ask"].between(.001,.999)
        & d["edge"].notna()
    ].copy()
    d["correct"]=(
        d["preferred_side_num"].astype(int)==d["final_side"].astype(int)
    ).astype(int)
    d["preferred_agrees_current"]=(
        d["preferred_side_num"]==d["current_side"]
    ).astype(int)
    d["fair_minus_ask_ratio"]=(
        d["preferred_fair"]/d["preferred_ask"].clip(lower=.01)
    )
    d["gap_per_range"]=(
        d["abs_dist_target"]/d["range5"].clip(lower=1.0)
    )
    return d

def candidate_pool(d):
    return d[
        (d["preferred_ask"]<=.50)
        & (d["preferred_fair"]>=.65)
        & (d["edge"]>=.05)
        & d["remaining"].between(4.,10.)
        & (d["abs_dist_target"]>=15.)
    ].copy()

def first_per_contract(d):
    return (
        d.sort_values(["ticker","elapsed"])
        .groupby("ticker",as_index=False)
        .first()
    )

def score_calls(q):
    if q.empty:
        return None
    return {
        "calls":len(q),
        "accuracy":float(q["correct"].mean()),
        "avg_ask":float(q["preferred_ask"].mean()),
        "median_ask":float(q["preferred_ask"].median()),
        "pct_le40":float((q["preferred_ask"]<=.40).mean()),
        "pct_20_40":float(q["preferred_ask"].between(.20,.40).mean()),
        "avg_time_left":float(q["remaining"].mean()),
        "median_time_left":float(q["remaining"].median()),
        "avg_meta_prob":float(q["meta_prob"].mean()),
    }

def fmt(x):
    return f"{100*x:.1f}%"

def main():
    needed=[CAL,BTC_CACHE,OLD_CANDLES,FRESH_MANIFEST,FRESH_CANDLES]
    missing=[str(p) for p in needed if not p.exists()]
    if missing:
        raise SystemExit("Missing required files: "+", ".join(missing))

    btc=load_btc()
    old=load_old_contracts()
    fresh=load_fresh_contracts()
    old_c=load_candles(OLD_CANDLES)
    fresh_c=load_candles(FRESH_CANDLES)

    print("="*76)
    print("BTC15 EARLY-PERSISTENCE META-MODEL V1")
    print("="*76)
    print("Training preserved base fair model...")
    rf,sig=train_base_fair(old,btc)

    print("Building old priced candidate pool...")
    old_f=build_features(old,btc,rf,sig,old=True)
    old_p=align_prices(old_f,old_c)
    old_pool=candidate_pool(old_p)

    old_contracts=(
        old_pool[["ticker","start"]].drop_duplicates()
        .sort_values("start").reset_index(drop=True)
    )
    n=len(old_contracts)
    i1,i2=int(n*.70),int(n*.85)
    train_c=set(old_contracts.iloc[:i1]["ticker"])
    val_c=set(old_contracts.iloc[i1:i2]["ticker"])
    hold_c=set(old_contracts.iloc[i2:]["ticker"])

    train=old_pool[old_pool["ticker"].isin(train_c)].copy()
    val=old_pool[old_pool["ticker"].isin(val_c)].copy()
    hold=old_pool[old_pool["ticker"].isin(hold_c)].copy()

    print(
        f"Meta split: train {len(train_c)} contracts | "
        f"validation {len(val_c)} | old holdout {len(hold_c)}"
    )

    meta=RandomForestClassifier(
        n_estimators=1200,
        max_depth=6,
        min_samples_leaf=8,
        class_weight="balanced",
        random_state=77,
        n_jobs=-1
    )
    meta.fit(train[META_FEATURES],train["correct"])

    for frame in [train,val,hold]:
        frame["meta_prob"]=meta.predict_proba(frame[META_FEATURES])[:,1]

    rows=[]
    for threshold in np.arange(.60,.951,.01):
        q=first_per_contract(val[val["meta_prob"]>=threshold])
        s=score_calls(q)
        if s is None:
            continue
        rows.append({
            "threshold":round(float(threshold),2),
            **s
        })

    grid=pd.DataFrame(rows)
    grid.to_csv(VAL_GRID,index=False)
    if grid.empty:
        raise SystemExit("No validation thresholds produced calls.")

    viable=grid[
        (grid["accuracy"]>=.93)
        & (grid["calls"]>=12)
    ].copy()

    if not viable.empty:
        viable=viable.sort_values(
            ["accuracy","calls","avg_ask","avg_time_left"],
            ascending=[False,False,True,False]
        )
        winner=viable.iloc[0]
        selection_note="Met >=93% accuracy and >=12 validation calls."
    else:
        # If target is not feasible, choose strongest honest fallback,
        # prioritizing accuracy with at least 8 calls.
        fallback=grid[grid["calls"]>=8].copy()
        if fallback.empty:
            fallback=grid.copy()
        fallback=fallback.sort_values(
            ["accuracy","calls","avg_ask","avg_time_left"],
            ascending=[False,False,True,False]
        )
        winner=fallback.iloc[0]
        selection_note="No validation threshold met full target; best honest fallback."

    th=float(winner["threshold"])

    hold_q=first_per_contract(hold[hold["meta_prob"]>=th])
    hold_s=score_calls(hold_q)
    hold_q.to_csv(OLD_CALLS,index=False)

    print("Building untouched fresh 250-contract report...")
    fresh_f=build_features(fresh,btc,rf,sig,old=False)
    fresh_p=align_prices(fresh_f,fresh_c)
    fresh_pool=candidate_pool(fresh_p)
    fresh_pool["meta_prob"]=meta.predict_proba(
        fresh_pool[META_FEATURES]
    )[:,1]
    fresh_q=first_per_contract(fresh_pool[fresh_pool["meta_prob"]>=th])
    fresh_s=score_calls(fresh_q)
    fresh_q.to_csv(FRESH_CALLS,index=False)

    lines=[]
    lines.append("="*76)
    lines.append("EARLY-PERSISTENCE META-MODEL V1 RESULTS")
    lines.append("="*76)
    lines.append(f"Selected meta threshold: {th:.2f}")
    lines.append(selection_note)
    lines.append("")
    lines.append("OLD VALIDATION WINNER")
    lines.append(
        f"accuracy {fmt(float(winner['accuracy']))} | "
        f"calls {int(winner['calls'])} | "
        f"avg ask {100*float(winner['avg_ask']):.1f}c | "
        f"avg time left {float(winner['avg_time_left']):.2f}m"
    )
    lines.append("")
    lines.append("OLD UNTOUCHED HOLDOUT")
    if hold_s:
        lines.append(
            f"accuracy {fmt(hold_s['accuracy'])} | calls {hold_s['calls']} | "
            f"avg ask {100*hold_s['avg_ask']:.1f}c | "
            f"median ask {100*hold_s['median_ask']:.1f}c | "
            f"<=40c {fmt(hold_s['pct_le40'])} | "
            f"20-40c {fmt(hold_s['pct_20_40'])} | "
            f"avg time left {hold_s['avg_time_left']:.2f}m"
        )
    else:
        lines.append("No calls.")
    lines.append("")
    lines.append("FRESH 250-CONTRACT REPORT-ONLY TEST")
    if fresh_s:
        fresh_contract_count=fresh["ticker"].nunique()
        coverage=fresh_s["calls"]/fresh_contract_count
        lines.append(
            f"accuracy {fmt(fresh_s['accuracy'])} | "
            f"calls {fresh_s['calls']} | "
            f"coverage {fmt(coverage)}"
        )
        lines.append(
            f"avg ask {100*fresh_s['avg_ask']:.1f}c | "
            f"median ask {100*fresh_s['median_ask']:.1f}c | "
            f"<=40c {fmt(fresh_s['pct_le40'])} | "
            f"20-40c {fmt(fresh_s['pct_20_40'])}"
        )
        lines.append(
            f"avg time left {fresh_s['avg_time_left']:.2f}m | "
            f"median {fresh_s['median_time_left']:.2f}m"
        )
        lines.append("")
        checks={
            "fresh accuracy >=93%":fresh_s["accuracy"]>=.93,
            "fresh calls >=15":fresh_s["calls"]>=15,
            "fresh avg ask <=40c":fresh_s["avg_ask"]<=.40,
            "fresh avg time left >=6m":fresh_s["avg_time_left"]>=6.,
        }
        lines.append("FRESH ACCEPTANCE")
        for k,v in checks.items():
            lines.append(f"{k}: {'PASS' if v else 'FAIL'}")
        lines.append(
            "OVERALL: "+("PASS" if all(checks.values()) else "NOT READY")
        )
    else:
        lines.append("No fresh calls. OVERALL: NOT READY")

    lines.append("")
    lines.append("INTEGRITY")
    lines.append("- Fresh 250 contracts are never used for training or threshold selection.")
    lines.append("- Base fair model remains the preserved target-aware RF+sigmoid.")
    lines.append("- Meta-model is trained only on old priced candidate snapshots.")
    lines.append("- Meta threshold is selected only on old chronological validation.")
    lines.append("- Fresh block is revealed once at the end.")
    lines.append("- Actual Kalshi asks are part of both development and fresh scoring.")
    lines.append("- No orders; bot.py unchanged.")

    SUMMARY.write_text("\n".join(lines))
    print("\n".join(lines))

if __name__=="__main__":
    main()
