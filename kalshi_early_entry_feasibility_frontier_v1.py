#!/usr/bin/env python3
"""
BTC15 EARLY-ENTRY FEASIBILITY FRONTIER V1
=========================================

Purpose
-------
Answer one question honestly:

    How good can early entry realistically get using only our current
    1-minute historical feature set and actual Kalshi prices?

This is NOT a live test.
This is NOT a threshold tweak around one rule.
This compares several distinct model families and candidate-pool structures.

Integrity
---------
OLD priced data only for model/threshold development:
- brti_calibration_results.csv
- btc_35d_live_cache.csv
- kalshi_kxbtc15m_1m_candles_cache.csv

Chronological split of OLD priced contracts:
- 60% model-train
- 20% model-validation
- 20% old holdout

Fresh 250-contract block:
- fresh_oos_market_manifest.csv
- fresh_oos_candles_cache.csv

The fresh block is NEVER used to fit a model or choose a threshold.
It is report-only after the old-development winners are frozen.

Compared model families
-----------------------
1) Logistic regression
2) Random forest
3) Gradient boosting
4) Extra Trees

Fixed candidate pools
---------------------
A) CHEAP50_BROAD
   ask <= 50c, fair >= 60%, edge >= 3%, 4-10m left, abs gap >= $10
B) CHEAP45_BALANCED
   ask <= 45c, fair >= 65%, edge >= 5%, 4-10m left, abs gap >= $15
C) CHEAP40_STRICT
   ask <= 40c, fair >= 70%, edge >= 8%, 4-10m left, abs gap >= $20

For every model+pool, a model-probability threshold is selected on OLD
VALIDATION ONLY. Fresh 250 contracts are revealed only after that.

No orders. bot.py unchanged.
"""

from pathlib import Path
from zoneinfo import ZoneInfo
import re, warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import (
    RandomForestClassifier,
    ExtraTreesClassifier,
    GradientBoostingClassifier,
)

CAL = Path("brti_calibration_results.csv")
BTC_CACHE = Path("btc_35d_live_cache.csv")
OLD_CANDLES = Path("kalshi_kxbtc15m_1m_candles_cache.csv")
FRESH_MANIFEST = Path("fresh_oos_market_manifest.csv")
FRESH_CANDLES = Path("fresh_oos_candles_cache.csv")

SUMMARY = Path("early_entry_feasibility_frontier_summary.txt")
DETAIL = Path("early_entry_feasibility_frontier_results.csv")
FRESH_CALLS = Path("early_entry_feasibility_best_fresh_calls.csv")

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
    "preferred_fair","preferred_ask","edge","remaining",
    "abs_dist_target","dist_over_range5","range5","vol5",
    "move1","move2","move3","move5",
    "support1","support2","support3","support5",
    "dist_per_min_remaining",
    "preferred_agrees_current",
    "fair_ask_ratio",
    "edge_per_time",
    "gap_per_time",
]

POOLS = {
    "CHEAP50_BROAD": dict(
        ask_max=.50, fair_min=.60, edge_min=.03,
        min_tl=4., max_tl=10., min_gap=10.,
    ),
    "CHEAP45_BALANCED": dict(
        ask_max=.45, fair_min=.65, edge_min=.05,
        min_tl=4., max_tl=10., min_gap=15.,
    ),
    "CHEAP40_STRICT": dict(
        ask_max=.40, fair_min=.70, edge_min=.08,
        min_tl=4., max_tl=10., min_gap=20.,
    ),
}

def parse_contract_times(ticker):
    m = re.search(
        r"KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-",
        str(ticker).upper()
    )
    if not m:
        return pd.NaT,pd.NaT
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
    d[ts_col] = pd.to_datetime(d[ts_col],errors="coerce",utc=True)
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
    f["start"]=pd.to_datetime(f["start"],errors="coerce",utc=True)
    f["close"]=pd.to_datetime(f["close"],errors="coerce",utc=True)
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

    if not parts:
        raise SystemExit("No snapshots aligned to Kalshi prices.")

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

    d["fair_ask_ratio"]=(
        d["preferred_fair"]/d["preferred_ask"].clip(lower=.01)
    )
    d["edge_per_time"]=d["edge"]/d["remaining"].clip(lower=.25)
    d["gap_per_time"]=(
        d["abs_dist_target"]/d["remaining"].clip(lower=.25)
    )
    return d

def pool_frame(d,p):
    return d[
        (d["preferred_ask"]<=p["ask_max"])
        & (d["preferred_fair"]>=p["fair_min"])
        & (d["edge"]>=p["edge_min"])
        & d["remaining"].between(p["min_tl"],p["max_tl"])
        & (d["abs_dist_target"]>=p["min_gap"])
    ].copy()

