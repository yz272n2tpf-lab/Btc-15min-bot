#!/usr/bin/env python3
"""
BTC15 EARLY PRE-WATCH -> ACTIONABLE handoff tournament V1.

READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS

Purpose
-------
Take the validation-selected PRE-WATCH champion calls produced by
BTC15_EARLY_PREWATCH_TOURNAMENT_V1.py and research a separate confirmation
handoff that could turn some watches into an earlier actionable EARLY tier.

Critical guardrails
-------------------
- Protected Tier-1 EARLY is NEVER changed.
- PRE-WATCH itself remains non-actionable.
- Selection uses VALIDATION calls only.
- REPORT_ONLY calls are scored only after the validation champion is frozen.
- Confirmation ask can never exceed 50c.
- No live behavior changes and no order-placement code.

The confirmation grid asks whether, 30/60/90/120 seconds after PRE-WATCH:
- the preferred side is unchanged;
- Kalshi ask is still economically acceptable;
- fair probability has held/strengthened;
- edge has held/strengthened;
- exact-target gap has held/strengthened.
"""
from __future__ import annotations

import argparse
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_CACHE = "union_optimizer_processed_snapshot_cache.csv"
DEFAULT_CALLS = "early_prewatch_tournament_v1_champion_calls.csv"
DEFAULT_RULES = "early_prewatch_handoff_v1_rules.csv"
DEFAULT_ACTIONS = "early_prewatch_handoff_v1_champion_actions.csv"
DEFAULT_REPORT = "early_prewatch_handoff_v1.txt"

HORIZONS = [30, 60, 90, 120]
ASK_CAPS = [0.35, 0.40, 0.45, 0.50]
FAIR_DELTAS = [-0.02, 0.00, 0.02, 0.05]
EDGE_DELTAS = [-0.01, 0.00, 0.02, 0.04]
GAP_RATIOS = [0.90, 1.00, 1.10]
MAX_SNAPSHOT_LAG_SEC = 75

NUMERIC = [
    "remaining", "abs_dist_target", "final_side", "preferred_side_num",
    "preferred_fair", "preferred_ask", "preferred_bid", "edge",
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
        "ticker", "snapshot_utc", "remaining", "abs_dist_target", "final_side",
        "preferred_side", "preferred_side_num", "preferred_fair",
        "preferred_ask", "preferred_bid", "edge",
    }
    missing = sorted(need - set(d.columns))
    if missing:
        raise SystemExit(f"Missing cache columns: {missing}")
    d["snapshot_utc"] = pd.to_datetime(d["snapshot_utc"], utc=True, errors="coerce")
    for c in NUMERIC:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=[
        "ticker", "snapshot_utc", "remaining", "abs_dist_target", "final_side",
        "preferred_side_num", "preferred_fair", "preferred_ask", "edge",
    ]).copy()
    d["ticker"] = d["ticker"].astype(str)
    d["preferred_side"] = d["preferred_side"].astype(str).str.upper()
    d = d.sort_values(["ticker", "snapshot_utc"]).reset_index(drop=True)

    # Exact protected Tier-1 definition — descriptive comparison only.
    d["tier1_early"] = (
        (d["preferred_ask"] <= 0.45)
        & (d["preferred_fair"] >= 0.75)
        & (d["edge"] >= 0.08)
        & d["remaining"].between(2.0, 10.0, inclusive="both")
        & (d["abs_dist_target"] >= 25.0)
    )
    return d


