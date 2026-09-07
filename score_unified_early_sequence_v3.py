
import base64, time, math, warnings
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
OUT_GRID = Path("unified_early_sequence_v3_grid.csv")
OUT_WF = Path("unified_early_sequence_v3_walkforward_signals.csv")
OUT_HOLD = Path("unified_early_sequence_v3_holdout_signals.csv")

KALSHI_BASE_URL = "https://api.elections.kalshi.com"
KEY_ID_PATH = Path.home() / ".kalshi" / "key_id"
PRIVATE_KEY_PATH = Path.home() / ".kalshi" / "private_key.pem"

def truthy(v):
    return str(v).strip().lower() in ("true","1","yes")

if not DATA.exists():
    raise SystemExit("ERROR: kalshi_subminute_unified_v1_1.csv not found")
if not (KEY_ID_PATH.exists() and PRIVATE_KEY_PATH.exists()):
    raise SystemExit("ERROR: Kalshi credentials not found in ~/.kalshi")

KEY_ID = KEY_ID_PATH.read_text().strip()
PRIVATE_KEY = serialization.load_pem_private_key(
    PRIVATE_KEY_PATH.read_bytes(), password=None
)

def headers(method, path):
    ts = str(int(time.time()*1000))
    msg = ts + method.upper() + path
    sig = PRIVATE_KEY.sign(
        msg.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }

def kget(path):
    r = requests.get(
        KALSHI_BASE_URL + path,
        headers=headers("GET", path),
        timeout=12,
    )
    r.raise_for_status()
    return r.json()

def official_side(ticker):
    try:
        m = kget(f"/trade-api/v2/markets/{ticker}").get("market", {})
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    for k in ("result","settlement_result","settled_result"):
        v = str(m.get(k) or "").strip().lower()
        if v == "yes":
            return "UP", k
        if v == "no":
            return "DOWN", k
    return None, "unsettled"

def num(df, c):
    if c not in df.columns:
        df[c] = np.nan
    df[c] = pd.to_numeric(df[c], errors="coerce")

def boolnum(df, src, dst):
    if src not in df.columns:
        df[dst] = 0.0
    else:
        df[dst] = df[src].map(lambda x: 1.0 if truthy(x) else 0.0)

def safe_metrics(sig, contracts):
    n = len(sig)
    if n == 0:
        return dict(
            calls=0,accuracy=np.nan,coverage=0.0,
            avg_ask=np.nan,median_ask=np.nan,pct2040=np.nan,
            avg_time=np.nan,median_time=np.nan
        )
    correct = (sig["side"] == sig["official_side"]).astype(int)
    ask = pd.to_numeric(sig["side_ask"], errors="coerce")
    mins = pd.to_numeric(sig["minutes_left"], errors="coerce")
    return dict(
        calls=n,
        accuracy=100*correct.mean(),
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
        f"{m['coverage']:.1f}% cov | avg ask {m['avg_ask']:.1f}c | "
        f"20-40c {m['pct2040']:.1f}% | avg {m['avg_time']:.2f}m left"
    )

print("="*80)
print("UNIFIED SUB-MINUTE EARLY ENTRY — SEQUENCE / TRAJECTORY V3")
print("="*80)

d = pd.read_csv(DATA)
d["timestamp_utc"] = pd.to_datetime(d["timestamp_utc"], errors="coerce", utc=True)

numeric_cols = [
    "minutes_left","seconds_left","side_ask","side_bid",
    "side_fair","side_edge","preferred_fair","preferred_edge",
    "btc_gap_side","abs_btc_gap",
    "btc_move_5s_side","btc_move_15s_side","btc_move_30s_side",
    "ask_move_5s","ask_move_15s","ask_move_30s",
    "fair_move_5s","fair_move_15s","fair_move_30s",
    "candidate_persistence_30s",
    "brti_gap_side","brti_minus_coinbase_side","brti_age_seconds",
    "dist_over_range5","range5","vol5",
]
for c in numeric_cols:
    num(d,c)

boolnum(d,"brti_ready","brti_ready_n")
boolnum(d,"brti_agrees_side","brti_agrees_n")
boolnum(d,"kalshi_lag_15s","lag15_n")
boolnum(d,"kalshi_lag_30s","lag30_n")
boolnum(d,"preferred_side_match","preferred_side_match_n")

