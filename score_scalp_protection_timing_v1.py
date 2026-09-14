#!/usr/bin/env python3
"""
BTC15 frozen scalp profit-protection timing audit V1.

READ ONLY | SIGNAL ONLY | NO ORDERS

Measures how the already-frozen +5c arm / 4c giveback management behaves on the
untouched-forward tape. It does not select, tighten, or loosen any threshold.

Questions answered:
- How quickly does PROTECT become armed after entry?
- Once a running peak starts giving back, how long until the frozen EXIT fires?
- How many cents of a winner are retained at the first frozen EXIT observation?
- Does 5-second PATH sampling materially overshoot the 4c giveback threshold?
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_CSV = "/data/scalp_move_shadow_v1_events.csv"
FREEZE = pd.Timestamp("2026-09-14T02:24:03.366238Z")
ARM = 0.05
GIVEBACK = 0.04


def pct(x):
    return "—" if pd.isna(x) else f"{100*float(x):.1f}%"


def cents(x):
    return "—" if pd.isna(x) else f"{100*float(x):+.2f}c"


def secs(x):
    return "—" if pd.isna(x) else f"{float(x):.1f}s"


def median_or_nan(values):
    a = pd.Series(list(values), dtype="float64").dropna()
    return float(a.median()) if len(a) else np.nan


def analyze_candidate(candidate, paths):
    g = paths.sort_values("elapsed_sec").copy()
    g = g[pd.to_numeric(g["exec_gain"], errors="coerce").notna()].copy()
    if g.empty:
        return None

    g["elapsed_sec"] = pd.to_numeric(g["elapsed_sec"], errors="coerce")
    g["exec_gain"] = pd.to_numeric(g["exec_gain"], errors="coerce")
    g = g.dropna(subset=["elapsed_sec", "exec_gain"]).sort_values("elapsed_sec")
    if g.empty:
        return None

    diffs = g["elapsed_sec"].diff().dropna()
    med_step = float(diffs.median()) if len(diffs) else np.nan

    armed = False
    arm_elapsed = np.nan
    running_peak = -math.inf
    running_peak_elapsed = np.nan
    exit_elapsed = np.nan
    exit_gain = np.nan
    exit_peak = np.nan
    exit_peak_elapsed = np.nan
    exit_giveback = np.nan

    for _, row in g.iterrows():
        elapsed = float(row["elapsed_sec"])
        gain = float(row["exec_gain"])

        if gain > running_peak:
            running_peak = gain
            running_peak_elapsed = elapsed

        if not armed and running_peak >= ARM:
            armed = True
            arm_elapsed = elapsed

        if armed and running_peak - gain >= GIVEBACK - 1e-12:
            exit_elapsed = elapsed
            exit_gain = gain
            exit_peak = running_peak
            exit_peak_elapsed = running_peak_elapsed
            exit_giveback = running_peak - gain
            break

    full_peak = float(g["exec_gain"].max())
    full_peak_elapsed = float(g.loc[g["exec_gain"].idxmax(), "elapsed_sec"])

    if armed:
        protect_lead_to_exit = (
            float(exit_elapsed - arm_elapsed) if not pd.isna(exit_elapsed) else np.nan
        )
    else:
        protect_lead_to_exit = np.nan

    peak_to_exit = (
        float(exit_elapsed - exit_peak_elapsed)
        if not pd.isna(exit_elapsed) and not pd.isna(exit_peak_elapsed)
        else np.nan
    )

    retained_fraction = (
        float(exit_gain / exit_peak)
        if not pd.isna(exit_gain) and not pd.isna(exit_peak) and exit_peak > 0
        else np.nan
    )

    overshoot = (
        max(0.0, float(exit_giveback - GIVEBACK))
        if not pd.isna(exit_giveback)
        else np.nan
    )

    return {
        "contract": candidate["contract"],
        "candidate_id": candidate["candidate_id"],
        "side": candidate["side"],
        "entry_seconds_left": float(candidate["seconds_left"]),
        "entry_ask": float(candidate["entry_ask"]),
        "btc30": float(candidate["btc30"]),
        "path_rows": len(g),
        "median_path_step_sec": med_step,
        "armed": armed,
        "arm_elapsed_sec": arm_elapsed,
        "full_peak": full_peak,
        "full_peak_elapsed_sec": full_peak_elapsed,
        "exit_triggered": not pd.isna(exit_elapsed),
        "exit_elapsed_sec": exit_elapsed,
        "peak_at_exit": exit_peak,
        "peak_at_exit_elapsed_sec": exit_peak_elapsed,
        "exit_gain": exit_gain,
        "giveback_at_exit": exit_giveback,
        "overshoot_beyond_4c": overshoot,
        "protect_lead_to_exit_sec": protect_lead_to_exit,
        "peak_to_exit_sec": peak_to_exit,
        "retained_fraction": retained_fraction,
    }


def emit_group(name, g):
    if g.empty:
        print(f"{name}: n=0")
        return
    exits = g[g.exit_triggered]
    print(
        f"{name}: n={len(g)} armed={pct(g.armed.mean())} exits={len(exits)} "
        f"median_peak={cents(g.full_peak.median())} "
        f"median_path_step={secs(g.median_path_step_sec.median())}"
    )
    if len(exits):
        print(
            "  EXIT timing: "
            f"median peak->exit={secs(exits.peak_to_exit_sec.median())} "
            f"median arm->exit={secs(exits.protect_lead_to_exit_sec.median())} "
            f"median giveback={cents(exits.giveback_at_exit.median())} "
            f"median overshoot={cents(exits.overshoot_beyond_4c.median())} "
            f"median exit_gain={cents(exits.exit_gain.median())} "
            f"median retained={pct(exits.retained_fraction.median())}"
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--freeze", default=str(FREEZE))
    ap.add_argument("--rows-out", default="scalp_protection_timing_v1_rows.csv")
    args = ap.parse_args()

    d = pd.read_csv(args.csv, low_memory=False)
    d["timestamp_utc"] = pd.to_datetime(d["timestamp_utc"], utc=True, errors="coerce")
    d = d[d.timestamp_utc > pd.Timestamp(args.freeze)].copy()

    for col in ["seconds_left", "entry_ask", "btc30", "elapsed_sec", "exec_gain"]:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce")

    cand = d[d.record_type.eq("CANDIDATE")].copy()
    path = d[d.record_type.eq("PATH")].copy()

    # Exact frozen primary-challenger qualification. No price filter.
    qual = cand[(cand.seconds_left >= 120) & (cand.btc30 >= 15)].copy()
    qual = qual.sort_values(["contract", "timestamp_utc"]).drop_duplicates("contract", keep="first")

    by_path = {cid: g for cid, g in path.groupby("candidate_id", sort=False)}
    rows = []
    for _, c in qual.iterrows():
        r = analyze_candidate(c, by_path.get(c.candidate_id, path.iloc[0:0]))
        if r is not None:
            rows.append(r)

    out = pd.DataFrame(rows)
    out.to_csv(args.rows_out, index=False)

    print("=" * 96)
    print("BTC15 FROZEN SCALP PROFIT-PROTECTION TIMING AUDIT V1 | READ ONLY | NO ORDERS")
    print("=" * 96)
    print(f"freeze={args.freeze}")
    print(f"qualified_with_path={len(out)}")
    print("frozen management=arm +5c | EXIT after 4c running-peak giveback")
    print("PROTECT presentation begins when the already-validated +5c arm fires")
    print("")

    emit_group("ALL", out)
    emit_group("PEAK >=10c", out[out.full_peak >= .10])
    emit_group("PEAK >=15c", out[out.full_peak >= .15])
    emit_group("PEAK >=20c", out[out.full_peak >= .20])

    if len(out):
        exits = out[out.exit_triggered]
        print("")
        print("PROTECTION COVERAGE")
        print(f"armed after +5c: {int(out.armed.sum())}/{len(out)} ({pct(out.armed.mean())})")
        print(f"4c giveback EXIT observed: {len(exits)}/{len(out)} ({pct(out.exit_triggered.mean())})")
        if len(exits):
            print(f"exit still positive: {pct((exits.exit_gain > 0).mean())}")
            print(f"exit >=+5c: {pct((exits.exit_gain >= .05).mean())}")
            print(f"exit >=+10c: {pct((exits.exit_gain >= .10).mean())}")

    print("")
    print("GUARDRAILS")
    print("- This is a timing/retention audit only; it does not tune the 5c/4c rule.")
    print("- No SCALP entry-price filter is introduced.")
    print("- PROTECT is advisory presentation after the validated arm; user executes manually.")
    print("- Exact live alert latency still requires the integrated smoke test.")
    print("- No order-placement code exists.")
    print(f"WROTE {Path(args.rows_out)}")


if __name__ == "__main__":
    main()