def load_calls(path: str) -> pd.DataFrame:
    c = pd.read_csv(path, low_memory=False)
    need = {
        "split", "ticker", "snapshot_utc", "remaining", "preferred_side",
        "preferred_side_num", "preferred_ask", "preferred_fair", "edge",
        "abs_dist_target", "final_side",
    }
    missing = sorted(need - set(c.columns))
    if missing:
        raise SystemExit(f"Missing champion-call columns: {missing}")
    c["snapshot_utc"] = pd.to_datetime(c["snapshot_utc"], utc=True, errors="coerce")
    for col in [
        "remaining", "preferred_side_num", "preferred_ask", "preferred_fair",
        "edge", "abs_dist_target", "final_side",
    ]:
        c[col] = pd.to_numeric(c[col], errors="coerce")
    c = c.dropna(subset=[
        "split", "ticker", "snapshot_utc", "remaining", "preferred_side_num",
        "preferred_ask", "preferred_fair", "edge", "abs_dist_target", "final_side",
    ]).copy()
    c["ticker"] = c["ticker"].astype(str)
    c["preferred_side"] = c["preferred_side"].astype(str).str.upper()
    return c.sort_values(["split", "ticker", "snapshot_utc"]).reset_index(drop=True)


def follow_snapshot(g: pd.DataFrame, base_ts: pd.Timestamp, horizon: int):
    target = base_ts + pd.Timedelta(seconds=horizon)
    q = g[g["snapshot_utc"] >= target]
    if q.empty:
        return None
    r = q.iloc[0]
    lag = (r["snapshot_utc"] - target).total_seconds()
    if lag > MAX_SNAPSHOT_LAG_SEC:
        return None
    return r


def first_future_tier1(g: pd.DataFrame, base_ts: pd.Timestamp, side_num: int):
    q = g[
        (g["snapshot_utc"] > base_ts)
        & g["tier1_early"]
        & (g["preferred_side_num"].astype(int) == int(side_num))
    ]
    return None if q.empty else q.iloc[0]


def action_for_call(g: pd.DataFrame, call, rule: dict):
    r = follow_snapshot(g, call.snapshot_utc, int(rule["horizon_sec"]))
    if r is None:
        return None

    side_num = int(call.preferred_side_num)
    if int(r["preferred_side_num"]) != side_num:
        return None
    if not (2.0 <= float(r["remaining"]) <= 12.0):
        return None
    if float(r["preferred_ask"]) > float(rule["ask_cap"]):
        return None
    if float(r["preferred_fair"]) < float(call.preferred_fair) + float(rule["fair_delta"]):
        return None
    if float(r["edge"]) < float(call.edge) + float(rule["edge_delta"]):
        return None
    if float(r["abs_dist_target"]) < float(call.abs_dist_target) * float(rule["gap_ratio"]):
        return None

    tier = first_future_tier1(g, call.snapshot_utc, side_num)
    before_tier1 = tier is None or r["snapshot_utc"] < tier["snapshot_utc"]
    lead_to_tier1 = np.nan if tier is None else (tier["snapshot_utc"] - r["snapshot_utc"]).total_seconds()

    return {
        "split": call.split,
        "ticker": call.ticker,
        "prewatch_utc": call.snapshot_utc,
        "action_utc": r["snapshot_utc"],
        "horizon_sec": int(rule["horizon_sec"]),
        "side": call.preferred_side,
        "side_num": side_num,
        "action_ask": float(r["preferred_ask"]),
        "action_fair": float(r["preferred_fair"]),
        "action_edge": float(r["edge"]),
        "action_gap": float(r["abs_dist_target"]),
        "action_remaining": float(r["remaining"]),
        "fair_delta_actual": float(r["preferred_fair"] - call.preferred_fair),
        "edge_delta_actual": float(r["edge"] - call.edge),
        "gap_ratio_actual": float(r["abs_dist_target"] / max(float(call.abs_dist_target), 1e-9)),
        "final_side": int(call.final_side),
        "correct": int(side_num == int(call.final_side)),
        "before_same_side_tier1": int(before_tier1),
        "lead_to_same_side_tier1_sec": lead_to_tier1,
    }


