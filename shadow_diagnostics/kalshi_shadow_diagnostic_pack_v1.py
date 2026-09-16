#!/usr/bin/env python3
"""
Read-only shadow diagnostics for the Kalshi BTC 15-minute signal-only bot.

This module NEVER imports or modifies bot.py / production ladder logic.  It reads
historical/replay snapshots, joins official settlement truth, and writes only to
an explicitly separate diagnostic output directory.

Diagnostics:
1) First-fire frontier: accuracy vs coverage vs ask price vs timing.
2) Tier-1 EARLY blocker ledger and one-gate-relaxation rescue audit.
3) Lead-survival / flip-hazard descriptive bins + chronological model.
4) Candidate -> Verify -> FINAL transition analysis.

The goal is to discover whether earlier/cheaper confidence is supported by the
existing information before any production rule is changed.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

try:
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
except Exception:  # pragma: no cover - diagnostic can still run non-model sections
    ColumnTransformer = SimpleImputer = LogisticRegression = Pipeline = StandardScaler = None


UP_WORDS = {"UP", "YES", "Y", "HIGHER", "ABOVE", "TRUE", "1"}
DOWN_WORDS = {"DOWN", "NO", "N", "LOWER", "BELOW", "FALSE", "0"}

EARLY_GATES = {
    "time_2_10m": "2 <= minutes_left <= 10",
    "ask_le_45c": "preferred-side ask <= 45c",
    "fair_ge_75": "preferred fair >= 75%",
    "edge_ge_8pp": "preferred edge >= 8 percentage points",
    "gap_ge_25": "absolute BTC/target gap >= $25",
}


def norm_side(value) -> str:
    s = str(value if value is not None else "").strip().upper()
    if s in UP_WORDS:
        return "UP"
    if s in DOWN_WORDS:
        return "DOWN"
    try:
        v = float(s)
        if v == 1:
            return "UP"
        if v == 0:
            return "DOWN"
    except Exception:
        pass
    return ""


def boolish(value) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value if value is not None else "").strip().lower() in {
        "1", "true", "yes", "y", "t"
    }


def num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def prob_series(series: pd.Series) -> pd.Series:
    x = num(series).astype(float)
    # Support both 0-1 and 0-100 encodings without changing sane 0-1 values.
    return x.where(~(x.abs() > 1.5), x / 100.0)


def cents_series(series: pd.Series) -> pd.Series:
    x = num(series).astype(float)
    return x.where(~(x.abs() <= 1.5), x * 100.0)


def parse_timestamp(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")


def first_existing(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    s = set(columns)
    for c in candidates:
        if c in s:
            return c
    return None


def load_truth_csv(path: str | Path) -> dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}
    d = pd.read_csv(p)
    contract_col = first_existing(d.columns, ["contract", "ticker", "market_ticker"])
    if not contract_col:
        return {}

    side_col = first_existing(
        d.columns,
        ["official_side", "final_side", "settlement_side", "winner", "result", "y"],
    )
    if not side_col:
        return {}

    out: dict[str, str] = {}
    for _, r in d[[contract_col, side_col]].dropna().iterrows():
        c = str(r[contract_col]).strip()
        s = norm_side(r[side_col])
        if c and s:
            out[c] = s
    return out


def fetch_kalshi_truth(contracts: Iterable[str], quiet: bool = False) -> dict[str, str]:
    live = "https://external-api.kalshi.com/trade-api/v2/markets/"
    hist = "https://external-api.kalshi.com/trade-api/v2/historical/markets/"
    out: dict[str, str] = {}
    contracts = list(dict.fromkeys(str(c).strip() for c in contracts if str(c).strip()))
    for i, c in enumerate(contracts, 1):
        q = urllib.parse.quote(c, safe="-")
        market = None
        for base in (live, hist):
            try:
                req = urllib.request.Request(
                    base + q,
                    headers={"User-Agent": "btc15-shadow-diagnostics/1.0", "Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                market = payload.get("market", payload)
                if isinstance(market, dict):
                    break
            except Exception:
                market = None
        if isinstance(market, dict):
            s = norm_side(market.get("result"))
            if s:
                out[c] = s
        if not quiet and (i % 25 == 0 or i == len(contracts)):
            print(f"truth fetch: {i}/{len(contracts)}", end="\r", flush=True)
    if contracts and not quiet:
        print()
    return out


def _derive_preferred_side(raw: pd.DataFrame) -> pd.Series:
    if "preferred_fair_side" in raw.columns:
        p = raw["preferred_fair_side"].map(norm_side)
    elif "preferred_side" in raw.columns:
        p = raw["preferred_side"].map(norm_side)
    else:
        p = pd.Series("", index=raw.index, dtype="object")

    if "side" in raw.columns and "side_fair" in raw.columns and "preferred_fair" in raw.columns:
        row_side = raw["side"].map(norm_side)
        sf = prob_series(raw["side_fair"])
        pf = prob_series(raw["preferred_fair"])
        match = sf.notna() & pf.notna() & ((sf - pf).abs() <= 1e-8)
        p = p.mask((p == "") & match, row_side)
    return p.fillna("")


def prepare_preferred_frame(raw: pd.DataFrame, truth: Mapping[str, str] | None = None) -> pd.DataFrame:
    """Collapse side-row snapshots to one preferred-side row per contract/timestamp."""
    d = raw.copy()
    contract_col = first_existing(d.columns, ["contract", "ticker", "market_ticker"])
    ts_col = first_existing(d.columns, ["timestamp_utc", "timestamp", "ts", "time"])
    if not contract_col or not ts_col:
        raise ValueError("Input needs contract/ticker and timestamp_utc/timestamp columns")

    d["contract"] = d[contract_col].astype(str).str.strip()
    d["timestamp"] = parse_timestamp(d[ts_col])
    d = d.dropna(subset=["timestamp"])
    d["row_side"] = d[first_existing(d.columns, ["side"])].map(norm_side) if "side" in d.columns else ""
    d["preferred_side"] = _derive_preferred_side(d)

    if "preferred_fair" in d.columns:
        d["fair"] = prob_series(d["preferred_fair"])
    elif "side_fair" in d.columns:
        d["fair"] = prob_series(d["side_fair"])
    else:
        d["fair"] = np.nan

    side_ask = cents_series(d["side_ask"]) if "side_ask" in d.columns else pd.Series(np.nan, index=d.index)
    opp_ask = cents_series(d["opposite_ask"]) if "opposite_ask" in d.columns else pd.Series(np.nan, index=d.index)
    same = d["row_side"].eq(d["preferred_side"])
    d["ask_c"] = np.where(same, side_ask, opp_ask)
    d["ask_c"] = pd.to_numeric(d["ask_c"], errors="coerce")

    if "preferred_edge" in d.columns:
        d["edge"] = prob_series(d["preferred_edge"])
    elif "side_edge" in d.columns:
        se = prob_series(d["side_edge"])
        d["edge"] = se.where(same)
    else:
        d["edge"] = d["fair"] - d["ask_c"] / 100.0

    d["minutes_left"] = num(d["minutes_left"]) if "minutes_left" in d.columns else (
        num(d["seconds_left"]) / 60.0 if "seconds_left" in d.columns else np.nan
    )
    d["abs_gap"] = (
        num(d["abs_btc_gap"]) if "abs_btc_gap" in d.columns
        else num(d["btc_gap"]).abs() if "btc_gap" in d.columns
        else np.nan
    )
    d["ratio"] = num(d["dist_over_range5"]) if "dist_over_range5" in d.columns else np.nan
    d["current_side"] = (
        d["current_target_side"].map(norm_side)
        if "current_target_side" in d.columns else
        np.where(num(d.get("btc_gap", pd.Series(np.nan, index=d.index))) >= 0, "UP", "DOWN")
    )

    d["brti_agree"] = d["brti_agrees_side"].map(boolish) if "brti_agrees_side" in d.columns else False
    for c in ["btc_move_5s_side", "btc_move_15s_side", "btc_move_30s_side"]:
        d[c] = num(d[c]) if c in d.columns else np.nan

    # Prefer the physical row that corresponds to preferred side; one row per timestamp.
    d["_preferred_row"] = d["row_side"].eq(d["preferred_side"]).astype(int)
    d = (
        d.sort_values(["contract", "timestamp", "_preferred_row"])
        .drop_duplicates(["contract", "timestamp"], keep="last")
        .drop(columns=["_preferred_row"])
        .reset_index(drop=True)
    )

    if truth:
        d["official_side"] = d["contract"].map(truth).fillna("")
        d["correct"] = d["preferred_side"].eq(d["official_side"]) & d["official_side"].ne("")
    else:
        d["official_side"] = ""
        d["correct"] = False
    return d


def prepare_lead_frame(raw: pd.DataFrame, truth: Mapping[str, str]) -> pd.DataFrame:
    """One row per timestamp for the currently leading target side."""
    d = raw.copy()
    contract_col = first_existing(d.columns, ["contract", "ticker", "market_ticker"])
    ts_col = first_existing(d.columns, ["timestamp_utc", "timestamp", "ts", "time"])
    if not contract_col or not ts_col:
        raise ValueError("Input needs contract/ticker and timestamp columns")
    d["contract"] = d[contract_col].astype(str).str.strip()
    d["timestamp"] = parse_timestamp(d[ts_col])
    d["row_side"] = d["side"].map(norm_side) if "side" in d.columns else ""
    if "current_target_side" in d.columns:
        d["lead_side"] = d["current_target_side"].map(norm_side)
    elif "btc_gap" in d.columns:
        d["lead_side"] = np.where(num(d["btc_gap"]) >= 0, "UP", "DOWN")
    else:
        raise ValueError("Need current_target_side or btc_gap to build lead-survival frame")

    d = d[(d["lead_side"] != "") & d["row_side"].eq(d["lead_side"])].copy()
    d = d.dropna(subset=["timestamp"])
    d = d.sort_values(["contract", "timestamp"]).drop_duplicates(["contract", "timestamp"])

    d["minutes_left"] = num(d["minutes_left"]) if "minutes_left" in d.columns else num(d["seconds_left"]) / 60.0
    d["abs_gap"] = num(d["abs_btc_gap"]) if "abs_btc_gap" in d.columns else num(d["btc_gap"]).abs()
    d["ratio"] = num(d["dist_over_range5"]) if "dist_over_range5" in d.columns else np.nan
    d["lead_ask_c"] = cents_series(d["side_ask"]) if "side_ask" in d.columns else np.nan
    d["lead_fair"] = prob_series(d["side_fair"]) if "side_fair" in d.columns else np.nan
    d["lead_edge"] = prob_series(d["side_edge"]) if "side_edge" in d.columns else np.nan
    d["brti_agree"] = d["brti_agrees_side"].map(boolish).astype(float) if "brti_agrees_side" in d.columns else np.nan
    d["lag15"] = d["kalshi_lag_15s"].map(boolish).astype(float) if "kalshi_lag_15s" in d.columns else np.nan
    d["lag30"] = d["kalshi_lag_30s"].map(boolish).astype(float) if "kalshi_lag_30s" in d.columns else np.nan

    for c in [
        "quote_advantage", "btc_move_5s_side", "btc_move_15s_side", "btc_move_30s_side",
        "btc_move_60s_side", "btc_move_120s_side", "brti_gap_side",
        "brti_minus_coinbase_side", "bounce_from_60s_low", "drawdown_from_60s_high",
        "range5", "vol5",
    ]:
        d[c] = num(d[c]) if c in d.columns else np.nan

    if "reversal_state" in d.columns:
        state = d["reversal_state"].astype(str).str.upper()
        d["reversal_risk"] = state.str.contains("MIXED|REVERS|CHOP", regex=True).astype(float)
    else:
        d["reversal_risk"] = 0.0

    # Time since the target-side last changed. This is a causal path-stability feature.
    changed = d.groupby("contract")["lead_side"].transform(lambda x: x.ne(x.shift()))
    d["_cross_ts"] = d["timestamp"].where(changed)
    d["_last_cross_ts"] = d.groupby("contract")["_cross_ts"].ffill()
    d["stable_side_seconds"] = (d["timestamp"] - d["_last_cross_ts"]).dt.total_seconds().clip(lower=0)
    d["recent_cross_60s"] = (d["stable_side_seconds"] <= 60).astype(float)
    d = d.drop(columns=["_cross_ts", "_last_cross_ts"])

    d["official_side"] = d["contract"].map(truth).fillna("")
    d = d[d["official_side"] != ""].copy()
    d["lead_survived"] = d["lead_side"].eq(d["official_side"]).astype(int)
    return d.reset_index(drop=True)


def _score_first_fire(
    df: pd.DataFrame,
    mask: pd.Series,
    total_truth_contracts: int,
    side_col: str = "preferred_side",
    ask_col: str = "ask_c",
    correct_col: str = "correct",
) -> dict:
    q = df.loc[mask].sort_values(["contract", "timestamp"]).drop_duplicates("contract", keep="first")
    n = len(q)
    scored = q[q["official_side"].ne("")] if "official_side" in q.columns else q.iloc[0:0]
    sn = len(scored)
    accuracy = float(scored[correct_col].mean()) if sn else np.nan
    return {
        "calls": n,
        "scored_calls": sn,
        "coverage": (sn / total_truth_contracts) if total_truth_contracts else np.nan,
        "accuracy": accuracy,
        "avg_ask_c": float(scored[ask_col].mean()) if sn and ask_col in scored.columns else np.nan,
        "median_ask_c": float(scored[ask_col].median()) if sn and ask_col in scored.columns else np.nan,
        "pct_le_50c": float((scored[ask_col] <= 50).mean()) if sn and ask_col in scored.columns else np.nan,
        "avg_time_left": float(scored["minutes_left"].mean()) if sn else np.nan,
        "median_time_left": float(scored["minutes_left"].median()) if sn else np.nan,
    }


def baseline_scorecard(pref: pd.DataFrame, total_truth_contracts: int) -> pd.DataFrame:
    tier1 = (
        pref["minutes_left"].between(2, 10, inclusive="both")
        & pref["ask_c"].le(45)
        & pref["fair"].ge(0.75)
        & pref["edge"].ge(0.08)
        & pref["abs_gap"].ge(25)
    )
    final = (
        pref["minutes_left"].between(0, 8, inclusive="both")
        & pref["fair"].ge(0.90)
        & np.where(pref["minutes_left"] > 6, pref["abs_gap"].ge(75), pref["abs_gap"].ge(50))
        & pref["ratio"].ge(1.0)
        & pref["preferred_side"].eq(pref["current_side"])
    )
    rows = []
    for name, mask in [("LOCKED_TIER1_EARLY", tier1), ("LOCKED_FINAL_V47", final)]:
        s = _score_first_fire(pref, pd.Series(mask, index=pref.index), total_truth_contracts)
        rows.append({"lane": name, **s})
    return pd.DataFrame(rows)


def signal_frontier(pref: pd.DataFrame, total_truth_contracts: int) -> pd.DataFrame:
    rows: list[dict] = []
    lane_specs = {
        "EARLY_WINDOW": {
            "time": pref["minutes_left"].between(2, 10, inclusive="both"),
            "fair": [0.70, 0.75, 0.80, 0.85, 0.90, 0.93],
            "ask": [40, 45, 50, 60, 70, 80, 90],
            "gap": [0, 25, 50, 75],
            "ratio": [0.0, 0.5, 1.0],
        },
        "FINAL_WINDOW": {
            "time": pref["minutes_left"].between(0.25, 8, inclusive="both"),
            "fair": [0.80, 0.85, 0.90, 0.93, 0.95],
            "ask": [50, 60, 70, 80, 90, 100],
            "gap": [25, 50, 75],
            "ratio": [0.5, 1.0],
        },
    }

    # If ratio is unavailable for a snapshot, ratio>0 candidates should fail rather
    # than silently gain coverage.
    ratio = pref["ratio"].fillna(-np.inf)
    for lane, spec in lane_specs.items():
        time_mask = spec["time"]
        for fair_t, ask_cap, gap_min, ratio_min in itertools.product(
            spec["fair"], spec["ask"], spec["gap"], spec["ratio"]
        ):
            mask = (
                time_mask
                & pref["fair"].ge(fair_t)
                & pref["ask_c"].le(ask_cap)
                & pref["abs_gap"].ge(gap_min)
                & ratio.ge(ratio_min)
            )
            score = _score_first_fire(pref, mask, total_truth_contracts)
            rows.append(
                {
                    "lane": lane,
                    "fair_min": fair_t,
                    "ask_cap_c": ask_cap,
                    "gap_min": gap_min,
                    "ratio_min": ratio_min,
                    **score,
                }
            )
    return pd.DataFrame(rows)


def early_blocker_audit(pref: pd.DataFrame, truth: Mapping[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = pref.copy()
    d["g_time_2_10m"] = d["minutes_left"].between(2, 10, inclusive="both")
    d["g_ask_le_45c"] = d["ask_c"].le(45)
    d["g_fair_ge_75"] = d["fair"].ge(0.75)
    d["g_edge_ge_8pp"] = d["edge"].ge(0.08)
    d["g_gap_ge_25"] = d["abs_gap"].ge(25)
    gate_cols = [f"g_{k}" for k in EARLY_GATES]
    d["gate_passes"] = d[gate_cols].sum(axis=1)
    d["full_pass"] = d[gate_cols].all(axis=1)

    ledger_rows = []
    for contract, g in d.groupby("contract", sort=False):
        g = g.sort_values("timestamp")
        full = g[g["full_pass"]]
        if len(full):
            first = full.iloc[0]
            ledger_rows.append(
                {
                    "contract": contract,
                    "official_side": truth.get(contract, ""),
                    "qualified": True,
                    "nearest_timestamp": first["timestamp"],
                    "nearest_side": first["preferred_side"],
                    "nearest_correct": bool(first["correct"]) if truth.get(contract) else np.nan,
                    "nearest_ask_c": first["ask_c"],
                    "nearest_fair": first["fair"],
                    "nearest_edge": first["edge"],
                    "nearest_time_left": first["minutes_left"],
                    "nearest_abs_gap": first["abs_gap"],
                    "failed_gates": "",
                    "failed_gate_count": 0,
                }
            )
            continue

        # Choose the closest row to the exact Tier-1 rule; ties prefer higher fair,
        # bigger edge, cheaper ask, then the earliest chronological snapshot.
        ranked = g.copy()
        ranked["_ask_rank"] = -ranked["ask_c"].fillna(999)
        ranked = ranked.sort_values(
            ["gate_passes", "fair", "edge", "_ask_rank", "timestamp"],
            ascending=[False, False, False, False, True],
        )
        r = ranked.iloc[0]
        failed = [name for name in EARLY_GATES if not bool(r[f"g_{name}"])]
        ledger_rows.append(
            {
                "contract": contract,
                "official_side": truth.get(contract, ""),
                "qualified": False,
                "nearest_timestamp": r["timestamp"],
                "nearest_side": r["preferred_side"],
                "nearest_correct": (
                    bool(r["preferred_side"] == truth.get(contract)) if truth.get(contract) else np.nan
                ),
                "nearest_ask_c": r["ask_c"],
                "nearest_fair": r["fair"],
                "nearest_edge": r["edge"],
                "nearest_time_left": r["minutes_left"],
                "nearest_abs_gap": r["abs_gap"],
                "failed_gates": "|".join(failed),
                "failed_gate_count": len(failed),
            }
        )

    ledger = pd.DataFrame(ledger_rows)

    summary_rows = []
    for gate_name in EARLY_GATES:
        gate = f"g_{gate_name}"
        other = [c for c in gate_cols if c != gate]
        rescues = []
        for contract, g in d.groupby("contract", sort=False):
            if g["full_pass"].any():
                continue
            q = g[g[other].all(axis=1)]
            if q.empty:
                continue
            first = q.sort_values("timestamp").iloc[0]
            rescues.append(first)
        if rescues:
            q = pd.DataFrame(rescues)
            scored = q[q["official_side"].ne("")]
            rescue_acc = (
                float(scored["preferred_side"].eq(scored["official_side"]).mean())
                if len(scored) else np.nan
            )
            avg_ask = float(scored["ask_c"].mean()) if len(scored) else np.nan
            avg_time = float(scored["minutes_left"].mean()) if len(scored) else np.nan
        else:
            rescue_acc = avg_ask = avg_time = np.nan

        nearest_count = int(
            ledger.loc[~ledger["qualified"], "failed_gates"]
            .fillna("")
            .str.split("|")
            .map(lambda xs: gate_name in xs)
            .sum()
        ) if len(ledger) else 0

        sole_count = int(
            (
                (~ledger["qualified"])
                & ledger["failed_gates"].fillna("").eq(gate_name)
            ).sum()
        ) if len(ledger) else 0

        summary_rows.append(
            {
                "gate": gate_name,
                "description": EARLY_GATES[gate_name],
                "nearest_blocker_contracts": nearest_count,
                "sole_blocker_contracts": sole_count,
                "one_gate_removed_rescue_contracts": len(rescues),
                "rescue_accuracy": rescue_acc,
                "rescue_avg_ask_c": avg_ask,
                "rescue_avg_time_left": avg_time,
            }
        )
    return ledger, pd.DataFrame(summary_rows)


def survival_descriptive_bins(lead: pd.DataFrame) -> pd.DataFrame:
    if lead.empty:
        return pd.DataFrame()
    d = lead.copy()
    d["time_bin"] = pd.cut(
        d["minutes_left"],
        bins=[-np.inf, 2, 4, 6, 8, 10, np.inf],
        labels=["<=2", "2-4", "4-6", "6-8", "8-10", ">10"],
        right=True,
    )
    d["ratio_bin"] = pd.cut(
        d["ratio"],
        bins=[-np.inf, 0.25, 0.5, 1.0, 1.5, 2.0, np.inf],
        labels=["<=0.25", "0.25-0.5", "0.5-1.0", "1.0-1.5", "1.5-2.0", ">2.0"],
        right=True,
    )
    d["brti_state"] = np.where(d["brti_agree"].eq(1.0), "AGREE", "NOT_AGREE_OR_MISSING")
    out = (
        d.groupby(["time_bin", "ratio_bin", "brti_state"], observed=True)
        .agg(
            snapshots=("lead_survived", "size"),
            contracts=("contract", "nunique"),
            survival_rate=("lead_survived", "mean"),
            avg_lead_ask_c=("lead_ask_c", "mean"),
            avg_gap=("abs_gap", "mean"),
            avg_stable_seconds=("stable_side_seconds", "mean"),
        )
        .reset_index()
    )
    return out


SURVIVAL_FEATURES = [
    "minutes_left", "abs_gap", "ratio", "lead_ask_c", "lead_fair", "lead_edge",
    "quote_advantage", "btc_move_5s_side", "btc_move_15s_side", "btc_move_30s_side",
    "btc_move_60s_side", "btc_move_120s_side", "brti_agree", "brti_gap_side",
    "brti_minus_coinbase_side", "lag15", "lag30", "bounce_from_60s_low",
    "drawdown_from_60s_high", "range5", "vol5", "stable_side_seconds",
    "recent_cross_60s", "reversal_risk",
]


@dataclass
class SurvivalResult:
    validation_frontier: pd.DataFrame
    selected_holdout: pd.DataFrame
    snapshot_predictions: pd.DataFrame
    status: str


def _contract_split(d: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    order = d.groupby("contract")["timestamp"].min().sort_values().index.tolist()
    n = len(order)
    i70 = max(1, int(n * 0.70))
    i85 = max(i70 + 1, int(n * 0.85))
    i85 = min(i85, n)
    return order[:i70], order[i70:i85], order[i85:]


def _survival_threshold_score(
    d: pd.DataFrame,
    threshold: float,
    universe_contracts: int,
) -> dict:
    eligible = (
        d["minutes_left"].between(0.5, 10, inclusive="both")
        & d["survival_p"].ge(threshold)
    )
    q = d.loc[eligible].sort_values(["contract", "timestamp"]).drop_duplicates("contract")
    return {
        "threshold": threshold,
        "calls": len(q),
        "coverage": len(q) / universe_contracts if universe_contracts else np.nan,
        "accuracy": float(q["lead_survived"].mean()) if len(q) else np.nan,
        "avg_ask_c": float(q["lead_ask_c"].mean()) if len(q) else np.nan,
        "median_ask_c": float(q["lead_ask_c"].median()) if len(q) else np.nan,
        "pct_le_50c": float((q["lead_ask_c"] <= 50).mean()) if len(q) else np.nan,
        "avg_time_left": float(q["minutes_left"].mean()) if len(q) else np.nan,
        "median_time_left": float(q["minutes_left"].median()) if len(q) else np.nan,
    }


def survival_model_audit(lead: pd.DataFrame, min_contracts: int = 40) -> SurvivalResult:
    if LogisticRegression is None:
        return SurvivalResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "SKIPPED: scikit-learn unavailable")
    contracts = lead["contract"].nunique()
    if contracts < min_contracts:
        return SurvivalResult(
            pd.DataFrame(), pd.DataFrame(), pd.DataFrame(),
            f"SKIPPED: need >= {min_contracts} settled contracts, found {contracts}",
        )

    d = lead.copy()
    # At most one observation per contract per 30-second time bucket to reduce
    # serial-overweighting while retaining intracontract path information.
    d["_bucket"] = np.floor(d["minutes_left"] * 2) / 2
    d = (
        d.sort_values(["contract", "timestamp"])
        .drop_duplicates(["contract", "_bucket"], keep="last")
        .drop(columns=["_bucket"])
    )

    train_c, val_c, hold_c = _contract_split(d)
    if not val_c or not hold_c:
        return SurvivalResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "SKIPPED: split too small")

    train = d[d["contract"].isin(train_c)].copy()
    val = d[d["contract"].isin(val_c)].copy()
    hold = d[d["contract"].isin(hold_c)].copy()

    # Guard against degenerate historical slices.
    if train["lead_survived"].nunique() < 2:
        return SurvivalResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "SKIPPED: train labels degenerate")

    features = [c for c in SURVIVAL_FEATURES if c in d.columns]
    prep = ColumnTransformer(
        [("num", Pipeline([("impute", SimpleImputer(strategy="median")),
                           ("scale", StandardScaler())]), features)],
        remainder="drop",
    )
    model = Pipeline(
        [
            ("prep", prep),
            ("model", LogisticRegression(
                C=0.5, max_iter=2500, solver="lbfgs", random_state=42
            )),
        ]
    )
    model.fit(train[features], train["lead_survived"])
    for part in (val, hold):
        part["survival_p"] = model.predict_proba(part[features])[:, 1]

    thresholds = [0.80, 0.85, 0.88, 0.90, 0.92, 0.93, 0.94, 0.95, 0.96, 0.97]
    val_rows = [_survival_threshold_score(val, t, len(val_c)) for t in thresholds]
    vf = pd.DataFrame(val_rows)

    # Selection uses validation only. Require a non-tiny number of calls.
    min_calls = max(5, math.ceil(len(val_c) * 0.20))
    good = vf[(vf["calls"] >= min_calls) & (vf["accuracy"] >= 0.93)].copy()
    if len(good):
        chosen = good.sort_values(
            ["coverage", "avg_ask_c", "avg_time_left"],
            ascending=[False, True, False],
        ).iloc[0]
        selection_reason = "validation met >=93% accuracy"
    else:
        eligible = vf[vf["calls"] >= min_calls].copy()
        if eligible.empty:
            return SurvivalResult(vf, pd.DataFrame(), pd.concat([val, hold]), "NO SELECTABLE THRESHOLD: too few validation calls")
        chosen = eligible.sort_values(
            ["accuracy", "coverage", "avg_ask_c"],
            ascending=[False, False, True],
        ).iloc[0]
        selection_reason = "best honest validation fallback; did not clear 93%"

    h = _survival_threshold_score(hold, float(chosen["threshold"]), len(hold_c))
    h.update(
        {
            "selected_on_validation": True,
            "selection_reason": selection_reason,
            "train_contracts": len(train_c),
            "validation_contracts": len(val_c),
            "holdout_contracts": len(hold_c),
        }
    )
    hp = pd.DataFrame([h])
    preds = pd.concat(
        [
            val.assign(split="VALIDATION"),
            hold.assign(split="UNTOUCHED_HOLDOUT"),
        ],
        ignore_index=True,
    )
    return SurvivalResult(vf, hp, preds, "OK")


def candidate_verify_transition(pref: pd.DataFrame, total_truth_contracts: int) -> pd.DataFrame:
    d = pref.sort_values(["contract", "timestamp"]).copy()
    candidate_mask = (
        d["minutes_left"].between(2, 10, inclusive="both")
        & d["ask_c"].le(50)
        & d["fair"].ge(0.70)
        & d["edge"].ge(0.05)
        & d["abs_gap"].ge(15)
    )
    candidates = d[candidate_mask].drop_duplicates("contract", keep="first").copy()
    rows = []

    for horizon in [15, 30, 60]:
        for variant in ["PERSIST", "FAIR_HOLD", "BRTI_CONFIRM", "MOMENTUM_CONFIRM"]:
            verified_records = []
            for _, c in candidates.iterrows():
                g = d[
                    (d["contract"] == c["contract"])
                    & (d["timestamp"] >= c["timestamp"] + pd.Timedelta(seconds=horizon))
                    & (d["timestamp"] <= c["timestamp"] + pd.Timedelta(seconds=horizon + 15))
                ]
                if g.empty:
                    continue
                v = g.iloc[0]
                same_side = v["preferred_side"] == c["preferred_side"]
                target_agree = v["current_side"] == c["preferred_side"]
                fair_hold = bool(
                    pd.notna(v["fair"]) and pd.notna(c["fair"])
                    and v["fair"] >= max(0.70, float(c["fair"]) - 0.02)
                )
                brti = bool(v["brti_agree"])
                moves = [v.get("btc_move_5s_side"), v.get("btc_move_15s_side"), v.get("btc_move_30s_side")]
                momentum = sum(pd.notna(x) and float(x) > 0 for x in moves) >= 2

                ok = same_side and target_agree
                if variant in {"FAIR_HOLD", "BRTI_CONFIRM", "MOMENTUM_CONFIRM"}:
                    ok = ok and fair_hold
                if variant in {"BRTI_CONFIRM", "MOMENTUM_CONFIRM"}:
                    ok = ok and brti
                if variant == "MOMENTUM_CONFIRM":
                    ok = ok and momentum
                if ok:
                    rec = v.to_dict()
                    rec["candidate_ask_c"] = c["ask_c"]
                    rec["candidate_time_left"] = c["minutes_left"]
                    rec["candidate_side"] = c["preferred_side"]
                    rec["verify_correct"] = (
                        c["preferred_side"] == v["official_side"] if v["official_side"] else np.nan
                    )
                    verified_records.append(rec)

            q = pd.DataFrame(verified_records)
            scored = q[q["official_side"].ne("")] if len(q) else q
            rows.append(
                {
                    "horizon_seconds": horizon,
                    "variant": variant,
                    "candidate_contracts": len(candidates),
                    "verified_calls": len(q),
                    "scored_calls": len(scored),
                    "coverage": len(scored) / total_truth_contracts if total_truth_contracts else np.nan,
                    "verification_rate": len(q) / len(candidates) if len(candidates) else np.nan,
                    "accuracy": float(scored["verify_correct"].mean()) if len(scored) else np.nan,
                    "avg_candidate_ask_c": float(scored["candidate_ask_c"].mean()) if len(scored) else np.nan,
                    "avg_verify_ask_c": float(scored["ask_c"].mean()) if len(scored) else np.nan,
                    "avg_verify_time_left": float(scored["minutes_left"].mean()) if len(scored) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def frontier_goal_slice(frontier: pd.DataFrame, min_calls: int) -> pd.DataFrame:
    if frontier.empty:
        return frontier
    q = frontier[
        (frontier["scored_calls"] >= min_calls)
        & (frontier["accuracy"] >= 0.93)
        & (frontier["avg_ask_c"] <= 50)
    ].copy()
    return q.sort_values(
        ["coverage", "accuracy", "avg_ask_c", "avg_time_left"],
        ascending=[False, False, True, False],
    )


def write_summary(
    outdir: Path,
    source_path: str,
    observed_contracts: int,
    truth_contracts: int,
    baselines: pd.DataFrame,
    frontier: pd.DataFrame,
    blocker_summary: pd.DataFrame,
    survival: SurvivalResult,
    transitions: pd.DataFrame,
) -> None:
    min_calls = max(10, math.ceil(truth_contracts * 0.05)) if truth_contracts else 10
    goals = frontier_goal_slice(frontier, min_calls)
    lines = [
        "# BTC15 Shadow Diagnostic Pack V1",
        "",
        "**Status:** research-only / read-only against production logic.",
        "",
        f"- Source: `{source_path}`",
        f"- Observed contracts: {observed_contracts}",
        f"- Settled contracts with official truth: {truth_contracts}",
        "- Production bot / frozen FINAL / Tier-1 rules modified: **NO**",
        "- Orders placed: **NO**",
        "",
        "## Locked-anchor replay",
        "",
    ]
    if len(baselines):
        for _, r in baselines.iterrows():
            acc = "N/A" if pd.isna(r["accuracy"]) else f"{100*r['accuracy']:.1f}%"
            lines.append(
                f"- {r['lane']}: {int(r['scored_calls'])} settled calls | "
                f"{acc} accuracy | {100*r['coverage']:.1f}% coverage | "
                f"{r['avg_ask_c']:.1f}c avg ask | {r['avg_time_left']:.2f}m avg time left"
            )
    lines += ["", "## First-fire frontier", ""]
    if len(goals):
        best = goals.iloc[0]
        lines.append(
            f"At least one exploratory configuration cleared the report-only filter "
            f"(>=93% accuracy, <=50c avg ask, >= {min_calls} calls). "
            f"Best coverage row: {100*best['coverage']:.1f}% coverage, "
            f"{100*best['accuracy']:.1f}% accuracy, {best['avg_ask_c']:.1f}c avg ask, "
            f"{best['avg_time_left']:.2f}m left. This is NOT production-approved."
        )
    else:
        lines.append(
            f"No frontier row with >= {min_calls} settled calls simultaneously reached "
            ">=93% accuracy and <=50c average ask in this dataset."
        )

    lines += ["", "## Tier-1 EARLY blocker audit", ""]
    if len(blocker_summary):
        top = blocker_summary.sort_values(
            ["one_gate_removed_rescue_contracts", "sole_blocker_contracts"],
            ascending=False,
        ).head(3)
        for _, r in top.iterrows():
            acc = "N/A" if pd.isna(r["rescue_accuracy"]) else f"{100*r['rescue_accuracy']:.1f}%"
            lines.append(
                f"- {r['gate']}: removing only this gate would rescue "
                f"{int(r['one_gate_removed_rescue_contracts'])} contracts; "
                f"rescue accuracy {acc}."
            )

    lines += ["", "## Lead-survival / flip-hazard model", "", f"- Model status: {survival.status}"]
    if len(survival.selected_holdout):
        r = survival.selected_holdout.iloc[0]
        acc = "N/A" if pd.isna(r["accuracy"]) else f"{100*r['accuracy']:.1f}%"
        lines.append(
            f"- Validation-selected threshold {r['threshold']:.2f}; untouched holdout: "
            f"{int(r['calls'])} calls | {acc} accuracy | "
            f"{100*r['coverage']:.1f}% coverage | {r['avg_ask_c']:.1f}c avg ask | "
            f"{r['avg_time_left']:.2f}m left."
        )
        lines.append(f"- Selection note: {r['selection_reason']}.")

    lines += ["", "## Candidate -> Verify transitions", ""]
    if len(transitions):
        eligible = transitions[transitions["scored_calls"] >= min_calls].copy()
        if len(eligible):
            r = eligible.sort_values(["accuracy", "coverage"], ascending=False).iloc[0]
            lines.append(
                f"- Highest-accuracy non-tiny report row: {r['variant']} at "
                f"{int(r['horizon_seconds'])}s; {int(r['scored_calls'])} scored calls | "
                f"{100*r['accuracy']:.1f}% accuracy | {100*r['coverage']:.1f}% coverage | "
                f"{r['avg_candidate_ask_c']:.1f}c candidate ask | "
                f"{r['avg_verify_time_left']:.2f}m at verification."
            )
        else:
            lines.append(f"- No transition row reached the non-tiny floor of {min_calls} scored calls.")

    lines += [
        "",
        "## Integrity / interpretation",
        "",
        "- All thresholds and transition ideas in this pack are **shadow research only**.",
        "- Untouched-holdout survival results are report-only and must not be retuned against.",
        "- First qualifying signal per contract is used for timing/entry scorecards.",
        "- Official settlement truth is required for correctness metrics.",
        "- A high-accuracy row with tiny call count is not treated as evidence of readiness.",
        "- The existing locked/provisionally locked production anchors remain unchanged.",
        "",
    ]
    (outdir / "shadow_diagnostic_summary_v1.md").write_text("\n".join(lines), encoding="utf-8")


def save_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only BTC15 shadow diagnostic pack")
    ap.add_argument("--input", default="kalshi_subminute_unified_v1_1.csv")
    ap.add_argument("--truth", default="fresh_oos_market_manifest.csv")
    ap.add_argument("--out", default="shadow_diagnostics/output_v1")
    ap.add_argument("--start", default=None, help="optional UTC/ISO lower timestamp bound")
    ap.add_argument("--end", default=None, help="optional UTC/ISO upper timestamp bound")
    ap.add_argument("--fetch-truth", action="store_true", help="fill missing official settlements from Kalshi API")
    ap.add_argument("--min-survival-contracts", type=int, default=40)
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        raise SystemExit(f"input not found: {src}")
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(src, low_memory=False)
    ts_col = first_existing(raw.columns, ["timestamp_utc", "timestamp", "ts", "time"])
    contract_col = first_existing(raw.columns, ["contract", "ticker", "market_ticker"])
    if not ts_col or not contract_col:
        raise SystemExit("input needs timestamp and contract/ticker columns")
    raw["_filter_ts"] = parse_timestamp(raw[ts_col])
    if args.start:
        raw = raw[raw["_filter_ts"] >= pd.to_datetime(args.start, utc=True)]
    if args.end:
        raw = raw[raw["_filter_ts"] <= pd.to_datetime(args.end, utc=True)]
    raw = raw.drop(columns=["_filter_ts"])

    observed = sorted(raw[contract_col].dropna().astype(str).str.strip().unique())
    truth = load_truth_csv(args.truth) if args.truth else {}
    if args.fetch_truth:
        missing = [c for c in observed if c not in truth]
        truth.update(fetch_kalshi_truth(missing))
        if truth:
            pd.DataFrame(
                [{"contract": c, "official_side": s} for c, s in sorted(truth.items())]
            ).to_csv(outdir / "official_truth_cache_v1.csv", index=False)

    truth_for_observed = {c: truth[c] for c in observed if c in truth}
    print("=" * 78)
    print("BTC15 SHADOW DIAGNOSTIC PACK V1")
    print("=" * 78)
    print(f"Input rows: {len(raw):,}")
    print(f"Observed contracts: {len(observed)}")
    print(f"Official truth available: {len(truth_for_observed)}")
    print("Production logic changed: NO")
    print("Orders placed: NO")

    if not truth_for_observed:
        print("WARNING: no official truth overlaps this input. Correctness metrics will be unavailable.")
        print("Use a matching --truth file or add --fetch-truth for settled contracts.")

    pref = prepare_preferred_frame(raw, truth_for_observed)
    total_truth_contracts = len(truth_for_observed)

    baselines = baseline_scorecard(pref, total_truth_contracts)
    frontier = signal_frontier(pref, total_truth_contracts)
    blocker_ledger, blocker_summary = early_blocker_audit(pref, truth_for_observed)
    transitions = candidate_verify_transition(pref, total_truth_contracts)

    lead = prepare_lead_frame(raw, truth_for_observed) if truth_for_observed else pd.DataFrame()
    bins = survival_descriptive_bins(lead)
    survival = (
        survival_model_audit(lead, min_contracts=args.min_survival_contracts)
        if len(lead)
        else SurvivalResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "SKIPPED: no official truth")
    )

    save_csv(baselines, outdir / "baseline_anchor_replay_v1.csv")
    save_csv(frontier, outdir / "first_fire_frontier_v1.csv")
    save_csv(blocker_ledger, outdir / "early_blocker_ledger_v1.csv")
    save_csv(blocker_summary, outdir / "early_blocker_summary_v1.csv")
    save_csv(transitions, outdir / "candidate_verify_transition_v1.csv")
    save_csv(bins, outdir / "survival_descriptive_bins_v1.csv")
    save_csv(survival.validation_frontier, outdir / "survival_validation_frontier_v1.csv")
    save_csv(survival.selected_holdout, outdir / "survival_selected_holdout_v1.csv")
    if len(survival.snapshot_predictions):
        keep = [
            c for c in [
                "contract", "timestamp", "split", "lead_side", "official_side",
                "lead_survived", "survival_p", "lead_ask_c", "minutes_left",
                "abs_gap", "ratio", "stable_side_seconds", "brti_agree"
            ] if c in survival.snapshot_predictions.columns
        ]
        save_csv(
            survival.snapshot_predictions[keep],
            outdir / "survival_snapshot_predictions_v1.csv",
        )

    write_summary(
        outdir,
        str(src),
        len(observed),
        total_truth_contracts,
        baselines,
        frontier,
        blocker_summary,
        survival,
        transitions,
    )

    metadata = {
        "input": str(src),
        "truth_file": args.truth,
        "observed_contracts": len(observed),
        "truth_contracts": total_truth_contracts,
        "production_modified": False,
        "orders_placed": False,
        "survival_model_status": survival.status,
    }
    (outdir / "run_metadata_v1.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Outputs written to: {outdir}")
    print(f"Survival model: {survival.status}")
    print("DONE — diagnostic outputs only; frozen production logic untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
