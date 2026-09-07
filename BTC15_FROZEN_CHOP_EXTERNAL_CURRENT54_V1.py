#!/usr/bin/env python3
"""
BTC15 FROZEN CHOP EXTERNAL CURRENT54 V1

Purpose:
- Freeze the old-pool candidate exactly as selected:
    logistic / enriched / threshold 0.80 / ask <= 35c
- Train it ONLY on the 60 older contracts outside the current unified sample.
- Apply it WITHOUT retuning to the current 54-contract sample.
- Primary use case: current UNION GAPS only.
- Also report all-current-contract behavior for context.
- Does NOT modify FINAL, primary scalp, or profit protection.
"""

from pathlib import Path
import math, sys, warnings
warnings.filterwarnings("ignore")

try:
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
except Exception as e:
    print("IMPORT ERROR:", e)
    sys.exit(2)

ROOT = Path(".")
SNAP = ROOT / "kalshi_scalp_shadow_snapshots_v1.csv"
EVENT = ROOT / "kalshi_scalp_shadow_events_v1.csv"
UNIFIED = ROOT / "kalshi_subminute_unified_v1_1.csv"
GAPS = ROOT / "union_coverage_gap_audit_v1_gaps.csv"

for p in (SNAP, EVENT, UNIFIED, GAPS):
    if not p.exists():
        print("MISSING:", p.name)
        sys.exit(2)

snap = pd.read_csv(SNAP, low_memory=False)
ev = pd.read_csv(EVENT, low_memory=False)
uni = pd.read_csv(UNIFIED, low_memory=False)
gaps_df = pd.read_csv(GAPS, low_memory=False)

for df,name in [(snap,"snapshot"),(ev,"event"),(uni,"unified")]:
    if "contract" not in df.columns:
        print("ERROR: contract column missing from", name)
        sys.exit(2)

# Detect gap contract column robustly.
gap_contract_col = None
for c in gaps_df.columns:
    if c.lower() == "contract":
        gap_contract_col = c
        break
if gap_contract_col is None:
    # fallback: first column containing 'contract'
    for c in gaps_df.columns:
        if "contract" in c.lower():
            gap_contract_col = c
            break
if gap_contract_col is None:
    print("ERROR: could not identify contract column in", GAPS.name)
    print("Columns:", list(gaps_df.columns))
    sys.exit(2)

snap_contracts = set(snap["contract"].dropna().astype(str))
current_contracts = set(uni["contract"].dropna().astype(str))
old_contracts = snap_contracts - current_contracts
gap_contracts = set(gaps_df[gap_contract_col].dropna().astype(str))

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

positive_asks = ev.loc[ev["entry_ask"] > 0, "entry_ask"]
median_ask_raw = float(positive_asks.median()) if len(positive_asks) else math.nan
price_scale = 100.0 if math.isfinite(median_ask_raw) and median_ask_raw <= 1.5 else 1.0

ev["entry_ask_c"] = ev["entry_ask"] * price_scale
ev["entry_bid_c"] = ev["entry_bid"] * price_scale
ev["max_future_bid_c"] = ev["max_future_bid"] * price_scale
ev["roi18_target_c"] = np.ceil(ev["entry_ask_c"] * 1.18 - 1e-12)
ev["y"] = (ev["max_future_bid_c"] >= ev["roi18_target_c"]).astype(int)

side_sign = ev["side"].astype(str).str.upper().map({"UP":1.0,"DOWN":-1.0})
ev["side_sign"] = side_sign
for c in ["btc_gap","btc_move_15s","btc_move_30s","btc_move_60s"]:
    ev["aligned_" + c] = ev[c] * ev["side_sign"]

for c in ["recent_low_60s","recent_high_60s","bounce_from_low","drawdown_from_high",
          "ask_move_15s","ask_move_30s","ask_move_60s"]:
    ev[c + "_c"] = ev[c] * price_scale

