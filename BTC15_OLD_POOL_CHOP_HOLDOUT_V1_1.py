#!/usr/bin/env python3
"""
BTC15 OLD-POOL CHOP / TEMPORARY-MOVE HOLDOUT V1.1

Fixes V1 unit bug:
- Kalshi prices in this historical event file are stored as 0.xx dollars, not whole cents.
- V1 used ceil() directly on 0.xx values, turning an 18% target into $1.00 and labeling everything false.
- V1.1 normalizes prices to cents for filtering/display and computes ROI correctly.

Purpose:
- Use ONLY the old contracts outside the current unified set.
- Select on chronological walk-forward data.
- Keep the last chronological contracts untouched.
- Ask one narrow question: can entry-time event features identify an 18%+ temporary move?
- This is NOT union coverage and does NOT alter FINAL or primary scalp.
"""

from pathlib import Path
import math, sys, warnings
warnings.filterwarnings("ignore")

try:
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
except Exception as e:
    print("IMPORT ERROR:", e)
    sys.exit(2)

ROOT = Path(".")
SNAP = ROOT / "kalshi_scalp_shadow_snapshots_v1.csv"
EVENT = ROOT / "kalshi_scalp_shadow_events_v1.csv"
UNIFIED = ROOT / "kalshi_subminute_unified_v1_1.csv"

for p in (SNAP, EVENT, UNIFIED):
    if not p.exists():
        print("MISSING:", p.name)
        sys.exit(2)

snap = pd.read_csv(SNAP, low_memory=False)
ev = pd.read_csv(EVENT, low_memory=False)
uni = pd.read_csv(UNIFIED, low_memory=False)

for df, name in [(snap,"snapshot"),(ev,"event"),(uni,"unified")]:
    if "contract" not in df.columns:
        print("ERROR: contract column missing from", name)
        sys.exit(2)

snap_contracts = set(snap["contract"].dropna().astype(str))
uni_contracts = set(uni["contract"].dropna().astype(str))
old_contracts = snap_contracts - uni_contracts
ev = ev[ev["contract"].astype(str).isin(old_contracts)].copy()

required = [
    "contract","side","entry_timestamp_utc","entry_ask","entry_bid",
    "btc_gap","seconds_left","btc_move_15s","btc_move_30s","btc_move_60s",
    "ask_move_15s","ask_move_30s","ask_move_60s",
    "recent_low_60s","recent_high_60s","bounce_from_low","drawdown_from_high",
    "max_future_bid"
]
missing = [c for c in required if c not in ev.columns]
if missing:
    print("ERROR: missing event columns:", ", ".join(missing))
    sys.exit(2)

ev["entry_timestamp_utc"] = pd.to_datetime(ev["entry_timestamp_utc"], utc=True, errors="coerce")
for c in [x for x in required if x not in ("contract","side","entry_timestamp_utc")]:
    ev[c] = pd.to_numeric(ev[c], errors="coerce")

ev = ev.dropna(subset=["contract","side","entry_timestamp_utc","entry_ask","max_future_bid"]).copy()

# Detect Kalshi price units. Historical files commonly store 0.xx dollars.
positive_asks = ev.loc[ev["entry_ask"] > 0, "entry_ask"]
median_ask_raw = float(positive_asks.median()) if len(positive_asks) else math.nan
price_scale = 100.0 if math.isfinite(median_ask_raw) and median_ask_raw <= 1.5 else 1.0

ev["entry_ask_c"] = ev["entry_ask"] * price_scale
ev["entry_bid_c"] = ev["entry_bid"] * price_scale
ev["max_future_bid_c"] = ev["max_future_bid"] * price_scale

# Correct 18% ROI test with discrete-cent target.
ev["roi18_target_c"] = np.ceil(ev["entry_ask_c"] * 1.18 - 1e-12)
ev["y"] = (ev["max_future_bid_c"] >= ev["roi18_target_c"]).astype(int)

# Keep only economically relevant cheap-entry events.
ev = ev[(ev["entry_ask_c"] > 0) & (ev["entry_ask_c"] <= 45)].copy()

side_sign = ev["side"].astype(str).str.upper().map({"UP":1.0,"DOWN":-1.0})
ev["side_sign"] = side_sign
for c in ["btc_gap","btc_move_15s","btc_move_30s","btc_move_60s"]:
    ev["aligned_" + c] = ev[c] * ev["side_sign"]

# Ask-path features normalized to cents where appropriate.
for c in ["recent_low_60s","recent_high_60s","bounce_from_low","drawdown_from_high",
          "ask_move_15s","ask_move_30s","ask_move_60s"]:
    ev[c + "_c"] = ev[c] * price_scale

