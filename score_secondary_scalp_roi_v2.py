
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

OUT_GRID = Path("secondary_scalp_roi_v2_grid.csv")
OUT_WF = Path("secondary_scalp_roi_v2_walkforward_signals.csv")
OUT_HOLD = Path("secondary_scalp_roi_v2_holdout_signals.csv")

HORIZON_SECONDS = 180
ASK_MAX = 0.50
MIN_MOVE_CENTS = 4

ROI_CONFIGS = [
    (0.18,0.18),
    (0.18,0.25),
    (0.25,0.18),
    (0.25,0.25),
    (0.30,0.18),
    (0.30,0.25),
]

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

def roi_delta(entry, roi):
    # Round UP to the next tradable cent and never accept a micro scalp.
    return max(
        MIN_MOVE_CENTS / 100.0,
        math.ceil(float(entry) * float(roi) * 100.0 - 1e-12) / 100.0
    )

def metrics(sig, contracts, target_roi, stop_roi):
    n = len(sig)
    if n == 0:
        return dict(
            calls=0,accuracy=np.nan,coverage=0.0,
            avg_ask=np.nan,median_ask=np.nan,pct2040=np.nan,
            avg_time=np.nan,median_time=np.nan,
            avg_target_c=np.nan,avg_stop_c=np.nan
        )

    y = sig["scalp_win"].astype(int)
    ask = pd.to_numeric(sig["side_ask"], errors="coerce")
    mins = pd.to_numeric(sig["minutes_left"], errors="coerce")

    target_c = ask.map(lambda x: roi_delta(x,target_roi)*100)
    stop_c = ask.map(lambda x: roi_delta(x,stop_roi)*100)

    return dict(
        calls=n,
        accuracy=100*y.mean(),
        coverage=100*n/max(1,len(contracts)),
        avg_ask=100*ask.mean(),
        median_ask=100*ask.median(),
        pct2040=100*((ask>=.20)&(ask<=.40)).mean(),
        avg_time=mins.mean(),
        median_time=mins.median(),
        avg_target_c=target_c.mean(),
        avg_stop_c=stop_c.mean(),
    )

def fmt(m):
    if m["calls"] == 0:
        return "0 calls"
    return (
        f"{m['accuracy']:.1f}% | {m['calls']} calls | "
        f"{m['coverage']:.1f}% gap-fill cov | "
        f"avg ask {m['avg_ask']:.1f}c | "
        f"avg target +{m['avg_target_c']:.1f}c | "
        f"avg {m['avg_time']:.2f}m left"
    )

print("="*82)
print("SECONDARY SCALP GAP-FILLER — ROI-NORMALIZED TOURNAMENT V2")
print("="*82)

if not UNIFIED.exists():
    raise SystemExit("ERROR: kalshi_subminute_unified_v1_1.csv missing")

d = pd.read_csv(UNIFIED)
d["timestamp_utc"] = pd.to_datetime(
    d["timestamp_utc"], errors="coerce", utc=True
)

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
    "reversal_state",pd.Series("",index=d.index)
).fillna("").astype(str).str.upper()

for state in ["PUSH","PULLBACK","AGAINST","MIXED","WARMING","REVERSAL_WARN"]:
    d[f"rev_{state.lower()}_n"] = (
        d["reversal_state"] == state
    ).astype(float)

print(f"UNIFIED ROWS: {len(d)}")
print(f"UNIFIED CONTRACTS: {d['contract'].nunique()}")

primary_contracts=set()
if PRIMARY.exists():
    p=pd.read_csv(PRIMARY)
    if "contract" in p.columns:
        primary_contracts=set(
            p["contract"].dropna().astype(str).unique()
        )

all_contracts=set(d["contract"].dropna().astype(str).unique())
gap_contracts=sorted(all_contracts-primary_contracts)

print(
    f"PRIMARY SCALP-COVERED CONTRACTS: "
    f"{len(primary_contracts & all_contracts)}"
)
print(f"GAP CONTRACTS AVAILABLE: {len(gap_contracts)}")

if len(gap_contracts)<12:
    raise SystemExit("STOP: too few gap contracts.")

d=d[d["contract"].astype(str).isin(gap_contracts)].copy()
d=d[
    d["minutes_left"].between(2.0,10.0,inclusive="both")
    & (d["side_ask"]<=ASK_MAX)
    & d["side_bid"].notna()
].copy()

d=d.sort_values(
    ["contract","side","timestamp_utc"]
).reset_index(drop=True)

