#!/usr/bin/env python3
"""
KALSHI BTC 15-MIN ENTRY TOURNAMENT V2 — OFFICIAL SETTLEMENT
============================================================

Goal
----
Find the best ACTUAL <=50c live Kalshi entry rule using all compatible v4 logs,
without spending one live hour per idea.

Integrity rules
---------------
- Uses the ACTUAL logged Kalshi ask at each snapshot.
- Fetches OFFICIAL Kalshi settlement for each logged contract.
- Tests many rule combinations offline.
- First 70% of settled logged contracts = rule-selection development.
- Last 30% = untouched chronological holdout.
- Winner selected on development ONLY.
- Holdout is report-only; never used to tune.
- Scores FIRST qualifying entry per contract.
- Signal only. NO ORDERS.

This does NOT modify bot.py.
"""

from pathlib import Path
from datetime import datetime, timezone
import sys, time, json, base64
import numpy as np
import pandas as pd
import requests

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

KALSHI_BASE_URL = "https://api.elections.kalshi.com"
RESULT_CACHE = Path("kalshi_logged_contract_official_results.csv")
ALL_RESULTS = Path("entry_tournament_v2_all_results.csv")
SUMMARY = Path("entry_tournament_v2_summary.txt")
WINNER_ROWS = Path("entry_tournament_v2_winner_holdout_calls.csv")

def load_auth():
    key_id_path = Path.home() / ".kalshi" / "key_id"
    key_path = Path.home() / ".kalshi" / "private_key.pem"
    if not key_id_path.exists() or not key_path.exists():
        raise SystemExit(
            "Kalshi credentials not found in ~/.kalshi. "
            "This script only reads market settlement; it places no orders."
        )
    key_id = key_id_path.read_text().strip()
    private_key = serialization.load_pem_private_key(
        key_path.read_bytes(), password=None
    )
    return key_id, private_key

KEY_ID, PRIVATE_KEY = load_auth()

def kalshi_headers(method, path):
    timestamp = str(int(time.time() * 1000))
    msg = timestamp + method.upper() + path
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
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
    }

