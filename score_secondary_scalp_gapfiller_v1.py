
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
PRIMARY = Path("kalshi_true_scalp_forward_shadow_v1.csv")

OUT_GRID = Path("secondary_scalp_gapfiller_v1_grid.csv")
OUT_WF = Path("secondary_scalp_gapfiller_v1_walkforward_signals.csv")
OUT_HOLD = Path("secondary_scalp_gapfiller_v1_holdout_signals.csv")

HORIZON_SECONDS = 180
TARGET = 0.10
STOP = 0.10
ASK_MAX = 0.50

def truthy(v):
    return str(v).strip().lower() in ("true","1","yes")

def num(df, c):
    if c not in df.columns:
        df[c] = np.nan
    df[c] = pd.to_numeric(df[c], errors="coerce")

def boolnum(df, src, dst):
    if src not in df.columns:
        df[dst] = 0.0
    else:
        df[dst] = df[src].map(lambda x: 1.0 if truthy(x) else 0.0)

def metrics(sig, contracts):
    n = len(sig)
    if n == 0:
        return dict(
            calls=0,accuracy=np.nan,coverage=0.0,
            avg_ask=np.nan,median_ask=np.nan,
            pct2040=np.nan,avg_time=np.nan,median_time=np.nan
        )
    y = sig["scalp_win"].astype(int)
    ask = pd.to_numeric(sig["side_ask"], errors="coerce")
    mins = pd.to_numeric(sig["minutes_left"], errors="coerce")
    return dict(
        calls=n,
        accuracy=100*y.mean(),
        coverage=100*n/max(1,len(contracts)),
        avg_ask=100*ask.mean(),
        median_ask=100*ask.median(),
        pct2040=100*((ask>=.20)&(ask<=.40)).mean(),
        avg_time=mins.mean(),
        median_time=mins.median(),
    )

def fmt(m):
    if m["calls"] == 0:
        return "0 calls"
    return (
        f"{m['accuracy']:.1f}% | {m['calls']} calls | "
        f"{m['coverage']:.1f}% gap-fill cov | avg ask {m['avg_ask']:.1f}c | "
        f"20-40c {m['pct2040']:.1f}% | avg {m['avg_time']:.2f}m left"
    )

print("="*80)
print("SECONDARY SCALP / PULLBACK GAP-FILLER — OFFLINE TOURNAMENT V1")
print("="*80)

if not UNIFIED.exists():
    raise SystemExit("ERROR: kalshi_subminute_unified_v1_1.csv missing")

d = pd.read_csv(UNIFIED)
d["timestamp_utc"] = pd.to_datetime(d["timestamp_utc"], errors="coerce", utc=True)

numeric = [
    "minutes_left","seconds_left","side_ask","side_bid","side_spread",
    "opposite_ask","quote_advantage","side_fair","side_edge",
    "btc_gap_side","abs_btc_gap",
    "btc_move_5s_side","btc_move_15s_side","btc_move_30s_side",
    "btc_move_60s_side","btc_move_120s_side",
    "ask_move_5s","ask_move_15s","ask_move_30s",
    "ask_move_60s","ask_move_120s",
    "fair_move_5s","fair_move_15s","fair_move_30s",
    "candidate_persistence_30s",
    "brti_gap_side","brti_minus_coinbase_side","brti_age_seconds",
    "dist_over_range5","range5","vol5",
    "bounce_from_low_30s","drawdown_from_high_30s",
    "bounce_from_low_60s","drawdown_from_high_60s",
    "bounce_from_low_120s","drawdown_from_high_120s",
]
for c in numeric:
    num(d,c)

boolnum(d,"brti_ready","brti_ready_n")
boolnum(d,"brti_agrees_side","brti_agrees_n")
boolnum(d,"kalshi_lag_15s","lag15_n")
boolnum(d,"kalshi_lag_30s","lag30_n")
boolnum(d,"preferred_side_match","preferred_side_match_n")