# ---------------------------------------------------------------------
# Past-only features first.
# ---------------------------------------------------------------------
g=d.groupby(["contract","side"],group_keys=False)

for col in [
    "side_ask","side_fair","side_edge","btc_gap_side",
    "brti_gap_side","brti_agrees_n","lag15_n","lag30_n",
    "rev_push_n","rev_pullback_n","rev_against_n",
    "rev_mixed_n","rev_reversal_warn_n",
]:
    for label,w in [("30",6),("60",12)]:
        d[f"{col}_mean_{label}"]=(
            g[col].rolling(w,min_periods=max(3,w//2))
             .mean().reset_index(level=[0,1],drop=True)
        )
        d[f"{col}_chg_{label}"]=d[col]-g[col].shift(w-1)

d["ask_rebound_30"]=-d["side_ask_chg_30"]
d["ask_rebound_60"]=-d["side_ask_chg_60"]
d["btc_recovery_30"]=d["btc_gap_side_chg_30"]
d["fair_recovery_30"]=d["side_fair_chg_30"]
d["brti_persist_60"]=d["brti_agrees_n_mean_60"]
d["lag_persist_60"]=(
    d["lag15_n_mean_60"]+d["lag30_n_mean_60"]
)/2.0
d["push_frac_60"]=d["rev_push_n_mean_60"]
d["pullback_frac_60"]=d["rev_pullback_n_mean_60"]
d["against_frac_60"]=d["rev_against_n_mean_60"]
d["warn_frac_60"]=d["rev_reversal_warn_n_mean_60"]

d=d[
    d["side_ask_mean_60"].notna()
    & d["brti_agrees_n_mean_60"].notna()
].copy()

# ---------------------------------------------------------------------
# Future executable-BID labels for each ROI target/stop pair.
# ---------------------------------------------------------------------
def add_labels_group(grp):
    grp=grp.sort_values("timestamp_utc").copy()
    ts=grp["timestamp_utc"].tolist()
    bids=grp["side_bid"].astype(float).to_numpy()
    asks=grp["side_ask"].astype(float).to_numpy()

    for target_roi,stop_roi in ROI_CONFIGS:
        key=f"T{int(target_roi*100)}_S{int(stop_roi*100)}"
        wins=np.zeros(len(grp),dtype=int)
        target_secs=np.full(len(grp),np.nan)
        stop_secs=np.full(len(grp),np.nan)

        for i in range(len(grp)):
            entry=asks[i]
            if not np.isfinite(entry):
                continue

            target_delta=roi_delta(entry,target_roi)
            stop_delta=roi_delta(entry,stop_roi)
            t0=ts[i]

            first_target=None
            first_stop=None

            j=i
            while j<len(grp):
                dt=(ts[j]-t0).total_seconds()
                if dt<0:
                    j+=1
                    continue
                if dt>HORIZON_SECONDS:
                    break

                b=bids[j]
                if np.isfinite(b):
                    if (
                        first_target is None
                        and b>=entry+target_delta
                    ):
                        first_target=dt

                    if (
                        first_stop is None
                        and b<=entry-stop_delta
                    ):
                        first_stop=dt

                if first_target is not None or first_stop is not None:
                    if (
                        first_target is not None
                        and (
                            first_stop is None
                            or first_target<=first_stop
                        )
                    ):
                        break
                    if (
                        first_stop is not None
                        and (
                            first_target is None
                            or first_stop<first_target
                        )
                    ):
                        break
                j+=1

            wins[i]=int(
                first_target is not None
                and (
                    first_stop is None
                    or first_target<=first_stop
                )
            )
            target_secs[i]=(
                np.nan if first_target is None
                else first_target
            )
            stop_secs[i]=(
                np.nan if first_stop is None
                else first_stop
            )

        grp[f"win_{key}"]=wins
        grp[f"target_seconds_{key}"]=target_secs
        grp[f"stop_seconds_{key}"]=stop_secs

    return grp

parts=[]
for (contract,side),grp in d.groupby(
    ["contract","side"],sort=False,dropna=False
):
    x=add_labels_group(grp.copy())
    x["contract"]=contract
    x["side"]=side
    parts.append(x)

if not parts:
    raise SystemExit("STOP: no candidate groups.")

d=pd.concat(parts,ignore_index=True)

# Keep rows with enough future observation or a decisive boundary.
last_ts=(
    d.groupby(["contract","side"])["timestamp_utc"]
     .transform("max")
)
future_obs=(last_ts-d["timestamp_utc"]).dt.total_seconds()

any_decisive=pd.Series(False,index=d.index)
for target_roi,stop_roi in ROI_CONFIGS:
    key=f"T{int(target_roi*100)}_S{int(stop_roi*100)}"
    any_decisive |= (
        d[f"target_seconds_{key}"].notna()
        | d[f"stop_seconds_{key}"].notna()
    )
d=d[(future_obs>=90)|any_decisive].copy()

order=(
    d.groupby("contract")["timestamp_utc"]
     .min().sort_values().index.tolist()
)

if len(order)<12:
    raise SystemExit("STOP: too few usable gap contracts.")

hold_n=max(4,int(round(len(order)*.25)))
hold_n=min(hold_n,len(order)-8)
dev_contracts=order[:-hold_n]
hold_contracts=order[-hold_n:]

print(f"USABLE GAP CONTRACTS: {len(order)}")
print(f"DEVELOPMENT GAP CONTRACTS: {len(dev_contracts)}")
print(f"UNTOUCHED GAP CONTRACTS: {len(hold_contracts)}")

FEATURES=[
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
FEATURES=[c for c in FEATURES if c in d.columns]

def build_model(name):
    if name=="LOGISTIC":
        return Pipeline([
            ("scale",StandardScaler()),
            ("model",LogisticRegression(
                C=.5,max_iter=1000,class_weight="balanced",
                random_state=23
            ))
        ])
    if name=="RF":
        return RandomForestClassifier(
            n_estimators=300,max_depth=6,min_samples_leaf=18,
            max_features="sqrt",class_weight="balanced_subsample",
            random_state=23,n_jobs=-1
        )
    if name=="HGB":
        return HistGradientBoostingClassifier(
            max_iter=220,max_depth=4,learning_rate=.035,
            min_samples_leaf=20,l2_regularization=1.2,
            random_state=23
        )
    raise ValueError(name)

def prep(train,test,label_col):
    X=train[FEATURES].apply(pd.to_numeric,errors="coerce")
    T=test[FEATURES].apply(pd.to_numeric,errors="coerce")
    med=X.median().fillna(0)
    X=X.fillna(med).fillna(0)
    T=T.fillna(med).fillna(0)
    y=train[label_col].astype(int)

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

    if gate=="PULLBACK":
        mask &= (
            (x["pullback_frac_60"]>=.15)
            | (x["ask_rebound_30"]>=.02)
        )
    elif gate=="LAG":
        mask &= x["lag_persist_60"]>=.25
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
    raise SystemExit("STOP: insufficient walk-forward data.")

wf_contracts=list(dict.fromkeys(
    c for _,te in folds for c in te
))
min_calls=max(4,int(math.ceil(len(wf_contracts)*.40)))

print(f"WALK-FORWARD FOLDS: {len(folds)}")
print(f"WALK-FORWARD GAP CONTRACTS: {len(wf_contracts)}")
print(f"MIN CALLS TO QUALIFY: {min_calls}")

rows=[]
store={}

for target_roi,stop_roi in ROI_CONFIGS:
    label_key=f"T{int(target_roi*100)}_S{int(stop_roi*100)}"
    label_col=f"win_{label_key}"

    for model_name in ["LOGISTIC","RF","HGB"]:
        pred_parts=[]

        for trc,tec in folds:
            tr=d[d["contract"].isin(trc)].copy()
            te=d[d["contract"].isin(tec)].copy()

            if (
                tr.empty or te.empty
                or tr[label_col].nunique()<2
            ):
                continue

            X,y,T,w=prep(tr,te,label_col)
            model=fit_model(build_model(model_name),X,y,w)
            te=te.copy()
            te["prob"]=model.predict_proba(T)[:,1]
            te["scalp_win"]=te[label_col].astype(int)
            pred_parts.append(te)

        if not pred_parts:
            continue

        pred=pd.concat(pred_parts,ignore_index=True)

        for gate in ["OPEN","PULLBACK","LAG","BRTI","HYBRID"]:
            for th in [.55,.60,.65,.70,.75,.80,.85,.90]:
                sig=first_signal(pred,th,gate)
                m=metrics(
                    sig,wf_contracts,target_roi,stop_roi
                )
                key=(
                    target_roi,stop_roi,model_name,gate,th
                )
                store[key]=sig
                rows.append({
                    "target_roi":target_roi,
                    "stop_roi":stop_roi,
                    "model":model_name,
                    "gate":gate,
                    "threshold":th,
                    "calls":m["calls"],
                    "accuracy":m["accuracy"],
                    "coverage":m["coverage"],
                    "avg_ask":m["avg_ask"],
                    "avg_target_c":m["avg_target_c"],
                    "avg_stop_c":m["avg_stop_c"],
                    "avg_time":m["avg_time"],
                })

grid=pd.DataFrame(rows)
eligible=grid[grid["calls"]>=min_calls].copy()

if eligible.empty:
    grid.to_csv(OUT_GRID,index=False)
    raise SystemExit("NO ROI CONFIG CLEARED MIN CALL COUNT.")

high=eligible[eligible["accuracy"]>=90].copy()

if len(high):
    selected=high.sort_values(
        [
            "coverage","accuracy","target_roi",
            "avg_ask","avg_time"
        ],
        ascending=[False,False,False,True,False]
    ).iloc[0]
    note=">=90% GROUP; MAX COVERAGE"
else:
    selected=eligible.sort_values(
        [
            "accuracy","coverage","target_roi",
            "avg_ask","avg_time"
        ],
        ascending=[False,False,False,True,False]
    ).iloc[0]
    note="NO >=90% GROUP; BEST HONEST FALLBACK"

key=(
    float(selected["target_roi"]),
    float(selected["stop_roi"]),
    selected["model"],
    selected["gate"],
    float(selected["threshold"]),
)

wf_sig=store[key]
wf_m=metrics(
    wf_sig,wf_contracts,key[0],key[1]
)

print("-"*82)
print("SELECTED ROI-NORMALIZED SECONDARY SCALP:")
print(
    f"  target {key[0]*100:.0f}% ROI / "
    f"stop {key[1]*100:.0f}% ROI / "
    f"{key[2]} / {key[3]} / threshold {key[4]:.2f}"
)
print(f"  Selection: {note}")
print(f"  WALK-FORWARD: {fmt(wf_m)}")

# Untouched holdout.
label_key=f"T{int(key[0]*100)}_S{int(key[1]*100)}"
label_col=f"win_{label_key}"

tr=d[d["contract"].isin(dev_contracts)].copy()
ho=d[d["contract"].isin(hold_contracts)].copy()

X,y,T,w=prep(tr,ho,label_col)
model=fit_model(build_model(key[2]),X,y,w)
ho=ho.copy()
ho["prob"]=model.predict_proba(T)[:,1]
ho["scalp_win"]=ho[label_col].astype(int)

hold_sig=first_signal(ho,key[4],key[3])
hold_m=metrics(
    hold_sig,hold_contracts,key[0],key[1]
)

print(f"  UNTOUCHED GAP HOLDOUT: {fmt(hold_m)}")

grid.to_csv(OUT_GRID,index=False)
wf_sig.to_csv(OUT_WF,index=False)
hold_sig.to_csv(OUT_HOLD,index=False)

print("-"*82)
print("TOP 5 WALK-FORWARD ROI CONFIGS:")
top=eligible.sort_values(
    ["accuracy","coverage","target_roi","avg_ask","avg_time"],
    ascending=[False,False,False,True,False]
).head(5)

for _,r in top.iterrows():
    print(
        f"  T{r['target_roi']*100:.0f}/S{r['stop_roi']*100:.0f} "
        f"{r['model']}/{r['gate']}/{r['threshold']:.2f}: "
        f"{r['accuracy']:.1f}% | {int(r['calls'])} calls | "
        f"{r['coverage']:.1f}% cov | "
        f"ask {r['avg_ask']:.1f}c | "
        f"target +{r['avg_target_c']:.1f}c | "
        f"{r['avg_time']:.2f}m"
    )

print("="*82)

if (
    hold_m["calls"]>=4
    and hold_m["accuracy"]>=90
    and hold_m["avg_ask"]<=45
    and hold_m["avg_time"]>=4.0
):
    print("SCREEN RESULT: PROMISING ROI-NORMALIZED GAP-FILLER")
    print("NEXT: freeze exactly this setup as SHADOW ONLY.")
elif (
    hold_m["calls"]>=3
    and hold_m["accuracy"]>=80
):
    print("SCREEN RESULT: SOME ROI GAP-FILLER SIGNAL, BELOW STANDARD")
    print("Do not weaken it; keep collecting naturally.")
else:
    print("SCREEN RESULT: ROI-NORMALIZED SECONDARY SCALP ALSO FAILS")
    print("CLOSE this secondary scalp branch.")
    print("Preserve FINAL + primary scalp + profit protection.")

print(f"Saved grid: {OUT_GRID}")
print(f"Saved walk-forward signals: {OUT_WF}")
print(f"Saved untouched signals: {OUT_HOLD}")
print("="*82)
