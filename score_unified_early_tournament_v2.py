
import base64, time, warnings, math
from pathlib import Path
import numpy as np
import pandas as pd
import requests

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier

warnings.filterwarnings("ignore")

DATA = Path("kalshi_subminute_unified_v1_1.csv")
OUT_GRID = Path("unified_early_tournament_v2_grid.csv")
OUT_HOLD = Path("unified_early_tournament_v2_holdout_signals.csv")
OUT_WF = Path("unified_early_tournament_v2_walkforward_signals.csv")

KALSHI_BASE_URL = "https://api.elections.kalshi.com"
KEY_ID_PATH = Path.home() / ".kalshi" / "key_id"
PRIVATE_KEY_PATH = Path.home() / ".kalshi" / "private_key.pem"

def truthy(v):
    return str(v).strip().lower() in ("true","1","yes")

def auth_ready():
    return KEY_ID_PATH.exists() and PRIVATE_KEY_PATH.exists()

if not DATA.exists():
    raise SystemExit("ERROR: kalshi_subminute_unified_v1_1.csv not found")
if not auth_ready():
    raise SystemExit("ERROR: Kalshi credentials not found in ~/.kalshi")

KEY_ID = KEY_ID_PATH.read_text().strip()
PRIVATE_KEY = serialization.load_pem_private_key(
    PRIVATE_KEY_PATH.read_bytes(), password=None
)

def kalshi_headers(method, path):
    ts = str(int(time.time() * 1000))
    msg = ts + method.upper() + path
    sig = PRIVATE_KEY.sign(
        msg.encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode("utf-8"),
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }

def kalshi_get(path):
    r = requests.get(
        KALSHI_BASE_URL + path,
        headers=kalshi_headers("GET", path),
        timeout=12,
    )
    r.raise_for_status()
    return r.json()

def official_side(ticker):
    try:
        m = kalshi_get(f"/trade-api/v2/markets/{ticker}").get("market", {})
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

    for k in ("result","settlement_result","settled_result"):
        v = str(m.get(k) or "").strip().lower()
        if v == "yes":
            return "UP", k
        if v == "no":
            return "DOWN", k
    return None, "unsettled"

def num(df, col):
    if col not in df.columns:
        df[col] = np.nan
    df[col] = pd.to_numeric(df[col], errors="coerce")

def boolnum(df, source, target):
    if source not in df.columns:
        df[target] = 0.0
    else:
        df[target] = df[source].map(
            lambda x: 1.0 if truthy(x) else 0.0
        )

def first_signal_from_predictions(pred, threshold, gate_name):
    if pred.empty:
        return pred

    x = pred.copy()

    gate = pd.Series(True, index=x.index)

    if gate_name in ("BRTI","BRTI_SAFE","BRTI_SAFE_LAG"):
        gate &= (
            (x["brti_ready_n"] >= 0.5)
            & (x["brti_agrees_n"] >= 0.5)
            & (x["brti_age_seconds"] <= 5.0)
        )

    if gate_name in ("BRTI_SAFE","BRTI_SAFE_LAG"):
        gate &= x["reversal_safe_n"] >= 0.5

    if gate_name == "BRTI_SAFE_LAG":
        gate &= (x["lag15_n"] >= 0.5) | (x["lag30_n"] >= 0.5)

    x = x[
        gate
        & (x["prob"] >= threshold)
        & x["minutes_left"].between(4.0,10.0,inclusive="both")
        & (x["side_ask"] <= 0.50)
    ].copy()

    if x.empty:
        return x

    # Earliest actionable time per contract: greatest time-left first.
    # At a tied timestamp choose the side with the larger modeled probability.
    x = x.sort_values(
        ["contract","minutes_left","timestamp_utc","prob","side_edge"],
        ascending=[True,False,True,False,False],
    )
    return x.groupby("contract", as_index=False).head(1).copy()

