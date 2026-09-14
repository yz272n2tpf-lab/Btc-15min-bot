#!/usr/bin/env python3
"""
BTC15 EARLY PRE-WATCH progression audit V1.

READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS

Purpose
-------
After BTC15_EARLY_PREWATCH_TOURNAMENT_V1.py selects one validation-only
pre-watch champion, measure what happens next without changing the champion:
- whether the same direction persists 30/60/90/120 seconds later;
- whether fair, edge, target gap, and Kalshi ask strengthen or weaken;
- whether the pre-watch later reaches the protected Tier-1 EARLY anchor;
- whether Kalshi reprices above 45c before Tier-1 becomes available;
- outcome accuracy for descriptive progression groups.

This file never chooses or promotes thresholds. It is a diagnostic bridge for
the future EARLY WATCH -> EARLY QUALIFIED handoff. Protected Tier-1 is unchanged.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

DEFAULT_CACHE = "union_optimizer_processed_snapshot_cache.csv"
DEFAULT_CALLS = "early_prewatch_tournament_v1_champion_calls.csv"
DEFAULT_ROWS = "early_prewatch_progress_audit_v1_rows.csv"
DEFAULT_REPORT = "early_prewatch_progress_audit_v1.txt"
HORIZONS = [30, 60, 90, 120]

NUMERIC = [
    "elapsed", "remaining", "abs_dist_target", "final_side",
    "preferred_side_num", "preferred_fair", "preferred_ask", "edge",
]


def pct(x):
    return "—" if pd.isna(x) else f"{100.0 * float(x):.1f}%"


def cents(x):
    return "—" if pd.isna(x) else f"{100.0 * float(x):.1f}c"


def secs(x):
    return "—" if pd.isna(x) else f"{float(x):.0f}s"


def load_cache(path: str) -> pd.DataFrame:
    d = pd.read_csv(path, low_memory=False)
    need = {
        "ticker", "snapshot_utc", "remaining", "abs_dist_target",
        "final_side", "preferred_side", "preferred_side_num",
        "preferred_fair", "preferred_ask", "edge",
    }
    missing = sorted(need - set(d.columns))
    if missing:
        raise SystemExit(f"Missing cache columns: {missing}")
    d["snapshot_utc"] = pd.to_datetime(d["snapshot_utc"], utc=True, errors="coerce")
    for c in NUMERIC:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=[
        "ticker", "snapshot_utc", "remaining", "abs_dist_target",
        "final_side", "preferred_side_num", "preferred_fair",
        "preferred_ask", "edge",
    ]).copy()
    d["ticker"] = d["ticker"].astype(str)
    d["preferred_side"] = d["preferred_side"].astype(str).str.upper()
    d = d.sort_values(["ticker", "snapshot_utc"]).reset_index(drop=True)

    # Protected Tier-1 EARLY anchor — exact locked definition, unchanged.
    d["tier1_early"] = (
        (d["preferred_ask"] <= 0.45)
        & (d["preferred_fair"] >= 0.75)
        & (d["edge"] >= 0.08)
        & d["remaining"].between(2.0, 10.0, inclusive="both")
        & (d["abs_dist_target"] >= 25.0)
    )
    d["expensive_ready"] = (
        (d["preferred_ask"] > 0.45)
        & (d["preferred_fair"] >= 0.75)
        & (d["edge"] >= 0.08)
        & d["remaining"].between(2.0, 10.0, inclusive="both")
        & (d["abs_dist_target"] >= 25.0)
    )
    return d


def load_calls(path: str) -> pd.DataFrame:
    c = pd.read_csv(path, low_memory=False)
    need = {
        "split", "ticker", "snapshot_utc", "preferred_side",
        "preferred_side_num", "preferred_ask", "preferred_fair",
        "edge", "abs_dist_target", "final_side",
    }
    missing = sorted(need - set(c.columns))
    if missing:
        raise SystemExit(f"Missing champion-call columns: {missing}")
    c["snapshot_utc"] = pd.to_datetime(c["snapshot_utc"], utc=True, errors="coerce")
    for col in ["preferred_side_num", "preferred_ask", "preferred_fair", "edge", "abs_dist_target", "final_side"]:
        c[col] = pd.to_numeric(c[col], errors="coerce")
    c = c.dropna(subset=["ticker", "snapshot_utc", "preferred_side_num", "final_side"]).copy()
    c["ticker"] = c["ticker"].astype(str)
    c["preferred_side"] = c["preferred_side"].astype(str).str.upper()
    return c.sort_values(["split", "ticker", "snapshot_utc"]).reset_index(drop=True)


def first_after(g: pd.DataFrame, ts: pd.Timestamp, seconds: int):
    q = g[g["snapshot_utc"] >= ts + pd.Timedelta(seconds=seconds)]
    return None if q.empty else q.iloc[0]


def first_future(g: pd.DataFrame, ts: pd.Timestamp, mask_col: str, side_num: int):
    q = g[(g["snapshot_utc"] > ts) & g[mask_col] & (g["preferred_side_num"].astype(int) == int(side_num))]
    return None if q.empty else q.iloc[0]


def make_rows(cache: pd.DataFrame, calls: pd.DataFrame) -> pd.DataFrame:
    grouped = {ticker: g.sort_values("snapshot_utc") for ticker, g in cache.groupby("ticker", sort=False)}
    rows = []
    for call in calls.itertuples(index=False):
        g = grouped.get(call.ticker)
        if g is None or g.empty:
            continue
        base_ts = call.snapshot_utc
        side_num = int(call.preferred_side_num)
        out = {
            "split": call.split,
            "ticker": call.ticker,
            "call_utc": base_ts,
            "side": call.preferred_side,
            "side_num": side_num,
            "entry_ask": float(call.preferred_ask),
            "entry_fair": float(call.preferred_fair),
            "entry_edge": float(call.edge),
            "entry_gap": float(call.abs_dist_target),
            "final_side": int(call.final_side),
            "correct": int(side_num == int(call.final_side)),
        }

        for h in HORIZONS:
            r = first_after(g, base_ts, h)
            p = f"h{h}"
            if r is None:
                out[f"{p}_available"] = 0
                out[f"{p}_same_side"] = np.nan
                out[f"{p}_fair_delta"] = np.nan
                out[f"{p}_edge_delta"] = np.nan
                out[f"{p}_ask_delta"] = np.nan
                out[f"{p}_gap_delta"] = np.nan
                continue
            out[f"{p}_available"] = 1
            out[f"{p}_same_side"] = int(int(r["preferred_side_num"]) == side_num)
            # Deltas are descriptive. For a side flip, fair/edge/ask refer to the then-preferred side.
            out[f"{p}_fair_delta"] = float(r["preferred_fair"] - call.preferred_fair)
            out[f"{p}_edge_delta"] = float(r["edge"] - call.edge)
            out[f"{p}_ask_delta"] = float(r["preferred_ask"] - call.preferred_ask)
            out[f"{p}_gap_delta"] = float(r["abs_dist_target"] - call.abs_dist_target)

        tier = first_future(g, base_ts, "tier1_early", side_num)
        expensive = first_future(g, base_ts, "expensive_ready", side_num)
        out["later_tier1_same_side"] = int(tier is not None)
        out["sec_to_tier1"] = np.nan if tier is None else float((tier["snapshot_utc"] - base_ts).total_seconds())
        out["tier1_ask"] = np.nan if tier is None else float(tier["preferred_ask"])
        out["later_expensive_ready_same_side"] = int(expensive is not None)
        out["sec_to_expensive_ready"] = np.nan if expensive is None else float((expensive["snapshot_utc"] - base_ts).total_seconds())
        out["expensive_ready_ask"] = np.nan if expensive is None else float(expensive["preferred_ask"])
        out["expensive_before_tier1"] = int(
            expensive is not None and (tier is None or expensive["snapshot_utc"] < tier["snapshot_utc"])
        )
        rows.append(out)
    return pd.DataFrame(rows)


def group_line(label: str, d: pd.DataFrame) -> str:
    if d.empty:
        return f"{label}: n=0"
    return (
        f"{label}: n={len(d)} accuracy={pct(d['correct'].mean())} "
        f"avg_entry={cents(d['entry_ask'].mean())} "
        f"tier1_conversion={pct(d['later_tier1_same_side'].mean())} "
        f"expensive_before_tier1={pct(d['expensive_before_tier1'].mean())}"
    )


def report_text(rows: pd.DataFrame) -> str:
    lines = []
    lines.append("=" * 96)
    lines.append("BTC15 EARLY PRE-WATCH PROGRESSION AUDIT V1")
    lines.append("READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS")
    lines.append("=" * 96)
    lines.append(f"Champion calls audited: {len(rows)}")
    lines.append("")

    for split in ["VALIDATION", "REPORT_ONLY"]:
        d = rows[rows["split"] == split].copy()
        lines.append(split)
        lines.append("  " + group_line("ALL", d))
        if d.empty:
            lines.append("")
            continue
        if d["later_tier1_same_side"].any():
            z = d[d["later_tier1_same_side"] == 1]
            lines.append(
                f"  Same-side Tier-1 later: {len(z)} | accuracy={pct(z['correct'].mean())} "
                f"median time={secs(z['sec_to_tier1'].median())}"
            )
        else:
            lines.append("  Same-side Tier-1 later: 0")

        for h in HORIZONS:
            p = f"h{h}"
            a = d[d[f"{p}_available"] == 1]
            same = a[a[f"{p}_same_side"] == 1]
            if a.empty:
                lines.append(f"  +{h}s: no follow-up snapshots")
                continue
            lines.append(
                f"  +{h}s: available={len(a)} same-side={pct(a[f'{p}_same_side'].mean())} "
                f"same-side accuracy={pct(same['correct'].mean()) if len(same) else '—'} "
                f"median fair Δ={pct(same[f'{p}_fair_delta'].median()) if len(same) else '—'} "
                f"median ask Δ={cents(same[f'{p}_ask_delta'].median()) if len(same) else '—'}"
            )
        lines.append("")

    lines.append("GUARDRAILS")
    lines.append("- No threshold is selected or promoted by this audit.")
    lines.append("- Protected Tier-1 EARLY definition is unchanged.")
    lines.append("- REPORT_ONLY remains report-only; do not tune from it.")
    lines.append("- Progression metrics are descriptive evidence for a future WATCH-to-QUALIFIED handoff.")
    lines.append("- No live code and no order-placement code.")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--calls", default=DEFAULT_CALLS)
    ap.add_argument("--rows-out", default=DEFAULT_ROWS)
    ap.add_argument("--report-out", default=DEFAULT_REPORT)
    args = ap.parse_args()

    cache = load_cache(args.cache)
    calls = load_calls(args.calls)
    rows = make_rows(cache, calls)
    text = report_text(rows)
    rows.to_csv(args.rows_out, index=False)
    Path(args.report_out).write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"WROTE {args.rows_out}")
    print(f"WROTE {args.report_out}")


if __name__ == "__main__":
    main()
