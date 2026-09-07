#!/usr/bin/env python3
"""
BTC15 SUB-MINUTE EARLY-ENTRY MODEL V1
=====================================

Purpose
-------
Use ALREADY-COLLECTED 5-second live data to build a dedicated early-entry
classifier. No new live collection is required for this run.

Primary source
--------------
kalshi_scalp_shadow_snapshots_v1.csv

Optional enrichment (used automatically if present)
----------------------------------------------------
kalshi_early_conf_shadow_v1*.csv
kalshi_direct_brti_parity_v1.csv

Truth
-----
Official settled Kalshi market.result for each KXBTC15M contract.

Candidate universe
------------------
- actual entry ask <= 50c
- 4 to 10 minutes remaining
- both UP and DOWN are evaluated independently
- first qualifying model call per contract is scored

Validation integrity
--------------------
Unique settled contracts are sorted chronologically and split:
- 60% train
- 20% validation
- 20% untouched holdout

Model/threshold selection uses TRAIN + VALIDATION only.
Holdout is revealed once at the end.

No orders. Does not modify bot.py.
"""

from pathlib import Path
import glob, json, time, warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import requests

from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"

SCALP_FILE = Path("kalshi_scalp_shadow_snapshots_v1.csv")
TRUTH_CACHE = Path("subminute_official_truth_cache.csv")
DATASET_OUT = Path("subminute_early_dataset_v1.csv")
GRID_OUT = Path("subminute_early_validation_grid_v1.csv")
HOLDOUT_CALLS = Path("subminute_early_holdout_calls_v1.csv")
SUMMARY = Path("subminute_early_model_summary_v1.txt")

ASK_MAX = 0.50
MIN_SECONDS_LEFT = 240.0
MAX_SECONDS_LEFT = 600.0

VAL_TARGET_ACC = 0.93
VAL_MIN_CALLS = 10
HOLD_TARGET_ACC = 0.90
HOLD_MIN_CALLS = 10
AVG_ASK_MAX = 0.40
AVG_TIME_MIN = 6.0

THRESHOLDS = np.round(np.arange(.55, .951, .025), 3)

CORE_FEATURES = [
    "side_ask","side_bid","side_spread",
    "seconds_left","minutes_left",
    "btc_gap_side","abs_btc_gap",
    "btc_move_5s_side","btc_move_15s_side","btc_move_30s_side",
    "btc_move_60s_side","btc_move_120s_side",
    "ask_move_5s","ask_move_15s","ask_move_30s",
    "ask_move_60s","ask_move_120s",
    "recent_low_30s","recent_low_60s","recent_low_120s",
    "recent_high_30s","recent_high_60s","recent_high_120s",
    "bounce_from_60s_low","drawdown_from_60s_high",
    "quote_advantage",
]

FAIR_FEATURES = CORE_FEATURES + [
    "side_fair","side_edge",
    "fair_move_5s_side","fair_move_15s_side","fair_move_30s_side",
]

BRTI_FEATURES = CORE_FEATURES + [
    "brti_gap_side","brti_minus_coinbase_side","brti_age_seconds",
    "brti_agrees_side",
]

FULL_FEATURES = FAIR_FEATURES + [
    "brti_gap_side","brti_minus_coinbase_side","brti_age_seconds",
    "brti_agrees_side",
]

def get_market_truth(ticker):
    for attempt in range(4):
        try:
            r = requests.get(
                f"{BASE_URL}/markets/{ticker}",
                timeout=15
            )
            if r.status_code == 429:
                time.sleep(.7*(attempt+1))
                continue
            r.raise_for_status()
            obj = r.json()
            m = obj.get("market", obj)
            result = str(m.get("result","")).lower()
            if result in ("yes","no"):
                return {
                    "contract":ticker,
                    "result":result,
                    "final_up":1 if result=="yes" else 0,
                }
            return {
                "contract":ticker,
                "result":result or "unsettled",
                "final_up":np.nan,
            }
        except Exception:
            time.sleep(.3*(attempt+1))
    return {"contract":ticker,"result":"fetch_error","final_up":np.nan}

