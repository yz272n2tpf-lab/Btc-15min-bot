#!/usr/bin/env python3
"""
TRUE SCALP TWO-MODE OPTIMIZER V1

Purpose:
- Separate pullback/rebound scalps from extreme-collapse reversals.
- Use event-level live shadow data.
- Preserve FINAL and Tier-1; this script does not touch bot.py.
- Chronological contract split: 18 train / 8 validation / 8 untouched holdout.
- Select on train+validation only; report holdout afterward.

Success target:
- +10c executable BID move from entry ASK before the recorded -10c stop.
- Also reports +15c and +20c follow-through.

Inputs:
  kalshi_scalp_shadow_events_v1.csv

Outputs:
  true_scalp_two_mode_summary.txt
  true_scalp_pullback_candidates.csv
  true_scalp_extreme_candidates.csv
"""

import itertools
from pathlib import Path
import numpy as np
import pandas as pd

SRC = Path("kalshi_scalp_shadow_events_v1.csv")
SUMMARY = Path("true_scalp_two_mode_summary.txt")
PULL_OUT = Path("true_scalp_pullback_candidates.csv")
EXT_OUT = Path("true_scalp_extreme_candidates.csv")

df = pd.read_csv(SRC)
df["ts"] = pd.to_datetime(df["entry_timestamp_utc"], utc=True, errors="coerce")
df["minutes_left"] = pd.to_numeric(df["seconds_left"], errors="coerce") / 60.0
df["entry_ask"] = pd.to_numeric(df["entry_ask"], errors="coerce")
df["btc_gap"] = pd.to_numeric(df["btc_gap"], errors="coerce")
df["abs_gap"] = df["btc_gap"].abs()
for c in [
    "btc_move_15s","btc_move_30s","drawdown_from_high","bounce_from_low",
    "hit_10c","hit_15c","hit_20c"
]:
    if c.startswith("hit_"):
        df[c] = df[c].astype(str).str.lower().eq("true")
    else:
        df[c] = pd.to_numeric(df[c], errors="coerce")

df["side_mom15"] = np.where(df["side"].eq("UP"), df["btc_move_15s"], -df["btc_move_15s"])
df["side_mom30"] = np.where(df["side"].eq("UP"), df["btc_move_30s"], -df["btc_move_30s"])

contracts = (
    df.groupby("contract")["ts"].min()
      .sort_values()
      .index.tolist()
)

if len(contracts) < 34:
    raise SystemExit(f"Expected at least 34 contracts, found {len(contracts)}")

train = set(contracts[:18])
valid = set(contracts[18:26])
hold = set(contracts[26:34])

def score(frame, contract_set, p):
    x = frame[frame["contract"].isin(contract_set)].copy()
    m = (
        x["entry_ask"].between(p["entry_lo"], p["entry_hi"])
        & x["minutes_left"].between(p["min_tl"], p["max_tl"])
        & (x["abs_gap"] <= p["max_gap"])
        & (x["drawdown_from_high"].fillna(-999) >= p["min_draw"])
        & (x["side_mom15"].fillna(-999) >= p["mom15"])
        & (x["side_mom30"].fillna(-999) >= p["mom30"])
    )
    q = (
        x[m].sort_values(["contract","ts"])
            .groupby("contract", as_index=False)
            .first()
    )
    if q.empty:
        return None
    return {
        "calls": len(q),
        "accuracy_10c": float(q["hit_10c"].mean()),
        "hit_15c": float(q["hit_15c"].mean()),
        "hit_20c": float(q["hit_20c"].mean()),
        "avg_ask": float(q["entry_ask"].mean()),
        "avg_time_left": float(q["minutes_left"].mean()),
    }

def search(mode):
    if mode == "pullback":
        grids = dict(
            entry_lo=[.20,.25,.30],
            entry_hi=[.35,.40,.45],
            min_tl=[4,6,8],
            max_tl=[10,12,14],
            max_gap=[25,50,75,100],
            min_draw=[0,.05,.10],
            mom15=[-20,0,10],
            mom30=[-30,0,20],
        )
        min_train_calls = 6
        min_val_calls = 3
        min_train_acc = .70
    else:
        grids = dict(
            entry_lo=[.01,.03,.05],
            entry_hi=[.10,.12,.15],
            min_tl=[4,6,8],
            max_tl=[10,12,14],
            max_gap=[10,25,50,75],
            min_draw=[0,.03,.05],
            mom15=[-20,0,10,20],
            mom30=[-30,0,20,40],
        )
        min_train_calls = 4
        min_val_calls = 2
        min_train_acc = .50

    keys = list(grids)
    rows = []
    for vals in itertools.product(*(grids[k] for k in keys)):
        p = dict(zip(keys, vals))
        if p["entry_lo"] >= p["entry_hi"] or p["min_tl"] > p["max_tl"]:
            continue
        tr = score(df, train, p)
        if not tr or tr["calls"] < min_train_calls or tr["accuracy_10c"] < min_train_acc:
            continue
        va = score(df, valid, p)
        if not va or va["calls"] < min_val_calls:
            continue
        row = {**p}
        row.update({f"train_{k}":v for k,v in tr.items()})
        row.update({f"valid_{k}":v for k,v in va.items()})
        rows.append(row)

    res = pd.DataFrame(rows)
    if res.empty:
        return res, None, None

    res = res.sort_values(
        ["valid_accuracy_10c","valid_calls","train_accuracy_10c","train_calls"],
        ascending=[False,False,False,False],
    ).reset_index(drop=True)

    winner = res.iloc[0].to_dict()
    p = {k:winner[k] for k in keys}
    holdout = score(df, hold, p)
    return res, p, holdout

pull, pull_winner, pull_hold = search("pullback")
extreme, extreme_winner, extreme_hold = search("extreme")

pull.to_csv(PULL_OUT, index=False)
extreme.to_csv(EXT_OUT, index=False)

lines = []
lines.append("TRUE SCALP TWO-MODE OPTIMIZER V1")
lines.append("="*70)
lines.append(f"Contracts: {len(contracts)} | train 18 | validation 8 | untouched holdout 8")
lines.append("")

lines.append("PULLBACK / REBOUND")
if pull_winner is None:
    lines.append("No viable candidate.")
else:
    lines.append(f"Winner: {pull_winner}")
    lines.append(f"Untouched holdout: {pull_hold}")

lines.append("")
lines.append("EXTREME-COLLAPSE REVERSAL")
if extreme_winner is None:
    lines.append("No viable candidate.")
else:
    lines.append(f"Winner: {extreme_winner}")
    lines.append(f"Untouched holdout: {extreme_hold}")

lines.append("")
lines.append("IMPORTANT")
lines.append("- Holdout is report-only and is not used to select the winner.")
lines.append("- Small contract count means this run is discovery, not final proof.")
lines.append("- FINAL and Tier-1 are untouched.")

SUMMARY.write_text("\n".join(lines))
print("\n".join(lines))
