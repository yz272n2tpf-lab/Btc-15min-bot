#!/usr/bin/env python3
"""
BTC15 EARLY ladder combined scorecard V1.

READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS

Purpose:
- Compare the protected Tier-1 EARLY anchor with the validation-selected
  PRE-WATCH -> handoff extension.
- Measure overlap, true incremental coverage, earliest actionable union,
  economics, timing and directional accuracy by chronological split.
- Apply only the already-frozen mechanical promotion gates.
- Never tune thresholds and never change live behavior.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

DEFAULT_CACHE = "union_optimizer_processed_snapshot_cache.csv"
DEFAULT_ACTIONS = "early_prewatch_handoff_v1_champion_actions.csv"
DEFAULT_ROWS = "early_ladder_combined_scorecard_v1_rows.csv"
DEFAULT_REPORT = "early_ladder_combined_scorecard_v1.txt"

NUMERIC = [
    "remaining", "abs_dist_target", "final_side", "preferred_side_num",
    "preferred_fair", "preferred_ask", "edge",
]


def pct(x):
    return "—" if pd.isna(x) else f"{100.0*float(x):.1f}%"


def cents(x):
    return "—" if pd.isna(x) else f"{100.0*float(x):.1f}c"


def mins(x):
    return "—" if pd.isna(x) else f"{float(x):.2f}m"


def load_cache(path: str) -> pd.DataFrame:
    d = pd.read_csv(path, low_memory=False)
    need = {
        "ticker", "snapshot_utc", "remaining", "abs_dist_target", "final_side",
        "preferred_side", "preferred_side_num", "preferred_fair",
        "preferred_ask", "edge",
    }
    missing = sorted(need - set(d.columns))
    if missing:
        raise SystemExit(f"Missing cache columns: {missing}")
    d["snapshot_utc"] = pd.to_datetime(d["snapshot_utc"], utc=True, errors="coerce")
    for c in NUMERIC:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=[
        "ticker", "snapshot_utc", "remaining", "abs_dist_target", "final_side",
        "preferred_side_num", "preferred_side", "preferred_fair",
        "preferred_ask", "edge",
    ]).copy()
    d["ticker"] = d["ticker"].astype(str)
    d["preferred_side"] = d["preferred_side"].astype(str).str.upper()
    d = d.sort_values(["ticker", "snapshot_utc"]).reset_index(drop=True)

    # Exact protected Tier-1 EARLY anchor. DO NOT CHANGE.
    d["tier1_early"] = (
        (d["preferred_ask"] <= 0.45)
        & (d["preferred_fair"] >= 0.75)
        & (d["edge"] >= 0.08)
        & d["remaining"].between(2.0, 10.0, inclusive="both")
        & (d["abs_dist_target"] >= 25.0)
    )
    return d


def split_map(d: pd.DataFrame) -> dict[str, str]:
    c = (
        d[["ticker", "snapshot_utc"]]
        .groupby("ticker", as_index=False)["snapshot_utc"].min()
        .sort_values("snapshot_utc")
        .reset_index(drop=True)
    )
    mid = len(c) // 2
    out = {t: "VALIDATION" for t in c.iloc[:mid]["ticker"]}
    out.update({t: "REPORT_ONLY" for t in c.iloc[mid:]["ticker"]})
    return out


def tier1_calls(d: pd.DataFrame, smap: dict[str, str]) -> pd.DataFrame:
    q = d[d["tier1_early"]].sort_values(["ticker", "snapshot_utc"])
    if q.empty:
        return pd.DataFrame()
    q = q.groupby("ticker", as_index=False).first()
    out = pd.DataFrame({
        "split": q["ticker"].map(smap),
        "ticker": q["ticker"],
        "source": "PROTECTED_TIER1",
        "action_utc": q["snapshot_utc"],
        "side_num": q["preferred_side_num"].astype(int),
        "side": q["preferred_side"],
        "ask": q["preferred_ask"].astype(float),
        "remaining": q["remaining"].astype(float),
        "final_side": q["final_side"].astype(int),
    })
    out["correct"] = (out["side_num"] == out["final_side"]).astype(int)
    return out


def load_actions(path: str) -> pd.DataFrame:
    a = pd.read_csv(path, low_memory=False)
    need = {
        "split", "ticker", "action_utc", "side", "side_num", "action_ask",
        "action_remaining", "final_side", "correct", "before_same_side_tier1",
    }
    missing = sorted(need - set(a.columns))
    if missing:
        raise SystemExit(f"Missing handoff action columns: {missing}")
    a["action_utc"] = pd.to_datetime(a["action_utc"], utc=True, errors="coerce")
    for c in ["side_num", "action_ask", "action_remaining", "final_side", "correct", "before_same_side_tier1"]:
        a[c] = pd.to_numeric(a[c], errors="coerce")
    a = a.dropna(subset=["split", "ticker", "action_utc", "side_num", "action_ask", "action_remaining", "final_side", "correct"]).copy()
    a["ticker"] = a["ticker"].astype(str)
    a["side"] = a["side"].astype(str).str.upper()
    a = a.sort_values(["split", "ticker", "action_utc"]).groupby(["split", "ticker"], as_index=False).first()
    out = pd.DataFrame({
        "split": a["split"],
        "ticker": a["ticker"],
        "source": "HANDOFF_EXTENSION",
        "action_utc": a["action_utc"],
        "side_num": a["side_num"].astype(int),
        "side": a["side"],
        "ask": a["action_ask"].astype(float),
        "remaining": a["action_remaining"].astype(float),
        "final_side": a["final_side"].astype(int),
        "correct": a["correct"].astype(int),
        "before_same_side_tier1": a["before_same_side_tier1"].astype(int),
    })
    return out


def stats(x: pd.DataFrame, universe_n: int) -> dict:
    if x.empty:
        return {
            "n": 0, "coverage": 0.0, "accuracy": np.nan,
            "avg_ask": np.nan, "median_ask": np.nan,
            "avg_time": np.nan, "median_time": np.nan,
            "le35": np.nan, "le40": np.nan, "le50": np.nan,
        }
    return {
        "n": int(len(x)),
        "coverage": float(len(x) / max(universe_n, 1)),
        "accuracy": float(x["correct"].mean()),
        "avg_ask": float(x["ask"].mean()),
        "median_ask": float(x["ask"].median()),
        "avg_time": float(x["remaining"].mean()),
        "median_time": float(x["remaining"].median()),
        "le35": float((x["ask"] <= 0.35).mean()),
        "le40": float((x["ask"] <= 0.40).mean()),
        "le50": float((x["ask"] <= 0.50).mean()),
    }


def earliest_union(tier: pd.DataFrame, ext: pd.DataFrame) -> pd.DataFrame:
    both = pd.concat([tier, ext], ignore_index=True, sort=False)
    if both.empty:
        return both
    # More time remaining == earlier actionable point. action_utc is tie-breaker.
    both = both.sort_values(["split", "ticker", "remaining", "action_utc"], ascending=[True, True, False, True])
    return both.groupby(["split", "ticker"], as_index=False).first()


def line(label: str, s: dict) -> str:
    return (
        f"{label}: n={s['n']} coverage={pct(s['coverage'])} accuracy={pct(s['accuracy'])} "
        f"avg_ask={cents(s['avg_ask'])} median_ask={cents(s['median_ask'])} "
        f"avg_time={mins(s['avg_time'])}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--actions", default=DEFAULT_ACTIONS)
    ap.add_argument("--rows-out", default=DEFAULT_ROWS)
    ap.add_argument("--report-out", default=DEFAULT_REPORT)
    args = ap.parse_args()

    d = load_cache(args.cache)
    smap = split_map(d)
    universe = pd.DataFrame({"ticker": list(smap.keys()), "split": list(smap.values())})
    tier = tier1_calls(d, smap)
    ext = load_actions(args.actions)

    # Enforce the same split identity as the cache, rather than trusting an external label.
    ext["split"] = ext["ticker"].map(smap)
    ext = ext.dropna(subset=["split"]).copy()

    union = earliest_union(tier, ext)
    rows = pd.concat([tier, ext], ignore_index=True, sort=False)
    rows.to_csv(args.rows_out, index=False)

    lines = []
    lines.append("=" * 100)
    lines.append("BTC15 EARLY LADDER COMBINED SCORECARD V1")
    lines.append("READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS")
    lines.append("=" * 100)
    lines.append(f"Replay contracts: {len(universe)}")
    lines.append("")

    split_summary = {}
    for split in ["VALIDATION", "REPORT_ONLY"]:
        n = int((universe["split"] == split).sum())
        t = tier[tier["split"] == split].copy()
        e = ext[ext["split"] == split].copy()
        u = union[union["split"] == split].copy()
        tset, eset = set(t["ticker"]), set(e["ticker"])
        overlap = tset & eset
        incremental = eset - tset
        e_inc = e[e["ticker"].isin(incremental)].copy()
        ts, es, us, eis = stats(t, n), stats(e, n), stats(u, n), stats(e_inc, n)
        before_share = float(e["before_same_side_tier1"].mean()) if len(e) and "before_same_side_tier1" in e else np.nan
        split_summary[split] = {"tier": ts, "ext": es, "union": us, "inc": eis, "before_share": before_share}

        lines.append(split)
        lines.append("  " + line("Protected Tier-1", ts))
        lines.append("  " + line("Handoff extension", es))
        lines.append("  " + line("Incremental extension only", eis))
        lines.append("  " + line("Earliest-action union", us))
        lines.append(
            f"  overlap={len(overlap)} | incremental extension contracts={len(incremental)} "
            f"({pct(len(incremental)/max(n,1))}) | extension before same-side Tier-1={pct(before_share)}"
        )
        lines.append(
            f"  extension entry shares: <=35c={pct(es['le35'])} <=40c={pct(es['le40'])} <=50c={pct(es['le50'])}"
        )
        lines.append("")

    v = split_summary["VALIDATION"]["ext"]
    r = split_summary["REPORT_ONLY"]["ext"]
    v_inc = split_summary["VALIDATION"]["inc"]["n"]
    r_inc = split_summary["REPORT_ONLY"]["inc"]["n"]

    mechanical = {
        "validation_n>=12": v["n"] >= 12,
        "validation_accuracy>=90%": (not pd.isna(v["accuracy"])) and v["accuracy"] >= 0.90,
        "report_n>=12": r["n"] >= 12,
        "report_accuracy>=90%": (not pd.isna(r["accuracy"])) and r["accuracy"] >= 0.90,
        "validation_all_entries<=50c": (not pd.isna(v["le50"])) and v["le50"] == 1.0,
        "report_all_entries<=50c": (not pd.isna(r["le50"])) and r["le50"] == 1.0,
        "validation_median_ask<=45c": (not pd.isna(v["median_ask"])) and v["median_ask"] <= 0.45,
        "report_median_ask<=45c": (not pd.isna(r["median_ask"])) and r["median_ask"] <= 0.45,
        "real_incremental_contracts": (v_inc > 0 and r_inc > 0),
    }
    lines.append("PRE-FROZEN MECHANICAL GATE CHECK")
    for k, ok in mechanical.items():
        lines.append(f"  {'PASS' if ok else 'FAIL'} | {k}")
    lines.append("")
    if all(mechanical.values()):
        lines.append("STATUS: Mechanical gates pass. Timing/rescue usefulness still requires review before any forward-test freeze.")
    else:
        lines.append("STATUS: Mechanical gates do NOT all pass. Do not forward-test or promote this extension as-is.")
    lines.append("")
    lines.append("GUARDRAILS")
    lines.append("- Protected Tier-1 EARLY is unchanged.")
    lines.append("- No threshold is selected or tuned by this scorecard.")
    lines.append("- REPORT_ONLY is descriptive only and must not be used to retune.")
    lines.append("- PRE-WATCH alone is non-actionable.")
    lines.append("- Passing offline gates earns at most forward-test candidate status, never live promotion.")
    lines.append("- No live behavior changes and no order-placement code.")

    text = "\n".join(lines) + "\n"
    Path(args.report_out).write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"WROTE {args.rows_out}")
    print(f"WROTE {args.report_out}")


if __name__ == "__main__":
    main()