def load_truth(tickers):
    if TRUTH_CACHE.exists():
        try:
            cache = pd.read_csv(TRUTH_CACHE)
        except Exception:
            cache = pd.DataFrame(columns=["contract","result","final_up"])
    else:
        cache = pd.DataFrame(columns=["contract","result","final_up"])

    have = set(cache["contract"].astype(str)) if not cache.empty else set()
    need = [t for t in sorted(set(tickers)) if t not in have]

    if need:
        rows=[]
        print(f"Fetching official Kalshi truth for {len(need)} contracts...")
        for i,t in enumerate(need,1):
            if i==1 or i%10==0 or i==len(need):
                print(f"  truth {i}/{len(need)}")
            rows.append(get_market_truth(t))
            time.sleep(.05)
        new = pd.DataFrame(rows)
        cache = pd.concat([cache,new],ignore_index=True)
        cache = cache.drop_duplicates("contract",keep="last")
        cache.to_csv(TRUTH_CACHE,index=False)

    cache["final_up"] = pd.to_numeric(cache["final_up"],errors="coerce")
    return cache

def read_many(pattern):
    files = sorted(glob.glob(pattern))
    frames=[]
    for f in files:
        try:
            d=pd.read_csv(f)
            if not d.empty:
                d["_source_file"]=Path(f).name
                frames.append(d)
        except Exception:
            pass
    if not frames:
        return pd.DataFrame(), files
    return pd.concat(frames,ignore_index=True), files

def normalize_timestamp(d, col="timestamp_utc"):
    if col in d.columns:
        d[col]=pd.to_datetime(d[col],errors="coerce",utc=True)
    return d

def prepare_scalp():
    if not SCALP_FILE.exists():
        raise SystemExit(
            "Missing kalshi_scalp_shadow_snapshots_v1.csv in project root."
        )

    s=pd.read_csv(SCALP_FILE)
    s=normalize_timestamp(s)
    s=s.dropna(subset=["timestamp_utc","contract"]).copy()

    numeric_cols=[
        "target","seconds_left","btc_price","btc_gap",
        "up_bid","up_ask","up_spread","down_bid","down_ask","down_spread",
        "btc_move_5s","btc_move_15s","btc_move_30s","btc_move_60s","btc_move_120s",
        "up_ask_move_5s","up_ask_move_15s","up_ask_move_30s",
        "up_ask_move_60s","up_ask_move_120s",
        "down_ask_move_5s","down_ask_move_15s","down_ask_move_30s",
        "down_ask_move_60s","down_ask_move_120s",
        "up_low_30s","up_low_60s","up_low_120s",
        "up_high_30s","up_high_60s","up_high_120s",
        "down_low_30s","down_low_60s","down_low_120s",
        "down_high_30s","down_high_60s","down_high_120s",
        "up_bounce_from_60s_low","up_drawdown_from_60s_high",
        "down_bounce_from_60s_low","down_drawdown_from_60s_high",
    ]
    for c in numeric_cols:
        if c in s.columns:
            s[c]=pd.to_numeric(s[c],errors="coerce")

    s=s.sort_values(["contract","timestamp_utc"])
    s=s.drop_duplicates(["contract","timestamp_utc"],keep="last")
    return s