ev["market_range_60s_c"] = ev["recent_high_60s_c"] - ev["recent_low_60s_c"]
ev["entry_pos_60s"] = np.where(
    ev["market_range_60s_c"].abs() > 1e-9,
    (ev["entry_ask_c"] - ev["recent_low_60s_c"]) / ev["market_range_60s_c"],
    0.5
)

features = [
    "entry_ask_c","entry_bid_c","seconds_left",
    "aligned_btc_gap","aligned_btc_move_15s","aligned_btc_move_30s","aligned_btc_move_60s",
    "ask_move_15s_c","ask_move_30s_c","ask_move_60s_c",
    "recent_low_60s_c","recent_high_60s_c","market_range_60s_c",
    "entry_pos_60s","bounce_from_low_c","drawdown_from_high_c",
]

# Frozen candidate from old-pool V1.1.
THRESHOLD = 0.80
ASK_CEILING = 35.0

train = ev[ev["contract"].astype(str).isin(old_contracts)].copy()
test = ev[ev["contract"].astype(str).isin(current_contracts)].copy()

# Economically relevant cheap-entry universe, same as frozen screen.
train = train[(train["entry_ask_c"] > 0) & (train["entry_ask_c"] <= 45)].copy()
test = test[(test["entry_ask_c"] > 0) & (test["entry_ask_c"] <= 45)].copy()

if train["contract"].nunique() < 30 or test["contract"].nunique() < 20:
    print("ERROR: insufficient train/test contract coverage.")
    print("train contracts:", train["contract"].nunique(), "test contracts:", test["contract"].nunique())
    sys.exit(2)

Xtr = train[features].replace([np.inf,-np.inf],np.nan)
Xte = test[features].replace([np.inf,-np.inf],np.nan)
med = Xtr.median(numeric_only=True).fillna(0.0)
Xtr = Xtr.fillna(med).fillna(0.0)
Xte = Xte.fillna(med).fillna(0.0)

ytr = train["y"].astype(int)
if ytr.nunique() < 2:
    print("ERROR: old-pool labels contain only one class.")
    sys.exit(2)

model = make_pipeline(
    StandardScaler(),
    LogisticRegression(max_iter=2000, class_weight="balanced", random_state=7)
)
model.fit(Xtr, ytr)
test["pred"] = model.predict_proba(Xte)[:,1]

def first_signal(df):
    q = df[(df["pred"] >= THRESHOLD) & (df["entry_ask_c"] <= ASK_CEILING)].copy()
    if q.empty:
        return q
    q = q.sort_values("entry_timestamp_utc")
    return q.groupby("contract", as_index=False).first()

def summarize(sig, contracts):
    n = len(contracts)
    if sig.empty:
        return dict(calls=0,wins=0,acc=np.nan,cov=0.0,avgask=np.nan,avgl=np.nan)
    s = sig[sig["contract"].astype(str).isin(contracts)].copy()
    if s.empty:
        return dict(calls=0,wins=0,acc=np.nan,cov=0.0,avgask=np.nan,avgl=np.nan)
    return dict(
        calls=len(s),
        wins=int(s["y"].sum()),
        acc=float(s["y"].mean()),
        cov=float(s["contract"].nunique()/n) if n else np.nan,
        avgask=float(s["entry_ask_c"].mean()),
        avgl=float(s["seconds_left"].mean()/60.0),
    )

all_sig = first_signal(test)

# Current 54 summary.
cur_contracts = sorted(current_contracts)
s_all = summarize(all_sig, current_contracts)

# Gap-only summary.
actual_gap_contracts = gap_contracts & current_contracts
gap_sig = all_sig[all_sig["contract"].astype(str).isin(actual_gap_contracts)].copy()
s_gap = summarize(all_sig, actual_gap_contracts)

# Gap feasibility truth from event rows, independent of detector.
gap_event = test[test["contract"].astype(str).isin(actual_gap_contracts)].copy()
gap_feasible = set(
    gap_event.groupby("contract")["y"].max()
             .loc[lambda s: s == 1].index.astype(str)
)
gap_infeasible = actual_gap_contracts - gap_feasible