def metrics(sig, contracts):
    n_contracts = len(contracts)
    n = len(sig)
    if n == 0:
        return {
            "calls":0,"accuracy":np.nan,"coverage":0.0,
            "avg_ask":np.nan,"median_ask":np.nan,"pct2040":np.nan,
            "avg_time":np.nan,"median_time":np.nan
        }
    correct = (sig["side"] == sig["official_side"]).astype(int)
    ask = pd.to_numeric(sig["side_ask"], errors="coerce")
    mins = pd.to_numeric(sig["minutes_left"], errors="coerce")
    return {
        "calls":n,
        "accuracy":100*correct.mean(),
        "coverage":100*n/max(1,n_contracts),
        "avg_ask":100*ask.mean(),
        "median_ask":100*ask.median(),
        "pct2040":100*((ask>=.20)&(ask<=.40)).mean(),
        "avg_time":mins.mean(),
        "median_time":mins.median(),
    }

def fmt(m):
    if m["calls"] == 0:
        return "0 calls"
    return (
        f"{m['accuracy']:.1f}% | {m['calls']} calls | "
        f"{m['coverage']:.1f}% cov | avg ask {m['avg_ask']:.1f}c | "
        f"20-40c {m['pct2040']:.1f}% | avg {m['avg_time']:.2f}m left"
    )

print("="*78)
print("UNIFIED SUB-MINUTE EARLY ENTRY — TOURNAMENT V2")
print("="*78)

d = pd.read_csv(DATA)
d["timestamp_utc"] = pd.to_datetime(
    d["timestamp_utc"], errors="coerce", utc=True
)

numeric_cols = [
    "minutes_left","seconds_left","side_ask","side_bid","side_spread",
    "opposite_ask","quote_advantage",
    "side_fair","side_edge","preferred_fair","preferred_edge",
    "btc_gap_side","abs_btc_gap",
    "btc_move_5s_side","btc_move_15s_side","btc_move_30s_side",
    "btc_move_60s_side","btc_move_120s_side",
    "ask_move_5s","ask_move_15s","ask_move_30s",
    "ask_move_60s","ask_move_120s",
    "side_ask_low_30s","side_ask_high_30s",
    "side_ask_low_60s","side_ask_high_60s",
    "side_ask_low_120s","side_ask_high_120s",
    "bounce_from_low_30s","drawdown_from_high_30s",
    "bounce_from_low_60s","drawdown_from_high_60s",
    "bounce_from_low_120s","drawdown_from_high_120s",
    "fair_move_5s","fair_move_15s","fair_move_30s",
    "candidate_persistence_30s",
    "dist_over_range5","range5","vol5",
    "brti_gap_side","brti_age_seconds",
    "brti_minus_coinbase_side",
]
for c in numeric_cols:
    num(d,c)

boolnum(d,"brti_ready","brti_ready_n")
boolnum(d,"brti_agrees_side","brti_agrees_n")
boolnum(d,"kalshi_lag_15s","lag15_n")
boolnum(d,"kalshi_lag_30s","lag30_n")
boolnum(d,"preferred_side_match","preferred_side_match_n")

d["reversal_state"] = d.get(
    "reversal_state", pd.Series("", index=d.index)
).fillna("").astype(str).str.upper()
d["reversal_safe_n"] = (~d["reversal_state"].isin(
    ["AGAINST","REVERSAL_WARN"]
)).astype(float)

# Derived microstructure positions.
for horizon in (30,60,120):
    lo = f"side_ask_low_{horizon}s"
    hi = f"side_ask_high_{horizon}s"
    out = f"ask_position_{horizon}s"
    span = (d[hi]-d[lo]).replace(0,np.nan)
    d[out] = (d["side_ask"]-d[lo]) / span

print(f"RAW ROWS: {len(d)}")
print(f"RAW CONTRACTS: {d['contract'].nunique()}")

# Official Kalshi labels.
labels={}
sources={}
for ticker in sorted(d["contract"].dropna().astype(str).unique()):
    side, src = official_side(ticker)
    labels[ticker]=side
    sources[ticker]=src
    time.sleep(0.06)

d["official_side"] = d["contract"].map(labels)
settled = [t for t,s in labels.items() if s in ("UP","DOWN")]
print(f"OFFICIAL SETTLED: {len(settled)}")

d = d[d["official_side"].isin(["UP","DOWN"])].copy()