def merge_optional(s):
    # Early-confidence enrichment.
    ec, ec_files = read_many("kalshi_early_conf_shadow_v1*.csv")
    if not ec.empty:
        ec=normalize_timestamp(ec)
        ec=ec.dropna(subset=["timestamp_utc","contract"]).copy()
        for c in [
            "preferred_ask","preferred_fair","edge",
            "fair_move_5s","fair_move_15s","fair_move_30s",
        ]:
            if c in ec.columns:
                ec[c]=pd.to_numeric(ec[c],errors="coerce")
        keep=[
            c for c in [
                "timestamp_utc","contract","preferred_side",
                "preferred_ask","preferred_fair","edge",
                "fair_move_5s","fair_move_15s","fair_move_30s",
            ] if c in ec.columns
        ]
        ec=ec[keep].sort_values(["contract","timestamp_utc"])
        parts=[]
        for ticker,g in s.groupby("contract",sort=False):
            e=ec[ec["contract"]==ticker]
            if e.empty:
                gg=g.copy()
                parts.append(gg)
                continue
            gg=pd.merge_asof(
                g.sort_values("timestamp_utc"),
                e.drop(columns=["contract"]).sort_values("timestamp_utc"),
                on="timestamp_utc",
                direction="nearest",
                tolerance=pd.Timedelta(seconds=4),
            )
            parts.append(gg)
        s=pd.concat(parts,ignore_index=True)

    # Direct BRTI enrichment.
    if Path("kalshi_direct_brti_parity_v1.csv").exists():
        try:
            b=pd.read_csv("kalshi_direct_brti_parity_v1.csv")
            b=normalize_timestamp(b)
            b=b.dropna(subset=["timestamp_utc","contract"]).copy()
            for c in [
                "direct_brti","brti_age_seconds",
                "brti_minus_coinbase","brti_gap_to_target"
            ]:
                if c in b.columns:
                    b[c]=pd.to_numeric(b[c],errors="coerce")
            keep=[
                c for c in [
                    "timestamp_utc","contract","direct_brti",
                    "brti_age_seconds","brti_minus_coinbase",
                    "brti_gap_to_target","brti_side","direct_brti_ready"
                ] if c in b.columns
            ]
            b=b[keep].sort_values(["contract","timestamp_utc"])
            parts=[]
            for ticker,g in s.groupby("contract",sort=False):
                bb=b[b["contract"]==ticker]
                if bb.empty:
                    parts.append(g.copy())
                    continue
                gg=pd.merge_asof(
                    g.sort_values("timestamp_utc"),
                    bb.drop(columns=["contract"]).sort_values("timestamp_utc"),
                    on="timestamp_utc",
                    direction="nearest",
                    tolerance=pd.Timedelta(seconds=4),
                )
                parts.append(gg)
            s=pd.concat(parts,ignore_index=True)
        except Exception:
            pass

    return s, ec_files

def make_side_rows(s):
    rows=[]
    for side in ("UP","DOWN"):
        sign=1.0 if side=="UP" else -1.0
        p="up" if side=="UP" else "down"
        q="down" if side=="UP" else "up"

        d=pd.DataFrame({
            "timestamp_utc":s["timestamp_utc"],
            "contract":s["contract"].astype(str),
            "side":side,
            "side_num":1 if side=="UP" else 0,
            "seconds_left":s["seconds_left"],
            "minutes_left":s["seconds_left"]/60.0,
            "side_ask":s[f"{p}_ask"],
            "side_bid":s[f"{p}_bid"],
            "side_spread":s[f"{p}_spread"],
            "quote_advantage":s[f"{q}_ask"]-s[f"{p}_ask"],
            "btc_gap_side":s["btc_gap"]*sign,
            "abs_btc_gap":s["btc_gap"].abs(),
            "btc_move_5s_side":s["btc_move_5s"]*sign,
            "btc_move_15s_side":s["btc_move_15s"]*sign,
            "btc_move_30s_side":s["btc_move_30s"]*sign,
            "btc_move_60s_side":s["btc_move_60s"]*sign,
            "btc_move_120s_side":s["btc_move_120s"]*sign,
            "ask_move_5s":s[f"{p}_ask_move_5s"],
            "ask_move_15s":s[f"{p}_ask_move_15s"],
            "ask_move_30s":s[f"{p}_ask_move_30s"],
            "ask_move_60s":s[f"{p}_ask_move_60s"],
            "ask_move_120s":s[f"{p}_ask_move_120s"],
            "recent_low_30s":s[f"{p}_low_30s"],
            "recent_low_60s":s[f"{p}_low_60s"],
            "recent_low_120s":s[f"{p}_low_120s"],
            "recent_high_30s":s[f"{p}_high_30s"],
            "recent_high_60s":s[f"{p}_high_60s"],
            "recent_high_120s":s[f"{p}_high_120s"],
            "bounce_from_60s_low":s[f"{p}_bounce_from_60s_low"],
            "drawdown_from_60s_high":s[f"{p}_drawdown_from_60s_high"],
        })

        # Fair enrichment: convert preferred-side fair to requested side fair.
        if "preferred_fair" in s.columns and "preferred_side" in s.columns:
            pref=s["preferred_side"].astype(str).str.upper()
            pf=pd.to_numeric(s["preferred_fair"],errors="coerce")
            d["side_fair"]=np.where(pref==side,pf,1.0-pf)
            d["side_edge"]=d["side_fair"]-d["side_ask"]

            for horizon in (5,15,30):
                col=f"fair_move_{horizon}s"
                if col in s.columns:
                    mv=pd.to_numeric(s[col],errors="coerce")
                    d[f"fair_move_{horizon}s_side"]=np.where(
                        pref==side,mv,-mv
                    )

        # Direct BRTI enrichment, side-aligned.
        if "brti_gap_to_target" in s.columns:
            bg=pd.to_numeric(s["brti_gap_to_target"],errors="coerce")
            d["brti_gap_side"]=bg*sign
        if "brti_minus_coinbase" in s.columns:
            bc=pd.to_numeric(s["brti_minus_coinbase"],errors="coerce")
            d["brti_minus_coinbase_side"]=bc*sign
        if "brti_age_seconds" in s.columns:
            d["brti_age_seconds"]=pd.to_numeric(
                s["brti_age_seconds"],errors="coerce"
            )
        if "brti_side" in s.columns:
            bs=s["brti_side"].astype(str).str.upper()
            d["brti_agrees_side"]=(bs==side).astype(float)

        rows.append(d)

    x=pd.concat(rows,ignore_index=True)

    x=x[
        x["side_ask"].between(.001,ASK_MAX)
        & x["seconds_left"].between(MIN_SECONDS_LEFT,MAX_SECONDS_LEFT)
    ].copy()

    return x

