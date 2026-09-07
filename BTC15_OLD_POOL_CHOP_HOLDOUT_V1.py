#!/usr/bin/env python3
"""
BTC15 OLD-POOL CHOP / TEMPORARY-MOVE HOLDOUT V1

Purpose:
- Use ONLY the 61-contract historical pool that sits outside the current unified set.
- Keep the last chronological contracts untouched while selecting a model only on earlier data.
- Ask one narrow question: can entry-time event features identify an 18%+ temporary move?
- This is NOT union coverage and does NOT alter FINAL or primary scalp.

Outputs:
- old_pool_chop_holdout_v1_grid.csv
- old_pool_chop_holdout_v1_holdout_signals.csv
"""

from pathlib import Path
import math
import sys
import warnings
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
    print("This scorer needs pandas/numpy/scikit-learn.")
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

if "contract" not in snap or "contract" not in ev or "contract" not in uni:
    print("ERROR: contract column missing from one required file.")
    sys.exit(2)

snap_contracts = set(snap["contract"].dropna().astype(str))
uni_contracts = set(uni["contract"].dropna().astype(str))
old_contracts = snap_contracts - uni_contracts

ev = ev[ev["contract"].astype(str).isin(old_contracts)].copy()
if ev.empty:
    print("ERROR: no old-pool event rows.")
    sys.exit(2)

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
num_cols = [c for c in required if c not in ("contract","side","entry_timestamp_utc")]
for c in num_cols:
    ev[c] = pd.to_numeric(ev[c], errors="coerce")

ev = ev.dropna(subset=["contract","side","entry_timestamp_utc","entry_ask","max_future_bid"]).copy()
ev = ev[(ev["entry_ask"] > 0) & (ev["entry_ask"] <= 45)].copy()

# Exact discrete-cents 18% ROI target.
ev["roi18_target_bid"] = np.ceil(ev["entry_ask"] * 1.18 - 1e-12)
ev["y"] = (ev["max_future_bid"] >= ev["roi18_target_bid"]).astype(int)

side = ev["side"].astype(str).str.upper().map({"UP":1.0, "DOWN":-1.0})
ev["side_sign"] = side
for c in ["btc_gap","btc_move_15s","btc_move_30s","btc_move_60s"]:
    ev["aligned_" + c] = ev[c] * ev["side_sign"]

ev["market_range_60s"] = ev["recent_high_60s"] - ev["recent_low_60s"]
ev["entry_pos_60s"] = np.where(
    ev["market_range_60s"].abs() > 1e-9,
    (ev["entry_ask"] - ev["recent_low_60s"]) / ev["market_range_60s"],
    0.5,
)

core = [
    "entry_ask","entry_bid","seconds_left",
    "aligned_btc_gap","aligned_btc_move_15s","aligned_btc_move_30s","aligned_btc_move_60s",
    "ask_move_15s","ask_move_30s","ask_move_60s",
]
enriched = core + [
    "recent_low_60s","recent_high_60s","market_range_60s",
    "entry_pos_60s","bounce_from_low","drawdown_from_high",
]
feature_sets = {"core": core, "enriched": enriched}

# Order contracts chronologically by first event time.
contract_order = (
    ev.groupby("contract")["entry_timestamp_utc"].min()
      .sort_values()
      .index.tolist()
)
n_contracts = len(contract_order)
if n_contracts < 30:
    print(f"ERROR: only {n_contracts} old contracts with usable events; need >=30.")
    sys.exit(2)

# Keep last 25% untouched, minimum 12 contracts.
holdout_n = max(12, int(round(n_contracts * 0.25)))
holdout_n = min(holdout_n, n_contracts - 24)
dev_contracts = contract_order[:-holdout_n]
holdout_contracts = contract_order[-holdout_n:]