ev["market_range_60s_c"] = ev["recent_high_60s_c"] - ev["recent_low_60s_c"]
ev["entry_pos_60s"] = np.where(
    ev["market_range_60s_c"].abs() > 1e-9,
    (ev["entry_ask_c"] - ev["recent_low_60s_c"]) / ev["market_range_60s_c"],
    0.5
)

core = [
    "entry_ask_c","entry_bid_c","seconds_left",
    "aligned_btc_gap","aligned_btc_move_15s","aligned_btc_move_30s","aligned_btc_move_60s",
    "ask_move_15s_c","ask_move_30s_c","ask_move_60s_c",
]
enriched = core + [
    "recent_low_60s_c","recent_high_60s_c","market_range_60s_c",
    "entry_pos_60s","bounce_from_low_c","drawdown_from_high_c",
]
feature_sets = {"core":core,"enriched":enriched}

contract_order = (
    ev.groupby("contract")["entry_timestamp_utc"].min()
      .sort_values().index.tolist()
)
n_contracts = len(contract_order)
if n_contracts < 30:
    print("ERROR: insufficient old contracts after filtering:", n_contracts)
    sys.exit(2)

holdout_n = max(12, int(round(n_contracts * 0.25)))
holdout_n = min(holdout_n, n_contracts - 24)
dev_contracts = contract_order[:-holdout_n]
holdout_contracts = contract_order[-holdout_n:]

