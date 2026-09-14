#!/usr/bin/env python3
"""
BTC15 EARLY PRE-WATCH tournament V1.

READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS

Goal
----
Research a pre-Tier-1 EARLY watch state that can appear before Kalshi has fully
repriced the move. The protected Tier-1 EARLY anchor is NEVER changed here.

The tournament:
- uses only information available at each historical snapshot;
- requires an economically acceptable ask (<= a tested cap, never > 50c);
- searches modest fair / edge / exact-target-gap / time-window combinations;
- selects a champion ONLY on the chronological validation half;
- prints the second-half result as REPORT ONLY and never uses it to tune;
- separately measures whether a candidate would have appeared before contracts
  that later became "everything-ready-except-ask>45c" expensive near-misses.

No live behavior is changed. No order-placement code exists.
"""
from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_CACHE = "union_optimizer_processed_snapshot_cache.csv"
DEFAULT_RULES = "early_prewatch_tournament_v1_rules.csv"
DEFAULT_CALLS = "early_prewatch_tournament_v1_champion_calls.csv"
DEFAULT_REPORT = "early_prewatch_tournament_v1.txt"

ASK_CAPS = [0.35, 0.40, 0.45, 0.50]
FAIR_MINS = [0.60, 0.65, 0.70, 0.75]
EDGE_MINS = [0.02, 0.04, 0.06, 0.08]
GAP_MINS = [10.0, 15.0, 20.0, 25.0]
TIME_WINDOWS = [
    ("2-10m", 2.0, 10.0),
    ("3-11m", 3.0, 11.0),
    ("4-12m", 4.0, 12.0),
    ("5-12m", 5.0, 12.0),
]

NUMERIC = [
    "elapsed", "remaining", "current_side", "abs_dist_target", "final_side",
    "fair_up", "fair_down", "preferred_side_num", "preferred_fair",
    "preferred_ask", "preferred_bid", "edge",
]


def pct(x):
    return "—" if pd.isna(x) else f"{100.0 * float(x):.1f}%"


def cents(x):
    return "—" if pd.isna(x) else f"{100.0 * float(x):.1f}c"


def mins(x):
    return "—" if pd.isna(x) else f"{float(x):.2f}m"


def load_cache(path: str) -> pd.DataFrame:
    d = pd.read_csv(path, low_memory=False)
    need = {
        "ticker", "snapshot_utc", "elapsed", "remaining", "current_side",
        "abs_dist_target", "final_side", "fair_up", "fair_down",
        "preferred_side_num", "preferred_side", "preferred_fair",
        "preferred_ask", "preferred_bid", "edge",
    }
    missing = sorted(need - set(d.columns))
    if missing:
        raise SystemExit(f"Missing required cache columns: {missing}")

    d["snapshot_utc"] = pd.to_datetime(d["snapshot_utc"], utc=True, errors="coerce")
    for c in NUMERIC:
        d[c] = pd.to_numeric(d[c], errors="coerce")

    d = d.dropna(
        subset=[
            "ticker", "snapshot_utc", "elapsed", "remaining",
            "abs_dist_target", "final_side", "preferred_side_num",
            "preferred_side", "preferred_fair", "preferred_ask", "edge",
        ]
    ).copy()
    d["ticker"] = d["ticker"].astype(str)
    d["preferred_side"] = d["preferred_side"].astype(str).str.upper()
    d = d.sort_values(["ticker", "elapsed", "snapshot_utc"]).reset_index(drop=True)

    # Protected Tier-1 EARLY anchor. DO NOT CHANGE.
    d["tier1_early"] = (
        (d["preferred_ask"] <= 0.45)
        & (d["preferred_fair"] >= 0.75)
        & (d["edge"] >= 0.08)
        & d["remaining"].between(2.0, 10.0, inclusive="both")
        & (d["abs_dist_target"] >= 25.0)
    )

    # Gap-audit target: all protected non-price gates are already satisfied,
    # but Kalshi ask has repriced above the protected 45c entry cap.
    d["expensive_near_miss"] = (
        (d["preferred_ask"] > 0.45)
        & (d["preferred_fair"] >= 0.75)
        & (d["edge"] >= 0.08)
        & d["remaining"].between(2.0, 10.0, inclusive="both")
        & (d["abs_dist_target"] >= 25.0)
    )
    return d


