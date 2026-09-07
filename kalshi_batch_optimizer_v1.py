#!/usr/bin/env python3
"""
KALSHI BTC 15-MIN BATCH OPTIMIZER V1
====================================

Purpose
-------
Replace repeated one-hour live experiments with an offline tournament.

FINAL OUTCOME tournament
- Uses official YES/NO settlement labels from brti_calibration_results.csv.
- Rebuilds the same target-aware snapshot features used by the working
  fair-value monitor.
- Chronological split:
    50% model train
    20% probability calibration
    15% rule-selection validation
    15% untouched final holdout
- Trains the RF + sigmoid ONE TIME.
- Tests hundreds/thousands of gate combinations on validation.
- Chooses the winner using validation only.
- Reports that winner on untouched holdout.

ENTRY tournament
- Uses actual Kalshi asks from existing v4 live logs.
- Joins official settlement labels where those logged contracts are present
  in brti_calibration_results.csv.
- Sweeps ask ceilings, fair thresholds, edge thresholds, and persistence.
- Reports entry accuracy / price / timing only when enough officially settled
  logged contracts are available.

Signal-only research. No orders.
"""

from pathlib import Path
from zoneinfo import ZoneInfo
import re
import json
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

CAL = Path("brti_calibration_results.csv")
BTC_CACHE = Path("btc_35d_live_cache.csv")

FINAL_RESULTS = Path("batch_tournament_final_results.csv")
ENTRY_RESULTS = Path("batch_tournament_entry_results.csv")
SUMMARY = Path("batch_tournament_summary.txt")

MONTHS = {m:i+1 for i,m in enumerate(
    ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
)}

FEATURES = [
    "elapsed","remaining","current_side",
    "dist_target","abs_dist_target","dist_target_pct",
    "move_from_start","move_from_start_pct",
    "move1","move2","move3","move5",
    "support1","support2","support3","support5",
    "range5","vol5",
    "dist_per_min_remaining","dist_over_range5",
]

def parse_contract_times(ticker):
    m = re.search(
        r"KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-",
        str(ticker).upper(),
    )
    if not m:
        return pd.NaT, pd.NaT
    yy, mon, dd, hh, mm = m.groups()
    wall = pd.Timestamp(
        year=2000+int(yy), month=MONTHS[mon], day=int(dd),
        hour=int(hh), minute=int(mm),
    )
    close_utc = wall.tz_localize(
        ZoneInfo("America/New_York")
    ).tz_convert("UTC")
    return close_utc-pd.Timedelta(minutes=15), close_utc

def load_btc(path):
    # The working live monitor normally writes index as Datetime.
    try:
        d = pd.read_csv(path, index_col="Datetime", parse_dates=True)
    except Exception:
        d = pd.read_csv(path)
        # Try common timestamp columns.
        ts_col = None
        for c in ["Datetime","datetime","timestamp","Timestamp","time","Time"]:
            if c in d.columns:
                ts_col = c
                break
        if ts_col is None:
            # Last resort: first column if it parses as datetime.
            ts_col = d.columns[0]
        d[ts_col] = pd.to_datetime(d[ts_col], errors="coerce", utc=True)
        d = d.dropna(subset=[ts_col]).set_index(ts_col)

    idx = pd.to_datetime(d.index, errors="coerce", utc=True)
    d = d.loc[~pd.isna(idx)].copy()
    d.index = idx[~pd.isna(idx)]
    d = d[~d.index.duplicated(keep="last")].sort_index()

    # Normalize OHLC column capitalization if needed.
    rename = {}
    for want in ["Open","High","Low","Close","Volume"]:
        for c in d.columns:
            if str(c).lower() == want.lower():
                rename[c] = want
                break
    d = d.rename(columns=rename)
    need = {"High","Low","Close"}
    missing = need - set(d.columns)
    if missing:
        raise RuntimeError(f"BTC cache missing columns: {sorted(missing)}")
    return d

def price_at_or_before(data, ts):
    i = data.index.searchsorted(ts, side="right") - 1
    if i < 0:
        return np.nan, pd.NaT
    ti = data.index[i]
    if ts-ti > pd.Timedelta(minutes=2):
        return np.nan, pd.NaT
    return float(data.iloc[i]["Close"]), ti

