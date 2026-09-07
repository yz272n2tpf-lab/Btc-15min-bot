#!/usr/bin/env python3
"""
BTC15 SUB-MINUTE WALK-FORWARD DEVELOPMENT V1
=============================================

Uses the ALREADY-BUILT:
    subminute_early_dataset_v1.csv

Purpose
-------
Use the existing 57 settled sub-minute contracts more efficiently with
chronological expanding-window walk-forward evaluation.

This is DEVELOPMENT ONLY.
The previously viewed 57-contract sample is no longer called pristine holdout.

No new live data is required.

Method
------
- Sort unique contracts chronologically.
- Keep at least 20 earliest contracts as initial training.
- Evaluate repeated next-7-contract blocks.
- Refit on all past contracts before each block.
- Aggregate genuinely out-of-fold calls across later contracts.
- Compare Logistic / Random Forest / Extra Trees.
- Compare CORE and optional enriched feature sets when enough fields exist.
- Thresholds are evaluated across the walk-forward predictions.
- Require >=12 total walk-forward calls before a candidate can be considered.

Target
------
Development candidate should aim for:
- accuracy >= 90% preliminary
- >=12 walk-forward calls
- avg ask <= 40c
- avg time left >= 6m

93-95% remains the product target, but this script does not pretend a
57-contract development sample can prove that level.

Outputs
-------
subminute_walkforward_grid_v1.csv
subminute_walkforward_calls_v1.csv
subminute_walkforward_summary_v1.txt

No orders. bot.py unchanged.
"""

from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DATA = Path("subminute_early_dataset_v1.csv")
GRID = Path("subminute_walkforward_grid_v1.csv")
CALLS = Path("subminute_walkforward_calls_v1.csv")
SUMMARY = Path("subminute_walkforward_summary_v1.txt")