def contract_split(d: pd.DataFrame):
    contracts = (
        d[["ticker", "snapshot_utc"]]
        .groupby("ticker", as_index=False)["snapshot_utc"].min()
        .sort_values("snapshot_utc")
        .reset_index(drop=True)
    )
    mid = len(contracts) // 2
    return set(contracts.iloc[:mid]["ticker"]), set(contracts.iloc[mid:]["ticker"])


def first_rows(d: pd.DataFrame, mask) -> pd.DataFrame:
    q = d.loc[mask].sort_values(["ticker", "elapsed", "snapshot_utc"])
    if q.empty:
        return q.copy()
    return q.groupby("ticker", as_index=False).first()


def score_calls(calls: pd.DataFrame, universe_n: int) -> dict:
    if calls.empty:
        return {
            "calls": 0, "coverage": 0.0, "accuracy": np.nan,
            "avg_ask": np.nan, "median_ask": np.nan,
            "avg_remaining": np.nan, "median_remaining": np.nan,
            "ideal_ask_le_35": np.nan, "good_ask_le_40": np.nan,
        }
    correct = calls["preferred_side_num"].astype(int) == calls["final_side"].astype(int)
    return {
        "calls": int(len(calls)),
        "coverage": float(len(calls) / max(universe_n, 1)),
        "accuracy": float(correct.mean()),
        "avg_ask": float(calls["preferred_ask"].mean()),
        "median_ask": float(calls["preferred_ask"].median()),
        "avg_remaining": float(calls["remaining"].mean()),
        "median_remaining": float(calls["remaining"].median()),
        "ideal_ask_le_35": float((calls["preferred_ask"] <= 0.35).mean()),
        "good_ask_le_40": float((calls["preferred_ask"] <= 0.40).mean()),
    }


def candidate_mask(d, ask_cap, fair_min, edge_min, gap_min, tlo, thi):
    return (
        (d["preferred_ask"] <= ask_cap)
        & (d["preferred_fair"] >= fair_min)
        & (d["edge"] >= edge_min)
        & (d["abs_dist_target"] >= gap_min)
        & d["remaining"].between(tlo, thi, inclusive="both")
    )


def rescue_stats(calls: pd.DataFrame, expensive_first: pd.DataFrame) -> dict:
    if calls.empty or expensive_first.empty:
        return {
            "rescue_before_n": 0,
            "rescue_before_accuracy": np.nan,
            "avg_lead_sec": np.nan,
            "median_lead_sec": np.nan,
        }

    e = expensive_first[
        ["ticker", "elapsed", "remaining"]
    ].rename(columns={"elapsed": "exp_elapsed", "remaining": "exp_remaining"})
    m = calls.merge(e, on="ticker", how="inner")

    # Earlier snapshot means lower elapsed / greater remaining.
    m = m[m["elapsed"] < m["exp_elapsed"]].copy()
    if m.empty:
        return {
            "rescue_before_n": 0,
            "rescue_before_accuracy": np.nan,
            "avg_lead_sec": np.nan,
            "median_lead_sec": np.nan,
        }

    lead_sec = (m["exp_elapsed"] - m["elapsed"]) * 60.0
    correct = m["preferred_side_num"].astype(int) == m["final_side"].astype(int)
    return {
        "rescue_before_n": int(len(m)),
        "rescue_before_accuracy": float(correct.mean()),
        "avg_lead_sec": float(lead_sec.mean()),
        "median_lead_sec": float(lead_sec.median()),
    }


def incremental_without_tier1(calls: pd.DataFrame, tier1_first: pd.DataFrame, universe_n: int):
    if calls.empty:
        return 0, 0.0
    tier1_tickers = set(tier1_first["ticker"]) if not tier1_first.empty else set()
    n = int((~calls["ticker"].isin(tier1_tickers)).sum())
    return n, float(n / max(universe_n, 1))


def evaluate_pool(pool: pd.DataFrame, rule: dict) -> tuple[dict, pd.DataFrame]:
    n = pool["ticker"].nunique()
    mask = candidate_mask(
        pool,
        rule["ask_cap"], rule["fair_min"], rule["edge_min"],
        rule["gap_min"], rule["time_lo"], rule["time_hi"],
    )
    calls = first_rows(pool, mask)
    tier1 = first_rows(pool, pool["tier1_early"])
    expensive = first_rows(pool, pool["expensive_near_miss"])

    out = score_calls(calls, n)
    out.update(rescue_stats(calls, expensive))
    inc_n, inc_cov = incremental_without_tier1(calls, tier1, n)
    out["incremental_without_tier1_n"] = inc_n
    out["incremental_without_tier1_cov"] = inc_cov
    out["expensive_near_miss_contracts"] = int(len(expensive))
    return out, calls