def build_snapshot(data, start, target, final_side=None, elapsed=None, cut=None):
    if cut is None:
        cut = start + pd.Timedelta(minutes=float(elapsed))
    elapsed_actual = (cut-start).total_seconds()/60.0

    pstart, tstart = price_at_or_before(data, start)
    vals = [
        price_at_or_before(data, cut-pd.Timedelta(minutes=m))
        for m in [0,1,2,3,5]
    ]
    if pd.isna(pstart) or any(pd.isna(v[0]) for v in vals):
        return None

    p0,p1,p2,p3,p5 = [v[0] for v in vals]
    w = data.loc[
        (data.index > cut-pd.Timedelta(minutes=5))
        & (data.index <= cut)
    ]
    if len(w) < 3:
        return None
    closes = w["Close"].dropna()
    if len(closes) < 2:
        return None

    latest_used = max([tstart] + [v[1] for v in vals] + [w.index.max()])
    if latest_used > cut:
        raise RuntimeError("FUTURE DATA DETECTED")

    current_side = int(p0 >= target)
    dist = p0-target
    abs_dist = abs(dist)
    remaining = max(0.0, 15.0-elapsed_actual)
    sign = 1.0 if current_side == 1 else -1.0

    move1 = p0-p1
    move2 = p0-p2
    move3 = p0-p3
    move5 = p0-p5
    range5 = float(w["High"].max()-w["Low"].min())

    row = {
        "elapsed": float(elapsed_actual),
        "remaining": float(remaining),
        "current_side": int(current_side),
        "dist_target": float(dist),
        "abs_dist_target": float(abs_dist),
        "dist_target_pct": float(dist/target),
        "move_from_start": float(p0-pstart),
        "move_from_start_pct": float((p0-pstart)/pstart),
        "move1": float(move1),
        "move2": float(move2),
        "move3": float(move3),
        "move5": float(move5),
        "support1": float(move1*sign),
        "support2": float(move2*sign),
        "support3": float(move3*sign),
        "support5": float(move5*sign),
        "range5": float(range5),
        "vol5": float(closes.pct_change().std(ddof=0)),
        "dist_per_min_remaining": float(abs_dist/max(remaining,0.25)),
        "dist_over_range5": float(abs_dist/max(range5,1.0)),
        "current_coinbase_close": float(p0),
    }
    if final_side is not None:
        row["final_side"] = int(final_side)
        row["flip"] = int(int(final_side) != current_side)
    return row

def support_count(row):
    return int(sum(float(row[c]) > 0 for c in ["support1","support2","support3","support5"]))

def prepare_contracts_and_history():
    if not CAL.exists():
        raise SystemExit(f"MISSING REQUIRED FILE: {CAL}")
    if not BTC_CACHE.exists():
        raise SystemExit(f"MISSING REQUIRED FILE: {BTC_CACHE}")

    cal = pd.read_csv(CAL)
    required = {"ticker","target_brti","final_brti","result"}
    miss = required-set(cal.columns)
    if miss:
        raise SystemExit(f"{CAL} missing columns: {sorted(miss)}")

    pairs = cal["ticker"].map(parse_contract_times)
    cal["start"] = [x[0] for x in pairs]
    cal["close"] = [x[1] for x in pairs]
    cal["target_brti"] = pd.to_numeric(cal["target_brti"], errors="coerce")
    cal["final_brti"] = pd.to_numeric(cal["final_brti"], errors="coerce")
    cal["final_side"] = (
        cal["result"].astype(str).str.lower().map({"yes":1,"no":0})
    )
    cal = (
        cal.dropna(subset=["start","close","target_brti","final_brti","final_side"])
        .sort_values("start")
        .drop_duplicates("ticker", keep="last")
        .reset_index(drop=True)
    )

    btc = load_btc(BTC_CACHE)

    rows = []
    total = len(cal)
    print(f"Building historical snapshots from {total} officially settled contracts...")
    for i, r in cal.iterrows():
        for elapsed in range(1,15):
            s = build_snapshot(
                btc, r["start"], float(r["target_brti"]),
                final_side=int(r["final_side"]),
                elapsed=elapsed,
            )
            if s is not None:
                s["ticker"] = r["ticker"]
                s["start"] = r["start"]
                rows.append(s)
        if (i+1) % 100 == 0:
            print(f"  processed {i+1}/{total}")

    hist = pd.DataFrame(rows)
    if hist.empty:
        raise SystemExit("NO HISTORICAL FEATURE ROWS COULD BE BUILT")

    coverage = hist.groupby("ticker")["elapsed"].nunique()
    keep = coverage[coverage >= 10].index
    hist = hist[hist["ticker"].isin(keep)].copy()

    contracts = (
        hist[["ticker","start"]]
        .drop_duplicates("ticker")
        .sort_values("start")
        .reset_index(drop=True)
    )
    return cal, btc, hist, contracts

