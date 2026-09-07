
import math, warnings
from pathlib import Path
import numpy as np
import pandas as pd

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier

warnings.filterwarnings("ignore")

UNIFIED = Path("kalshi_subminute_unified_v1_1.csv")
AUDIT = Path("union_coverage_gap_audit_v1_contracts.csv")

OUT_GRID = Path("chop_reversal_event_detector_v1_grid.csv")
OUT_WF = Path("chop_reversal_event_detector_v1_walkforward_signals.csv")
OUT_GAPS = Path("chop_reversal_event_detector_v1_gap_signals.csv")
OUT_FINAL = Path("final_mixed_sensitivity_v1.csv")

HORIZON = 180
TARGET_ROI = 0.18
STOP_ROI = 0.18
MIN_MOVE_C = 4
ASK_MAX = 0.50
EVENT_COOLDOWN = 30.0

def truthy(v):
    return str(v).strip().lower() in ("true","1","yes")

def num(df,c):
    if c not in df.columns:
        df[c]=np.nan
    df[c]=pd.to_numeric(df[c],errors="coerce")

def bnum(df,src,dst):
    if src not in df.columns:
        df[dst]=0.0
    else:
        df[dst]=df[src].map(lambda x: 1.0 if truthy(x) else 0.0)

def roi_delta(entry,roi):
    return max(
        MIN_MOVE_C/100.0,
        math.ceil(float(entry)*float(roi)*100-1e-12)/100.0
    )

def metrics(sig,contracts):
    n=len(sig)
    if n==0:
        return dict(
            calls=0,accuracy=np.nan,coverage=0.0,
            avg_ask=np.nan,avg_time=np.nan,avg_target_c=np.nan
        )
    ask=pd.to_numeric(sig["side_ask"],errors="coerce")
    mins=pd.to_numeric(sig["minutes_left"],errors="coerce")
    return dict(
        calls=n,
        accuracy=100*sig["scalp_win"].astype(int).mean(),
        coverage=100*n/max(1,len(contracts)),
        avg_ask=100*ask.mean(),
        avg_time=mins.mean(),
        avg_target_c=ask.map(
            lambda x: roi_delta(x,TARGET_ROI)*100
        ).mean(),
    )

def fmt(m):
    if m["calls"]==0:
        return "0 calls"
    return (
        f"{m['accuracy']:.1f}% | {m['calls']} calls | "
        f"{m['coverage']:.1f}% cov | ask {m['avg_ask']:.1f}c | "
        f"target +{m['avg_target_c']:.1f}c | "
        f"{m['avg_time']:.2f}m left"
    )

print("="*86)
print("CHOP / REVERSAL EVENT DETECTOR V1")
print("="*86)

if not UNIFIED.exists():
    raise SystemExit("ERROR: unified log missing")
if not AUDIT.exists():
    raise SystemExit("ERROR: union coverage audit missing")

d=pd.read_csv(UNIFIED)
a=pd.read_csv(AUDIT)

d["timestamp_utc"]=pd.to_datetime(
    d["timestamp_utc"],errors="coerce",utc=True
)

for c in [
    "minutes_left","seconds_left","side_ask","side_bid","side_fair","side_edge",
    "btc_gap_side","abs_btc_gap",
    "btc_move_5s_side","btc_move_15s_side","btc_move_30s_side",
    "ask_move_5s","ask_move_15s","ask_move_30s",
    "fair_move_5s","fair_move_15s","fair_move_30s",
    "brti_gap_side","brti_minus_coinbase_side","brti_age_seconds",
    "bounce_from_low_30s","drawdown_from_high_30s",
    "bounce_from_low_60s","drawdown_from_high_60s",
    "dist_over_range5","range5","vol5",
]:
    num(d,c)

bnum(d,"brti_ready","brti_ready_n")
bnum(d,"brti_agrees_side","brti_agrees_n")
bnum(d,"kalshi_lag_15s","lag15_n")
bnum(d,"kalshi_lag_30s","lag30_n")
bnum(d,"preferred_side_match","preferred_match_n")

d["reversal_state"]=d.get(
    "reversal_state",pd.Series("",index=d.index)
).fillna("").astype(str).str.upper()

# Current state one-hot.
states=["WARMING","PUSH","PULLBACK","REVERSAL_WARN","AGAINST","MIXED"]
for s in states:
    d[f"state_{s.lower()}"]=(d["reversal_state"]==s).astype(float)

# Sort and create past-only transitions.
d=d.sort_values(["contract","side","timestamp_utc"]).copy()
g=d.groupby(["contract","side"],group_keys=False)