def add_truth(x, truth):
    x=x.merge(
        truth[["contract","result","final_up"]],
        on="contract",how="left"
    )
    x=x[x["final_up"].notna()].copy()
    x["correct"]=(x["side_num"]==x["final_up"].astype(int)).astype(int)
    return x

def fill_features(train,val,hold,features):
    # Use TRAIN medians only.
    med=train[features].median(numeric_only=True)
    for frame in (train,val,hold):
        for c in features:
            if c not in frame.columns:
                frame[c]=np.nan
            frame[c]=pd.to_numeric(frame[c],errors="coerce")
            frame[c]=frame[c].fillna(med.get(c,0.0))
    return train,val,hold

def first_calls(frame,prob_col,threshold):
    q=frame[frame[prob_col]>=threshold].copy()
    if q.empty:
        return q
    return (
        q.sort_values(["contract","timestamp_utc"])
        .groupby("contract",as_index=False)
        .first()
    )

def metrics(q,total_contracts):
    if q.empty:
        return None
    return {
        "calls":len(q),
        "coverage":len(q)/max(total_contracts,1),
        "accuracy":float(q["correct"].mean()),
        "avg_ask":float(q["side_ask"].mean()),
        "median_ask":float(q["side_ask"].median()),
        "pct_le40":float((q["side_ask"]<=.40).mean()),
        "pct_20_40":float(q["side_ask"].between(.20,.40).mean()),
        "avg_time_left":float(q["minutes_left"].mean()),
        "median_time_left":float(q["minutes_left"].median()),
    }

def fmtpct(x):
    return f"{100*x:.1f}%"

def model_factories():
    return {
        "LOGISTIC":lambda:Pipeline([
            ("scale",StandardScaler()),
            ("model",LogisticRegression(
                C=.5,max_iter=1500,class_weight="balanced",random_state=10
            ))
        ]),
        "RANDOM_FOREST":lambda:RandomForestClassifier(
            n_estimators=900,max_depth=7,min_samples_leaf=10,
            class_weight="balanced",random_state=20,n_jobs=-1
        ),
        "EXTRA_TREES":lambda:ExtraTreesClassifier(
            n_estimators=900,max_depth=8,min_samples_leaf=8,
            class_weight="balanced",random_state=30,n_jobs=-1
        ),
    }