def kalshi_get(path, params=None):
    r = requests.get(
        KALSHI_BASE_URL + path,
        headers=kalshi_headers("GET", path),
        params=params,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()

def normalize_official_result(market):
    # Current API commonly exposes result = yes/no on settled markets.
    raw = str(market.get("result", "")).strip().lower()
    if raw in {"yes","up"}:
        return "UP"
    if raw in {"no","down"}:
        return "DOWN"

    # Conservative fallbacks for possible settlement fields.
    for key in ["settlement_value", "settlement_value_dollars"]:
        val = market.get(key)
        try:
            if val is not None:
                f = float(val)
                if f >= 0.999:
                    return "UP"
                if f <= 0.001:
                    return "DOWN"
        except Exception:
            pass
    return None

def fetch_official_result(ticker):
    path = f"/trade-api/v2/markets/{ticker}"
    try:
        data = kalshi_get(path)
        market = data.get("market", data)
        result = normalize_official_result(market)
        status = str(market.get("status", "")).lower()
        return {
            "contract": ticker,
            "official_result": result,
            "market_status": status,
            "settled": bool(result in {"UP","DOWN"}),
            "fetched_utc": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "contract": ticker,
            "official_result": None,
            "market_status": "ERROR",
            "settled": False,
            "fetched_utc": datetime.now(timezone.utc).isoformat(),
            "error": str(e)[:180],
        }

def load_logs():
    files = sorted(Path(".").glob("kalshi_two_output_live_log_v4*.csv"))
    frames = []
    for f in files:
        try:
            d = pd.read_csv(f)
        except Exception:
            continue

        required = {
            "timestamp_utc","contract","time_left_min",
            "target_gap_dollars","fair_ready",
            "fair_preferred_side","fair_preferred",
            "preferred_kalshi_ask","fair_edge_vs_ask",
        }
        if not required.issubset(d.columns):
            continue

        # Use raw fair/ask fields only; do NOT inherit any version-specific
        # OPPORTUNITY decision because this tournament recomputes rules.
        keep = [
            "timestamp_utc","contract","time_left_min",
            "target_gap_dollars","fair_ready",
            "fair_preferred_side","fair_preferred",
            "preferred_kalshi_ask","fair_edge_vs_ask",
        ]
        if "dist_over_range5" in d.columns:
            keep.append("dist_over_range5")

        x = d[keep].copy()
        x["source_file"] = f.name
        frames.append(x)

    if not frames:
        raise SystemExit("No compatible kalshi_two_output_live_log_v4*.csv files found.")

    d = pd.concat(frames, ignore_index=True, sort=False)
    d["timestamp_utc"] = pd.to_datetime(
        d["timestamp_utc"], errors="coerce", utc=True
    )
    for c in [
        "time_left_min","target_gap_dollars","fair_preferred",
        "preferred_kalshi_ask","fair_edge_vs_ask","dist_over_range5"
    ]:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")

    d["fair_ready_bool"] = (
        d["fair_ready"].astype(str).str.lower().isin(["true","1","yes"])
    )
    d["fair_preferred_side"] = (
        d["fair_preferred_side"].astype(str).str.upper()
    )

    d = d[
        d["timestamp_utc"].notna()
        & d["contract"].notna()
        & d["fair_ready_bool"]
        & d["fair_preferred_side"].isin(["UP","DOWN"])
        & d["fair_preferred"].notna()
        & d["preferred_kalshi_ask"].notna()
        & d["fair_edge_vs_ask"].notna()
        & d["time_left_min"].notna()
    ].copy()

    # De-duplicate overlapping log versions by contract/timestamp. Prefer the
    # row from the latest filename when timestamps collide.
    d = d.sort_values(["contract","timestamp_utc","source_file"])
    d = d.drop_duplicates(["contract","timestamp_utc"], keep="last")
    d = d.sort_values(["timestamp_utc","contract"]).reset_index(drop=True)
    return d

def load_or_refresh_truth(contracts):
    existing = pd.DataFrame()
    if RESULT_CACHE.exists():
        try:
            existing = pd.read_csv(RESULT_CACHE)
        except Exception:
            existing = pd.DataFrame()

    existing_map = {}
    if not existing.empty and "contract" in existing.columns:
        for _, r in existing.iterrows():
            if bool(r.get("settled", False)) and str(r.get("official_result")) in {"UP","DOWN"}:
                existing_map[str(r["contract"])] = r.to_dict()

    rows = []
    to_fetch = []
    for c in contracts:
        if c in existing_map:
            rows.append(existing_map[c])
        else:
            to_fetch.append(c)

    print(
        f"Official-settlement cache: {len(rows)} settled cached | "
        f"{len(to_fetch)} contract(s) to query"
    )

    for i, c in enumerate(to_fetch, 1):
        r = fetch_official_result(c)
        rows.append(r)
        state = r.get("official_result") or r.get("market_status") or "unknown"
        print(f"  [{i}/{len(to_fetch)}] {c}: {state}")
        time.sleep(0.08)

    truth = pd.DataFrame(rows)
    if truth.empty:
        raise SystemExit("No Kalshi settlement responses available.")

    truth = truth.sort_values("contract").drop_duplicates("contract", keep="last")
    truth.to_csv(RESULT_CACHE, index=False)
    return truth

def merge_truth(d, truth):
    z = d.merge(
        truth[["contract","official_result","settled"]],
        on="contract", how="left"
    )
    z = z[
        z["official_result"].isin(["UP","DOWN"])
        & z["settled"].astype(str).str.lower().isin(["true","1","yes"])
    ].copy()
    return z

def add_sequence_features(d):
    out = []
    for contract, g in d.groupby("contract", sort=False):
        g = g.sort_values("timestamp_utc").copy()

        # Candidate persistence is recomputed GENERICALLY. It is not taken
        # from v4.4, so every bot version is evaluated on the same basis.
        prev_side = None
        streak = 0
        prev_fair = np.nan
        prev_edge = np.nan
        streaks = []
        strengthening = []

        for _, r in g.iterrows():
            side = r["fair_preferred_side"]
            if side == prev_side:
                streak += 1
            else:
                streak = 1
            is_strengthening = bool(
                side == prev_side
                and pd.notna(prev_fair)
                and pd.notna(prev_edge)
                and float(r["fair_preferred"]) >= float(prev_fair)
                and float(r["fair_edge_vs_ask"]) >= float(prev_edge)
            )
            streaks.append(streak)
            strengthening.append(is_strengthening)

            prev_side = side
            prev_fair = r["fair_preferred"]
            prev_edge = r["fair_edge_vs_ask"]

        g["same_side_streak"] = streaks
        g["fair_edge_strengthening"] = strengthening
        out.append(g)

    return pd.concat(out, ignore_index=True)

def rule_mask(d, p):
    mask = (
        (d["preferred_kalshi_ask"] <= p["ask_max"])
        & (d["fair_preferred"] >= p["fair_min"])
        & (d["fair_edge_vs_ask"] >= p["edge_min"])
        & (d["time_left_min"] >= p["min_time_left"])
        & (d["same_side_streak"] >= p["persistence"])
    )

    if p["min_gap"] > 0:
        mask &= d["target_gap_dollars"].abs() >= p["min_gap"]

    if p["strengthening_required"]:
        mask &= d["fair_edge_strengthening"]

    return mask

def score_rule(frame, p):
    q = frame[rule_mask(frame, p)].copy()
    if q.empty:
        return None, pd.DataFrame()

    # First qualifying entry per contract only.
    first = (
        q.sort_values(["contract","timestamp_utc"])
        .groupby("contract", as_index=False)
        .first()
    )
    first["correct"] = (
        first["fair_preferred_side"] == first["official_result"]
    )

    total_contracts = frame["contract"].nunique()
    n = len(first)
    return {
        **p,
        "calls": int(n),
        "contracts": int(total_contracts),
        "coverage": float(n/total_contracts if total_contracts else 0),
        "accuracy": float(first["correct"].mean()),
        "avg_ask": float(first["preferred_kalshi_ask"].mean()),
        "median_ask": float(first["preferred_kalshi_ask"].median()),
        "pct_entries_30c_or_less": float(
            (first["preferred_kalshi_ask"] <= 0.30).mean()
        ),
        "avg_time_left": float(first["time_left_min"].mean()),
        "median_time_left": float(first["time_left_min"].median()),
        "avg_fair": float(first["fair_preferred"].mean()),
        "avg_edge": float(first["fair_edge_vs_ask"].mean()),
        "avg_abs_target_gap": float(first["target_gap_dollars"].abs().mean()),
    }, first

def tournament(dev):
    ask_grid = [0.30,0.35,0.40,0.45,0.50]
    fair_grid = [0.60,0.65,0.70,0.75,0.80]
    edge_grid = [0.08,0.10,0.12,0.15,0.20,0.25]
    min_time_grid = [2.0,4.0,6.0,8.0,10.0]
    gap_grid = [0.0,25.0,50.0,75.0,100.0]
    persistence_grid = [1,2,3]
    strengthening_grid = [False, True]

    total = (
        len(ask_grid)*len(fair_grid)*len(edge_grid)
        *len(min_time_grid)*len(gap_grid)
        *len(persistence_grid)*len(strengthening_grid)
    )
    print(f"\nENTRY TOURNAMENT: {total:,} rule combinations")

    results = []
    for ask_max in ask_grid:
        for fair_min in fair_grid:
            for edge_min in edge_grid:
                for min_time_left in min_time_grid:
                    for min_gap in gap_grid:
                        for persistence in persistence_grid:
                            for strengthening_required in strengthening_grid:
                                p = {
                                    "ask_max":ask_max,
                                    "fair_min":fair_min,
                                    "edge_min":edge_min,
                                    "min_time_left":min_time_left,
                                    "min_gap":min_gap,
                                    "persistence":persistence,
                                    "strengthening_required":strengthening_required,
                                }
                                s, _ = score_rule(dev, p)
                                if s is not None:
                                    results.append(s)

    res = pd.DataFrame(results)
    if res.empty:
        raise SystemExit("No entry rule produced a development call.")

    # Avoid selecting a one-trade miracle.
    dev_contracts = dev["contract"].nunique()
    min_calls = max(3, int(np.ceil(dev_contracts*0.20)))
    eligible = res[res["calls"] >= min_calls].copy()
    if eligible.empty:
        print(
            f"WARNING: no rule produced {min_calls} development calls; "
            "falling back to >=2 calls."
        )
        eligible = res[res["calls"] >= 2].copy()
    if eligible.empty:
        eligible = res.copy()

    # Hierarchy matches user goal:
    # 1) accuracy, 2) useful coverage, 3) earlier entry,
    # 4) cheaper price. Price/timing can NEVER compensate for worse accuracy.
    eligible = eligible.sort_values(
        ["accuracy","coverage","avg_time_left","avg_ask","calls"],
        ascending=[False,False,False,True,False],
    ).reset_index(drop=True)
    eligible["development_rank"] = np.arange(1, len(eligible)+1)
    return eligible

def fmt_pct(x):
    return "N/A" if pd.isna(x) else f"{100*float(x):.1f}%"

def main():
    print("="*76)
    print("KALSHI BTC 15-MIN ENTRY TOURNAMENT V2 — OFFICIAL SETTLEMENT")
    print("ACTUAL KALSHI ASKS — OFFLINE BATCH TEST — SIGNAL ONLY — NO ORDERS")
    print("="*76)

    logs = load_logs()
    contracts = sorted(logs["contract"].unique())
    print(
        f"Compatible live data: {len(logs)} unique snapshots | "
        f"{len(contracts)} logged contracts"
    )

    truth = load_or_refresh_truth(contracts)
    settled = merge_truth(logs, truth)
    settled = add_sequence_features(settled)

    contract_start = (
        settled.groupby("contract")["timestamp_utc"]
        .min()
        .sort_values()
    )
    ordered = list(contract_start.index)
    n = len(ordered)

    print(
        f"\nOfficially settled usable contracts: {n}/{len(contracts)}"
    )
    if n < 8:
        raise SystemExit(
            "Fewer than 8 officially settled logged contracts. "
            "Do not optimize entry rules on a tiny sample."
        )

    split = max(1, int(np.floor(n*0.70)))
    if split >= n:
        split = n-1
    dev_contracts = ordered[:split]
    hold_contracts = ordered[split:]

    dev = settled[settled["contract"].isin(dev_contracts)].copy()
    hold = settled[settled["contract"].isin(hold_contracts)].copy()

    print(
        f"Chronological development: {len(dev_contracts)} contracts | "
        f"untouched holdout: {len(hold_contracts)} contracts"
    )

    ranked = tournament(dev)
    ranked.to_csv(ALL_RESULTS, index=False)

    winner_keys = [
        "ask_max","fair_min","edge_min","min_time_left",
        "min_gap","persistence","strengthening_required",
    ]
    winner = {k: ranked.iloc[0][k] for k in winner_keys}

    dev_score, dev_calls = score_rule(dev, winner)
    hold_score, hold_calls = score_rule(hold, winner)

    if not hold_calls.empty:
        hold_calls.to_csv(WINNER_ROWS, index=False)

    top = ranked.iloc[0]
    lines = []
    lines.append("="*76)
    lines.append("ENTRY TOURNAMENT V2 SUMMARY")
    lines.append("="*76)
    lines.append("")
    lines.append("WINNER — SELECTED ON DEVELOPMENT ONLY")
    for k in winner_keys:
        lines.append(f"{k}: {winner[k]}")
    lines.append("")
    lines.append(
        f"Development: accuracy {fmt_pct(dev_score['accuracy'])} | "
        f"calls {dev_score['calls']}/{dev_score['contracts']} "
        f"({fmt_pct(dev_score['coverage'])}) | "
        f"avg ask {100*dev_score['avg_ask']:.1f}c | "
        f"avg time left {dev_score['avg_time_left']:.2f}m"
    )
    lines.append("")
    lines.append("UNTOUCHED CHRONOLOGICAL HOLDOUT")
    if hold_score is None:
        lines.append("Winner produced no holdout entries.")
    else:
        lines.append(
            f"Accuracy {fmt_pct(hold_score['accuracy'])} | "
            f"calls {hold_score['calls']}/{hold_score['contracts']} "
            f"({fmt_pct(hold_score['coverage'])}) | "
            f"avg ask {100*hold_score['avg_ask']:.1f}c | "
            f"median ask {100*hold_score['median_ask']:.1f}c"
        )
        lines.append(
            f"Avg time left {hold_score['avg_time_left']:.2f}m | "
            f"median time left {hold_score['median_time_left']:.2f}m | "
            f"<=30c entries {fmt_pct(hold_score['pct_entries_30c_or_less'])}"
        )
        lines.append(
            f"Avg fair {fmt_pct(hold_score['avg_fair'])} | "
            f"avg edge {fmt_pct(hold_score['avg_edge'])}"
        )

    lines.append("")
    lines.append("INTEGRITY")
    lines.append("- Official Kalshi settlement only")
    lines.append("- Actual logged Kalshi asks only")
    lines.append("- First qualifying entry per contract")
    lines.append("- Winner chosen without seeing holdout")
    lines.append("- No orders; bot.py unchanged")
    lines.append("")
    lines.append("FILES WRITTEN")
    lines.append(str(RESULT_CACHE))
    lines.append(str(ALL_RESULTS))
    lines.append(str(WINNER_ROWS))
    lines.append(str(SUMMARY))

    summary = "\n".join(lines)
    SUMMARY.write_text(summary)
    print("\n"+summary)

if __name__ == "__main__":
    main()