# Four expanding walk-forward folds across the later part of development.
dev_n = len(dev_contracts)
test_total = min(24, max(12, dev_n // 2))
initial_train_n = dev_n - test_total
fold_sizes = [test_total // 4] * 4
for i in range(test_total % 4):
    fold_sizes[i] += 1

folds = []
start = initial_train_n
for fs in fold_sizes:
    train_c = dev_contracts[:start]
    test_c = dev_contracts[start:start+fs]
    if train_c and test_c:
        folds.append((train_c, test_c))
    start += fs

def clean_xy(df, feats):
    x = df[feats].replace([np.inf,-np.inf], np.nan).copy()
    # Training-median fill is handled outside for each fit.
    return x

def build_model(kind):
    if kind == "logistic":
        return make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=2000, class_weight="balanced", random_state=7)
        )
    if kind == "hgb":
        return HistGradientBoostingClassifier(
            learning_rate=0.06, max_iter=180, max_leaf_nodes=12,
            l2_regularization=1.0, random_state=7
        )
    raise ValueError(kind)

def fit_predict(train_df, test_df, feats, kind):
    Xtr = clean_xy(train_df, feats)
    Xte = clean_xy(test_df, feats)
    med = Xtr.median(numeric_only=True).fillna(0.0)
    Xtr = Xtr.fillna(med).fillna(0.0)
    Xte = Xte.fillna(med).fillna(0.0)
    ytr = train_df["y"].astype(int)
    if ytr.nunique() < 2:
        return np.full(len(test_df), ytr.iloc[0] if len(ytr) else 0.0, dtype=float)
    model = build_model(kind)
    model.fit(Xtr, ytr)
    return model.predict_proba(Xte)[:,1]

def first_signal_per_contract(df, threshold, ask_ceiling):
    q = df[(df["pred"] >= threshold) & (df["entry_ask"] <= ask_ceiling)].copy()
    if q.empty:
        return q
    q = q.sort_values(["entry_timestamp_utc"])
    return q.groupby("contract", as_index=False).first()

def summarize(sig, test_contract_count):
    calls = len(sig)
    if calls == 0:
        return dict(calls=0, wins=0, acc=np.nan, cov=0.0, avg_ask=np.nan, avg_left=np.nan)
    return dict(
        calls=calls,
        wins=int(sig["y"].sum()),
        acc=float(sig["y"].mean()),
        cov=float(sig["contract"].nunique()/test_contract_count),
        avg_ask=float(sig["entry_ask"].mean()),
        avg_left=float(sig["seconds_left"].mean()/60.0),
    )

models = ["logistic","hgb"]
thresholds = [0.55,0.60,0.65,0.70,0.75,0.80,0.85,0.90]
ask_ceilings = [30,35,40,45]

grid_rows = []

for feat_name, feats in feature_sets.items():
    for kind in models:
        fold_predictions = []
        total_test_contracts = 0
        for fold_id,(train_c,test_c) in enumerate(folds, start=1):
            tr = ev[ev["contract"].isin(train_c)].copy()
            te = ev[ev["contract"].isin(test_c)].copy()
            te["pred"] = fit_predict(tr, te, feats, kind)
            te["wf_fold"] = fold_id
            fold_predictions.append(te)
            total_test_contracts += len(test_c)
        wf = pd.concat(fold_predictions, ignore_index=True)

        for thr in thresholds:
            for cap in ask_ceilings:
                sig = first_signal_per_contract(wf, thr, cap)
                s = summarize(sig, total_test_contracts)
                grid_rows.append({
                    "features":feat_name, "model":kind, "threshold":thr, "ask_ceiling":cap,
                    "wf_calls":s["calls"],"wf_wins":s["wins"],
                    "wf_accuracy":s["acc"],"wf_coverage":s["cov"],
                    "wf_avg_ask":s["avg_ask"],"wf_avg_minutes_left":s["avg_left"],
                })

grid = pd.DataFrame(grid_rows)
grid.to_csv("old_pool_chop_holdout_v1_grid.csv", index=False)

qual = grid[grid["wf_calls"] >= 10].copy()
if qual.empty:
    qual = grid[grid["wf_calls"] >= 6].copy()
if qual.empty:
    qual = grid.copy()

# Select WITHOUT touching holdout:
# first seek >=93%, then >=90%, otherwise best honest fallback.
tier93 = qual[qual["wf_accuracy"] >= 0.93]
tier90 = qual[qual["wf_accuracy"] >= 0.90]
if not tier93.empty:
    pool = tier93
    selection_note = ">=93% walk-forward group"
elif not tier90.empty:
    pool = tier90
    selection_note = ">=90% walk-forward group"
else:
    pool = qual
    selection_note = "NO >=90% GROUP; BEST HONEST FALLBACK"

pool = pool.sort_values(
    ["wf_accuracy","wf_calls","wf_coverage","wf_avg_ask"],
    ascending=[False,False,False,True]
)
winner = pool.iloc[0]

# Fit winner on ALL development contracts, evaluate untouched holdout ONCE.
feats = feature_sets[winner["features"]]
tr = ev[ev["contract"].isin(dev_contracts)].copy()
ho = ev[ev["contract"].isin(holdout_contracts)].copy()
ho["pred"] = fit_predict(tr, ho, feats, winner["model"])
hold_sig = first_signal_per_contract(ho, float(winner["threshold"]), float(winner["ask_ceiling"]))
hs = summarize(hold_sig, len(holdout_contracts))
hold_sig.to_csv("old_pool_chop_holdout_v1_holdout_signals.csv", index=False)

# Baseline opportunity incidence by contract, for context only.
opp_by_contract = ev.groupby("contract")["y"].max()
dev_opp = opp_by_contract.reindex(dev_contracts).fillna(0)
ho_opp = opp_by_contract.reindex(holdout_contracts).fillna(0)

print("="*78)
print("BTC15 OLD-POOL CHOP / TEMPORARY-MOVE HOLDOUT V1")
print("="*78)
print(f"Usable old contracts: {n_contracts}")
print(f"Development contracts: {len(dev_contracts)}")
print(f"Untouched holdout contracts: {len(holdout_contracts)}")
print(f"Walk-forward folds: {len(folds)}")
print(f"Walk-forward test contracts: {sum(len(t) for _,t in folds)}")
print()
print("CONTEXT ONLY — WAS ANY 18%+ EVENT PRESENT?")
print(f"Development: {int(dev_opp.sum())}/{len(dev_opp)} = {100*dev_opp.mean():.1f}%")
print(f"Untouched:   {int(ho_opp.sum())}/{len(ho_opp)} = {100*ho_opp.mean():.1f}%")
print("This is feasibility, NOT detector accuracy and NOT union coverage.")
print()
print("SELECTED CONFIG (chosen before holdout)")
print(f"{winner['model']} / {winner['features']} / threshold {winner['threshold']:.2f} / ask <= {winner['ask_ceiling']:.0f}c")
print("Selection:", selection_note)
print(
    f"WALK-FORWARD: {int(winner['wf_wins'])}/{int(winner['wf_calls'])}"
    f" = {100*winner['wf_accuracy']:.1f}%"
    f" | coverage {100*winner['wf_coverage']:.1f}%"
    f" | avg ask {winner['wf_avg_ask']:.1f}c"
    f" | avg {winner['wf_avg_minutes_left']:.2f}m left"
)
print()
print("UNTOUCHED HOLDOUT")
if hs["calls"]:
    print(
        f"{hs['wins']}/{hs['calls']} = {100*hs['acc']:.1f}%"
        f" | coverage {100*hs['cov']:.1f}%"
        f" | avg ask {hs['avg_ask']:.1f}c"
        f" | avg {hs['avg_left']:.2f}m left"
    )
else:
    print("0 calls")
print()
print("="*78)
if winner["wf_accuracy"] >= 0.90 and hs["calls"] >= 6 and hs["acc"] >= 0.90:
    print("RESULT: PROMISING independent old-pool detector evidence.")
    print("NEXT: freeze this rule and test it as a shadow overlay on FUTURE union gaps.")
elif winner["wf_accuracy"] >= 0.90 and hs["calls"] < 6:
    print("RESULT: Accuracy is interesting, but untouched sample is too small.")
    print("NEXT: do not promote; use only as a frozen future-gap shadow candidate.")
else:
    print("RESULT: Old-pool detector does NOT clear the 90% quality screen.")
    print("NEXT: close this architecture rather than tuning it repeatedly.")
print("FINAL and primary scalp remain unchanged either way.")
print("="*78)