def evaluate(calls: pd.DataFrame, cache_groups: dict, rule: dict) -> tuple[dict, pd.DataFrame]:
    rows = []
    for call in calls.itertuples(index=False):
        g = cache_groups.get(call.ticker)
        if g is None or g.empty:
            continue
        a = action_for_call(g, call, rule)
        if a is not None:
            rows.append(a)
    out = pd.DataFrame(rows)
    universe = len(calls)
    if out.empty:
        return {
            "actions": 0, "conversion": 0.0, "accuracy": np.nan,
            "avg_ask": np.nan, "median_ask": np.nan,
            "avg_remaining": np.nan, "median_remaining": np.nan,
            "before_tier1_share": np.nan, "median_tier1_lead_sec": np.nan,
            "ideal_ask_le_35": np.nan, "good_ask_le_40": np.nan,
        }, out
    return {
        "actions": int(len(out)),
        "conversion": float(len(out) / max(universe, 1)),
        "accuracy": float(out["correct"].mean()),
        "avg_ask": float(out["action_ask"].mean()),
        "median_ask": float(out["action_ask"].median()),
        "avg_remaining": float(out["action_remaining"].mean()),
        "median_remaining": float(out["action_remaining"].median()),
        "before_tier1_share": float(out["before_same_side_tier1"].mean()),
        "median_tier1_lead_sec": float(out["lead_to_same_side_tier1_sec"].dropna().median()) if out["lead_to_same_side_tier1_sec"].notna().any() else np.nan,
        "ideal_ask_le_35": float((out["action_ask"] <= 0.35).mean()),
        "good_ask_le_40": float((out["action_ask"] <= 0.40).mean()),
    }, out


