#!/usr/bin/env python3
"""
BTC15 EARLY + FINAL ladder timeline scorer V1.

READ-ONLY OFFLINE RESEARCH. SIGNAL ONLY. NO ORDERS.

Purpose:
- Reproduce protected Tier-1 EARLY and protected high-confidence FINAL anchors.
- Build a contract-by-contract minute timeline.
- Expose research-only near-gate states without inventing new actionable thresholds.
- Export timeline, contract summary, and baseline scorecard.
- No live behavior changes.

Important:
- EARLY_WATCH_RESEARCH means exactly one protected Tier-1 gate is still missing.
- FINAL_WATCH_RESEARCH means exactly one protected FINAL gate is still missing.
- Those WATCH labels are research telemetry only and are NOT actionable rules.
- FINAL_LOCK_CANDIDATE_RESEARCH is descriptive only until an explicit LOCK handoff
  rule is validated separately.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

DEFAULT_CACHE = "union_optimizer_processed_snapshot_cache.csv"
DEFAULT_TIMELINE = "early_final_ladder_timeline_v1.csv"
DEFAULT_CONTRACTS = "early_final_ladder_contract_summary_v1.csv"
DEFAULT_SCORECARD = "early_final_ladder_scorecard_v1.txt"

NUMERIC = [
    "elapsed","remaining","current_side","dist_target","abs_dist_target",
    "dist_over_range5","final_side","fair_up","fair_down","preferred_side_num",
    "preferred_fair","preferred_ask","preferred_bid","edge",
]

def pct(x):
    return "—" if pd.isna(x) else f"{100.0*float(x):.1f}%"

def money(x):
    return "—" if pd.isna(x) else f"{100.0*float(x):.1f}c"

def mins(x):
    return "—" if pd.isna(x) else f"{float(x):.2f}m"

def load_cache(path: str) -> pd.DataFrame:
    d = pd.read_csv(path, low_memory=False)
    need = {
        "ticker","snapshot_utc","elapsed","remaining","current_side",
        "abs_dist_target","dist_over_range5","final_side",
        "fair_up","fair_down","preferred_side_num","preferred_side",
        "preferred_fair","preferred_ask","preferred_bid","edge",
    }
    missing = sorted(need - set(d.columns))
    if missing:
        raise SystemExit(f"Missing required cache columns: {missing}")

    d["snapshot_utc"] = pd.to_datetime(d["snapshot_utc"], utc=True, errors="coerce")
    for c in NUMERIC:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=[
        "ticker","snapshot_utc","elapsed","remaining","current_side",
        "abs_dist_target","dist_over_range5","final_side",
        "preferred_side_num","preferred_side","preferred_fair",
        "preferred_ask","edge",
    ]).copy()
    d["ticker"] = d["ticker"].astype(str)
    d["preferred_side"] = d["preferred_side"].astype(str).str.upper()
    return d.sort_values(["ticker","elapsed","snapshot_utc"]).reset_index(drop=True)

def add_gates(d: pd.DataFrame) -> pd.DataFrame:
    x = d.copy()

    # Protected Tier-1 EARLY anchor. Exact current project-state rule.
    x["early_ask_le_45c"] = x["preferred_ask"] <= 0.45
    x["early_fair_ge_75"] = x["preferred_fair"] >= 0.75
    x["early_edge_ge_8pp"] = x["edge"] >= 0.08
    x["early_time_2_to_10m"] = x["remaining"].between(2.0, 10.0, inclusive="both")
    x["early_gap_ge_25"] = x["abs_dist_target"] >= 25.0

    early_cols = [
        "early_ask_le_45c",
        "early_fair_ge_75",
        "early_edge_ge_8pp",
        "early_time_2_to_10m",
        "early_gap_ge_25",
    ]
    x["early_gate_count"] = x[early_cols].sum(axis=1).astype(int)
    x["early_qualified"] = x["early_gate_count"] == len(early_cols)
    x["early_watch_research"] = (
        (x["early_gate_count"] == len(early_cols)-1) & (~x["early_qualified"])
    )

    # Protected high-confidence FINAL anchor. Exact current project-state rule.
    x["final_fair_ge_90"] = x["preferred_fair"] >= 0.90
    x["final_time_le_8m"] = (x["remaining"] >= 0.0) & (x["remaining"] <= 8.0)
    gap_needed = np.where(x["remaining"] > 6.0, 75.0, 50.0)
    x["final_gap_needed"] = gap_needed
    x["final_conditional_gap"] = x["abs_dist_target"] >= gap_needed
    x["final_dist_over_range5_ge_1"] = x["dist_over_range5"] >= 1.0
    x["final_preferred_matches_current_side"] = (
        x["preferred_side_num"].astype(int) == x["current_side"].astype(int)
    )

    final_cols = [
        "final_fair_ge_90",
        "final_time_le_8m",
        "final_conditional_gap",
        "final_dist_over_range5_ge_1",
        "final_preferred_matches_current_side",
    ]
    x["final_gate_count"] = x[final_cols].sum(axis=1).astype(int)
    x["final_qualified"] = x["final_gate_count"] == len(final_cols)
    x["final_watch_research"] = (
        (x["final_gate_count"] == len(final_cols)-1) & (~x["final_qualified"])
    )

    # Descriptive only. This does not create a separate validated live LOCK rule.
    x["final_lock_candidate_research"] = x["final_qualified"]

    def missing_early(row):
        names = [
            ("ask<=45c", row.early_ask_le_45c),
            ("fair>=75%", row.early_fair_ge_75),
            ("edge>=8pp", row.early_edge_ge_8pp),
            ("2-10m", row.early_time_2_to_10m),
            ("gap>=25", row.early_gap_ge_25),
        ]
        return ",".join(n for n, ok in names if not bool(ok)) or "NONE"

    def missing_final(row):
        names = [
            ("fair>=90%", row.final_fair_ge_90),
            ("<=8m", row.final_time_le_8m),
            ("gap", row.final_conditional_gap),
            ("range_ratio>=1", row.final_dist_over_range5_ge_1),
            ("side=current", row.final_preferred_matches_current_side),
        ]
        return ",".join(n for n, ok in names if not bool(ok)) or "NONE"

    x["early_missing_gates"] = [missing_early(r) for r in x.itertuples(index=False)]
    x["final_missing_gates"] = [missing_final(r) for r in x.itertuples(index=False)]

    # State labels use only protected anchors plus one-missing-gate research telemetry.
    x["ladder_state"] = "OBSERVE"
    x.loc[x["early_watch_research"], "ladder_state"] = "EARLY_WATCH_RESEARCH"
    x.loc[x["early_qualified"], "ladder_state"] = "EARLY_QUALIFIED"
    x.loc[x["final_watch_research"], "ladder_state"] = "FINAL_WATCH_RESEARCH"
    x.loc[x["final_qualified"], "ladder_state"] = "FINAL_QUALIFIED_HIGH_CONF"

    return x

def first_rows(d: pd.DataFrame, mask_col: str) -> pd.DataFrame:
    q = d[d[mask_col]].sort_values(["ticker","elapsed","snapshot_utc"])
    if q.empty:
        return q.copy()
    return q.groupby("ticker", as_index=False).first()

def score_calls(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {
            "calls":0,"accuracy":np.nan,"coverage":np.nan,
            "avg_ask":np.nan,"median_ask":np.nan,
            "avg_time":np.nan,"median_time":np.nan,
        }
    correct = frame["preferred_side_num"].astype(int) == frame["final_side"].astype(int)
    return {
        "calls":len(frame),
        "accuracy":float(correct.mean()),
        "coverage":np.nan,
        "avg_ask":float(frame["preferred_ask"].mean()),
        "median_ask":float(frame["preferred_ask"].median()),
        "avg_time":float(frame["remaining"].mean()),
        "median_time":float(frame["remaining"].median()),
    }

def split_contracts(d: pd.DataFrame):
    # Existing processed cache is the validation+holdout research pool.
    # Mirror the established V1.2 convention: chronological first half validation,
    # second half untouched holdout.
    c = (
        d[["ticker","snapshot_utc"]]
        .groupby("ticker", as_index=False)["snapshot_utc"].min()
        .sort_values("snapshot_utc")
        .reset_index(drop=True)
    )
    mid = len(c)//2
    return set(c.iloc[:mid]["ticker"]), set(c.iloc[mid:]["ticker"])

def call_summary(d: pd.DataFrame, mask_col: str, universe_n: int) -> tuple[dict,pd.DataFrame]:
    first = first_rows(d, mask_col)
    s = score_calls(first)
    s["coverage"] = len(first)/max(universe_n,1)
    return s, first

def build_contract_summary(d: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticker, g in d.groupby("ticker", sort=False):
        g = g.sort_values(["elapsed","snapshot_utc"])
        early = g[g["early_qualified"]]
        final = g[g["final_qualified"]]
        ew = g[g["early_watch_research"]]
        fw = g[g["final_watch_research"]]
        first = g.iloc[0]

        def get(q, col, default=np.nan):
            return default if q.empty else q.iloc[0][col]

        rows.append({
            "ticker":ticker,
            "final_side":int(first["final_side"]),
            "first_early_watch_remaining":get(ew,"remaining"),
            "first_early_qualified_remaining":get(early,"remaining"),
            "first_early_qualified_side":get(early,"preferred_side",""),
            "first_early_qualified_ask":get(early,"preferred_ask"),
            "first_early_qualified_fair":get(early,"preferred_fair"),
            "first_early_correct":(
                np.nan if early.empty else
                int(int(early.iloc[0]["preferred_side_num"]) == int(first["final_side"]))
            ),
            "first_final_watch_remaining":get(fw,"remaining"),
            "first_final_qualified_remaining":get(final,"remaining"),
            "first_final_qualified_side":get(final,"preferred_side",""),
            "first_final_qualified_fair":get(final,"preferred_fair"),
            "first_final_correct":(
                np.nan if final.empty else
                int(int(final.iloc[0]["preferred_side_num"]) == int(first["final_side"]))
            ),
            "has_early":int(not early.empty),
            "has_final":int(not final.empty),
            "has_any_anchor":int((not early.empty) or (not final.empty)),
        })
    return pd.DataFrame(rows)

def scorecard_text(d: pd.DataFrame) -> str:
    valid_ticks, hold_ticks = split_contracts(d)
    total_n = d["ticker"].nunique()

    sections = []
    sections.append("="*86)
    sections.append("BTC15 EARLY + FINAL LADDER TIMELINE SCORER V1")
    sections.append("READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS")
    sections.append("="*86)
    sections.append(f"Snapshot rows: {len(d):,}")
    sections.append(f"Contracts: {total_n}")
    sections.append("")

    for label, pool in [
        ("ALL CACHE", d),
        ("VALIDATION HALF", d[d["ticker"].isin(valid_ticks)]),
        ("HOLDOUT HALF", d[d["ticker"].isin(hold_ticks)]),
    ]:
        n = pool["ticker"].nunique()
        es, _ = call_summary(pool, "early_qualified", n)
        fs, _ = call_summary(pool, "final_qualified", n)
        csum = build_contract_summary(pool)
        union = csum["has_any_anchor"].mean() if len(csum) else np.nan
        sections.append(label)
        sections.append(
            f"  Tier-1 EARLY: calls={es['calls']} coverage={pct(es['coverage'])} "
            f"accuracy={pct(es['accuracy'])} avg_ask={money(es['avg_ask'])} "
            f"median_ask={money(es['median_ask'])} avg_time={mins(es['avg_time'])}"
        )
        sections.append(
            f"  Protected FINAL: calls={fs['calls']} coverage={pct(fs['coverage'])} "
            f"accuracy={pct(fs['accuracy'])} avg_time={mins(fs['avg_time'])} "
            f"median_time={mins(fs['median_time'])}"
        )
        sections.append(f"  Anchor union coverage: {pct(union)}")
        sections.append("")

    early_watch = first_rows(d, "early_watch_research")
    final_watch = first_rows(d, "final_watch_research")
    sections.append("RESEARCH-ONLY WATCH INVENTORY")
    sections.append(
        f"  EARLY one-missing-gate contracts: {early_watch['ticker'].nunique()} "
        f"(NOT actionable)"
    )
    sections.append(
        f"  FINAL one-missing-gate contracts: {final_watch['ticker'].nunique()} "
        f"(NOT actionable)"
    )
    sections.append("")
    sections.append("GUARDRAILS")
    sections.append("- WATCH states are one-missing-gate diagnostics only; no new threshold is promoted.")
    sections.append("- Protected Tier-1 EARLY and protected FINAL definitions are unchanged.")
    sections.append("- FINAL_LOCK_CANDIDATE_RESEARCH is descriptive only; no new live LOCK behavior.")
    sections.append("- Continuous fair_up / fair_down remain visible in the timeline for every snapshot.")
    sections.append("- No order-placement code exists in this scorer.")
    return "\n".join(sections) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--timeline", default=DEFAULT_TIMELINE)
    ap.add_argument("--contracts", default=DEFAULT_CONTRACTS)
    ap.add_argument("--scorecard", default=DEFAULT_SCORECARD)
    args = ap.parse_args()

    d = add_gates(load_cache(args.cache))
    contracts = build_contract_summary(d)
    text = scorecard_text(d)

    out_cols = [
        "ticker","snapshot_utc","elapsed","remaining","current_side",
        "fair_up","fair_down","preferred_side","preferred_side_num",
        "preferred_fair","preferred_ask","preferred_bid","edge",
        "abs_dist_target","dist_over_range5","final_side",
        "early_gate_count","early_missing_gates","early_watch_research","early_qualified",
        "final_gate_count","final_missing_gates","final_watch_research","final_qualified",
        "final_lock_candidate_research","ladder_state",
    ]
    d[out_cols].to_csv(args.timeline, index=False)
    contracts.to_csv(args.contracts, index=False)
    Path(args.scorecard).write_text(text, encoding="utf-8")

    print(text, end="")
    print(f"WROTE {args.timeline}")
    print(f"WROTE {args.contracts}")
    print(f"WROTE {args.scorecard}")

if __name__ == "__main__":
    main()