d["reversal_state"] = d.get(
    "reversal_state", pd.Series("", index=d.index)
).fillna("").astype(str).str.upper()

for state in ["PUSH","PULLBACK","AGAINST","MIXED","WARMING","REVERSAL_WARN"]:
    d[f"rev_{state.lower()}_n"] = (d["reversal_state"] == state).astype(float)

print(f"UNIFIED ROWS: {len(d)}")
print(f"UNIFIED CONTRACTS: {d['contract'].nunique()}")

# Contracts already covered by the frozen primary scalp are excluded.
primary_contracts = set()
if PRIMARY.exists():
    p = pd.read_csv(PRIMARY)
    if "contract" in p.columns:
        primary_contracts = set(p["contract"].dropna().astype(str).unique())

all_contracts = set(d["contract"].dropna().astype(str).unique())
gap_contracts = sorted(all_contracts - primary_contracts)

print(f"PRIMARY SCALP-COVERED CONTRACTS: {len(primary_contracts & all_contracts)}")
print(f"GAP CONTRACTS AVAILABLE: {len(gap_contracts)}")

if len(gap_contracts) < 12:
    raise SystemExit(
        "STOP: fewer than 12 uncovered contracts. "
        "Not enough honest gap-filler data yet."
    )

d = d[d["contract"].astype(str).isin(gap_contracts)].copy()
d = d.sort_values(["contract","side","timestamp_utc"]).reset_index(drop=True)

# Require economic/timing universe.
d = d[
    d["minutes_left"].between(2.0,10.0,inclusive="both")
    & (d["side_ask"] <= ASK_MAX)
    & d["side_bid"].notna()
].copy()

# ---------------------------------------------------------------------
# Label each candidate by EXECUTABLE BID path:
# +10c from current ASK before -10c from current ASK, within 3 minutes.
# This is temporary-move/scalp truth, NOT settlement truth.
# ---------------------------------------------------------------------

def label_group(g):
    g = g.sort_values("timestamp_utc").copy()
    ts = g["timestamp_utc"].tolist()
    bids = g["side_bid"].astype(float).to_numpy()
    asks = g["side_ask"].astype(float).to_numpy()

    wins = np.zeros(len(g), dtype=int)
    hit10_s = np.full(len(g), np.nan)
    stop_s = np.full(len(g), np.nan)
    max_bid = np.full(len(g), np.nan)

    for i in range(len(g)):
        entry = asks[i]
        if not np.isfinite(entry):
            continue
        t0 = ts[i]

        first_target = None
        first_stop = None
        mx = bids[i]

        j = i
        while j < len(g):
            dt = (ts[j]-t0).total_seconds()
            if dt < 0:
                j += 1
                continue
            if dt > HORIZON_SECONDS:
                break

            b = bids[j]
            if np.isfinite(b):
                mx = max(mx,b)
                if first_target is None and b >= entry + TARGET:
                    first_target = dt
                if first_stop is None and b <= entry - STOP:
                    first_stop = dt

            if first_target is not None or first_stop is not None:
                # Once either boundary hits first, outcome is decided.
                if first_target is not None and (
                    first_stop is None or first_target <= first_stop
                ):
                    break
                if first_stop is not None and (
                    first_target is None or first_stop < first_target
                ):
                    break
            j += 1

        max_bid[i] = mx
        hit10_s[i] = first_target if first_target is not None else np.nan
        stop_s[i] = first_stop if first_stop is not None else np.nan

        wins[i] = int(
            first_target is not None and
            (first_stop is None or first_target <= first_stop)
        )

    g["scalp_win"] = wins
    g["seconds_to_10c"] = hit10_s
    g["seconds_to_stop"] = stop_s
    g["max_future_bid"] = max_bid
    return g

d = (
    d.groupby(["contract","side"], group_keys=False)
     .apply(label_group)
     .reset_index(drop=True)
)