dev_n = len(dev_contracts)
test_total = min(24, max(12, dev_n // 2))
initial_train_n = dev_n - test_total
fold_sizes = [test_total // 4] * 4
for i in range(test_total % 4):
    fold_sizes[i] += 1
folds, start = [], initial_train_n
for fs in fold_sizes:
    trc = dev_contracts[:start]
    tec = dev_contracts[start:start+fs]
    if trc and tec:
        folds.append((trc,tec))
    start += fs

def model(kind):
    if kind == "logistic":
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000,class_weight="balanced",random_state=7))
    return HistGradientBoostingClassifier(learning_rate=0.06,max_iter=180,max_leaf_nodes=12,l2_regularization=1.0,random_state=7)

def fit_predict(tr, te, feats, kind):
    Xtr = tr[feats].replace([np.inf,-np.inf],np.nan)
    Xte = te[feats].replace([np.inf,-np.inf],np.nan)
    med = Xtr.median(numeric_only=True).fillna(0.0)
    Xtr = Xtr.fillna(med).fillna(0.0)
    Xte = Xte.fillna(med).fillna(0.0)
    ytr = tr["y"].astype(int)
    if ytr.nunique() < 2:
        return np.full(len(te), float(ytr.iloc[0]) if len(ytr) else 0.0)
    m = model(kind)
    m.fit(Xtr,ytr)
    return m.predict_proba(Xte)[:,1]

def first_signal(df, thr, cap):
    q = df[(df["pred"] >= thr) & (df["entry_ask_c"] <= cap)].copy()
    if q.empty:
        return q
    q = q.sort_values("entry_timestamp_utc")
    return q.groupby("contract",as_index=False).first()

def summary(sig, ntest):
    if len(sig)==0:
        return (0,0,np.nan,0.0,np.nan,np.nan)
    return (
        len(sig), int(sig["y"].sum()), float(sig["y"].mean()),
        float(sig["contract"].nunique()/ntest),
        float(sig["entry_ask_c"].mean()),
        float(sig["seconds_left"].mean()/60.0)
    )

models = ["logistic","hgb"]
thresholds = [0.55,0.60,0.65,0.70,0.75,0.80,0.85,0.90]
caps = [30,35,40,45]
grid_rows=[]

for fname, feats in feature_sets.items():
    for kind in models:
        parts=[]; nt=0
        for fid,(trc,tec) in enumerate(folds,1):
            tr=ev[ev.contract.isin(trc)].copy()
            te=ev[ev.contract.isin(tec)].copy()
            te["pred"]=fit_predict(tr,te,feats,kind)
            te["fold"]=fid
            parts.append(te); nt += len(tec)
        wf=pd.concat(parts,ignore_index=True)
        for thr in thresholds:
            for cap in caps:
                sig=first_signal(wf,thr,cap)
                calls,wins,acc,cov,avgask,avgl=summary(sig,nt)
                grid_rows.append(dict(features=fname,model=kind,threshold=thr,ask_ceiling=cap,
                                      wf_calls=calls,wf_wins=wins,wf_accuracy=acc,wf_coverage=cov,
                                      wf_avg_ask=avgask,wf_avg_minutes_left=avgl))
grid=pd.DataFrame(grid_rows)
grid.to_csv("old_pool_chop_holdout_v1_1_grid.csv",index=False)

qual=grid[grid.wf_calls>=10].copy()
if qual.empty: qual=grid[grid.wf_calls>=6].copy()
if qual.empty: qual=grid.copy()

tier93=qual[qual.wf_accuracy>=0.93]
tier90=qual[qual.wf_accuracy>=0.90]
if not tier93.empty:
    pool=tier93; note=">=93% walk-forward group"
elif not tier90.empty:
    pool=tier90; note=">=90% walk-forward group"
else:
    pool=qual; note="NO >=90% GROUP; BEST HONEST FALLBACK"

pool=pool.sort_values(["wf_accuracy","wf_calls","wf_coverage","wf_avg_ask"],ascending=[False,False,False,True])
w=pool.iloc[0]

feats=feature_sets[w["features"]]
tr=ev[ev.contract.isin(dev_contracts)].copy()
ho=ev[ev.contract.isin(holdout_contracts)].copy()
ho["pred"]=fit_predict(tr,ho,feats,w["model"])
hsig=first_signal(ho,float(w["threshold"]),float(w["ask_ceiling"]))
hcalls,hwins,hacc,hcov,hask,hleft=summary(hsig,len(holdout_contracts))
hsig.to_csv("old_pool_chop_holdout_v1_1_holdout_signals.csv",index=False)

opp=ev.groupby("contract")["y"].max()
devopp=opp.reindex(dev_contracts).fillna(0)
hoopp=opp.reindex(holdout_contracts).fillna(0)

print("="*78)
print("BTC15 OLD-POOL CHOP / TEMPORARY-MOVE HOLDOUT V1.1")
print("="*78)
print(f"Detected price scale: x{price_scale:.0f} (raw median ask {median_ask_raw:.4f})")
print(f"Usable old contracts: {n_contracts}")
print(f"Development contracts: {len(dev_contracts)}")
print(f"Untouched holdout contracts: {len(holdout_contracts)}")
print(f"Walk-forward folds: {len(folds)}")
print(f"Walk-forward test contracts: {sum(len(t) for _,t in folds)}")
print()
print("SANITY CHECK — WAS ANY 18%+ EVENT PRESENT?")
print(f"Development: {int(devopp.sum())}/{len(devopp)} = {100*devopp.mean():.1f}%")
print(f"Untouched:   {int(hoopp.sum())}/{len(hoopp)} = {100*hoopp.mean():.1f}%")
print("These should be broadly consistent with the prior 56/60 feasibility audit.")
print()
print("SELECTED CONFIG (chosen before holdout)")
print(f"{w['model']} / {w['features']} / threshold {w['threshold']:.2f} / ask <= {w['ask_ceiling']:.0f}c")
print("Selection:",note)
print(f"WALK-FORWARD: {int(w['wf_wins'])}/{int(w['wf_calls'])} = {100*w['wf_accuracy']:.1f}%"
      f" | coverage {100*w['wf_coverage']:.1f}% | avg ask {w['wf_avg_ask']:.1f}c"
      f" | avg {w['wf_avg_minutes_left']:.2f}m left")
print()
print("UNTOUCHED HOLDOUT")
if hcalls:
    print(f"{hwins}/{hcalls} = {100*hacc:.1f}% | coverage {100*hcov:.1f}%"
          f" | avg ask {hask:.1f}c | avg {hleft:.2f}m left")
else:
    print("0 calls")
print()
print("="*78)
if int(devopp.sum()+hoopp.sum()) < 40:
    print("RESULT: SANITY CHECK FAILED — opportunity labels still do not match prior audit.")
    print("DO NOT interpret model result.")
elif w["wf_accuracy"]>=0.90 and hcalls>=6 and hacc>=0.90:
    print("RESULT: PROMISING independent old-pool detector evidence.")
    print("NEXT: freeze candidate and shadow it only on future union gaps.")
elif w["wf_accuracy"]>=0.90 and hcalls<6:
    print("RESULT: Interesting accuracy, but untouched sample is too small.")
    print("NEXT: do not promote; only freeze as future-gap shadow candidate.")
else:
    print("RESULT: Old-pool detector does NOT clear the 90% quality screen.")
    print("NEXT: close this architecture rather than repeatedly tuning it.")
print("FINAL and primary scalp remain unchanged.")
print("="*78)