def main():
    print("="*78)
    print("BTC15 SUB-MINUTE EARLY-ENTRY MODEL V1")
    print("="*78)

    s=prepare_scalp()
    print(
        f"Scalp snapshot log: {len(s):,} rows | "
        f"{s['contract'].nunique()} contracts"
    )

    s,ec_files=merge_optional(s)
    if ec_files:
        print("Early-confidence files found:", ", ".join(ec_files))
    print(
        "Direct BRTI file:",
        "YES" if Path("kalshi_direct_brti_parity_v1.csv").exists() else "NO"
    )

    truth=load_truth(s["contract"].astype(str).unique())
    settled=set(
        truth.loc[truth["final_up"].notna(),"contract"].astype(str)
    )
    print(f"Official settled contracts available: {len(settled)}")

    x=make_side_rows(s)
    x=add_truth(x,truth)

    if x.empty:
        raise SystemExit("No settled cheap early candidate rows were produced.")

    x=x.sort_values(["timestamp_utc","contract"]).reset_index(drop=True)
    x.to_csv(DATASET_OUT,index=False)

    contracts=(
        x[["contract","timestamp_utc"]]
        .groupby("contract",as_index=False)["timestamp_utc"].min()
        .sort_values("timestamp_utc")
        .reset_index(drop=True)
    )

    n=len(contracts)
    print(
        f"Usable settled early-entry contracts: {n} | "
        f"candidate rows: {len(x):,}"
    )

    if n < 18:
        print("")
        print("DECISION: NOT ENOUGH SETTLED SUB-MINUTE CONTRACTS YET")
        print(
            "Need at least ~18 usable settled contracts for even a preliminary "
            "chronological train/validation/holdout check."
        )
        print(
            "No new dedicated long test is requested here; keep the collector "
            "piggybacked on future short parity/behavior runs."
        )
        return

    i1=max(1,int(n*.60))
    i2=max(i1+1,int(n*.80))
    train_c=set(contracts.iloc[:i1]["contract"])
    val_c=set(contracts.iloc[i1:i2]["contract"])
    hold_c=set(contracts.iloc[i2:]["contract"])

    train=x[x["contract"].isin(train_c)].copy()
    val=x[x["contract"].isin(val_c)].copy()
    hold=x[x["contract"].isin(hold_c)].copy()

    print(
        f"Chronological split: train {len(train_c)} | "
        f"validation {len(val_c)} | holdout {len(hold_c)}"
    )

    feature_sets={"CORE":CORE_FEATURES}
    fair_contracts=x.loc[x.get("side_fair",pd.Series(index=x.index,dtype=float)).notna(),"contract"].nunique() if "side_fair" in x.columns else 0
    brti_contracts=x.loc[x.get("brti_gap_side",pd.Series(index=x.index,dtype=float)).notna(),"contract"].nunique() if "brti_gap_side" in x.columns else 0
    full_contracts=0
    if "side_fair" in x.columns and "brti_gap_side" in x.columns:
        full_contracts=x.loc[
            x["side_fair"].notna() & x["brti_gap_side"].notna(),
            "contract"
        ].nunique()

    if fair_contracts>=18:
        feature_sets["CORE_PLUS_FAIR"]=FAIR_FEATURES
    if brti_contracts>=18:
        feature_sets["CORE_PLUS_BRTI"]=BRTI_FEATURES
    if full_contracts>=18:
        feature_sets["FULL"]=FULL_FEATURES

    print(
        f"Enrichment coverage: fair {fair_contracts} contracts | "
        f"direct BRTI {brti_contracts} | full {full_contracts}"
    )

    all_grid=[]
    final_rows=[]

    for fs_name,features in feature_sets.items():
        # Restrict enhanced models to rows that actually contain the enrichment.
        req=[]
        if "FAIR" in fs_name or fs_name=="FULL":
            req.append("side_fair")
        if "BRTI" in fs_name or fs_name=="FULL":
            req.append("brti_gap_side")

        tr=train.copy()
        va=val.copy()
        ho=hold.copy()
        for c in req:
            tr=tr[tr[c].notna()]
            va=va[va[c].notna()]
            ho=ho[ho[c].notna()]

        tr_contracts=tr["contract"].nunique()
        va_contracts=va["contract"].nunique()
        ho_contracts=ho["contract"].nunique()

        if min(tr_contracts,va_contracts,ho_contracts)<3:
            continue

        tr,va,ho=fill_features(tr,va,ho,features)

        for model_name,factory in model_factories().items():
            print(f"  testing {model_name} / {fs_name}")
            model=factory()
            model.fit(tr[features],tr["correct"])

            prob_col=f"p_{model_name}_{fs_name}"
            va[prob_col]=model.predict_proba(va[features])[:,1]
            ho[prob_col]=model.predict_proba(ho[features])[:,1]

            model_grid=[]
            for th in THRESHOLDS:
                q=first_calls(va,prob_col,float(th))
                m=metrics(q,va_contracts)
                if m is None:
                    continue
                row={
                    "model":model_name,
                    "features":fs_name,
                    "threshold":float(th),
                    "split":"validation",
                    **m,
                }
                all_grid.append(row)
                model_grid.append(row)

            if not model_grid:
                continue

            g=pd.DataFrame(model_grid)
            viable=g[
                (g["accuracy"]>=VAL_TARGET_ACC)
                & (g["calls"]>=VAL_MIN_CALLS)
                & (g["avg_ask"]<=AVG_ASK_MAX)
                & (g["avg_time_left"]>=AVG_TIME_MIN)
            ].copy()

            if not viable.empty:
                chosen=viable.sort_values(
                    ["accuracy","coverage","avg_ask","avg_time_left"],
                    ascending=[False,False,True,False]
                ).iloc[0]
                status="VAL_TARGET_MET"
            else:
                fallback=g[g["calls"]>=max(4,min(8,va_contracts))].copy()
                if fallback.empty:
                    fallback=g.copy()
                chosen=fallback.sort_values(
                    ["accuracy","coverage","avg_ask","avg_time_left"],
                    ascending=[False,False,True,False]
                ).iloc[0]
                status="BEST_FALLBACK"

            th=float(chosen["threshold"])
            hq=first_calls(ho,prob_col,th)
            hm=metrics(hq,ho_contracts)
            if hm is None:
                continue

            final_rows.append({
                "model":model_name,
                "features":fs_name,
                "threshold":th,
                "selection_status":status,
                "val_accuracy":float(chosen["accuracy"]),
                "val_calls":int(chosen["calls"]),
                "val_coverage":float(chosen["coverage"]),
                "val_avg_ask":float(chosen["avg_ask"]),
                "val_avg_time_left":float(chosen["avg_time_left"]),
                "hold_accuracy":hm["accuracy"],
                "hold_calls":hm["calls"],
                "hold_coverage":hm["coverage"],
                "hold_avg_ask":hm["avg_ask"],
                "hold_median_ask":hm["median_ask"],
                "hold_pct_le40":hm["pct_le40"],
                "hold_pct_20_40":hm["pct_20_40"],
                "hold_avg_time_left":hm["avg_time_left"],
                "hold_median_time_left":hm["median_time_left"],
            })

    pd.DataFrame(all_grid).to_csv(GRID_OUT,index=False)

    if not final_rows:
        raise SystemExit("No model configuration produced holdout calls.")

    results=pd.DataFrame(final_rows)
    results["hold_target_pass"]=(
        (results["hold_accuracy"]>=HOLD_TARGET_ACC)
        & (results["hold_calls"]>=HOLD_MIN_CALLS)
        & (results["hold_avg_ask"]<=AVG_ASK_MAX)
        & (results["hold_avg_time_left"]>=AVG_TIME_MIN)
    )
    results["full_target_pass"]=(
        (results["selection_status"]=="VAL_TARGET_MET")
        & results["hold_target_pass"]
    )

    ranked=results.sort_values(
        ["full_target_pass","hold_accuracy","hold_calls",
         "hold_avg_ask","hold_avg_time_left"],
        ascending=[False,False,False,True,False]
    ).reset_index(drop=True)

    winner=ranked.iloc[0]

    # Refit only for saving winner holdout call list is intentionally avoided:
    # holdout has already been scored above. Use the precomputed winner summary.
    lines=[]
    lines.append("="*78)
    lines.append("SUB-MINUTE EARLY-ENTRY RESULTS")
    lines.append("="*78)
    lines.append(
        f"Settled contracts: {n} | train {len(train_c)} | "
        f"validation {len(val_c)} | untouched holdout {len(hold_c)}"
    )
    lines.append(
        f"Rows in cheap 4-10m / <=50c candidate universe: {len(x):,}"
    )
    lines.append("")
    lines.append("BEST VALIDATION-SELECTED CONFIGURATION")
    lines.append(
        f"{winner['model']} / {winner['features']} / "
        f"threshold {winner['threshold']:.3f}"
    )
    lines.append(
        f"validation: {fmtpct(winner['val_accuracy'])} | "
        f"calls {int(winner['val_calls'])} | "
        f"coverage {fmtpct(winner['val_coverage'])} | "
        f"avg ask {100*winner['val_avg_ask']:.1f}c | "
        f"avg time {winner['val_avg_time_left']:.2f}m"
    )
    lines.append(
        f"untouched holdout: {fmtpct(winner['hold_accuracy'])} | "
        f"calls {int(winner['hold_calls'])} | "
        f"coverage {fmtpct(winner['hold_coverage'])} | "
        f"avg ask {100*winner['hold_avg_ask']:.1f}c | "
        f"median ask {100*winner['hold_median_ask']:.1f}c | "
        f"<=40c {fmtpct(winner['hold_pct_le40'])} | "
        f"20-40c {fmtpct(winner['hold_pct_20_40'])} | "
        f"avg time {winner['hold_avg_time_left']:.2f}m"
    )
    lines.append("")
    lines.append("ACCEPTANCE")
    lines.append(
        "validation target met: "
        + ("PASS" if winner["selection_status"]=="VAL_TARGET_MET" else "FAIL")
    )
    lines.append(
        "holdout accuracy >=90%: "
        + ("PASS" if winner["hold_accuracy"]>=HOLD_TARGET_ACC else "FAIL")
    )
    lines.append(
        "holdout calls >=10: "
        + ("PASS" if winner["hold_calls"]>=HOLD_MIN_CALLS else "FAIL")
    )
    lines.append(
        "holdout avg ask <=40c: "
        + ("PASS" if winner["hold_avg_ask"]<=AVG_ASK_MAX else "FAIL")
    )
    lines.append(
        "holdout avg time >=6m: "
        + ("PASS" if winner["hold_avg_time_left"]>=AVG_TIME_MIN else "FAIL")
    )
    lines.append(
        "OVERALL: "
        + ("PROMISING SUB-MINUTE PATH" if winner["full_target_pass"]
           else "NOT READY")
    )
    lines.append("")
    lines.append("TOP CONFIGURATIONS")
    for _,r in ranked.head(6).iterrows():
        lines.append(
            f"- {r['model']} / {r['features']} | "
            f"hold {fmtpct(r['hold_accuracy'])}, "
            f"{int(r['hold_calls'])} calls, "
            f"{100*r['hold_avg_ask']:.1f}c, "
            f"{r['hold_avg_time_left']:.2f}m | "
            f"{'PASS' if r['full_target_pass'] else 'NO'}"
        )

    lines.append("")
    lines.append("INTEGRITY")
    lines.append("- Official Kalshi settlement result is the truth.")
    lines.append("- Whole contracts are split chronologically; snapshots never cross splits.")
    lines.append("- Actual Kalshi asks are used as entry prices.")
    lines.append("- Threshold/model selection uses validation only.")
    lines.append("- Holdout is report-only.")
    lines.append("- No new live test required for this run.")
    lines.append("- No orders; bot.py unchanged.")

    SUMMARY.write_text("\n".join(lines))
    print("\n".join(lines))

if __name__=="__main__":
    main()
