#!/usr/bin/env python3
"""
BTC15 EARLY HIGH-CONFIDENCE SCORER V1.

READ-ONLY HISTORICAL RESEARCH | SIGNAL ONLY | NO ORDERS

Implements only the candidate families frozen in
BTC15_EARLY_HIGH_CONFIDENCE_RESEARCH_FREEZE_V1.md.

The existing replay cache is treated as historical development/research data,
not as a new untouched holdout. Any winner requires fresh forward confirmation.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

DEFAULT_CACHE = "union_optimizer_processed_snapshot_cache.csv"
DEFAULT_RULES = "early_high_confidence_v1_rules.csv"
DEFAULT_CALLS = "early_high_confidence_v1_calls.csv"
DEFAULT_REPORT = "early_high_confidence_v1.txt"

NUMERIC = [
    "elapsed","remaining","current_side","abs_dist_target","final_side",
    "preferred_side_num","preferred_fair","preferred_ask","preferred_bid","edge",
]

SAME_ROW_RULES = {
    "FAIR80": lambda r: r.preferred_fair >= .80,
    "FAIR85": lambda r: r.preferred_fair >= .85,
    "EDGE10": lambda r: r.edge >= .10,
    "GAP35": lambda r: r.abs_dist_target >= 35.0,
    "CURRENT_SIDE": lambda r: int(r.preferred_side_num) == int(r.current_side),
    "FAIR80_CURRENT": lambda r: r.preferred_fair >= .80 and int(r.preferred_side_num) == int(r.current_side),
    "FAIR80_EDGE10": lambda r: r.preferred_fair >= .80 and r.edge >= .10,
    "FAIR80_GAP35": lambda r: r.preferred_fair >= .80 and r.abs_dist_target >= 35.0,
    "FAIR80_CURRENT_EDGE10": lambda r: r.preferred_fair >= .80 and int(r.preferred_side_num) == int(r.current_side) and r.edge >= .10,
    "FAIR85_CURRENT": lambda r: r.preferred_fair >= .85 and int(r.preferred_side_num) == int(r.current_side),
}


def pct(v):
    return "—" if pd.isna(v) else f"{100*float(v):.1f}%"


def cents(v):
    return "—" if pd.isna(v) else f"{100*float(v):.1f}c"


def mins(v):
    return "—" if pd.isna(v) else f"{float(v):.2f}m"


def load_cache(path: str) -> pd.DataFrame:
    d = pd.read_csv(path, low_memory=False)
    need = {
        "ticker","snapshot_utc","elapsed","remaining","current_side",
        "abs_dist_target","final_side","preferred_side_num","preferred_side",
        "preferred_fair","preferred_ask","preferred_bid","edge",
    }
    missing = sorted(need - set(d.columns))
    if missing:
        raise SystemExit(f"Missing required columns: {missing}")
    d["snapshot_utc"] = pd.to_datetime(d["snapshot_utc"], utc=True, errors="coerce")
    for c in NUMERIC:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=list(need)).copy()
    d["ticker"] = d["ticker"].astype(str)
    d["preferred_side"] = d["preferred_side"].astype(str).str.upper()
    return d.sort_values(["ticker","snapshot_utc","elapsed"]).reset_index(drop=True)


def tier1_mask(d: pd.DataFrame) -> pd.Series:
    return (
        (d.preferred_ask <= .45)
        & (d.preferred_fair >= .75)
        & (d.edge >= .08)
        & d.remaining.between(2.0, 10.0, inclusive="both")
        & (d.abs_dist_target >= 25.0)
    )


def first_tier1_rows(d: pd.DataFrame) -> pd.DataFrame:
    q = d[tier1_mask(d)].copy()
    if q.empty:
        return q
    return q.sort_values(["ticker","snapshot_utc"]).drop_duplicates("ticker", keep="first")


def chrono_halves(d: pd.DataFrame) -> tuple[set[str], set[str]]:
    contracts = (
        d[["ticker","snapshot_utc"]]
        .groupby("ticker", as_index=False).snapshot_utc.min()
        .sort_values("snapshot_utc")
        .reset_index(drop=True)
    )
    mid = len(contracts)//2
    return set(contracts.iloc[:mid].ticker), set(contracts.iloc[mid:].ticker)


def score(calls: pd.DataFrame, universe: int) -> dict:
    if calls.empty:
        return {
            "calls":0,"coverage":0.0,"accuracy":np.nan,"avg_ask":np.nan,
            "median_ask":np.nan,"avg_time":np.nan,"median_time":np.nan,
            "up":0,"down":0,
        }
    correct = calls.preferred_side_num.astype(int) == calls.final_side.astype(int)
    return {
        "calls":int(len(calls)),
        "coverage":float(len(calls)/max(universe,1)),
        "accuracy":float(correct.mean()),
        "avg_ask":float(calls.preferred_ask.mean()),
        "median_ask":float(calls.preferred_ask.median()),
        "avg_time":float(calls.remaining.mean()),
        "median_time":float(calls.remaining.median()),
        "up":int((calls.preferred_side.str.upper()=="UP").sum()),
        "down":int((calls.preferred_side.str.upper()=="DOWN").sum()),
    }


def same_row_calls(base: pd.DataFrame, rule_name: str) -> pd.DataFrame:
    fn = SAME_ROW_RULES[rule_name]
    keep = [bool(fn(r)) for r in base.itertuples(index=False)]
    return base.loc[keep].copy()


def confirmation_calls(d: pd.DataFrame, base: pd.DataFrame, strengthening: bool) -> pd.DataFrame:
    by = {t:g.sort_values("snapshot_utc") for t,g in d.groupby("ticker", sort=False)}
    out=[]
    for _, b in base.iterrows():
        g = by.get(b.ticker)
        if g is None:
            continue
        dt = (g.snapshot_utc - b.snapshot_utc).dt.total_seconds()
        later = g[(dt >= 30.0) & (dt <= 90.0)].copy()
        if later.empty:
            continue
        later = later.sort_values("snapshot_utc")
        for _, r in later.iterrows():
            if not bool(tier1_mask(pd.DataFrame([r])).iloc[0]):
                continue
            if int(r.preferred_side_num) != int(b.preferred_side_num):
                continue
            if strengthening:
                if float(r.preferred_fair) < float(b.preferred_fair):
                    continue
                if float(r.edge) < float(b.edge):
                    continue
            rr = r.copy()
            rr["initial_snapshot_utc"] = b.snapshot_utc
            rr["initial_ask"] = b.preferred_ask
            rr["initial_fair"] = b.preferred_fair
            rr["confirmation_delay_sec"] = float((r.snapshot_utc-b.snapshot_utc).total_seconds())
            out.append(rr)
            break
    if not out:
        return d.iloc[0:0].copy()
    return pd.DataFrame(out).reset_index(drop=True)


def add_metrics(row: dict, prefix: str, stats: dict) -> None:
    for k,v in stats.items():
        row[f"{prefix}_{k}"] = v


def gate(row: pd.Series) -> bool:
    return bool(
        row.all_calls >= 15
        and row.h1_calls >= 6
        and row.h2_calls >= 6
        and row.all_accuracy >= .93
        and row.h1_accuracy >= .90
        and row.h2_accuracy >= .90
        and row.all_avg_ask <= .45
        and row.all_median_ask <= .45
        and row.all_avg_time >= 5.0
    )


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--cache",default=DEFAULT_CACHE)
    ap.add_argument("--rules-out",default=DEFAULT_RULES)
    ap.add_argument("--calls-out",default=DEFAULT_CALLS)
    ap.add_argument("--report-out",default=DEFAULT_REPORT)
    args=ap.parse_args()

    d=load_cache(args.cache)
    base=first_tier1_rows(d)
    h1,h2=chrono_halves(d)
    universe=d.ticker.nunique()
    u1=len(h1);u2=len(h2)

    candidates={"TIER1_BASELINE_REFERENCE":base}
    for name in SAME_ROW_RULES:
        candidates[name]=same_row_calls(base,name)
    candidates["PERSIST_30_90"]=confirmation_calls(d,base,False)
    candidates["STRENGTHEN_30_90"]=confirmation_calls(d,base,True)

    rows=[]
    calls_out=[]
    for name,calls in candidates.items():
        calls=calls.sort_values(["ticker","snapshot_utc"]).copy()
        s_all=score(calls,universe)
        c1=calls[calls.ticker.isin(h1)].copy()
        c2=calls[calls.ticker.isin(h2)].copy()
        s1=score(c1,u1);s2=score(c2,u2)
        row={"rule":name,"eligible_for_selection":name!="TIER1_BASELINE_REFERENCE"}
        add_metrics(row,"all",s_all);add_metrics(row,"h1",s1);add_metrics(row,"h2",s2)
        rows.append(row)
        if not calls.empty:
            z=calls.copy();z.insert(0,"rule",name);calls_out.append(z)

    rules=pd.DataFrame(rows)
    rules["historical_gate_pass"]=rules.apply(
        lambda r: bool(r.eligible_for_selection and gate(r)),axis=1
    )
    eligible=rules[rules.historical_gate_pass].copy()
    if eligible.empty:
        winner=None
    else:
        eligible=eligible.sort_values(
            ["all_calls","all_accuracy","all_avg_ask","all_avg_time"],
            ascending=[False,False,True,False],
        ).reset_index(drop=True)
        winner=str(eligible.iloc[0].rule)

    rules=rules.sort_values(
        ["historical_gate_pass","all_calls","all_accuracy"],
        ascending=[False,False,False],
    )
    rules.to_csv(args.rules_out,index=False)
    if calls_out:
        pd.concat(calls_out,ignore_index=True).to_csv(args.calls_out,index=False)
    else:
        pd.DataFrame().to_csv(args.calls_out,index=False)

    b=rules[rules.rule.eq("TIER1_BASELINE_REFERENCE")].iloc[0]
    lines=[]
    lines.append("="*100)
    lines.append("BTC15 EARLY HIGH-CONFIDENCE SCORER V1 | HISTORICAL RESEARCH | SIGNAL ONLY | NO ORDERS")
    lines.append("="*100)
    lines.append(f"rows={len(d):,} contracts={universe} protected_tier1_calls={int(b.all_calls)}")
    lines.append("Existing cache is DEVELOPMENT/RESEARCH for this phase; fresh forward confirmation is mandatory.")
    lines.append("")
    lines.append("PROTECTED TIER-1 REFERENCE — UNCHANGED")
    lines.append(
        f"  ALL calls={int(b.all_calls)} accuracy={pct(b.all_accuracy)} coverage={pct(b.all_coverage)} "
        f"avg_ask={cents(b.all_avg_ask)} median_ask={cents(b.all_median_ask)} avg_time={mins(b.all_avg_time)}"
    )
    lines.append(
        f"  H1 calls={int(b.h1_calls)} accuracy={pct(b.h1_accuracy)} | "
        f"H2 calls={int(b.h2_calls)} accuracy={pct(b.h2_accuracy)}"
    )
    lines.append("")
    lines.append("FROZEN CANDIDATE SCORECARD")
    for _,r in rules[rules.rule.ne("TIER1_BASELINE_REFERENCE")].iterrows():
        lines.append(
            f"  {r.rule}: calls={int(r.all_calls)} acc={pct(r.all_accuracy)} "
            f"H1={int(r.h1_calls)}/{pct(r.h1_accuracy)} H2={int(r.h2_calls)}/{pct(r.h2_accuracy)} "
            f"ask={cents(r.all_avg_ask)} time={mins(r.all_avg_time)} "
            f"gate={'PASS' if r.historical_gate_pass else 'FAIL'}"
        )
    lines.append("")
    lines.append("SELECTION")
    if winner is None:
        lines.append("  NO CANDIDATE PASSED THE PRE-FROZEN HISTORICAL GATE.")
        lines.append("  SCRATCH higher-confidence sub-tier V1; keep protected Tier-1 unchanged.")
    else:
        w=rules[rules.rule.eq(winner)].iloc[0]
        lines.append(f"  HISTORICAL FORWARD-TEST CANDIDATE: {winner}")
        lines.append(
            f"  calls={int(w.all_calls)} accuracy={pct(w.all_accuracy)} avg_ask={cents(w.all_avg_ask)} "
            f"median_ask={cents(w.all_median_ask)} avg_time={mins(w.all_avg_time)}"
        )
        lines.append(
            f"  H1 calls={int(w.h1_calls)} accuracy={pct(w.h1_accuracy)} | "
            f"H2 calls={int(w.h2_calls)} accuracy={pct(w.h2_accuracy)}"
        )
        lines.append("  Historical PASS earns forward testing only, NOT live promotion.")
    lines.append("")
    lines.append("GUARDRAILS")
    lines.append("- Protected Tier-1 is not changed, weakened, or replaced.")
    lines.append("- V1 tests only the candidate families frozen before this run.")
    lines.append("- No candidate may create a call outside protected Tier-1 qualification.")
    lines.append("- No ask above 45c is permitted.")
    lines.append("- Fresh forward confirmation is mandatory for any selected candidate.")
    lines.append("- No orders.")
    text="\n".join(lines)+"\n"
    Path(args.report_out).write_text(text,encoding="utf-8")
    print(text,end="")
    print(f"WROTE {args.rules_out}")
    print(f"WROTE {args.calls_out}")
    print(f"WROTE {args.report_out}")


if __name__=="__main__":
    main()