d["prev_reversal_state"]=g["reversal_state"].shift(1)
d["state_changed"]=(
    d["reversal_state"]!=d["prev_reversal_state"]
).astype(float)

d["prev_brti_agrees"]=g["brti_agrees_n"].shift(1)
d["brti_flip"]=(
    d["brti_agrees_n"]!=d["prev_brti_agrees"]
).astype(float)

d["prev_lag15"]=g["lag15_n"].shift(1)
d["prev_lag30"]=g["lag30_n"].shift(1)
d["lag_on_event"]=(
    ((d["lag15_n"]>=.5)&(d["prev_lag15"]<.5))
    | ((d["lag30_n"]>=.5)&(d["prev_lag30"]<.5))
).astype(float)

# 30/60s past context.
for col in [
    "side_fair","side_edge","side_ask","btc_gap_side",
    "brti_agrees_n","lag15_n","lag30_n",
    "state_push","state_pullback","state_reversal_warn",
    "state_against","state_mixed",
]:
    for label,w in [("30",6),("60",12)]:
        d[f"{col}_mean_{label}"]=(
            g[col].rolling(w,min_periods=max(3,w//2))
            .mean().reset_index(level=[0,1],drop=True)
        )
        d[f"{col}_chg_{label}"]=d[col]-g[col].shift(w-1)

d["brti_persist_60"]=d["brti_agrees_n_mean_60"]
d["lag_persist_60"]=(
    d["lag15_n_mean_60"]+d["lag30_n_mean_60"]
)/2.0
d["chop_frac_60"]=(
    d["state_pullback_mean_60"]
    +d["state_against_mean_60"]
    +d["state_mixed_mean_60"]
    +d["state_reversal_warn_mean_60"]
).clip(upper=1.0)

# Candidate event must be an actual state/lead-lag change, not every row.
event_mask=(
    (d["state_changed"]>=.5)
    | (d["brti_flip"]>=.5)
    | (d["lag_on_event"]>=.5)
)

events=d[
    event_mask
    & d["minutes_left"].between(2.0,10.0,inclusive="both")
    & (d["side_ask"]<=ASK_MAX)
    & d["side_bid"].notna()
    & d["side_fair_mean_30"].notna()
].copy()

# Cooldown per contract/side so repeated 5s transitions do not spam events.
kept=[]
for (contract,side),grp in events.groupby(
    ["contract","side"],sort=False
):
    grp=grp.sort_values("timestamp_utc")
    last=None
    for idx,row in grp.iterrows():
        ts=row["timestamp_utc"]
        if last is None or (ts-last).total_seconds()>=EVENT_COOLDOWN:
            kept.append(idx)
            last=ts

events=events.loc[kept].copy().sort_values(
    ["contract","side","timestamp_utc"]
)

print(f"UNIFIED CONTRACTS: {d['contract'].nunique()}")
print(f"RAW TRANSITION EVENTS: {len(events)}")

# Label each event with 18% ROI executable-BID outcome.
parts=[]
for (contract,side),grp in d.groupby(
    ["contract","side"],sort=False
):
    path=grp.sort_values("timestamp_utc").copy()
    ev=events[
        (events["contract"]==contract)
        &(events["side"]==side)
    ].copy()
    if ev.empty:
        continue

    ts=path["timestamp_utc"].tolist()
    bids=path["side_bid"].astype(float).to_numpy()

    for idx,row in ev.iterrows():
        entry=float(row["side_ask"])
        t0=row["timestamp_utc"]
        target_delta=roi_delta(entry,TARGET_ROI)
        stop_delta=roi_delta(entry,STOP_ROI)

        first_target=None
        first_stop=None

        for j in range(len(path)):
            dt=(ts[j]-t0).total_seconds()
            if dt<0:
                continue
            if dt>HORIZON:
                break

            bid=bids[j]
            if not np.isfinite(bid):
                continue

            if first_target is None and bid>=entry+target_delta:
                first_target=dt
            if first_stop is None and bid<=entry-stop_delta:
                first_stop=dt

            if first_target is not None or first_stop is not None:
                if (
                    first_target is not None
                    and (first_stop is None or first_target<=first_stop)
                ):
                    break
                if (
                    first_stop is not None
                    and (first_target is None or first_stop<first_target)
                ):
                    break

        x=row.copy()
        x["scalp_win"]=int(
            first_target is not None
            and (first_stop is None or first_target<=first_stop)
        )
        x["seconds_to_target"]=first_target
        x["seconds_to_stop"]=first_stop
        x["target_delta_c"]=target_delta*100
        x["stop_delta_c"]=stop_delta*100
        parts.append(x)

if not parts:
    raise SystemExit("STOP: no labeled events.")

e=pd.DataFrame(parts)

# Chronological contract order.
order=(
    e.groupby("contract")["timestamp_utc"]
    .min().sort_values().index.tolist()
)

if len(order)<20:
    raise SystemExit("STOP: too few contracts for event walk-forward.")

# Last 10 contracts are held out only for reporting; selection is walk-forward.
hold_n=min(10,max(6,int(round(len(order)*.25))))
hold_n=min(hold_n,len(order)-16)

dev_contracts=order[:-hold_n]
late_contracts=order[-hold_n:]

# Expanding walk-forward in development.
n_dev=len(dev_contracts)
initial=max(14,int(round(n_dev*.50)))
remaining=n_dev-initial
fold_size=max(3,int(math.ceil(max(1,remaining)/4)))

folds=[]
start=initial
while start<n_dev:
    end=min(n_dev,start+fold_size)
    folds.append((dev_contracts[:start],dev_contracts[start:end]))
    start=end

wf_contracts=list(dict.fromkeys(
    c for _,te in folds for c in te
))
min_calls=max(10,int(math.ceil(len(wf_contracts)*.45)))

print(f"DEVELOPMENT CONTRACTS: {len(dev_contracts)}")
print(f"LATE REPORTING CONTRACTS: {len(late_contracts)}")
print(f"WALK-FORWARD FOLDS: {len(folds)}")
print(f"WALK-FORWARD TEST CONTRACTS: {len(wf_contracts)}")
print(f"MINIMUM CALLS TO QUALIFY: {min_calls}")

FEATURES=[
    "minutes_left","side_ask","side_bid","side_fair","side_edge",
    "btc_gap_side","abs_btc_gap",
    "btc_move_5s_side","btc_move_15s_side","btc_move_30s_side",
    "ask_move_5s","ask_move_15s","ask_move_30s",
    "fair_move_5s","fair_move_15s","fair_move_30s",
    "brti_gap_side","brti_minus_coinbase_side","brti_age_seconds",
    "brti_ready_n","brti_agrees_n","lag15_n","lag30_n",
    "preferred_match_n",
    "state_changed","brti_flip","lag_on_event",
    "state_warming","state_push","state_pullback",
    "state_reversal_warn","state_against","state_mixed",
    "side_fair_chg_30","side_fair_chg_60",
    "side_edge_chg_30","side_edge_chg_60",
    "side_ask_chg_30","side_ask_chg_60",
    "btc_gap_side_chg_30","btc_gap_side_chg_60",
    "brti_persist_60","lag_persist_60","chop_frac_60",
    "bounce_from_low_30s","drawdown_from_high_30s",
    "bounce_from_low_60s","drawdown_from_high_60s",
    "dist_over_range5","range5","vol5",
]
FEATURES=[c for c in FEATURES if c in e.columns]

def build_model(name):
    if name=="LOGISTIC":
        return Pipeline([
            ("scale",StandardScaler()),
            ("model",LogisticRegression(
                C=.5,max_iter=1200,class_weight="balanced",
                random_state=31
            ))
        ])
    if name=="RF":
        return RandomForestClassifier(
            n_estimators=350,max_depth=7,min_samples_leaf=12,
            max_features="sqrt",class_weight="balanced_subsample",
            random_state=31,n_jobs=-1
        )
    if name=="HGB":
        return HistGradientBoostingClassifier(
            max_iter=250,max_depth=4,learning_rate=.035,
            min_samples_leaf=15,l2_regularization=1.0,
            random_state=31
        )
    raise ValueError(name)

def prep(train,test):
    X=train[FEATURES].apply(pd.to_numeric,errors="coerce")
    T=test[FEATURES].apply(pd.to_numeric,errors="coerce")
    med=X.median().fillna(0)
    X=X.fillna(med).fillna(0)
    T=T.fillna(med).fillna(0)
    y=train["scalp_win"].astype(int)

    counts=train.groupby("contract")["contract"].transform("count")
    w=(1.0/counts)
    w=w/w.mean()
    return X,y,T,w

def fit_model(model,X,y,w):
    if isinstance(model,Pipeline):
        model.fit(X,y,model__sample_weight=w)
    else:
        model.fit(X,y,sample_weight=w)
    return model

def first_signal(pred,threshold,gate):
    x=pred.copy()
    mask=x["prob"]>=threshold

    if gate=="CHOP":
        mask &= x["chop_frac_60"]>=.35
    elif gate=="REVERSAL":
        mask &= (
            (x["state_pullback"]>=.5)
            |(x["state_against"]>=.5)
            |(x["state_reversal_warn"]>=.5)
            |(x["state_mixed"]>=.5)
        )
    elif gate=="BRTI_FLIP":
        mask &= x["brti_flip"]>=.5
    elif gate=="LAG_EVENT":
        mask &= x["lag_on_event"]>=.5
    elif gate=="HYBRID":
        mask &= (
            (x["chop_frac_60"]>=.30)
            & (
                (x["brti_flip"]>=.5)
                |(x["lag_on_event"]>=.5)
                |(x["state_changed"]>=.5)
            )
        )

    x=x[mask].copy()
    if x.empty:
        return x

    # Earliest event per contract.
    x=x.sort_values(
        ["contract","minutes_left","timestamp_utc","prob"],
        ascending=[True,False,True,False]
    )
    return x.groupby("contract",as_index=False).head(1).copy()

pred_store={}
for model_name in ["LOGISTIC","RF","HGB"]:
    fold_parts=[]
    for trc,tec in folds:
        tr=e[e["contract"].isin(trc)].copy()
        te=e[e["contract"].isin(tec)].copy()

        if tr.empty or te.empty or tr["scalp_win"].nunique()<2:
            continue

        X,y,T,w=prep(tr,te)
        model=fit_model(build_model(model_name),X,y,w)

        te=te.copy()
        te["prob"]=model.predict_proba(T)[:,1]
        fold_parts.append(te)

    if fold_parts:
        pred_store[model_name]=pd.concat(fold_parts,ignore_index=True)

rows=[]
store={}

for model_name,pred in pred_store.items():
    for gate in ["OPEN","CHOP","REVERSAL","BRTI_FLIP","LAG_EVENT","HYBRID"]:
        for th in [.55,.60,.65,.70,.75,.80,.85,.90]:
            sig=first_signal(pred,th,gate)
            m=metrics(sig,wf_contracts)
            key=(model_name,gate,th)
            store[key]=sig
            rows.append({
                "model":model_name,"gate":gate,"threshold":th,
                "calls":m["calls"],"accuracy":m["accuracy"],
                "coverage":m["coverage"],"avg_ask":m["avg_ask"],
                "avg_time":m["avg_time"],
                "avg_target_c":m["avg_target_c"],
            })

grid=pd.DataFrame(rows)
eligible=grid[grid["calls"]>=min_calls].copy()

if eligible.empty:
    grid.to_csv(OUT_GRID,index=False)
    raise SystemExit("NO EVENT CONFIG CLEARED MINIMUM CALL COUNT.")

high=eligible[eligible["accuracy"]>=90].copy()

if len(high):
    selected=high.sort_values(
        ["coverage","accuracy","avg_ask","avg_time"],
        ascending=[False,False,True,False]
    ).iloc[0]
    note=">=90% WALK-FORWARD GROUP; MAX COVERAGE"
else:
    selected=eligible.sort_values(
        ["accuracy","coverage","avg_ask","avg_time"],
        ascending=[False,False,True,False]
    ).iloc[0]
    note="NO >=90% GROUP; BEST HONEST FALLBACK"

key=(selected["model"],selected["gate"],float(selected["threshold"]))
wf_sig=store[key]
wf_m=metrics(wf_sig,wf_contracts)

print("-"*86)
print("SELECTED EVENT-BASED CHOP/REVERSAL CONFIG:")
print(f"  {key[0]} / {key[1]} / threshold {key[2]:.2f}")
print(f"  Selection: {note}")
print(f"  WALK-FORWARD: {fmt(wf_m)}")

# Retrain on all dev and report late block.
tr=e[e["contract"].isin(dev_contracts)].copy()
late=e[e["contract"].isin(late_contracts)].copy()

X,y,T,w=prep(tr,late)
model=fit_model(build_model(key[0]),X,y,w)
late=late.copy()
late["prob"]=model.predict_proba(T)[:,1]

late_sig=first_signal(late,key[2],key[1])
late_m=metrics(late_sig,late_contracts)

print(f"  LATE BLOCK:   {fmt(late_m)}")

# Incremental gap coverage using union audit.
a["union_actionable"]=a["union_actionable"].map(truthy)
gap_contracts=set(
    a.loc[~a["union_actionable"],"contract"].astype(str)
)

# Train on all available event data for descriptive gap application only.
Xa=e[FEATURES].apply(pd.to_numeric,errors="coerce")
med=Xa.median().fillna(0)
Xa=Xa.fillna(med).fillna(0)
ya=e["scalp_win"].astype(int)
counts=e.groupby("contract")["contract"].transform("count")
wa=(1.0/counts); wa=wa/wa.mean()

full_model=fit_model(build_model(key[0]),Xa,ya,wa)
allp=e.copy()
allp["prob"]=full_model.predict_proba(Xa)[:,1]
all_sig=first_signal(allp,key[2],key[1])

gap_sig=all_sig[
    all_sig["contract"].astype(str).isin(gap_contracts)
].copy()

print("-"*86)
print("DESCRIPTIVE CURRENT-UNION GAP APPLICATION:")
print(
    f"  Signals on uncovered contracts: "
    f"{gap_sig['contract'].nunique()}/{len(gap_contracts)}"
)

if len(gap_sig):
    print(
        f"  Gap-event historical accuracy: "
        f"{gap_sig['scalp_win'].mean()*100:.1f}% "
        f"({int(gap_sig['scalp_win'].sum())}/{len(gap_sig)})"
    )
    for _,r in gap_sig.iterrows():
        print(
            f"  {r['contract']} | {r['side']} | "
            f"ask {r['side_ask']*100:.0f}c | "
            f"{r['minutes_left']:.2f}m left | "
            f"{'WIN' if r['scalp_win'] else 'LOSS'}"
        )

grid.to_csv(OUT_GRID,index=False)
wf_sig.to_csv(OUT_WF,index=False)
gap_sig.to_csv(OUT_GAPS,index=False)

print("="*86)
print("FINAL MIXED SENSITIVITY AUDIT")
print("="*86)

fa=a[a["final_call"].map(truthy)].copy()
fa["final_correct_b"]=fa["final_correct"].map(truthy)

# Find reversal state nearest each final call.
rows_final=[]
for _,r in fa.iterrows():
    contract=str(r["contract"])
    side=str(r["final_side"])
    left=float(r["final_time_left"])

    cu=d[
        (d["contract"].astype(str)==contract)
        &(d["side"].astype(str)==side)
    ].copy()
    if cu.empty:
        continue

    cu["_delta"]=(cu["minutes_left"]-left).abs()
    rr=cu.sort_values("_delta").iloc[0]

    rows_final.append({
        "contract":contract,
        "correct":bool(r["final_correct_b"]),
        "time_left":left,
        "reversal_state":rr.get("reversal_state",""),
        "preferred_fair":rr.get("preferred_fair",np.nan),
        "abs_btc_gap":rr.get("abs_btc_gap",np.nan),
        "dist_over_range5":rr.get("dist_over_range5",np.nan),
    })

f=pd.DataFrame(rows_final)
f.to_csv(OUT_FINAL,index=False)

if len(f):
    base_acc=100*f["correct"].mean()
    mixed=f[f["reversal_state"]=="MIXED"]
    nonmixed=f[f["reversal_state"]!="MIXED"]

    print(
        f"ALL FINAL calls: {int(f['correct'].sum())}/{len(f)} "
        f"= {base_acc:.1f}%"
    )
    if len(mixed):
        print(
            f"MIXED calls: {int(mixed['correct'].sum())}/{len(mixed)} "
            f"= {mixed['correct'].mean()*100:.1f}%"
        )
    if len(nonmixed):
        print(
            f"NON-MIXED calls: {int(nonmixed['correct'].sum())}/{len(nonmixed)} "
            f"= {nonmixed['correct'].mean()*100:.1f}% | "
            f"coverage retained {len(nonmixed)}/{len(f)} "
            f"= {len(nonmixed)/len(f)*100:.1f}% of FINAL calls"
        )

    # Also report exact effect of suppressing MIXED.
    print(
        "MIXED GUARDRAIL EFFECT: "
        f"would remove {len(mixed)} of {len(f)} FINAL calls."
    )

print("="*86)

if (
    late_m["calls"]>=6
    and late_m["accuracy"]>=90
    and gap_sig["contract"].nunique()>=3
):
    print("SCREEN RESULT: PROMISING TARGETED CHOP/REVERSAL EVENT PATH")
    print("NEXT: freeze exactly this detector as SHADOW ONLY.")
else:
    print("SCREEN RESULT: EVENT DETECTOR NOT YET STRONG ENOUGH")
    print("Do not force the final 5 gaps.")

print(f"Saved grid: {OUT_GRID}")
print(f"Saved walk-forward: {OUT_WF}")
print(f"Saved current-gap signals: {OUT_GAPS}")
print(f"Saved FINAL mixed audit: {OUT_FINAL}")
print("="*86)