def model_factories():
    return {
        "LOGISTIC": lambda: Pipeline([
            ("scale",StandardScaler()),
            ("clf",LogisticRegression(
                solver="lbfgs",C=.7,max_iter=1500,
                class_weight="balanced",random_state=91
            ))
        ]),
        "RANDOM_FOREST": lambda: RandomForestClassifier(
            n_estimators=1000,max_depth=7,min_samples_leaf=8,
            class_weight="balanced",random_state=92,n_jobs=-1
        ),
        "EXTRA_TREES": lambda: ExtraTreesClassifier(
            n_estimators=1000,max_depth=8,min_samples_leaf=6,
            class_weight="balanced",random_state=93,n_jobs=-1
        ),
        "GRADIENT_BOOSTING": lambda: GradientBoostingClassifier(
            n_estimators=250,learning_rate=.035,max_depth=3,
            min_samples_leaf=8,subsample=.85,random_state=94
        ),
    }

def first_calls(frame,threshold):
    q=frame[frame["model_prob"]>=threshold].copy()
    if q.empty:
        return q
    return (
        q.sort_values(["ticker","elapsed"])
        .groupby("ticker",as_index=False)
        .first()
    )

def score(q,total_contracts):
    if q.empty:
        return None
    return {
        "calls":len(q),
        "coverage":len(q)/max(total_contracts,1),
        "accuracy":float(q["correct"].mean()),
        "avg_ask":float(q["preferred_ask"].mean()),
        "median_ask":float(q["preferred_ask"].median()),
        "pct_le40":float((q["preferred_ask"]<=.40).mean()),
        "pct_20_40":float(q["preferred_ask"].between(.20,.40).mean()),
        "avg_time_left":float(q["remaining"].mean()),
        "median_time_left":float(q["remaining"].median()),
    }

def choose_threshold(val,total_contracts):
    rows=[]
    for th in np.arange(.50,.951,.01):
        q=first_calls(val,float(th))
        s=score(q,total_contracts)
        if s is None:
            continue
        rows.append({"threshold":round(float(th),2),**s})

    g=pd.DataFrame(rows)
    if g.empty:
        return None,None

    viable=g[(g["accuracy"]>=.93)&(g["calls"]>=10)].copy()
    if not viable.empty:
        viable=viable.sort_values(
            ["accuracy","calls","avg_ask","avg_time_left"],
            ascending=[False,False,True,False]
        )
        return viable.iloc[0],"TARGET_MET"

    fallback=g[g["calls"]>=8].copy()
    if fallback.empty:
        fallback=g.copy()

    fallback=fallback.sort_values(
        ["accuracy","calls","avg_ask","avg_time_left"],
        ascending=[False,False,True,False]
    )
    return fallback.iloc[0],"BEST_FALLBACK"

def fpc(x):
    return "N/A" if x is None else f"{100*x:.1f}%"