def rule_label(rule: dict) -> str:
    return (
        f"ask<={int(round(rule['ask_cap']*100))}c "
        f"fair>={int(round(rule['fair_min']*100))}% "
        f"edge>={int(round(rule['edge_min']*100))}pp "
        f"gap>={int(rule['gap_min'])} "
        f"time={rule['time_name']}"
    )


def baseline_line(label: str, pool: pd.DataFrame) -> str:
    n = pool["ticker"].nunique()
    calls = first_rows(pool, pool["tier1_early"])
    s = score_calls(calls, n)
    return (
        f"{label}: calls={s['calls']} coverage={pct(s['coverage'])} "
        f"accuracy={pct(s['accuracy'])} avg_ask={cents(s['avg_ask'])} "
        f"median_ask={cents(s['median_ask'])} avg_time={mins(s['avg_remaining'])}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--rules-out", default=DEFAULT_RULES)
    ap.add_argument("--calls-out", default=DEFAULT_CALLS)
    ap.add_argument("--report-out", default=DEFAULT_REPORT)
    ap.add_argument("--min-validation-calls", type=int, default=12)
    ap.add_argument("--min-validation-accuracy", type=float, default=0.90)
    args = ap.parse_args()

    d = load_cache(args.cache)
    valid_ticks, report_ticks = contract_split(d)
    valid = d[d["ticker"].isin(valid_ticks)].copy()
    report = d[d["ticker"].isin(report_ticks)].copy()

    rows = []
    for ask_cap, fair_min, edge_min, gap_min, tw in itertools.product(
        ASK_CAPS, FAIR_MINS, EDGE_MINS, GAP_MINS, TIME_WINDOWS
    ):
        tname, tlo, thi = tw
        rule = {
            "ask_cap": ask_cap,
            "fair_min": fair_min,
            "edge_min": edge_min,
            "gap_min": gap_min,
            "time_name": tname,
            "time_lo": tlo,
            "time_hi": thi,
        }
        vs, _ = evaluate_pool(valid, rule)
        rows.append({**rule, **{f"val_{k}": v for k, v in vs.items()}})

    rules = pd.DataFrame(rows)

    eligible = rules[
        (rules["val_calls"] >= args.min_validation_calls)
        & (rules["val_accuracy"] >= args.min_validation_accuracy)
    ].copy()

    # Selection uses VALIDATION ONLY. Rank first for the actual gap-audit target:
    # rescue expensive near-miss contracts BEFORE repricing, then accuracy/support.
    if eligible.empty:
        ranked = rules.sort_values(
            ["val_accuracy", "val_calls", "val_rescue_before_n",
             "val_avg_ask", "val_avg_remaining"],
            ascending=[False, False, False, True, False],
        ).reset_index(drop=True)
        champion = ranked.iloc[0].to_dict()
        promoted_quality_gate = False
    else:
        ranked = eligible.sort_values(
            ["val_rescue_before_n", "val_accuracy", "val_calls",
             "val_incremental_without_tier1_n", "val_avg_ask", "val_avg_remaining"],
            ascending=[False, False, False, False, True, False],
        ).reset_index(drop=True)
        champion = ranked.iloc[0].to_dict()
        promoted_quality_gate = True

    champion_rule = {
        "ask_cap": float(champion["ask_cap"]),
        "fair_min": float(champion["fair_min"]),
        "edge_min": float(champion["edge_min"]),
        "gap_min": float(champion["gap_min"]),
        "time_name": str(champion["time_name"]),
        "time_lo": float(champion["time_lo"]),
        "time_hi": float(champion["time_hi"]),
    }

    report_stats, report_calls = evaluate_pool(report, champion_rule)
    val_stats, val_calls = evaluate_pool(valid, champion_rule)

    # Write full grid with validation stats. The report half is added only for the
    # single validation-selected champion, preventing report-half parameter tuning.
    rules = rules.sort_values(
        ["val_accuracy", "val_calls", "val_rescue_before_n"],
        ascending=[False, False, False],
    )
    rules.to_csv(args.rules_out, index=False)

    champion_calls = pd.concat(
        [
            val_calls.assign(split="VALIDATION"),
            report_calls.assign(split="REPORT_ONLY"),
        ],
        ignore_index=True,
    )
    keep_cols = [
        "split", "ticker", "snapshot_utc", "elapsed", "remaining",
        "preferred_side", "preferred_side_num", "preferred_ask",
        "preferred_fair", "edge", "abs_dist_target", "final_side",
    ]
    champion_calls[keep_cols].to_csv(args.calls_out, index=False)

    lines = []
    lines.append("=" * 92)
    lines.append("BTC15 EARLY PRE-WATCH TOURNAMENT V1")
    lines.append("READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS")
    lines.append("=" * 92)
    lines.append(f"Rows: {len(d):,} | Contracts: {d['ticker'].nunique()}")
    lines.append("")
    lines.append("PROTECTED TIER-1 EARLY BASELINE — UNCHANGED")
    lines.append("  " + baseline_line("VALIDATION", valid))
    lines.append("  " + baseline_line("REPORT_ONLY", report))
    lines.append("")
    lines.append("VALIDATION-SELECTED PRE-WATCH CHAMPION")
    lines.append("  " + rule_label(champion_rule))
    lines.append(
        f"  calls={val_stats['calls']} coverage={pct(val_stats['coverage'])} "
        f"accuracy={pct(val_stats['accuracy'])} avg_ask={cents(val_stats['avg_ask'])} "
        f"median_ask={cents(val_stats['median_ask'])} avg_time={mins(val_stats['avg_remaining'])}"
    )
    if not pd.isna(val_stats["avg_lead_sec"]):
        lines.append(
            f"  before-expensive-near-miss={val_stats['rescue_before_n']} "
            f"accuracy={pct(val_stats['rescue_before_accuracy'])} "
            f"avg_lead={val_stats['avg_lead_sec']:.0f}s"
        )
    else:
        lines.append(f"  before-expensive-near-miss={val_stats['rescue_before_n']}")
    lines.append(
        f"  incremental contracts without protected Tier-1 call="
        f"{val_stats['incremental_without_tier1_n']} "
        f"({pct(val_stats['incremental_without_tier1_cov'])})"
    )
    lines.append(
        f"  <=35c share={pct(val_stats['ideal_ask_le_35'])} "
        f"<=40c share={pct(val_stats['good_ask_le_40'])}"
    )
    lines.append("")
    lines.append("REPORT-ONLY SECOND HALF — NEVER USED TO CHOOSE THRESHOLDS")
    lines.append(
        f"  calls={report_stats['calls']} coverage={pct(report_stats['coverage'])} "
        f"accuracy={pct(report_stats['accuracy'])} avg_ask={cents(report_stats['avg_ask'])} "
        f"median_ask={cents(report_stats['median_ask'])} "
        f"avg_time={mins(report_stats['avg_remaining'])}"
    )
    lines.append(
        f"  before-expensive-near-miss={report_stats['rescue_before_n']} "
        f"accuracy={pct(report_stats['rescue_before_accuracy'])} "
        + (
            f"avg_lead={report_stats['avg_lead_sec']:.0f}s"
            if not pd.isna(report_stats["avg_lead_sec"])
            else "avg_lead=—"
        )
    )
    lines.append(
        f"  incremental contracts without protected Tier-1 call="
        f"{report_stats['incremental_without_tier1_n']} "
        f"({pct(report_stats['incremental_without_tier1_cov'])})"
    )
    lines.append(
        f"  <=35c share={pct(report_stats['ideal_ask_le_35'])} "
        f"<=40c share={pct(report_stats['good_ask_le_40'])}"
    )
    lines.append("")
    lines.append("SELECTION STATUS")
    if promoted_quality_gate:
        lines.append(
            f"  Validation gate PASSED: >= {args.min_validation_calls} calls and "
            f">= {100*args.min_validation_accuracy:.1f}% accuracy."
        )
    else:
        lines.append(
            "  No rule passed the validation quality gate; displayed champion is "
            "diagnostic only and MUST NOT be promoted."
        )
    lines.append("")
    lines.append("GUARDRAILS")
    lines.append("- This is PRE-WATCH research, not a new actionable EARLY rule.")
    lines.append("- Protected Tier-1 EARLY anchor is unchanged.")
    lines.append("- No candidate ever permits an ask above 50c.")
    lines.append("- Champion selection uses validation only; second half is report-only.")
    lines.append("- Do not tune to the report-only result.")
    lines.append("- No live behavior changes and no order-placement code.")
    text = "\n".join(lines) + "\n"

    Path(args.report_out).write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"WROTE {args.rules_out}")
    print(f"WROTE {args.calls_out}")
    print(f"WROTE {args.report_out}")


if __name__ == "__main__":
    main()