def chronological_splits(contracts):
    n = len(contracts)
    if n < 80:
        raise SystemExit(
            f"Only {n} usable contracts. Need at least 80 for tournament safety."
        )
    i1 = max(1, int(n*0.50))
    i2 = max(i1+1, int(n*0.70))
    i3 = max(i2+1, int(n*0.85))

    return (
        contracts.iloc[:i1].copy(),
        contracts.iloc[i1:i2].copy(),
        contracts.iloc[i2:i3].copy(),
        contracts.iloc[i3:].copy(),
    )

def fit_target_aware_model(hist, model_contracts, calib_contracts):
    train_ticks = set(model_contracts["ticker"])
    calib_ticks = set(calib_contracts["ticker"])
    train = hist[hist["ticker"].isin(train_ticks)].copy()
    calibrate = hist[hist["ticker"].isin(calib_ticks)].copy()

    if model_contracts["start"].max() >= calib_contracts["start"].min():
        raise RuntimeError("CHRONOLOGY FAILURE: model overlaps calibration")

    rf = RandomForestClassifier(
        n_estimators=900,
        max_depth=9,
        min_samples_leaf=12,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    print("Training target-aware RandomForest once...")
    rf.fit(train[FEATURES], train["flip"])

    calib_raw = rf.predict_proba(calibrate[FEATURES])[:,1]
    sigmoid = LogisticRegression(
        solver="lbfgs", C=1.0, max_iter=1000, random_state=42
    )
    sigmoid.fit(
        calib_raw.reshape(-1,1),
        calibrate["flip"].astype(int),
    )
    return rf, sigmoid

def add_fair_probabilities(frame, rf, sigmoid):
    d = frame.copy()
    raw_flip = rf.predict_proba(d[FEATURES])[:,1]
    flip = sigmoid.predict_proba(raw_flip.reshape(-1,1))[:,1]
    flip = np.clip(flip, 0.001, 0.999)
    d["fair_flip"] = flip
    d["fair_stay"] = 1.0-flip

    d["fair_up"] = np.where(
        d["current_side"].astype(int)==1,
        d["fair_stay"], d["fair_flip"]
    )
    d["fair_down"] = 1.0-d["fair_up"]
    d["preferred_side"] = np.where(d["fair_up"] >= d["fair_down"], 1, 0)
    d["preferred_fair"] = np.maximum(d["fair_up"], d["fair_down"])
    d["support_count"] = d.apply(support_count, axis=1)
    return d

def score_gate(frame, params):
    fair_min = params["fair_min"]
    max_time_left = params["max_time_left"]
    early_boundary = params["early_boundary"]
    early_gap = params["early_gap"]
    late_gap = params["late_gap"]
    min_support = params["min_support"]
    min_dist_range = params["min_dist_range"]

    d = frame.copy()
    req_gap = np.where(
        d["remaining"] > early_boundary,
        early_gap,
        late_gap,
    )
    qual = (
        (d["remaining"] <= max_time_left)
        & (d["preferred_fair"] >= fair_min)
        & (d["abs_dist_target"] >= req_gap)
        & (d["preferred_side"] == d["current_side"])
        & (d["support_count"] >= min_support)
        & (d["dist_over_range5"] >= min_dist_range)
    )
    q = d[qual].sort_values(["ticker","elapsed"])
    if q.empty:
        return None
    first = q.groupby("ticker", as_index=False).first()

    first["correct"] = (
        first["preferred_side"].astype(int)
        == first["final_side"].astype(int)
    )
    n = len(first)
    all_contracts = frame["ticker"].nunique()

    return {
        **params,
        "calls": int(n),
        "contracts": int(all_contracts),
        "coverage": float(n/all_contracts if all_contracts else 0),
        "accuracy": float(first["correct"].mean()),
        "avg_time_left": float(first["remaining"].mean()),
        "median_time_left": float(first["remaining"].median()),
        "pct_calls_5plus_min_left": float((first["remaining"] >= 5).mean()),
        "avg_gap": float(first["abs_dist_target"].mean()),
        "avg_fair": float(first["preferred_fair"].mean()),
    }

def final_tournament(hist, model_c, calib_c, valid_c, holdout_c):
    rf, sigmoid = fit_target_aware_model(hist, model_c, calib_c)

    valid = add_fair_probabilities(
        hist[hist["ticker"].isin(set(valid_c["ticker"]))].copy(),
        rf, sigmoid
    )
    holdout = add_fair_probabilities(
        hist[hist["ticker"].isin(set(holdout_c["ticker"]))].copy(),
        rf, sigmoid
    )

    # Broad but controlled tournament.
    fair_grid = [0.90,0.92,0.94,0.95]
    time_grid = [8.0,9.0,10.0]
    boundary_grid = [6.0,7.0,8.0]
    early_gap_grid = [75.0,90.0,100.0,110.0,125.0,150.0]
    late_gap_grid = [50.0,75.0,100.0]
    support_grid = [0,1,2,3]
    dist_range_grid = [0.0,0.5,1.0]

    results = []
    total = (
        len(fair_grid)*len(time_grid)*len(boundary_grid)
        *len(early_gap_grid)*len(late_gap_grid)
        *len(support_grid)*len(dist_range_grid)
    )
    print(f"Running FINAL tournament: {total:,} gate combinations...")

    for fair_min in fair_grid:
        for max_time_left in time_grid:
            for early_boundary in boundary_grid:
                for early_gap in early_gap_grid:
                    for late_gap in late_gap_grid:
                        for min_support in support_grid:
                            for min_dist_range in dist_range_grid:
                                p = {
                                    "fair_min":fair_min,
                                    "max_time_left":max_time_left,
                                    "early_boundary":early_boundary,
                                    "early_gap":early_gap,
                                    "late_gap":late_gap,
                                    "min_support":min_support,
                                    "min_dist_range":min_dist_range,
                                }
                                r = score_gate(valid, p)
                                if r is not None:
                                    results.append(r)

    res = pd.DataFrame(results)
    if res.empty:
        raise RuntimeError("No FINAL tournament candidates produced calls")

    # A candidate needs enough validation calls to be meaningful.
    min_calls = max(8, int(valid_c.shape[0]*0.20))
    eligible = res[res["calls"] >= min_calls].copy()
    if eligible.empty:
        eligible = res[res["calls"] >= 5].copy()
    if eligible.empty:
        eligible = res.copy()

    # Goal hierarchy:
    # 1. accuracy
    # 2. useful coverage
    # 3. earlier call timing
    # No hidden weighting that lets timing compensate for bad accuracy.
    eligible = eligible.sort_values(
        ["accuracy","coverage","avg_time_left","calls"],
        ascending=[False,False,False,False],
    ).reset_index(drop=True)

    winner_params = {
        k: eligible.iloc[0][k]
        for k in [
            "fair_min","max_time_left","early_boundary",
            "early_gap","late_gap","min_support","min_dist_range"
        ]
    }
    holdout_score = score_gate(holdout, winner_params)

    # Add rank and holdout only for the winner; don't tune on holdout.
    eligible["validation_rank"] = np.arange(1, len(eligible)+1)
    eligible.to_csv(FINAL_RESULTS, index=False)

    return eligible, winner_params, holdout_score, valid, holdout

def load_live_logs():
    files = sorted(Path(".").glob("kalshi_two_output_live_log_v4*.csv"))
    frames = []
    for f in files:
        try:
            d = pd.read_csv(f)
        except Exception:
            continue
        need = {
            "contract","timestamp_utc","time_left_min",
            "fair_ready","fair_preferred_side","fair_preferred",
            "preferred_kalshi_ask","fair_edge_vs_ask"
        }
        if not need.issubset(d.columns):
            continue
        d["source_file"] = f.name
        frames.append(d)
    if not frames:
        return pd.DataFrame()
    x = pd.concat(frames, ignore_index=True, sort=False)
    x["timestamp_utc"] = pd.to_datetime(x["timestamp_utc"], errors="coerce", utc=True)
    x = x.dropna(subset=["contract","timestamp_utc"])
    x = x.sort_values(["contract","timestamp_utc"]).drop_duplicates(
        ["contract","timestamp_utc"], keep="last"
    )
    return x

def entry_tournament(cal):
    logs = load_live_logs()
    if logs.empty:
        return pd.DataFrame(), "No compatible v4 live logs found."

    truth = (
        cal[["ticker","final_side"]]
        .drop_duplicates("ticker", keep="last")
        .rename(columns={"ticker":"contract"})
    )
    d = logs.merge(truth, on="contract", how="left")
    d["fair_preferred"] = pd.to_numeric(d["fair_preferred"], errors="coerce")
    d["preferred_kalshi_ask"] = pd.to_numeric(
        d["preferred_kalshi_ask"], errors="coerce"
    )
    d["fair_edge_vs_ask"] = pd.to_numeric(
        d["fair_edge_vs_ask"], errors="coerce"
    )
    d["time_left_min"] = pd.to_numeric(d["time_left_min"], errors="coerce")

    side_map = {"UP":1,"DOWN":0}
    d["pred_side"] = d["fair_preferred_side"].astype(str).str.upper().map(side_map)
    d = d[
        (d["fair_ready"].astype(str).str.lower().isin(["true","1","yes"]))
        & d["pred_side"].notna()
        & d["preferred_kalshi_ask"].notna()
        & d["fair_preferred"].notna()
        & d["fair_edge_vs_ask"].notna()
    ].copy()

    settled = d[d["final_side"].notna()].copy()
    settled_contracts = settled["contract"].nunique()

    rows = []
    ask_grid = [0.30,0.40,0.50]
    fair_grid = [0.60,0.65,0.70,0.75,0.80]
    edge_grid = [0.08,0.10,0.12,0.15,0.20]
    persistence_grid = [1,2,3]

    for ask_max in ask_grid:
        for fair_min in fair_grid:
            for edge_min in edge_grid:
                for persistence in persistence_grid:
                    calls = []
                    for contract, g in settled.groupby("contract", sort=False):
                        g = g.sort_values("timestamp_utc").copy()
                        streak = 0
                        last_side = None
                        picked = None
                        for _, r in g.iterrows():
                            candidate = bool(
                                r["preferred_kalshi_ask"] <= ask_max
                                and r["fair_preferred"] >= fair_min
                                and r["fair_edge_vs_ask"] >= edge_min
                            )
                            side = int(r["pred_side"])
                            if candidate:
                                if last_side == side:
                                    streak += 1
                                else:
                                    streak = 1
                                    last_side = side
                                if streak >= persistence:
                                    picked = r
                                    break
                            else:
                                streak = 0
                                last_side = None
                        if picked is not None:
                            calls.append(picked)

                    if calls:
                        c = pd.DataFrame(calls)
                        correct = (
                            c["pred_side"].astype(int)
                            == c["final_side"].astype(int)
                        )
                        rows.append({
                            "ask_max":ask_max,
                            "fair_min":fair_min,
                            "edge_min":edge_min,
                            "persistence":persistence,
                            "calls":len(c),
                            "settled_logged_contracts":settled_contracts,
                            "coverage":len(c)/settled_contracts if settled_contracts else 0,
                            "accuracy":float(correct.mean()),
                            "avg_ask":float(c["preferred_kalshi_ask"].mean()),
                            "median_ask":float(c["preferred_kalshi_ask"].median()),
                            "avg_time_left":float(c["time_left_min"].mean()),
                            "avg_fair":float(c["fair_preferred"].mean()),
                            "avg_edge":float(c["fair_edge_vs_ask"].mean()),
                        })

    res = pd.DataFrame(rows)
    if not res.empty:
        # Don't over-rank microscopic samples.
        eligible = res[res["calls"] >= 3].copy()
        if eligible.empty:
            eligible = res.copy()
        eligible = eligible.sort_values(
            ["accuracy","coverage","avg_time_left","avg_ask"],
            ascending=[False,False,False,True],
        )
        res = eligible.reset_index(drop=True)
        res.to_csv(ENTRY_RESULTS, index=False)

    note = (
        f"Compatible logged contracts: {d['contract'].nunique()} | "
        f"officially settled in calibration file: {settled_contracts}"
    )
    return res, note

def pct(x):
    return "N/A" if x is None or pd.isna(x) else f"{100*x:.1f}%"

def main():
    print("="*72)
    print("KALSHI BTC 15-MIN BATCH OPTIMIZER V1")
    print("OFFLINE TOURNAMENT — SIGNAL ONLY — NO ORDERS")
    print("="*72)

    cal, btc, hist, contracts = prepare_contracts_and_history()
    model_c, calib_c, valid_c, holdout_c = chronological_splits(contracts)

    print("\nCHRONOLOGICAL SPLIT")
    print(f"Model train: {len(model_c)} contracts")
    print(f"Calibration: {len(calib_c)} contracts")
    print(f"Validation tournament: {len(valid_c)} contracts")
    print(f"Untouched holdout: {len(holdout_c)} contracts")

    final_res, winner, holdout_score, valid, holdout = final_tournament(
        hist, model_c, calib_c, valid_c, holdout_c
    )

    entry_res, entry_note = entry_tournament(cal)

    top = final_res.iloc[0]
    lines = []
    lines.append("="*72)
    lines.append("BATCH TOURNAMENT SUMMARY")
    lines.append("="*72)
    lines.append("")
    lines.append("FINAL — VALIDATION WINNER")
    for k,v in winner.items():
        lines.append(f"{k}: {v}")
    lines.append(
        f"Validation: accuracy {pct(top['accuracy'])} | "
        f"calls {int(top['calls'])}/{int(top['contracts'])} "
        f"({pct(top['coverage'])}) | "
        f"avg time left {top['avg_time_left']:.2f}m"
    )

    lines.append("")
    lines.append("FINAL — UNTOUCHED HOLDOUT")
    if holdout_score is None:
        lines.append("Winner produced no holdout calls.")
    else:
        lines.append(
            f"Accuracy {pct(holdout_score['accuracy'])} | "
            f"calls {holdout_score['calls']}/{holdout_score['contracts']} "
            f"({pct(holdout_score['coverage'])}) | "
            f"avg time left {holdout_score['avg_time_left']:.2f}m | "
            f"median time left {holdout_score['median_time_left']:.2f}m"
        )
        lines.append(
            f"Calls with >=5m left: "
            f"{pct(holdout_score['pct_calls_5plus_min_left'])}"
        )

    lines.append("")
    lines.append("ENTRY — ACTUAL LIVE KALSHI ASKS")
    lines.append(entry_note)
    if entry_res.empty:
        lines.append(
            "Not enough officially settled compatible live-entry rows "
            "for a ranked result yet."
        )
    else:
        e = entry_res.iloc[0]
        lines.append(
            f"Top current setting: ask <= {e['ask_max']:.2f}, "
            f"fair >= {pct(e['fair_min'])}, edge >= {pct(e['edge_min'])}, "
            f"persistence {int(e['persistence'])}"
        )
        lines.append(
            f"Accuracy {pct(e['accuracy'])} | calls {int(e['calls'])} | "
            f"avg ask {100*e['avg_ask']:.1f}c | "
            f"avg time left {e['avg_time_left']:.2f}m"
        )
        lines.append(
            "CAUTION: entry ranking uses only live logged contracts that "
            "already have official settlement labels available."
        )

    lines.append("")
    lines.append("FILES WRITTEN")
    lines.append(str(FINAL_RESULTS))
    lines.append(str(ENTRY_RESULTS))
    lines.append(str(SUMMARY))
    lines.append("")
    lines.append(
        "RULE: Winner selected on validation only. Holdout is report-only; "
        "do not tune against it."
    )

    summary = "\n".join(lines)
    SUMMARY.write_text(summary)
    print("\n"+summary)

if __name__ == "__main__":
    main()