# Require a genuinely captured early window.
cov = (
    d.groupby("contract")
     .agg(
        first_ts=("timestamp_utc","min"),
        max_minutes=("minutes_left","max"),
        min_minutes=("minutes_left","min"),
        rows=("contract","size"),
     )
     .reset_index()
)
cov["full"] = (
    (cov["max_minutes"] >= 9.5)
    & (cov["min_minutes"] <= 4.2)
    & (cov["rows"] >= 100)
)
contracts = cov.loc[cov["full"],"contract"].tolist()

print(f"FULL 10->4m CONTRACTS: {len(contracts)}")
print(f"PARTIAL/THIN EXCLUDED: {len(cov)-len(contracts)}")

if len(contracts) < 18:
    raise SystemExit(
        "STOP: fewer than 18 full settled contracts. "
        "Keep collecting naturally; do not force a model."
    )

d = d[d["contract"].isin(contracts)].copy()

# Hard economic universe. Model is not allowed to learn from expensive entries
# that would never be actionable for this project.
d = d[
    d["minutes_left"].between(4.0,10.0,inclusive="both")
    & (d["side_ask"] <= 0.50)
    & d["side_fair"].notna()
].copy()

d["target"] = (d["side"] == d["official_side"]).astype(int)

order = (
    d.groupby("contract")["timestamp_utc"]
     .min().sort_values().index.tolist()
)

# Latest 25% untouched.
hold_n = max(6, int(round(len(order)*0.25)))
hold_n = min(hold_n, len(order)-12)
dev_contracts = order[:-hold_n]
hold_contracts = order[-hold_n:]

print(f"DEVELOPMENT CONTRACTS: {len(dev_contracts)}")
print(f"UNTOUCHED LATE CONTRACTS: {len(hold_contracts)}")

# Feature sets. Missing columns are retained as NaN and imputed by training medians.
CORE = [
    "minutes_left","side_ask","side_fair","side_edge",
    "btc_gap_side","abs_btc_gap",
    "btc_move_5s_side","btc_move_15s_side","btc_move_30s_side",
    "ask_move_5s","ask_move_15s","ask_move_30s",
    "fair_move_5s","fair_move_15s","fair_move_30s",
]
BRTI = CORE + [
    "brti_gap_side","brti_minus_coinbase_side",
    "brti_ready_n","brti_agrees_n","brti_age_seconds",
    "candidate_persistence_30s","lag15_n","lag30_n",
    "reversal_safe_n","preferred_side_match_n",
]
FULL = BRTI + [
    "btc_move_60s_side","btc_move_120s_side",
    "ask_move_60s","ask_move_120s",
    "quote_advantage","side_spread","opposite_ask",
    "bounce_from_low_30s","drawdown_from_high_30s",
    "bounce_from_low_60s","drawdown_from_high_60s",
    "bounce_from_low_120s","drawdown_from_high_120s",
    "ask_position_30s","ask_position_60s","ask_position_120s",
    "dist_over_range5","range5","vol5",
]

feature_sets = {
    "CORE":CORE,
    "BRTI":BRTI,
    "FULL":FULL,
}

def prep_xy(train_df, test_df, features):
    tr = train_df[features].apply(pd.to_numeric, errors="coerce")
    te = test_df[features].apply(pd.to_numeric, errors="coerce")
    med = tr.median().fillna(0.0)
    tr = tr.fillna(med).fillna(0.0)
    te = te.fillna(med).fillna(0.0)
    y = train_df["target"].astype(int)

    # Equal total influence per contract despite thousands of 5s rows.
    counts = train_df.groupby("contract")["contract"].transform("count")
    w = 1.0 / counts
    w = w / w.mean()
    return tr, y, te, w

def build_model(name):
    if name == "LOGISTIC":
        return Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(
                C=0.5, max_iter=1000, class_weight="balanced",
                random_state=7
            )),
        ])
    if name == "RF":
        return RandomForestClassifier(
            n_estimators=250,
            max_depth=6,
            min_samples_leaf=20,
            max_features="sqrt",
            class_weight="balanced_subsample",
            random_state=7,
            n_jobs=-1,
        )
    if name == "HGB":
        return HistGradientBoostingClassifier(
            max_iter=180,
            max_depth=4,
            learning_rate=0.04,
            min_samples_leaf=25,
            l2_regularization=1.0,
            random_state=7,
        )
    raise ValueError(name)