def label(rule):
    fd = int(round(100 * rule["fair_delta"]))
    ed = int(round(100 * rule["edge_delta"]))
    return (
        f"+{int(rule['horizon_sec'])}s ask<={int(round(100*rule['ask_cap']))}c "
        f"fairDelta>={fd:+d}pp edgeDelta>={ed:+d}pp gapRatio>={rule['gap_ratio']:.2f}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--calls", default=DEFAULT_CALLS)
    ap.add_argument("--rules-out", default=DEFAULT_RULES)
    ap.add_argument("--actions-out", default=DEFAULT_ACTIONS)
    ap.add_argument("--report-out", default=DEFAULT_REPORT)
    ap.add_argument("--min-validation-actions", type=int, default=12)
    ap.add_argument("--min-validation-accuracy", type=float, default=0.90)
    args = ap.parse_args()

    cache = load_cache(args.cache)
    calls = load_calls(args.calls)
    groups = {t: g.sort_values("snapshot_utc") for t, g in cache.groupby("ticker", sort=False)}
    val = calls[calls["split"] == "VALIDATION"].copy()
    rep = calls[calls["split"] == "REPORT_ONLY"].copy()
    if val.empty or rep.empty:
        raise SystemExit("Champion calls must contain VALIDATION and REPORT_ONLY rows")

    rows = []
    for horizon, ask, fd, ed, gr in itertools.product(
        HORIZONS, ASK_CAPS, FAIR_DELTAS, EDGE_DELTAS, GAP_RATIOS
    ):
        rule = {
            "horizon_sec": horizon,
            "ask_cap": ask,
            "fair_delta": fd,
            "edge_delta": ed,
            "gap_ratio": gr,
        }
        s, _ = evaluate(val, groups, rule)
        rows.append({**rule, **{f"val_{k}": v for k, v in s.items()}})

    grid = pd.DataFrame(rows)
    eligible = grid[
        (grid["val_actions"] >= args.min_validation_actions)
        & (grid["val_accuracy"] >= args.min_validation_accuracy)
    ].copy()

    if eligible.empty:
        ranked = grid.sort_values(
            ["val_accuracy", "val_actions", "val_avg_remaining", "val_avg_ask"],
            ascending=[False, False, False, True],
        ).reset_index(drop=True)
        passed = False
    else:
        ranked = eligible.sort_values(
            ["val_actions", "val_accuracy", "val_before_tier1_share", "val_avg_remaining", "val_avg_ask"],
            ascending=[False, False, False, False, True],
        ).reset_index(drop=True)
        passed = True

    champ = ranked.iloc[0].to_dict()
    rule = {
        "horizon_sec": int(champ["horizon_sec"]),
        "ask_cap": float(champ["ask_cap"]),
        "fair_delta": float(champ["fair_delta"]),
        "edge_delta": float(champ["edge_delta"]),
        "gap_ratio": float(champ["gap_ratio"]),
    }
    val_s, val_a = evaluate(val, groups, rule)
    rep_s, rep_a = evaluate(rep, groups, rule)

    grid.sort_values(
        ["val_accuracy", "val_actions", "val_avg_remaining"],
        ascending=[False, False, False],
    ).to_csv(args.rules_out, index=False)
    pd.concat([val_a, rep_a], ignore_index=True).to_csv(args.actions_out, index=False)

    lines = []
    lines.append("=" * 96)
    lines.append("BTC15 EARLY PRE-WATCH -> ACTIONABLE HANDOFF TOURNAMENT V1")
    lines.append("READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS")
    lines.append("=" * 96)
    lines.append(f"PRE-WATCH calls: validation={len(val)} report_only={len(rep)}")
    lines.append("")
    lines.append("VALIDATION-SELECTED HANDOFF CANDIDATE")
    lines.append("  " + label(rule))
    lines.append(
        f"  actions={val_s['actions']} conversion={pct(val_s['conversion'])} "
        f"accuracy={pct(val_s['accuracy'])} avg_ask={cents(val_s['avg_ask'])} "
        f"median_ask={cents(val_s['median_ask'])} avg_time={mins(val_s['avg_remaining'])}"
    )
    lines.append(
        f"  before same-side protected Tier-1={pct(val_s['before_tier1_share'])} "
        f"median lead to Tier-1={('—' if pd.isna(val_s['median_tier1_lead_sec']) else f'{val_s[\"median_tier1_lead_sec\"]:.0f}s')}"
    )
    lines.append(
        f"  <=35c share={pct(val_s['ideal_ask_le_35'])} <=40c share={pct(val_s['good_ask_le_40'])}"
    )
    lines.append("")
    lines.append("REPORT-ONLY SECOND HALF — NEVER USED TO CHOOSE HANDOFF")
    lines.append(
        f"  actions={rep_s['actions']} conversion={pct(rep_s['conversion'])} "
        f"accuracy={pct(rep_s['accuracy'])} avg_ask={cents(rep_s['avg_ask'])} "
        f"median_ask={cents(rep_s['median_ask'])} avg_time={mins(rep_s['avg_remaining'])}"
    )
    lines.append(
        f"  before same-side protected Tier-1={pct(rep_s['before_tier1_share'])} "
        f"median lead to Tier-1={('—' if pd.isna(rep_s['median_tier1_lead_sec']) else f'{rep_s[\"median_tier1_lead_sec\"]:.0f}s')}"
    )
    lines.append(
        f"  <=35c share={pct(rep_s['ideal_ask_le_35'])} <=40c share={pct(rep_s['good_ask_le_40'])}"
    )
    lines.append("")
    lines.append("SELECTION STATUS")
    if passed:
        lines.append(
            f"  Validation quality gate PASSED: >= {args.min_validation_actions} actions and "
            f">= {100*args.min_validation_accuracy:.1f}% accuracy."
        )
    else:
        lines.append("  No handoff passed the validation quality gate; candidate is DIAGNOSTIC ONLY.")
    lines.append("")
    lines.append("GUARDRAILS")
    lines.append("- PRE-WATCH remains non-actionable by itself.")
    lines.append("- Protected Tier-1 EARLY remains unchanged.")
    lines.append("- No confirmed action may exceed 50c.")
    lines.append("- Champion is selected on VALIDATION only; REPORT_ONLY must not be tuned against.")
    lines.append("- A passed validation gate is not automatic promotion; untouched forward validation is still required.")
    lines.append("- No live behavior changes and no order-placement code.")
    text = "\n".join(lines) + "\n"
    Path(args.report_out).write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"WROTE {args.rules_out}")
    print(f"WROTE {args.actions_out}")
    print(f"WROTE {args.report_out}")


if __name__ == "__main__":
    main()