d["reversal_state"] = d.get(
    "reversal_state", pd.Series("",index=d.index)
).fillna("").astype(str).str.upper()

d["rev_against_n"] = d["reversal_state"].isin(
    ["AGAINST","REVERSAL_WARN"]
).astype(float)
d["rev_push_n"] = d["reversal_state"].isin(
    ["PUSH"]
).astype(float)
d["rev_pullback_n"] = d["reversal_state"].isin(
    ["PULLBACK"]
).astype(float)
d["rev_mixed_n"] = d["reversal_state"].isin(
    ["MIXED","WARMING"]
).astype(float)

print(f"RAW ROWS: {len(d)}")
print(f"RAW CONTRACTS: {d['contract'].nunique()}")

# Official labels.
labels={}
for ticker in sorted(d["contract"].dropna().astype(str).unique()):
    side,_ = official_side(ticker)
    labels[ticker]=side
    time.sleep(0.05)

d["official_side"] = d["contract"].map(labels)
d = d[d["official_side"].isin(["UP","DOWN"])].copy()
print(f"OFFICIAL SETTLED: {d['contract'].nunique()}")

# Require full early-window coverage.
cov = (
    d.groupby("contract")
     .agg(
        max_minutes=("minutes_left","max"),
        min_minutes=("minutes_left","min"),
        rows=("contract","size"),
        first_ts=("timestamp_utc","min"),
     )
     .reset_index()
)
cov["full"] = (
    (cov["max_minutes"] >= 9.5)
    & (cov["min_minutes"] <= 4.2)
    & (cov["rows"] >= 100)
)
full_contracts = cov.loc[cov["full"],"contract"].tolist()

print(f"FULL 10->4m CONTRACTS: {len(full_contracts)}")
print(f"PARTIAL/THIN EXCLUDED: {len(cov)-len(full_contracts)}")

if len(full_contracts) < 20:
    raise SystemExit(
        "STOP: fewer than 20 full settled contracts. "
        "Sequence screen would be too small."
    )

d = d[d["contract"].isin(full_contracts)].copy()

# Sequence features are built chronologically, separately for each contract/side.
d = d.sort_values(["contract","side","timestamp_utc"]).copy()

base_signal_cols = [
    "side_fair","side_edge","side_ask","btc_gap_side",
    "brti_gap_side","brti_minus_coinbase_side",
    "brti_agrees_n","lag15_n","lag30_n",
    "preferred_side_match_n",
    "rev_against_n","rev_push_n","rev_pullback_n","rev_mixed_n",
]

# 5s cadence -> 6 / 12 / 18 rows approximately 30 / 60 / 90 seconds.
windows = {"30":6,"60":12,"90":18}

g = d.groupby(["contract","side"], group_keys=False)