def fit_model(model, X, y, w):
    if isinstance(model, Pipeline):
        model.fit(X,y,model__sample_weight=w)
    else:
        model.fit(X,y,sample_weight=w)
    return model

# Expanding walk-forward inside development.
n_dev = len(dev_contracts)
initial = max(10, int(round(n_dev*0.45)))
remaining = n_dev - initial
fold_size = max(3, int(math.ceil(remaining/4)))

folds=[]
start=initial
while start < n_dev:
    end=min(n_dev,start+fold_size)
    folds.append((dev_contracts[:start],dev_contracts[start:end]))
    start=end

print(f"WALK-FORWARD FOLDS: {len(folds)}")

models=["LOGISTIC","RF","HGB"]
gates=["OPEN","BRTI","BRTI_SAFE","BRTI_SAFE_LAG"]
thresholds=[0.60,0.65,0.70,0.75,0.80,0.85,0.90]

wf_predictions = {}

for fs_name, features in feature_sets.items():
    # Only use columns that actually exist after normalization.
    features=[c for c in features if c in d.columns]
    for model_name in models:
        all_pred=[]
        for train_contracts, test_contracts in folds:
            tr=d[d["contract"].isin(train_contracts)].copy()
            te=d[d["contract"].isin(test_contracts)].copy()

            if tr["target"].nunique() < 2 or te.empty:
                continue

            X,y,Xt,w = prep_xy(tr,te,features)
            model=fit_model(build_model(model_name),X,y,w)
            te=te.copy()
            te["prob"]=model.predict_proba(Xt)[:,1]
            all_pred.append(te)

        if all_pred:
            wf_predictions[(fs_name,model_name)] = pd.concat(
                all_pred, ignore_index=True
            )

rows=[]
wf_signal_store={}

for (fs_name,model_name), pred in wf_predictions.items():
    test_contracts = (
        pred.groupby("contract")["timestamp_utc"]
            .min().sort_values().index.tolist()
    )
    for gate in gates:
        for threshold in thresholds:
            sig=first_signal_from_predictions(pred,threshold,gate)
            m=metrics(sig,test_contracts)
            key=(fs_name,model_name,gate,threshold)
            wf_signal_store[key]=sig

            rows.append({
                "feature_set":fs_name,
                "model":model_name,
                "gate":gate,
                "threshold":threshold,
                "calls":m["calls"],
                "accuracy":m["accuracy"],
                "coverage":m["coverage"],
                "avg_ask":m["avg_ask"],
                "median_ask":m["median_ask"],
                "pct_20_40":m["pct2040"],
                "avg_time":m["avg_time"],
                "median_time":m["median_time"],
            })

grid=pd.DataFrame(rows)

wf_contract_count = len(set().union(*[
    set(test) for _,test in folds
]))
min_calls=max(8,int(math.ceil(wf_contract_count*0.30)))

eligible=grid[grid["calls"]>=min_calls].copy()

print(f"WALK-FORWARD TEST CONTRACTS: {wf_contract_count}")
print(f"MINIMUM CALLS TO QUALIFY: {min_calls}")

if eligible.empty:
    grid.to_csv(OUT_GRID,index=False)
    raise SystemExit(
        "NO CONFIGURATION CLEARED MINIMUM WALK-FORWARD CALL COUNT."
    )

# Selection philosophy:
# - first seek >=90% accuracy;
# - within that group maximize coverage;
# - then cheaper average ask and earlier time.
high=eligible[eligible["accuracy"]>=90.0].copy()

if len(high):
    selected=high.sort_values(
        ["coverage","accuracy","avg_ask","avg_time"],
        ascending=[False,False,True,False],
    ).iloc[0]
    selection_note=">=90% WALK-FORWARD GROUP; MAX COVERAGE"