CORE = [
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

FAIR_EXTRA = [
    "side_fair","side_edge",
    "fair_move_5s_side","fair_move_15s_side","fair_move_30s_side",
]

BRTI_EXTRA = [
    "brti_gap_side","brti_minus_coinbase_side",
    "brti_age_seconds","brti_agrees_side",
]

THRESHOLDS = np.round(np.arange(.50,.926,.025),3)

INITIAL_TRAIN_CONTRACTS = 20
TEST_BLOCK = 7
MIN_TOTAL_CALLS = 12

TARGET_ACC = .90
TARGET_ASK = .40
TARGET_TIME = 6.0

def factories():
    return {
        "LOGISTIC": lambda: Pipeline([
            ("scale",StandardScaler()),
            ("model",LogisticRegression(
                C=.5,max_iter=1500,
                class_weight="balanced",
                random_state=101
            ))
        ]),
        "RANDOM_FOREST": lambda: RandomForestClassifier(
            n_estimators=700,
            max_depth=7,
            min_samples_leaf=8,
            class_weight="balanced",
            random_state=202,
            n_jobs=-1
        ),
        "EXTRA_TREES": lambda: ExtraTreesClassifier(
            n_estimators=700,
            max_depth=8,
            min_samples_leaf=6,
            class_weight="balanced",
            random_state=303,
            n_jobs=-1
        ),
    }

def fill_train_medians(train,test,features):
    med={}
    for c in features:
        train[c]=pd.to_numeric(train[c],errors="coerce")
        test[c]=pd.to_numeric(test[c],errors="coerce")
        m=train[c].median()
        if pd.isna(m):
            m=0.0
        med[c]=float(m)
        train[c]=train[c].fillna(m)
        test[c]=test[c].fillna(m)
    return train,test

def first_calls(frame,prob_col,threshold):
    q=frame[frame[prob_col]>=threshold].copy()
    if q.empty:
        return q
    return (
        q.sort_values(["contract","timestamp_utc"])
        .groupby("contract",as_index=False)
        .first()
    )

def score(q,total_contracts):
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

def pct(x):
    return f"{100*x:.1f}%"

def main():
    if not DATA.exists():
        raise SystemExit(
            "Missing subminute_early_dataset_v1.csv. "
            "Run kalshi_subminute_early_entry_model_v1.py first."
        )

    d=pd.read_csv(DATA)
    d["timestamp_utc"]=pd.to_datetime(
        d["timestamp_utc"],errors="coerce",utc=True
    )
    d=d.dropna(subset=["timestamp_utc","contract","correct"]).copy()
    d["correct"]=pd.to_numeric(d["correct"],errors="coerce").astype(int)

    contracts=(
        d.groupby("contract",as_index=False)["timestamp_utc"]
        .min()
        .sort_values("timestamp_utc")
        .reset_index(drop=True)
    )
    n=len(contracts)

    print("="*78)
    print("BTC15 SUB-MINUTE WALK-FORWARD DEVELOPMENT V1")
    print("="*78)
    print(f"Contracts available: {n} | rows: {len(d):,}")

    if n < 35:
        raise SystemExit("Not enough contracts for useful walk-forward development.")

    feature_sets={"CORE":CORE}

    fair_cols=[c for c in FAIR_EXTRA if c in d.columns]
    brti_cols=[c for c in BRTI_EXTRA if c in d.columns]

    fair_contracts=(
        d.loc[d[fair_cols].notna().any(axis=1),"contract"].nunique()
        if fair_cols else 0
    )
    brti_contracts=(
        d.loc[d[brti_cols].notna().any(axis=1),"contract"].nunique()
        if brti_cols else 0
    )

    if len(fair_cols)==len(FAIR_EXTRA) and fair_contracts>=30:
        feature_sets["CORE_PLUS_FAIR"]=CORE+FAIR_EXTRA
    if len(brti_cols)==len(BRTI_EXTRA) and brti_contracts>=30:
        feature_sets["CORE_PLUS_BRTI"]=CORE+BRTI_EXTRA
    if (
        len(fair_cols)==len(FAIR_EXTRA)
        and len(brti_cols)==len(BRTI_EXTRA)
        and min(fair_contracts,brti_contracts)>=30
    ):
        feature_sets["FULL"]=CORE+FAIR_EXTRA+BRTI_EXTRA

    print(
        f"Enrichment contracts: fair={fair_contracts} | "
        f"BRTI={brti_contracts}"
    )
    print("Feature sets:", ", ".join(feature_sets))

    # Build chronological folds.
    folds=[]
    train_end=INITIAL_TRAIN_CONTRACTS
    fold_id=1
    while train_end < n:
        test_end=min(train_end+TEST_BLOCK,n)
        train_ids=set(contracts.iloc[:train_end]["contract"])
        test_ids=set(contracts.iloc[train_end:test_end]["contract"])
        if not test_ids:
            break
        folds.append((fold_id,train_ids,test_ids))
        fold_id+=1
        train_end=test_end

    print(
        "Walk-forward folds:",
        " | ".join(
            f"{fid}:train{len(tr)}->test{len(te)}"
            for fid,tr,te in folds
        )
    )

    prediction_frames=[]

    for fs_name,features in feature_sets.items():
        for model_name,factory in factories().items():
            print(f"  {model_name} / {fs_name}")
            fold_preds=[]

            for fid,train_ids,test_ids in folds:
                tr=d[d["contract"].isin(train_ids)].copy()
                te=d[d["contract"].isin(test_ids)].copy()

                # Enhanced models use only rows where enrichment exists.
                if "FAIR" in fs_name or fs_name=="FULL":
                    tr=tr[tr["side_fair"].notna()].copy()
                    te=te[te["side_fair"].notna()].copy()
                if "BRTI" in fs_name or fs_name=="FULL":
                    tr=tr[tr["brti_gap_side"].notna()].copy()
                    te=te[te["brti_gap_side"].notna()].copy()

                if (
                    tr["contract"].nunique()<12
                    or te["contract"].nunique()<2
                    or tr["correct"].nunique()<2
                ):
                    continue

                tr,te=fill_train_medians(tr,te,features)

                model=factory()
                model.fit(tr[features],tr["correct"])

                te=te.copy()
                te["model_prob"]=model.predict_proba(te[features])[:,1]
                te["model"]=model_name
                te["features"]=fs_name
                te["fold"]=fid
                fold_preds.append(te)

            if fold_preds:
                prediction_frames.append(pd.concat(fold_preds,ignore_index=True))

    if not prediction_frames:
        raise SystemExit("No walk-forward predictions produced.")

    pred=pd.concat(prediction_frames,ignore_index=True)

    rows=[]
    call_frames=[]

    for (model_name,fs_name),g in pred.groupby(["model","features"]):
        tested_contracts=g["contract"].nunique()

        for th in THRESHOLDS:
            q=first_calls(g,"model_prob",float(th))
            m=score(q,tested_contracts)
            if m is None:
                continue

            rows.append({
                "model":model_name,
                "features":fs_name,
                "threshold":float(th),
                "tested_contracts":tested_contracts,
                **m,
            })

    grid=pd.DataFrame(rows)
    grid.to_csv(GRID,index=False)

    viable=grid[
        (grid["calls"]>=MIN_TOTAL_CALLS)
        & (grid["avg_ask"]<=TARGET_ASK)
        & (grid["avg_time_left"]>=TARGET_TIME)
    ].copy()

    if viable.empty:
        viable=grid[grid["calls"]>=8].copy()

    if viable.empty:
        viable=grid.copy()

    ranked=viable.sort_values(
        ["accuracy","calls","coverage","avg_ask","avg_time_left"],
        ascending=[False,False,False,True,False]
    ).reset_index(drop=True)

    winner=ranked.iloc[0]

    wg=pred[
        (pred["model"]==winner["model"])
        & (pred["features"]==winner["features"])
    ].copy()
    wq=first_calls(wg,"model_prob",float(winner["threshold"]))
    wq.to_csv(CALLS,index=False)

    target_pass=bool(
        winner["accuracy"]>=TARGET_ACC
        and winner["calls"]>=MIN_TOTAL_CALLS
        and winner["avg_ask"]<=TARGET_ASK
        and winner["avg_time_left"]>=TARGET_TIME
    )

    lines=[]
    lines.append("="*78)
    lines.append("SUB-MINUTE WALK-FORWARD DEVELOPMENT RESULTS")
    lines.append("="*78)
    lines.append(
        f"Contracts: {n} | folds: {len(folds)} | "
        f"minimum calls required: {MIN_TOTAL_CALLS}"
    )
    lines.append("")
    lines.append("BEST WALK-FORWARD CONFIGURATION")
    lines.append(
        f"{winner['model']} / {winner['features']} / "
        f"threshold {winner['threshold']:.3f}"
    )
    lines.append(
        f"accuracy {pct(winner['accuracy'])} | "
        f"calls {int(winner['calls'])} | "
        f"coverage {pct(winner['coverage'])}"
    )
    lines.append(
        f"avg ask {100*winner['avg_ask']:.1f}c | "
        f"median ask {100*winner['median_ask']:.1f}c | "
        f"<=40c {pct(winner['pct_le40'])} | "
        f"20-40c {pct(winner['pct_20_40'])}"
    )
    lines.append(
        f"avg time left {winner['avg_time_left']:.2f}m | "
        f"median {winner['median_time_left']:.2f}m"
    )
    lines.append("")
    lines.append("PRELIMINARY DEVELOPMENT CHECK")
    lines.append(
        f"accuracy >=90%: {'PASS' if winner['accuracy']>=TARGET_ACC else 'FAIL'}"
    )
    lines.append(
        f"calls >=12: {'PASS' if winner['calls']>=MIN_TOTAL_CALLS else 'FAIL'}"
    )
    lines.append(
        f"avg ask <=40c: {'PASS' if winner['avg_ask']<=TARGET_ASK else 'FAIL'}"
    )
    lines.append(
        f"avg time >=6m: {'PASS' if winner['avg_time_left']>=TARGET_TIME else 'FAIL'}"
    )
    lines.append(
        "OVERALL: "
        + ("FREEZE CANDIDATE FOR FUTURE FORWARD VALIDATION"
           if target_pass else
           "NO STABLE SUB-MINUTE CANDIDATE YET")
    )

    lines.append("")
    lines.append("TOP 6 WALK-FORWARD CONFIGURATIONS")
    for _,r in ranked.head(6).iterrows():
        lines.append(
            f"- {r['model']} / {r['features']} / p>={r['threshold']:.3f} | "
            f"{pct(r['accuracy'])} | {int(r['calls'])} calls | "
            f"{100*r['avg_ask']:.1f}c | {r['avg_time_left']:.2f}m"
        )

    lines.append("")
    lines.append("INTERPRETATION")
    lines.append(
        "- This is development evidence only; the 57 contracts have already "
        "been inspected in earlier analyses."
    )
    lines.append(
        "- A passing candidate must be frozen before any future contracts are "
        "used to judge it."
    )
    lines.append(
        "- Future validation should piggyback on required parity/scalp runs; "
        "no standalone long collection is required."
    )
    lines.append("- No orders; bot.py unchanged.")

    SUMMARY.write_text("\n".join(lines))
    print("\n".join(lines))

if __name__=="__main__":
    main()