for col in base_signal_cols:
    if col not in d.columns:
        d[col] = np.nan

    for label, w in windows.items():
        # Rolling mean captures persistence / state occupancy.
        d[f"{col}_mean_{label}"] = (
            g[col].rolling(w, min_periods=max(3,w//2)).mean()
            .reset_index(level=[0,1], drop=True)
        )

        # Past-only net change over the window.
        d[f"{col}_chg_{label}"] = (
            d[col] - g[col].shift(w-1)
        )

# Consistency measures.
for label,w in windows.items():
    d[f"fair_up_frac_{label}"] = (
        g["fair_move_5s"].rolling(w,min_periods=max(3,w//2))
        .apply(lambda x: np.mean(np.asarray(x)>=0), raw=False)
        .reset_index(level=[0,1], drop=True)
    )
    d[f"edge_pos_frac_{label}"] = (
        g["side_edge"].rolling(w,min_periods=max(3,w//2))
        .apply(lambda x: np.mean(np.asarray(x)>=0), raw=False)
        .reset_index(level=[0,1], drop=True)
    )
    d[f"ask_up_frac_{label}"] = (
        g["ask_move_5s"].rolling(w,min_periods=max(3,w//2))
        .apply(lambda x: np.mean(np.asarray(x)>=0), raw=False)
        .reset_index(level=[0,1], drop=True)
    )
    d[f"brti_agree_frac_{label}"] = d[f"brti_agrees_n_mean_{label}"]
    d[f"lag_frac_{label}"] = (
        (d[f"lag15_n_mean_{label}"] + d[f"lag30_n_mean_{label}"]) / 2.0
    )
    d[f"reversal_bad_frac_{label}"] = d[f"rev_against_n_mean_{label}"]
    d[f"push_frac_{label}"] = d[f"rev_push_n_mean_{label}"]

# Acceleration: recent 30s behavior versus prior 60/90 structure.
d["fair_accel"] = (
    d["side_fair_chg_30"] - d["side_fair_chg_60"]/2.0
)
d["edge_accel"] = (
    d["side_edge_chg_30"] - d["side_edge_chg_60"]/2.0
)
d["ask_accel"] = (
    d["side_ask_chg_30"] - d["side_ask_chg_60"]/2.0
)
d["gap_accel"] = (
    d["btc_gap_side_chg_30"] - d["btc_gap_side_chg_60"]/2.0
)

# Cheap-entry persistence in last 60/90 sec.
for label,w in [("60",12),("90",18)]:
    d[f"cheap50_frac_{label}"] = (
        g["side_ask"].rolling(w,min_periods=max(3,w//2))
        .apply(lambda x: np.mean(np.asarray(x)<=0.50), raw=False)
        .reset_index(level=[0,1], drop=True)
    )
    d[f"cheap40_frac_{label}"] = (
        g["side_ask"].rolling(w,min_periods=max(3,w//2))
        .apply(lambda x: np.mean(np.asarray(x)<=0.40), raw=False)
        .reset_index(level=[0,1], drop=True)
    )

# Candidate rows only after enough history exists.
d["sequence_ready"] = (
    d["side_fair_mean_90"].notna()
    & d["brti_agree_frac_60"].notna()
)

# Economic/time universe.
d = d[
    d["sequence_ready"]
    & d["minutes_left"].between(4.0,10.0,inclusive="both")
    & (d["side_ask"] <= 0.50)
    & d["side_fair"].notna()
].copy()

d["target"] = (d["side"] == d["official_side"]).astype(int)

order = (
    d.groupby("contract")["timestamp_utc"]
     .min().sort_values().index.tolist()
)

hold_n = max(8, int(round(len(order)*0.25)))
hold_n = min(hold_n, len(order)-14)
dev_contracts = order[:-hold_n]
hold_contracts = order[-hold_n:]

print(f"DEVELOPMENT CONTRACTS: {len(dev_contracts)}")
print(f"UNTOUCHED LATE CONTRACTS: {len(hold_contracts)}")

CORE = [
    "minutes_left","side_ask","side_fair","side_edge",
    "btc_gap_side","brti_gap_side",
    "fair_accel","edge_accel","ask_accel","gap_accel",
    "fair_up_frac_30","fair_up_frac_60","fair_up_frac_90",
    "edge_pos_frac_30","edge_pos_frac_60","edge_pos_frac_90",
    "brti_agree_frac_30","brti_agree_frac_60","brti_agree_frac_90",
    "reversal_bad_frac_30","reversal_bad_frac_60","reversal_bad_frac_90",
]
ENRICHED = CORE + [
    "side_fair_chg_30","side_fair_chg_60","side_fair_chg_90",
    "side_edge_chg_30","side_edge_chg_60","side_edge_chg_90",
    "side_ask_chg_30","side_ask_chg_60","side_ask_chg_90",
    "btc_gap_side_chg_30","btc_gap_side_chg_60","btc_gap_side_chg_90",
    "lag_frac_30","lag_frac_60","lag_frac_90",
    "push_frac_30","push_frac_60","push_frac_90",
    "cheap50_frac_60","cheap50_frac_90",
    "cheap40_frac_60","cheap40_frac_90",
    "preferred_side_match_n_mean_30",
    "preferred_side_match_n_mean_60",
    "preferred_side_match_n_mean_90",
]

feature_sets={"CORE":CORE,"ENRICHED":ENRICHED}

def build_model(name):
    if name=="LOGISTIC":
        return Pipeline([
            ("scale",StandardScaler()),
            ("model",LogisticRegression(
                C=.4,max_iter=1000,class_weight="balanced",
                random_state=11
            ))
        ])
    if name=="RF":
        return RandomForestClassifier(
            n_estimators=300,max_depth=6,min_samples_leaf=18,
            max_features="sqrt",class_weight="balanced_subsample",
            random_state=11,n_jobs=-1
        )
    if name=="HGB":
        return HistGradientBoostingClassifier(
            max_iter=220,max_depth=4,learning_rate=.035,
            min_samples_leaf=20,l2_regularization=1.2,
            random_state=11
        )
    raise ValueError(name)

def prep(train,test,features):
    X=train[features].apply(pd.to_numeric,errors="coerce")
    T=test[features].apply(pd.to_numeric,errors="coerce")
    med=X.median().fillna(0)
    X=X.fillna(med).fillna(0)
    T=T.fillna(med).fillna(0)
    y=train["target"].astype(int)
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

    if gate=="PERSIST":
        mask &= (
            (x["brti_agree_frac_60"]>=.75)
            & (x["reversal_bad_frac_60"]<=.25)
        )
    elif gate=="STRONG":
        mask &= (
            (x["brti_agree_frac_60"]>=.80)
            & (x["fair_up_frac_60"]>=.60)
            & (x["edge_pos_frac_60"]>=.60)
            & (x["reversal_bad_frac_60"]<=.20)
        )
    elif gate=="CHEAP_STRONG":
        mask &= (
            (x["brti_agree_frac_60"]>=.80)
            & (x["fair_up_frac_60"]>=.60)
            & (x["reversal_bad_frac_60"]<=.20)
            & (x["cheap50_frac_60"]>=.75)
        )

    x=x[mask].copy()
    if x.empty:
        return x

    # Earliest setup per contract.
    x=x.sort_values(
        ["contract","minutes_left","timestamp_utc","prob","side_edge"],
        ascending=[True,False,True,False,False]
    )
    return x.groupby("contract",as_index=False).head(1).copy()

# Expanding walk-forward.
n_dev=len(dev_contracts)
initial=max(12,int(round(n_dev*.45)))
remaining=n_dev-initial
fold_size=max(3,int(math.ceil(remaining/4)))

folds=[]
start=initial
while start<n_dev:
    end=min(n_dev,start+fold_size)
    folds.append((dev_contracts[:start],dev_contracts[start:end]))
    start=end

print(f"WALK-FORWARD FOLDS: {len(folds)}")

models=["LOGISTIC","RF","HGB"]
gates=["OPEN","PERSIST","STRONG","CHEAP_STRONG"]
thresholds=[.55,.60,.65,.70,.75,.80,.85,.90]

pred_store={}

for fs_name,features in feature_sets.items():
    features=[c for c in features if c in d.columns]
    for model_name in models:
        parts=[]
        for trc,tec in folds:
            tr=d[d["contract"].isin(trc)].copy()
            te=d[d["contract"].isin(tec)].copy()
            if tr.empty or te.empty or tr["target"].nunique()<2:
                continue
            X,y,T,w=prep(tr,te,features)
            model=fit_model(build_model(model_name),X,y,w)
            te=te.copy()
            te["prob"]=model.predict_proba(T)[:,1]
            parts.append(te)
        if parts:
            pred_store[(fs_name,model_name)]=pd.concat(parts,ignore_index=True)

wf_test_contracts=list(dict.fromkeys(
    c for _,test in folds for c in test
))
min_calls=max(8,int(math.ceil(len(wf_test_contracts)*.35)))

print(f"WALK-FORWARD TEST CONTRACTS: {len(wf_test_contracts)}")
print(f"MINIMUM CALLS TO QUALIFY: {min_calls}")

rows=[]
sig_store={}

for (fs,model_name),pred in pred_store.items():
    for gate in gates:
        for th in thresholds:
            sig=first_signal(pred,th,gate)
            m=safe_metrics(sig,wf_test_contracts)
            key=(fs,model_name,gate,th)
            sig_store[key]=sig
            rows.append({
                "feature_set":fs,"model":model_name,"gate":gate,
                "threshold":th,
                "calls":m["calls"],"accuracy":m["accuracy"],
                "coverage":m["coverage"],"avg_ask":m["avg_ask"],
                "median_ask":m["median_ask"],"pct2040":m["pct2040"],
                "avg_time":m["avg_time"],"median_time":m["median_time"],
            })

grid=pd.DataFrame(rows)
eligible=grid[grid["calls"]>=min_calls].copy()

if eligible.empty:
    grid.to_csv(OUT_GRID,index=False)
    raise SystemExit("NO SEQUENCE CONFIG CLEARED MINIMUM CALL COUNT.")

high=eligible[eligible["accuracy"]>=90].copy()
if len(high):
    selected=high.sort_values(
        ["coverage","accuracy","avg_ask","avg_time"],
        ascending=[False,False,True,False]
    ).iloc[0]
    note=">=90% GROUP; MAX COVERAGE"
else:
    selected=eligible.sort_values(
        ["accuracy","coverage","avg_ask","avg_time"],
        ascending=[False,False,True,False]
    ).iloc[0]
    note="NO >=90% GROUP; BEST HONEST FALLBACK"

key=(
    selected["feature_set"],selected["model"],
    selected["gate"],float(selected["threshold"])
)
wf_sig=sig_store[key]
wf_m=safe_metrics(wf_sig,wf_test_contracts)

print("-"*80)
print("WALK-FORWARD SELECTED SEQUENCE CONFIG:")
print(
    f"  {key[1]} / {key[0]} / {key[2]} / threshold {key[3]:.2f}"
)
print(f"  Selection: {note}")
print(f"  WALK-FORWARD: {fmt(wf_m)}")

# Untouched holdout.
features=[c for c in feature_sets[key[0]] if c in d.columns]
tr=d[d["contract"].isin(dev_contracts)].copy()
ho=d[d["contract"].isin(hold_contracts)].copy()

X,y,T,w=prep(tr,ho,features)
model=fit_model(build_model(key[1]),X,y,w)
ho=ho.copy()
ho["prob"]=model.predict_proba(T)[:,1]

hold_sig=first_signal(ho,key[3],key[2])
hold_m=safe_metrics(hold_sig,hold_contracts)

print(f"  UNTOUCHED HOLDOUT: {fmt(hold_m)}")

grid.to_csv(OUT_GRID,index=False)
wf_sig.to_csv(OUT_WF,index=False)
hold_sig.to_csv(OUT_HOLD,index=False)

print("-"*80)
print("TOP 5 WALK-FORWARD SEQUENCE CONFIGS:")
top=eligible.sort_values(
    ["accuracy","coverage","avg_ask","avg_time"],
    ascending=[False,False,True,False]
).head(5)

for _,r in top.iterrows():
    print(
        f"  {r['model']}/{r['feature_set']}/{r['gate']}/"
        f"{r['threshold']:.2f}: "
        f"{r['accuracy']:.1f}% | {int(r['calls'])} calls | "
        f"{r['coverage']:.1f}% cov | {r['avg_ask']:.1f}c | "
        f"{r['avg_time']:.2f}m"
    )

print("="*80)

if (
    hold_m["calls"]>=6
    and hold_m["accuracy"]>=90
    and hold_m["avg_ask"]<=45
    and hold_m["avg_time"]>=5.5
):
    print("SCREEN RESULT: PROMISING SEQUENCE-BASED EARLY CANDIDATE")
    print("NEXT: freeze exactly this setup as SHADOW ONLY.")
elif (
    hold_m["calls"]>=5
    and hold_m["accuracy"]>=80
):
    print("SCREEN RESULT: SEQUENCE MODEL SHOWS SOME SIGNAL, BELOW STANDARD")
    print("Do not weaken it. Accumulate more data naturally.")
else:
    print("SCREEN RESULT: SEQUENCE-BASED EARLY ENTRY ALSO FAILS")
    print("STOP tuning early settlement prediction from this dataset.")
    print("Preserve FINAL/scalp and redirect effort to a different opportunity path.")

print(f"Saved grid: {OUT_GRID}")
print(f"Saved walk-forward signals: {OUT_WF}")
print(f"Saved untouched signals: {OUT_HOLD}")
print("="*80)