def main():
    required=[CAL,BTC_CACHE,OLD_CANDLES,FRESH_MANIFEST,FRESH_CANDLES]
    missing=[str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit("Missing required files: "+", ".join(missing))

    print("="*78)
    print("BTC15 EARLY-ENTRY FEASIBILITY FRONTIER V1")
    print("="*78)

    btc=load_btc()
    old=load_old_contracts()
    fresh=load_fresh_contracts()
    old_c=load_candles(OLD_CANDLES)
    fresh_c=load_candles(FRESH_CANDLES)

    print("Training preserved target-aware fair model...")
    rf,sig=train_base_fair(old,btc)

    print("Building OLD priced snapshots...")
    old_f=build_features(old,btc,rf,sig,old=True)
    old_p=align_prices(old_f,old_c)

    print("Building FRESH 250 priced snapshots (report-only)...")
    fresh_f=build_features(fresh,btc,rf,sig,old=False)
    fresh_p=align_prices(fresh_f,fresh_c)

    old_contracts=(
        old_p[["ticker","start"]].drop_duplicates()
        .sort_values("start").reset_index(drop=True)
    )
    n=len(old_contracts)
    i1,i2=int(n*.60),int(n*.80)

    train_c=set(old_contracts.iloc[:i1]["ticker"])
    val_c=set(old_contracts.iloc[i1:i2]["ticker"])
    hold_c=set(old_contracts.iloc[i2:]["ticker"])

    print(
        f"OLD split: train {len(train_c)} | "
        f"validation {len(val_c)} | holdout {len(hold_c)}"
    )

    all_results=[]
    frozen=[]

    for pool_name,p in POOLS.items():
        old_pool=pool_frame(old_p,p)
        fresh_pool=pool_frame(fresh_p,p)

        train=old_pool[old_pool["ticker"].isin(train_c)].copy()
        val=old_pool[old_pool["ticker"].isin(val_c)].copy()
        hold=old_pool[old_pool["ticker"].isin(hold_c)].copy()

        if train["correct"].nunique()<2 or len(train)<30:
            continue

        for model_name,factory in model_factories().items():
            print(f"Testing {model_name} / {pool_name} ...")
            model=factory()
            model.fit(train[META_FEATURES],train["correct"])

            val2=val.copy()
            hold2=hold.copy()
            fresh2=fresh_pool.copy()

            val2["model_prob"]=model.predict_proba(
                val2[META_FEATURES]
            )[:,1]
            hold2["model_prob"]=model.predict_proba(
                hold2[META_FEATURES]
            )[:,1]
            fresh2["model_prob"]=model.predict_proba(
                fresh2[META_FEATURES]
            )[:,1]

            selected,status=choose_threshold(
                val2,len(val_c)
            )
            if selected is None:
                continue

            th=float(selected["threshold"])

            hold_calls=first_calls(hold2,th)
            fresh_calls=first_calls(fresh2,th)

            hs=score(hold_calls,len(hold_c))
            fs=score(fresh_calls,fresh["ticker"].nunique())

            row={
                "model":model_name,
                "pool":pool_name,
                "threshold":th,
                "selection_status":status,
                "val_calls":int(selected["calls"]),
                "val_accuracy":float(selected["accuracy"]),
                "val_coverage":float(selected["coverage"]),
                "val_avg_ask":float(selected["avg_ask"]),
                "val_avg_time_left":float(selected["avg_time_left"]),
            }

            for prefix,s in [("hold",hs),("fresh",fs)]:
                if s is None:
                    row.update({
                        f"{prefix}_calls":0,
                        f"{prefix}_accuracy":np.nan,
                        f"{prefix}_coverage":0.,
                        f"{prefix}_avg_ask":np.nan,
                        f"{prefix}_median_ask":np.nan,
                        f"{prefix}_pct_le40":np.nan,
                        f"{prefix}_pct_20_40":np.nan,
                        f"{prefix}_avg_time_left":np.nan,
                        f"{prefix}_median_time_left":np.nan,
                    })
                else:
                    for k,v in s.items():
                        row[f"{prefix}_{k}"]=v

            all_results.append(row)
            frozen.append(
                (model_name,pool_name,th,model,fresh_calls)
            )

    results=pd.DataFrame(all_results)
    if results.empty:
        raise SystemExit("No frontier configurations produced results.")

    results.to_csv(DETAIL,index=False)

    # Choose a report winner WITHOUT optimizing on fresh accuracy.
    # First use old holdout as confirmation of development generalization.
    eligible=results[
        (results["hold_calls"]>=10)
        & (results["hold_accuracy"]>=.90)
        & (results["hold_avg_ask"]<=.45)
        & (results["hold_avg_time_left"]>=5.5)
    ].copy()

    if not eligible.empty:
        eligible=eligible.sort_values(
            ["hold_accuracy","hold_calls","hold_avg_ask","hold_avg_time_left"],
            ascending=[False,False,True,False]
        )
        winner=eligible.iloc[0]
        winner_note="Winner selected using OLD HOLDOUT constraints; fresh remains report-only."
    else:
        candidates=results[results["hold_calls"]>=8].copy()
        if candidates.empty:
            candidates=results.copy()
        candidates=candidates.sort_values(
            ["hold_accuracy","hold_calls","hold_avg_ask","hold_avg_time_left"],
            ascending=[False,False,True,False]
        )
        winner=candidates.iloc[0]
        winner_note="No old-holdout configuration cleared 90%; strongest honest fallback."

    wm=winner["model"]
    wp=winner["pool"]
    wt=float(winner["threshold"])

    # Recover already-frozen fresh calls for the selected old winner.
    best_fresh=None
    for model_name,pool_name,th,model,fq in frozen:
        if model_name==wm and pool_name==wp and abs(th-wt)<1e-9:
            best_fresh=fq
            break
    if best_fresh is not None:
        best_fresh.to_csv(FRESH_CALLS,index=False)

    lines=[]
    lines.append("="*78)
    lines.append("EARLY-ENTRY 1-MINUTE FEASIBILITY FRONTIER")
    lines.append("="*78)
    lines.append("")
    lines.append("SELECTED OLD-DEVELOPMENT CONFIGURATION")
    lines.append(f"model: {wm}")
    lines.append(f"pool: {wp}")
    lines.append(f"threshold: {wt:.2f}")
    lines.append(winner_note)
    lines.append("")
    lines.append(
        f"OLD VALIDATION: accuracy {fpc(winner['val_accuracy'])} | "
        f"calls {int(winner['val_calls'])} | "
        f"coverage {fpc(winner['val_coverage'])} | "
        f"avg ask {100*winner['val_avg_ask']:.1f}c | "
        f"avg time left {winner['val_avg_time_left']:.2f}m"
    )
    lines.append(
        f"OLD HOLDOUT: accuracy {fpc(winner['hold_accuracy'])} | "
        f"calls {int(winner['hold_calls'])} | "
        f"coverage {fpc(winner['hold_coverage'])} | "
        f"avg ask {100*winner['hold_avg_ask']:.1f}c | "
        f"avg time left {winner['hold_avg_time_left']:.2f}m"
    )
    lines.append(
        f"FRESH 250 REPORT: accuracy {fpc(winner['fresh_accuracy'])} | "
        f"calls {int(winner['fresh_calls'])} | "
        f"coverage {fpc(winner['fresh_coverage'])} | "
        f"avg ask {100*winner['fresh_avg_ask']:.1f}c | "
        f"avg time left {winner['fresh_avg_time_left']:.2f}m"
    )
    lines.append("")

    fresh15=results[results["fresh_calls"]>=15].copy()
    if not fresh15.empty:
        best_acc=fresh15.sort_values(
            ["fresh_accuracy","fresh_calls"],
            ascending=[False,False]
        ).iloc[0]
        lines.append("FRESH FRONTIER — REPORT ONLY")
        lines.append(
            f"Best accuracy with >=15 fresh calls: "
            f"{fpc(best_acc['fresh_accuracy'])} | "
            f"{best_acc['model']} / {best_acc['pool']} | "
            f"calls {int(best_acc['fresh_calls'])} | "
            f"avg ask {100*best_acc['fresh_avg_ask']:.1f}c | "
            f"time {best_acc['fresh_avg_time_left']:.2f}m"
        )

        f90=fresh15[ fresh15["fresh_accuracy"]>=.90 ].copy()
        if not f90.empty:
            r=f90.sort_values(
                ["fresh_coverage","fresh_accuracy"],
                ascending=[False,False]
            ).iloc[0]
            lines.append(
                f"Best fresh coverage at >=90% accuracy: "
                f"{fpc(r['fresh_coverage'])} | "
                f"{r['model']} / {r['pool']} | "
                f"accuracy {fpc(r['fresh_accuracy'])}"
            )
        else:
            lines.append("No configuration with >=15 fresh calls reached 90% accuracy.")

        f93=fresh15[ fresh15["fresh_accuracy"]>=.93 ].copy()
        if not f93.empty:
            r=f93.sort_values(
                ["fresh_coverage","fresh_accuracy"],
                ascending=[False,False]
            ).iloc[0]
            lines.append(
                f"Best fresh coverage at >=93% accuracy: "
                f"{fpc(r['fresh_coverage'])} | "
                f"{r['model']} / {r['pool']} | "
                f"accuracy {fpc(r['fresh_accuracy'])}"
            )
        else:
            lines.append("No configuration with >=15 fresh calls reached 93% accuracy.")

    lines.append("")
    lines.append("DECISION")
    fresh_acc=winner["fresh_accuracy"]
    fresh_calls=int(winner["fresh_calls"])
    fresh_ask=winner["fresh_avg_ask"]
    fresh_time=winner["fresh_avg_time_left"]

    if (
        pd.notna(fresh_acc)
        and fresh_acc>=.93
        and fresh_calls>=15
        and fresh_ask<=.40
        and fresh_time>=6.
    ):
        lines.append("1-MINUTE EARLY ENTRY: VIABLE")
        lines.append(
            "A genuinely fresh configuration cleared accuracy, price, timing, and sample-size targets."
        )
    else:
        lines.append("1-MINUTE EARLY ENTRY: CEILING NOT GOOD ENOUGH")
        lines.append(
            "Do not keep threshold-tuning the 1-minute architecture. "
            "Move early entry to sub-minute information: 5s/15s/30s momentum, "
            "direct BRTI, live Kalshi price persistence/lead-lag, and reversal structure."
        )

    lines.append("")
    lines.append("INTEGRITY")
    lines.append("- Fresh 250 contracts never used for model fitting.")
    lines.append("- Fresh 250 contracts never used for threshold selection.")
    lines.append("- Candidate pools fixed before fresh scoring.")
    lines.append("- Actual Kalshi asks used throughout.")
    lines.append("- Multiple distinct model families compared.")
    lines.append("- No orders; bot.py unchanged.")

    SUMMARY.write_text("\n".join(lines))
    print("\n".join(lines))

if __name__=="__main__":
    main()