caught_feasible = set(gap_sig.loc[gap_sig["y"] == 1, "contract"].astype(str))
false_on_infeasible = set(gap_sig["contract"].astype(str)) & gap_infeasible
missed_feasible = gap_feasible - set(gap_sig["contract"].astype(str))
correct_passes = gap_infeasible - set(gap_sig["contract"].astype(str))

gap_sig.to_csv("frozen_chop_external_current54_gap_signals_v1.csv", index=False)
all_sig.to_csv("frozen_chop_external_current54_all_signals_v1.csv", index=False)

print("="*82)
print("BTC15 FROZEN CHOP EXTERNAL CURRENT54 V1")
print("="*82)
print(f"Frozen rule: logistic / enriched / threshold {THRESHOLD:.2f} / ask <= {ASK_CEILING:.0f}c")
print(f"Training contracts (OLD only): {train['contract'].nunique()}")
print(f"External current contracts:    {len(current_contracts)}")
print(f"Current union gaps supplied:   {len(actual_gap_contracts)}")
print(f"Detected price scale:          x{price_scale:.0f}")
print()
print("ALL CURRENT CONTRACTS — CONTEXT ONLY")
if s_all["calls"]:
    print(f"{s_all['wins']}/{s_all['calls']} = {100*s_all['acc']:.1f}%"
          f" | contract coverage {100*s_all['cov']:.1f}%"
          f" | avg ask {s_all['avgask']:.1f}c"
          f" | avg {s_all['avgl']:.2f}m left")
else:
    print("0 calls")
print()
print("PRIMARY TEST — CURRENT UNION GAPS ONLY")
print(f"Feasible 18%+ gaps by event truth: {len(gap_feasible)}/{len(actual_gap_contracts)}")
print(f"True no-opportunity gaps:           {len(gap_infeasible)}")
if s_gap["calls"]:
    print(f"Detector: {s_gap['wins']}/{s_gap['calls']} = {100*s_gap['acc']:.1f}%"
          f" | gap coverage {100*s_gap['cov']:.1f}%"
          f" | avg ask {s_gap['avgask']:.1f}c"
          f" | avg {s_gap['avgl']:.2f}m left")
else:
    print("Detector: 0 calls")
print(f"Feasible gaps caught:              {len(caught_feasible)}/{len(gap_feasible)}")
print(f"Feasible gaps missed:              {len(missed_feasible)}")
print(f"False calls on no-opportunity gaps:{len(false_on_infeasible)}")
print(f"Correct PASS on no-opportunity gaps:{len(correct_passes)}/{len(gap_infeasible)}")
print()

if gap_sig.empty:
    print("No gap signals.")
else:
    print("GAP SIGNAL DETAILS")
    for _,r in gap_sig.sort_values("entry_timestamp_utc").iterrows():
        print(f"{r['contract']} | {str(r['side']).upper()} | ask {r['entry_ask_c']:.0f}c"
              f" | {r['seconds_left']/60.0:.2f}m left"
              f" | pred {r['pred']:.3f} | {'WIN' if int(r['y']) else 'LOSS'}")
print()
print("="*82)

# Decision logic: this is an external test of the frozen old-pool candidate.
if s_gap["calls"] >= 4 and s_gap["acc"] >= 0.90 and len(false_on_infeasible) == 0:
    print("RESULT: STRONG external confirmation on current union gaps.")
    print("NEXT: freeze as a GAP-ONLY live shadow layer; do not merge into production yet.")
elif s_gap["calls"] >= 3 and s_gap["acc"] >= 0.90:
    print("RESULT: PROMISING external confirmation, but gap sample remains small.")
    print("NEXT: freeze as GAP-ONLY shadow candidate and collect future gap evidence.")
else:
    print("RESULT: Frozen old-pool candidate does NOT externally confirm strongly enough.")
    print("NEXT: do not promote; close or redesign the gap architecture.")
print("FINAL, primary scalp, and profit protection remain unchanged.")
print("="*82)
