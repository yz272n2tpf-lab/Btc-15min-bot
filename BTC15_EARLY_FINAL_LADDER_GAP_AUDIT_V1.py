#!/usr/bin/env python3
"""
BTC15 EARLY + FINAL ladder gap audit V1.

READ-ONLY OFFLINE RESEARCH. SIGNAL ONLY. NO ORDERS.

Consumes the timeline CSV produced by BTC15_EARLY_FINAL_LADDER_TIMELINE_SCORER_V1.py.

Purpose:
- Identify contracts that were exactly one protected gate away from EARLY or FINAL.
- Score each missing-gate class on validation and report holdout separately.
- Quantify incremental coverage, accuracy, entry ask, and timing.
- Do NOT promote a relaxed gate. This is a target-selection audit only.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

DEFAULT_TIMELINE = "early_final_ladder_timeline_v1.csv"
DEFAULT_OUT = "early_final_ladder_gap_audit_v1.csv"
DEFAULT_SUMMARY = "early_final_ladder_gap_audit_v1.txt"

def pct(x):
    return "—" if pd.isna(x) else f"{100.0*float(x):.1f}%"

def cents(x):
    return "—" if pd.isna(x) else f"{100.0*float(x):.1f}c"

def mins(x):
    return "—" if pd.isna(x) else f"{float(x):.2f}m"

def load(path):
    d = pd.read_csv(path, low_memory=False)
    need = {
        "ticker","snapshot_utc","elapsed","remaining","preferred_side_num",
        "preferred_ask","preferred_fair","final_side",
        "early_missing_gates","early_watch_research","early_qualified",
        "final_missing_gates","final_watch_research","final_qualified",
    }
    missing = sorted(need - set(d.columns))
    if missing:
        raise SystemExit(f"Timeline missing columns: {missing}")
    d["snapshot_utc"] = pd.to_datetime(d["snapshot_utc"], utc=True, errors="coerce")
    for c in ["elapsed","remaining","preferred_side_num","preferred_ask","preferred_fair","final_side"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    for c in ["early_watch_research","early_qualified","final_watch_research","final_qualified"]:
        if d[c].dtype == object:
            d[c] = d[c].astype(str).str.lower().map({"true":True,"false":False})
        d[c] = d[c].fillna(False).astype(bool)
    return d.dropna(subset=["ticker","snapshot_utc","final_side","preferred_side_num"]).sort_values(
        ["ticker","elapsed","snapshot_utc"]
    )

def split_contracts(d):
    c = (
        d.groupby("ticker",as_index=False)["snapshot_utc"].min()
        .sort_values("snapshot_utc")
        .reset_index(drop=True)
    )
    mid = len(c)//2
    return set(c.iloc[:mid].ticker), set(c.iloc[mid:].ticker)

def first_per_contract(d):
    if d.empty:
        return d.copy()
    return d.sort_values(["ticker","elapsed","snapshot_utc"]).groupby("ticker",as_index=False).first()

def anchor_contracts(d, col):
    return set(first_per_contract(d[d[col]]).ticker)

def audit_class(pool, module, missing_gate):
    watch_col = f"{module}_watch_research"
    missing_col = f"{module}_missing_gates"
    qual_col = f"{module}_qualified"

    q = pool[pool[watch_col] & (pool[missing_col].astype(str) == missing_gate)].copy()
    q = first_per_contract(q)
    anchors = anchor_contracts(pool, qual_col)
    if not q.empty:
        q = q[~q.ticker.isin(anchors)].copy()

    n_contracts = pool.ticker.nunique()
    if q.empty:
        return {
            "module":module.upper(),"missing_gate":missing_gate,"calls":0,
            "incremental_coverage":0.0,"accuracy":np.nan,
            "avg_ask":np.nan,"median_ask":np.nan,
            "avg_time":np.nan,"median_time":np.nan,"avg_fair":np.nan,
        }

    correct = q.preferred_side_num.astype(int) == q.final_side.astype(int)
    return {
        "module":module.upper(),
        "missing_gate":missing_gate,
        "calls":len(q),
        "incremental_coverage":len(q)/max(n_contracts,1),
        "accuracy":float(correct.mean()),
        "avg_ask":float(q.preferred_ask.mean()),
        "median_ask":float(q.preferred_ask.median()),
        "avg_time":float(q.remaining.mean()),
        "median_time":float(q.remaining.median()),
        "avg_fair":float(q.preferred_fair.mean()),
    }

def collect(pool, split_name):
    rows = []
    for module in ("early","final"):
        missing_col = f"{module}_missing_gates"
        watch_col = f"{module}_watch_research"
        gates = sorted(
            g for g in pool.loc[pool[watch_col], missing_col].dropna().astype(str).unique()
            if g and g != "NONE" and "," not in g
        )
        for gate in gates:
            r = audit_class(pool,module,gate)
            r["split"] = split_name
            rows.append(r)
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", default=DEFAULT_TIMELINE)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--summary", default=DEFAULT_SUMMARY)
    args = ap.parse_args()

    d = load(args.timeline)
    valid, hold = split_contracts(d)
    pools = {
        "VALIDATION": d[d.ticker.isin(valid)].copy(),
        "HOLDOUT_REPORT_ONLY": d[d.ticker.isin(hold)].copy(),
    }

    rows = []
    for name,pool in pools.items():
        rows.extend(collect(pool,name))
    out = pd.DataFrame(rows)

    if out.empty:
        raise SystemExit("No one-missing-gate research states found")

    out = out.sort_values(
        ["split","module","accuracy","incremental_coverage"],
        ascending=[True,True,False,False],
        na_position="last",
    ).reset_index(drop=True)
    out.to_csv(args.out,index=False)

    lines = []
    lines.append("="*88)
    lines.append("BTC15 EARLY + FINAL LADDER GAP AUDIT V1")
    lines.append("TARGET SELECTION ONLY | READ ONLY | SIGNAL ONLY | NO ORDERS")
    lines.append("="*88)
    for split in ("VALIDATION","HOLDOUT_REPORT_ONLY"):
        lines.append("")
        lines.append(split)
        z = out[out.split.eq(split)]
        for _,r in z.iterrows():
            lines.append(
                f"{r.module:5s} missing={r.missing_gate:18s} "
                f"n={int(r.calls):3d} inc_cov={pct(r.incremental_coverage):>6s} "
                f"acc={pct(r.accuracy):>6s} ask={cents(r.avg_ask):>6s} "
                f"time={mins(r.avg_time):>7s} fair={pct(r.avg_fair):>6s}"
            )

    lines.append("")
    lines.append("INTERPRETATION GUARDRAILS")
    lines.append("- Validation ranks where future tournament effort should focus.")
    lines.append("- HOLDOUT_REPORT_ONLY is descriptive; never tune thresholds to it.")
    lines.append("- A high-accuracy missing-gate class is NOT permission to remove that gate.")
    lines.append("- Any relaxation/extension must be tested as a separate rule chronologically.")
    lines.append("- Protected EARLY and FINAL anchors remain unchanged.")
    lines.append("- No order-placement code exists in this audit.")

    text = "\n".join(lines) + "\n"
    Path(args.summary).write_text(text,encoding="utf-8")
    print(text,end="")
    print(f"WROTE {args.out}")
    print(f"WROTE {args.summary}")

if __name__ == "__main__":
    main()