else:
    selected=eligible.sort_values(
        ["accuracy","coverage","avg_ask","avg_time"],
        ascending=[False,False,True,False],
    ).iloc[0]
    selection_note="NO >=90% GROUP; BEST HONEST FALLBACK"

sel_key=(
    selected["feature_set"],
    selected["model"],
    selected["gate"],
    float(selected["threshold"]),
)

wf_sig=wf_signal_store[sel_key].copy()
wf_m=metrics(
    wf_sig,
    sorted(wf_sig["contract"].unique()) if False else
    list(set().union(*[set(test) for _,test in folds]))
)

print("-"*78)
print("WALK-FORWARD SELECTED CONFIG:")
print(
    f"  {sel_key[1]} / {sel_key[0]} / {sel_key[2]} / "
    f"threshold {sel_key[3]:.2f}"
)
print(f"  Selection: {selection_note}")
print(f"  WALK-FORWARD: {fmt(wf_m)}")

# Retrain selected config on ALL development contracts.
features=[c for c in feature_sets[sel_key[0]] if c in d.columns]
tr=d[d["contract"].isin(dev_contracts)].copy()
ho=d[d["contract"].isin(hold_contracts)].copy()

X,y,Xh,w=prep_xy(tr,ho,features)
model=fit_model(build_model(sel_key[1]),X,y,w)
ho=ho.copy()
ho["prob"]=model.predict_proba(Xh)[:,1]

hold_sig=first_signal_from_predictions(
    ho, sel_key[3], sel_key[2]
)
hold_m=metrics(hold_sig,hold_contracts)

print(f"  UNTOUCHED HOLDOUT: {fmt(hold_m)}")

# Descriptive all-contract fit, never used for selection.
Xa,ya,_,wa=prep_xy(d,d,features)
all_model=fit_model(build_model(sel_key[1]),Xa,ya,wa)
allp=d.copy()
allp["prob"]=all_model.predict_proba(Xa)[:,1]
all_sig=first_signal_from_predictions(
    allp,sel_key[3],sel_key[2]
)
all_m=metrics(all_sig,order)
print(f"  ALL FULL CONTRACTS (descriptive): {fmt(all_m)}")

grid.to_csv(OUT_GRID,index=False)
wf_sig.to_csv(OUT_WF,index=False)
hold_sig.to_csv(OUT_HOLD,index=False)

print("-"*78)

# Compact top five development configs.
top=eligible.sort_values(
    ["accuracy","coverage","avg_ask","avg_time"],
    ascending=[False,False,True,False]
).head(5)

print("TOP 5 WALK-FORWARD CONFIGS:")
for _,r in top.iterrows():
    print(
        f"  {r['model']}/{r['feature_set']}/{r['gate']}/"
        f"{r['threshold']:.2f}: "
        f"{r['accuracy']:.1f}% | {int(r['calls'])} calls | "
        f"{r['coverage']:.1f}% cov | {r['avg_ask']:.1f}c | "
        f"{r['avg_time']:.2f}m"
    )

print("="*78)

# Acceptance is intentionally strict.
if (
    hold_m["calls"] >= 6
    and hold_m["accuracy"] >= 90.0
    and hold_m["avg_ask"] <= 45.0
    and hold_m["avg_time"] >= 5.5
):
    print("SCREEN RESULT: PROMISING ENRICHED EARLY-ENTRY CANDIDATE")
    print("NEXT: freeze exactly this candidate as SHADOW ONLY.")
    print("Do NOT production-lock from this holdout alone.")
elif (
    hold_m["calls"] >= 5
    and hold_m["accuracy"] >= 80.0
):
    print("SCREEN RESULT: SOME SIGNAL, BELOW OUR EARLY-ENTRY STANDARD")
    print("Keep collecting naturally; do not weaken FINAL/scalp.")
else:
    print("SCREEN RESULT: ENRICHED EARLY ENTRY STILL NOT STABLE ENOUGH")
    print("Do not force coverage. Preserve FINAL/scalp and continue data accumulation.")

print(f"Saved grid: {OUT_GRID}")
print(f"Saved walk-forward signals: {OUT_WF}")
print(f"Saved untouched signals: {OUT_HOLD}")
print("="*78)
