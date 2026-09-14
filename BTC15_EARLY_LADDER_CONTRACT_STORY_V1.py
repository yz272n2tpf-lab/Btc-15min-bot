#!/usr/bin/env python3
"""
BTC15 EARLY ladder contract-story audit V1.

READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS

Purpose
-------
Turn the frozen EARLY research outputs into a contract-by-contract state story:
PRE-WATCH -> possible HANDOFF -> protected Tier-1 / repricing / side flip / fade.

This is diagnostic telemetry only. It selects no thresholds, promotes nothing,
and never changes protected Tier-1 or live behavior.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

DEFAULT_CACHE = "union_optimizer_processed_snapshot_cache.csv"
DEFAULT_CALLS = "early_prewatch_tournament_v1_champion_calls.csv"
DEFAULT_ACTIONS = "early_prewatch_handoff_v1_champion_actions.csv"
DEFAULT_ROWS = "early_ladder_contract_story_v1_rows.csv"
DEFAULT_REPORT = "early_ladder_contract_story_v1.txt"

NUMERIC = [
    "remaining", "abs_dist_target", "final_side", "preferred_side_num",
    "preferred_fair", "preferred_ask", "edge",
]


def pct(x):
    return "—" if pd.isna(x) else f"{100.0*float(x):.1f}%"


def cents(x):
    return "—" if pd.isna(x) else f"{100.0*float(x):.1f}c"


def secs(x):
    return "—" if pd.isna(x) else f"{float(x):.0f}s"


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
        "preferred_side", "preferred_side_num", "preferred_fair",
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

    # Diagnostic state discovered by the gap audit: non-price Tier-1 gates are
    # ready, but Kalshi has already moved above the protected 45c entry cap.
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
        "split", "ticker", "snapshot_utc", "remaining", "preferred_side",
        "preferred_side_num", "preferred_ask", "preferred_fair", "edge",
        "abs_dist_target", "final_side",
    }
    missing = sorted(need - set(c.columns))
    if missing:
        raise SystemExit(f"Missing PRE-WATCH call columns: {missing}")
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


def load_actions(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    a = pd.read_csv(p, low_memory=False)
    if a.empty:
        return a
    need = {
        "split", "ticker", "action_utc", "side", "side_num", "action_ask",
        "action_fair", "action_edge", "action_gap", "action_remaining",
        "final_side", "correct",
    }
    missing = sorted(need - set(a.columns))
    if missing:
        raise SystemExit(f"Missing handoff action columns: {missing}")
    a["action_utc"] = pd.to_datetime(a["action_utc"], utc=True, errors="coerce")
    for col in [
        "side_num", "action_ask", "action_fair", "action_edge", "action_gap",
        "action_remaining", "final_side", "correct",
    ]:
        a[col] = pd.to_numeric(a[col], errors="coerce")
    a = a.dropna(subset=[
        "split", "ticker", "action_utc", "side_num", "action_ask",
        "action_remaining", "final_side", "correct",
    ]).copy()
    a["ticker"] = a["ticker"].astype(str)
    a["side"] = a["side"].astype(str).str.upper()
    return (
        a.sort_values(["split", "ticker", "action_utc"])
        .groupby(["split", "ticker"], as_index=False)
        .first()
    )


def first_future(g: pd.DataFrame, ts: pd.Timestamp, mask, side_num: int | None = None):
    q = g[g["snapshot_utc"] > ts]
    q = q.loc[mask.loc[q.index]]
    if side_num is not None:
        q = q[q["preferred_side_num"].astype(int) == int(side_num)]
    return None if q.empty else q.iloc[0]


def first_flip(g: pd.DataFrame, ts: pd.Timestamp, side_num: int):
    q = g[(g["snapshot_utc"] > ts) & (g["preferred_side_num"].astype(int) != int(side_num))]
    return None if q.empty else q.iloc[0]


def dt_sec(a, b):
    if a is None or b is None:
        return np.nan
    return float((b - a).total_seconds())


def classify(action, tier, expensive, flip):
    ats = None if action is None else action["action_utc"]
    tts = None if tier is None else tier["snapshot_utc"]
    ets = None if expensive is None else expensive["snapshot_utc"]
    fts = None if flip is None else flip["snapshot_utc"]

    if action is not None:
        if tier is None:
            return "HANDOFF_NO_LATER_TIER1"
        if ats <= tts:
            return "HANDOFF_BEFORE_TIER1"
        return "HANDOFF_AFTER_TIER1"

    if expensive is not None and (tier is None or ets < tts) and (flip is None or ets <= fts):
        return "REPRICED_BEFORE_TIER1"
    if flip is not None and (tier is None or fts < tts):
        return "SIDE_FLIP_BEFORE_TIER1"
    if tier is not None:
        return "TIER1_ONLY"
    return "WATCH_FADED_OR_UNRESOLVED"


def reason_for(state: str) -> str:
    return {
        "HANDOFF_BEFORE_TIER1": "PRE-WATCH confirmed early while entry was still acceptable, before protected Tier-1.",
        "HANDOFF_AFTER_TIER1": "Protected Tier-1 arrived before the research handoff; extension added no timing advantage.",
        "HANDOFF_NO_LATER_TIER1": "Research handoff confirmed but the same side never later reached protected Tier-1.",
        "REPRICED_BEFORE_TIER1": "Non-price Tier-1 evidence became ready only after Kalshi moved above the protected entry cap.",
        "SIDE_FLIP_BEFORE_TIER1": "Preferred direction flipped before the same side reached protected Tier-1.",
        "TIER1_ONLY": "PRE-WATCH later strengthened into protected Tier-1 without an earlier research handoff.",
        "WATCH_FADED_OR_UNRESOLVED": "PRE-WATCH did not produce a research handoff, protected Tier-1, or a clear repricing/flip transition.",
    }[state]


def build_rows(cache: pd.DataFrame, calls: pd.DataFrame, actions: pd.DataFrame) -> pd.DataFrame:
    groups = {t: g.sort_values("snapshot_utc") for t, g in cache.groupby("ticker", sort=False)}
    action_map = {}
    if not actions.empty:
        action_map = {(r.split, r.ticker): r._asdict() for r in actions.itertuples(index=False)}

    rows = []
    for c in calls.itertuples(index=False):
        g = groups.get(c.ticker)
        if g is None or g.empty:
            continue
        watch_ts = c.snapshot_utc
        side_num = int(c.preferred_side_num)
        tier = first_future(g, watch_ts, g["tier1_early"], side_num)
        expensive = first_future(g, watch_ts, g["expensive_ready"], side_num)
        flip = first_flip(g, watch_ts, side_num)
        action = action_map.get((c.split, c.ticker))
        state = classify(action, tier, expensive, flip)

        action_ts = None if action is None else action["action_utc"]
        tier_ts = None if tier is None else tier["snapshot_utc"]
        expensive_ts = None if expensive is None else expensive["snapshot_utc"]
        flip_ts = None if flip is None else flip["snapshot_utc"]

        rows.append({
            "split": c.split,
            "ticker": c.ticker,
            "watch_utc": watch_ts,
            "watch_side": c.preferred_side,
            "watch_side_num": side_num,
            "watch_ask": float(c.preferred_ask),
            "watch_fair": float(c.preferred_fair),
            "watch_edge": float(c.edge),
            "watch_gap": float(c.abs_dist_target),
            "watch_remaining": float(c.remaining),
            "final_side": int(c.final_side),
            "watch_correct": int(side_num == int(c.final_side)),
            "transition": state,
            "reason": reason_for(state),
            "has_handoff": int(action is not None),
            "handoff_utc": action_ts,
            "handoff_ask": np.nan if action is None else float(action["action_ask"]),
            "handoff_remaining": np.nan if action is None else float(action["action_remaining"]),
            "handoff_correct": np.nan if action is None else int(action["correct"]),
            "sec_watch_to_handoff": dt_sec(watch_ts, action_ts),
            "has_later_tier1": int(tier is not None),
            "tier1_utc": tier_ts,
            "tier1_ask": np.nan if tier is None else float(tier["preferred_ask"]),
            "tier1_remaining": np.nan if tier is None else float(tier["remaining"]),
            "sec_watch_to_tier1": dt_sec(watch_ts, tier_ts),
            "has_expensive_ready": int(expensive is not None),
            "expensive_utc": expensive_ts,
            "expensive_ask": np.nan if expensive is None else float(expensive["preferred_ask"]),
            "sec_watch_to_expensive": dt_sec(watch_ts, expensive_ts),
            "has_side_flip": int(flip is not None),
            "flip_utc": flip_ts,
            "sec_watch_to_flip": dt_sec(watch_ts, flip_ts),
        })
    return pd.DataFrame(rows)


def transition_line(name: str, d: pd.DataFrame) -> str:
    if d.empty:
        return f"{name}: n=0"
    hand = d[d["has_handoff"] == 1]
    return (
        f"{name}: n={len(d)} ({pct(len(d)/max(len(d),1))}) "
        f"watch_acc={pct(d['watch_correct'].mean())} "
        f"handoff_acc={pct(hand['handoff_correct'].mean()) if len(hand) else '—'}"
    )


def report_text(rows: pd.DataFrame) -> str:
    lines = []
    lines.append("=" * 100)
    lines.append("BTC15 EARLY LADDER CONTRACT-STORY AUDIT V1")
    lines.append("READ-ONLY OFFLINE RESEARCH | SIGNAL ONLY | NO ORDERS")
    lines.append("=" * 100)
    lines.append(f"PRE-WATCH contracts audited: {len(rows)}")
    lines.append("")

    states = [
        "HANDOFF_BEFORE_TIER1",
        "HANDOFF_AFTER_TIER1",
        "HANDOFF_NO_LATER_TIER1",
        "TIER1_ONLY",
        "REPRICED_BEFORE_TIER1",
        "SIDE_FLIP_BEFORE_TIER1",
        "WATCH_FADED_OR_UNRESOLVED",
    ]

    for split in ["VALIDATION", "REPORT_ONLY"]:
        d = rows[rows["split"] == split].copy()
        lines.append(split)
        if d.empty:
            lines.append("  n=0")
            lines.append("")
            continue

        hand = d[d["has_handoff"] == 1]
        tier = d[d["has_later_tier1"] == 1]
        lines.append(
            f"  watches={len(d)} watch_accuracy={pct(d['watch_correct'].mean())} "
            f"handoff_conversion={pct(d['has_handoff'].mean())} "
            f"later_Tier1={pct(d['has_later_tier1'].mean())}"
        )
        lines.append(
            f"  repriced-before-Tier1={pct((d['transition']=='REPRICED_BEFORE_TIER1').mean())} "
            f"flip-before-Tier1={pct((d['transition']=='SIDE_FLIP_BEFORE_TIER1').mean())}"
        )
        if len(hand):
            lines.append(
                f"  handoff_accuracy={pct(hand['handoff_correct'].mean())} "
                f"median_handoff_ask={cents(hand['handoff_ask'].median())} "
                f"median_watch->handoff={secs(hand['sec_watch_to_handoff'].median())}"
            )
        if len(tier):
            lines.append(
                f"  median_watch->Tier1={secs(tier['sec_watch_to_tier1'].median())}"
            )
        lines.append("  TRANSITIONS")
        for state in states:
            z = d[d["transition"] == state]
            if z.empty:
                continue
            hand_z = z[z["has_handoff"] == 1]
            lines.append(
                f"    {state}: n={len(z)} share={pct(len(z)/len(d))} "
                f"watch_acc={pct(z['watch_correct'].mean())} "
                f"handoff_acc={pct(hand_z['handoff_correct'].mean()) if len(hand_z) else '—'}"
            )
        lines.append("")

    lines.append("STATE MEANINGS")
    for state in states:
        lines.append(f"- {state}: {reason_for(state)}")
    lines.append("")
    lines.append("GUARDRAILS")
    lines.append("- Transition labels are research telemetry, not new live trading states.")
    lines.append("- Protected Tier-1 EARLY is unchanged.")
    lines.append("- PRE-WATCH is non-actionable by itself.")
    lines.append("- No threshold is chosen or tuned by this audit.")
    lines.append("- REPORT_ONLY remains report-only and must not drive threshold changes.")
    lines.append("- No live behavior changes and no order-placement code.")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--calls", default=DEFAULT_CALLS)
    ap.add_argument("--actions", default=DEFAULT_ACTIONS)
    ap.add_argument("--rows-out", default=DEFAULT_ROWS)
    ap.add_argument("--report-out", default=DEFAULT_REPORT)
    args = ap.parse_args()

    cache = load_cache(args.cache)
    calls = load_calls(args.calls)
    actions = load_actions(args.actions)
    rows = build_rows(cache, calls, actions)
    text = report_text(rows)

    rows.to_csv(args.rows_out, index=False)
    Path(args.report_out).write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"WROTE {args.rows_out}")
    print(f"WROTE {args.report_out}")


if __name__ == "__main__":
    main()