# Remove rows too close to end of available data to observe enough future path.
# We require at least 90 seconds of future data OR a decisive hit already occurred.
g = d.groupby(["contract","side"], group_keys=False)
last_ts = g["timestamp_utc"].transform("max")
future_obs = (last_ts - d["timestamp_utc"]).dt.total_seconds()

decisive = d["seconds_to_10c"].notna() | d["seconds_to_stop"].notna()
d = d[(future_obs >= 90) | decisive].copy()

# ---------------------------------------------------------------------
# Past-only trajectory features for pullback / reversal / lag behavior.
# ---------------------------------------------------------------------

d = d.sort_values(["contract","side","timestamp_utc"]).copy()
g = d.groupby(["contract","side"], group_keys=False)

for col in [
    "side_ask","side_fair","side_edge","btc_gap_side",
    "brti_gap_side","brti_agrees_n","lag15_n","lag30_n",
    "rev_push_n","rev_pullback_n","rev_against_n",
    "rev_mixed_n","rev_reversal_warn_n",
]:
    for label,w in [("30",6),("60",12)]:
        d[f"{col}_mean_{label}"] = (
            g[col].rolling(w,min_periods=max(3,w//2)).mean()
             .reset_index(level=[0,1],drop=True)
        )
        d[f"{col}_chg_{label}"] = d[col] - g[col].shift(w-1)

d["ask_rebound_30"] = -d["side_ask_chg_30"]
d["ask_rebound_60"] = -d["side_ask_chg_60"]
d["btc_recovery_30"] = d["btc_gap_side_chg_30"]
d["fair_recovery_30"] = d["side_fair_chg_30"]

d["brti_persist_60"] = d["brti_agrees_n_mean_60"]
d["lag_persist_60"] = (
    d["lag15_n_mean_60"] + d["lag30_n_mean_60"]
)/2.0

d["push_frac_60"] = d["rev_push_n_mean_60"]
d["pullback_frac_60"] = d["rev_pullback_n_mean_60"]
d["against_frac_60"] = d["rev_against_n_mean_60"]
d["warn_frac_60"] = d["rev_reversal_warn_n_mean_60"]

d["sequence_ready"] = (
    d["side_ask_mean_60"].notna()
    & d["brti_agrees_n_mean_60"].notna()
)
d = d[d["sequence_ready"]].copy()

# Chronological contract order.
order = (
    d.groupby("contract")["timestamp_utc"]
     .min().sort_values().index.tolist()
)

if len(order) < 12:
    raise SystemExit("STOP: too few usable gap contracts after labeling.")

hold_n = max(4, int(round(len(order)*0.25)))
hold_n = min(hold_n, len(order)-8)

dev_contracts = order[:-hold_n]
hold_contracts = order[-hold_n:]

print(f"USABLE GAP CONTRACTS: {len(order)}")
print(f"DEVELOPMENT GAP CONTRACTS: {len(dev_contracts)}")
print(f"UNTOUCHED GAP CONTRACTS: {len(hold_contracts)}")

FEATURES = [
    "minutes_left","side_ask","side_bid","side_spread",
    "side_fair","side_edge","btc_gap_side","abs_btc_gap",
    "btc_move_5s_side","btc_move_15s_side","btc_move_30s_side",
    "ask_move_5s","ask_move_15s","ask_move_30s",
    "fair_move_5s","fair_move_15s","fair_move_30s",
    "brti_gap_side","brti_minus_coinbase_side","brti_age_seconds",
    "brti_ready_n","brti_agrees_n","lag15_n","lag30_n",
    "preferred_side_match_n",
    "ask_rebound_30","ask_rebound_60",
    "btc_recovery_30","fair_recovery_30",
    "brti_persist_60","lag_persist_60",
    "push_frac_60","pullback_frac_60",
    "against_frac_60","warn_frac_60",
    "bounce_from_low_30s","drawdown_from_high_30s",
    "bounce_from_low_60s","drawdown_from_high_60s",
    "dist_over_range5","range5","vol5",
]
FEATURES = [c for c in FEATURES if c in d.columns]

def build_model(name):
    if name == "LOGISTIC":
        return Pipeline([
            ("scale",StandardScaler()),
            ("model",LogisticRegression(
                C=.5,max_iter=1000,class_weight="balanced",
                random_state=19
            ))
        ])
    if name == "RF":
        return RandomForestClassifier(
            n_estimators=300,max_depth=6,min_samples_leaf=18,
            max_features="sqrt",class_weight="balanced_subsample",
            random_state=19,n_jobs=-1
        )
    if name == "HGB":
        return HistGradientBoostingClassifier(
            max_iter=220,max_depth=4,learning_rate=.035,
            min_samples_leaf=20,l2_regularization=1.2,
            random_state=19
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
    mask=(x["prob"]>=threshold)

    if gate=="PULLBACK":
        mask &= (
            (x["pullback_frac_60"]>=.15)
            | (x["ask_rebound_30"]>=.02)
        )
    elif gate=="LAG":
        mask &= (x["lag_persist_60"]>=.25)
    elif gate=="BRTI":
        mask &= (
            (x["brti_persist_60"]>=.65)
            & (x["brti_ready_n"]>=.5)
        )
    elif gate=="HYBRID":
        mask &= (
            (x["brti_persist_60"]>=.60)
            & (
                (x["pullback_frac_60"]>=.15)
                | (x["lag_persist_60"]>=.20)
                | (x["ask_rebound_30"]>=.02)
            )
        )

    x=x[mask].copy()
    if x.empty:
        return x

    x=x.sort_values(
        ["contract","minutes_left","timestamp_utc","prob"],
        ascending=[True,False,True,False]
    )
    return x.groupby("contract",as_index=False).head(1).copy()

# Expanding walk-forward.
n_dev=len(dev_contracts)
initial=max(6,int(round(n_dev*.50)))
remaining=n_dev-initial
fold_size=max(2,int(math.ceil(max(1,remaining)/3)))

folds=[]
start=initial
while start<n_dev:
    end=min(n_dev,start+fold_size)
    folds.append((dev_contracts[:start],dev_contracts[start:end]))
    start=end

if not folds:
    raise SystemExit("STOP: not enough development contracts for walk-forward.")

wf_contracts=list(dict.fromkeys(c for _,te in folds for c in te))
min_calls=max(4,int(math.ceil(len(wf_contracts)*.40)))

print(f"WALK-FORWARD FOLDS: {len(folds)}")
print(f"WALK-FORWARD GAP CONTRACTS: {len(wf_contracts)}")
print(f"MIN CALLS TO QUALIFY: {min_calls}")

preds={}
for model_name in ["LOGISTIC","RF","HGB"]:
    parts=[]
    for trc,tec in folds:
        tr=d[d["contract"].isin(trc)].copy()
        te=d[d["contract"].isin(tec)].copy()
        if tr.empty or te.empty or tr["scalp_win"].nunique()<2:
            continue
        X,y,T,w=prep(tr,te)
        model=fit_model(build_model(model_name),X,y,w)
        te=te.copy()
        te["prob"]=model.predict_proba(T)[:,1]
        parts.append(te)
    if parts:
        preds[model_name]=pd.concat(parts,ignore_index=True)

rows=[]
store={}
for model_name,pred in preds.items():
    for gate in ["OPEN","PULLBACK","LAG","BRTI","HYBRID"]:
        for th in [.55,.60,.65,.70,.75,.80,.85,.90]:
            sig=first_signal(pred,th,gate)
            m=metrics(sig,wf_contracts)
            key=(model_name,gate,th)
            store[key]=sig
            rows.append({
                "model":model_name,"gate":gate,"threshold":th,
                "calls":m["calls"],"accuracy":m["accuracy"],
                "coverage":m["coverage"],"avg_ask":m["avg_ask"],
                "median_ask":m["median_ask"],"pct2040":m["pct2040"],
                "avg_time":m["avg_time"],"median_time":m["median_time"],
            })

grid=pd.DataFrame(rows)
eligible=grid[grid["calls"]>=min_calls].copy()

if eligible.empty:
    grid.to_csv(OUT_GRID,index=False)
    raise SystemExit("NO SECONDARY SCALP CONFIG CLEARED MIN CALL COUNT.")

high=eligible[eligible["accuracy"]>=90].copy()
if len(high):
    selected=high.sort_values(
        ["coverage","accuracy","avg_ask","avg_time"],
        ascending=[False,False,True,False]
    ).iloc[0]
    note=">=90% GROUP; MAX GAP-FILL COVERAGE"
else:
    selected=eligible.sort_values(
        ["accuracy","coverage","avg_ask","avg_time"],
        ascending=[False,False,True,False]
    ).iloc[0]
    note="NO >=90% GROUP; BEST HONEST FALLBACK"

key=(selected["model"],selected["gate"],float(selected["threshold"]))
wf_sig=store[key]
wf_m=metrics(wf_sig,wf_contracts)

print("-"*80)
print("SELECTED SECONDARY SCALP CONFIG:")
print(f"  {key[0]} / {key[1]} / threshold {key[2]:.2f}")
print(f"  Selection: {note}")
print(f"  WALK-FORWARD: {fmt(wf_m)}")

# Untouched gap holdout.
tr=d[d["contract"].isin(dev_contracts)].copy()
ho=d[d["contract"].isin(hold_contracts)].copy()
X,y,T,w=prep(tr,ho)
model=fit_model(build_model(key[0]),X,y,w)
ho=ho.copy()
ho["prob"]=model.predict_proba(T)[:,1]
hold_sig=first_signal(ho,key[2],key[1])
hold_m=metrics(hold_sig,hold_contracts)

print(f"  UNTOUCHED GAP HOLDOUT: {fmt(hold_m)}")

grid.to_csv(OUT_GRID,index=False)
wf_sig.to_csv(OUT_WF,index=False)
hold_sig.to_csv(OUT_HOLD,index=False)

print("-"*80)
print("TOP 5 WALK-FORWARD SECONDARY CONFIGS:")
top=eligible.sort_values(
    ["accuracy","coverage","avg_ask","avg_time"],
    ascending=[False,False,True,False]
).head(5)

for _,r in top.iterrows():
    print(
        f"  {r['model']}/{r['gate']}/{r['threshold']:.2f}: "
        f"{r['accuracy']:.1f}% | {int(r['calls'])} calls | "
        f"{r['coverage']:.1f}% gap-fill cov | "
        f"{r['avg_ask']:.1f}c | {r['avg_time']:.2f}m"
    )

print("="*80)

if (
    hold_m["calls"]>=4
    and hold_m["accuracy"]>=90
    and hold_m["avg_ask"]<=45
    and hold_m["avg_time"]>=4.0
):
    print("SCREEN RESULT: PROMISING SECONDARY SCALP GAP-FILLER")
    print("NEXT: freeze exactly this rule as SHADOW ONLY.")
elif (
    hold_m["calls"]>=3
    and hold_m["accuracy"]>=80
):
    print("SCREEN RESULT: SOME SECONDARY SCALP SIGNAL, BELOW STANDARD")
    print("Keep collecting naturally; do not force it.")
else:
    print("SCREEN RESULT: NO STABLE SECONDARY SCALP GAP-FILLER YET")
    print("Do not weaken primary scalp or FINAL.")

print(f"Saved grid: {OUT_GRID}")
print(f"Saved walk-forward signals: {OUT_WF}")
print(f"Saved untouched signals: {OUT_HOLD}")
print("="*80)
