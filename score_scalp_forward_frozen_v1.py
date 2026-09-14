#!/usr/bin/env python3
"""
BTC15 frozen generalized-scalp untouched-forward scorekeeper V1.
READ-ONLY OFFLINE RESEARCH. SIGNAL ONLY. NO ORDERS.

Frozen challenger (do not retune here):
- post-freeze rows only
- first candidate per contract satisfying seconds_left >= 120 and btc30 >= 15
- no entry-price filter
- management: arm at +5c, protect/exit on 4c giveback from executable peak
- primary decision gate: >=20 new unique qualified contracts
"""
from __future__ import annotations
import argparse
import numpy as np
import pandas as pd

DEFAULT_CSV = "/data/scalp_move_shadow_v1_events.csv"
FREEZE = pd.Timestamp("2026-09-14T02:24:03.366238Z")
TARGET_CONTRACTS = 20


def pct(v):
    return "—" if pd.isna(v) else f"{100*v:.1f}%"


def cents(v):
    return "—" if pd.isna(v) else f"{100*v:+.2f}c"


def seconds(v):
    return "—" if pd.isna(v) else f"{v:.1f}s"


def managed_exit(candidate_ids, paths, results, arm=.05, giveback=.04):
    pmap = {k:g.sort_values("elapsed_sec") for k,g in paths.groupby("candidate_id")}
    rmap = results.set_index("candidate_id")
    out = []
    for cid in candidate_ids:
        peak = -1e9
        armed = False
        exit_gain = np.nan
        exit_sec = np.nan
        exit_reason = "HORIZON"
        for _, z in pmap.get(cid, paths.iloc[0:0]).iterrows():
            g = z.get("exec_gain")
            if pd.isna(g):
                continue
            peak = max(peak, float(g))
            armed = armed or peak >= arm
            if armed and peak - float(g) >= giveback:
                exit_gain = float(g)
                exit_sec = float(z.get("elapsed_sec")) if not pd.isna(z.get("elapsed_sec")) else np.nan
                exit_reason = "GIVEBACK"
                break
        if pd.isna(exit_gain):
            if cid in rmap.index:
                v = rmap.loc[cid].get("horizon_exec_gain")
                exit_gain = 0.0 if pd.isna(v) else float(v)
        out.append((cid, exit_gain, exit_sec, exit_reason))
    return pd.DataFrame(out, columns=["candidate_id","managed_gain","managed_exit_sec","managed_exit_reason"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--freeze", default=str(FREEZE))
    a = ap.parse_args()

    d = pd.read_csv(a.csv, low_memory=False)
    d["timestamp_utc"] = pd.to_datetime(d["timestamp_utc"], utc=True, errors="coerce")
    freeze = pd.Timestamp(a.freeze)
    d = d[d["timestamp_utc"] > freeze].copy()

    for f in ["seconds_left","entry_ask","btc30","elapsed_sec","exec_gain","peak_exec_gain",
              "max_adverse","horizon_exec_gain","hit5_sec","hit10_sec","hit15_sec","hit20_sec","hit30_sec"]:
        if f in d.columns:
            d[f] = pd.to_numeric(d[f], errors="coerce")

    cand = d[d.record_type.eq("CANDIDATE")].copy()
    res = d[d.record_type.eq("RESULT")].copy()
    path = d[d.record_type.eq("PATH")].copy()
    snap = d[d.record_type.eq("SNAPSHOT")].copy()

    qual = cand[(cand.seconds_left >= 120) & (cand.btc30 >= 15)].copy()
    qual = qual.sort_values(["contract","timestamp_utc"]).drop_duplicates("contract", keep="first")

    keep = ["candidate_id","timestamp_utc","contract","side","seconds_left","entry_ask","btc30"]
    outcomes = ["candidate_id","peak_exec_gain","max_adverse","horizon_exec_gain",
                "hit5_sec","hit10_sec","hit15_sec","hit20_sec","hit30_sec"]
    done = qual[keep].merge(res[outcomes], on="candidate_id", how="inner")

    managed = managed_exit(done.candidate_id.tolist(), path, res, .05, .04)
    done = done.merge(managed, on="candidate_id", how="left")

    observed = set(snap.contract.dropna()) if "contract" in snap else set()
    qualified_contracts = set(qual.contract.dropna())
    completed_contracts = set(done.contract.dropna())
    coverage = len(qualified_contracts) / len(observed) if observed else np.nan

    n = len(done)
    print("="*92)
    print("BTC15 FROZEN SCALP FORWARD SCOREKEEPER V1 | READ ONLY | SIGNAL ONLY | NO ORDERS")
    print("="*92)
    print(f"freeze_utc={freeze}")
    print(f"post_freeze_rows={len(d):,} observed_contracts={len(observed)}")
    print(f"qualified_unique_contracts={len(qualified_contracts)} completed_qualified={n} target={TARGET_CONTRACTS}")
    print(f"qualified_actionable_coverage={pct(coverage)}")
    print()

    if n:
        for t in (5,10,15,20,30):
            print(f"+{t}c hit rate: {pct(done[f'hit{t}_sec'].notna().mean())}")
        print(f"avg peak executable: {cents(done.peak_exec_gain.mean())}")
        print(f"median peak executable: {cents(done.peak_exec_gain.median())}")
        print(f"median adverse excursion: {cents(done.max_adverse.median())}")
        print(f"managed avg: {cents(done.managed_gain.mean())}")
        print(f"managed median: {cents(done.managed_gain.median())}")
        print(f"managed positive-exit rate: {pct((done.managed_gain > 0).mean())}")
        for t in (5,10,20):
            print(f"median time to +{t}c among hits: {seconds(done[f'hit{t}_sec'].median())}")
        print()
        print("SIDE BREAKDOWN")
        for side, g in done.groupby("side"):
            print(f"{side}: n={len(g)} +10={pct(g.hit10_sec.notna().mean())} +20={pct(g.hit20_sec.notna().mean())} managed_avg={cents(g.managed_gain.mean())}")

    remaining = max(TARGET_CONTRACTS - len(completed_contracts), 0)
    print()
    if len(completed_contracts) < TARGET_CONTRACTS:
        print(f"GATE: COLLECT | need {remaining} more completed unique qualified contracts before primary PASS/FAIL decision")
    else:
        print("GATE: READY TO JUDGE | >=20 completed unique qualified contracts reached")
        print("Compare against frozen development reference WITHOUT retuning:")
        print("  dev +10=77.6% | +20=34.7% | managed_avg=+10.06c | managed_median=+10.00c | positive=83.7%")
        print("Do not promote automatically; inspect coverage, downside, side balance and regime stability.")

    print("\nGUARDRAILS: no price eligibility filter; no threshold tuning; no orders; no changes to locked V8.1/FINAL/EARLY.")

if __name__ == "__main__":
    main()
