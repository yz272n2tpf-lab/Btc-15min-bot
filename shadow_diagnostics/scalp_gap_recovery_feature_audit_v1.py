#!/usr/bin/env python3
"""BTC15 missed-contract gap-recovery feature audit V1.

RESEARCH ONLY | DESCRIPTIVE ONLY | SIGNAL ONLY | NO ORDERS

For raw-baseline uncovered contracts that still contain complete candidate paths,
compare candidate-time causal features for paths that later reached executable
+10c versus those that did not. This tool does NOT select a threshold, train a
production model, or promote a rule. The entire source tape is already observed,
so any insight here is development-only and must be frozen before a new forward
window.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import scalp_baseline_coverage_gap_audit_v1 as gap
import scalp_event_schema_adapter_v1 as adapter
import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_frontier_v1 as union

VERSION = "BTC15_SCALP_GAP_RECOVERY_FEATURE_AUDIT_V1"
FEATURES = [
    "entry_ask", "spread", "seconds_left",
    "btc_move5_side", "btc_move15_side", "btc_move30_side",
    "brti_move5_side", "brti_move15_side",
    "ask_move5", "ask_move15", "acceleration", "confirm_count",
    "recent_range60", "btc_move5_norm", "btc_move15_norm",
    "brti_latency_sec", "structure_ok", "btc_against_side",
    "brti_against_side", "dual_reversal_evidence", "brti_primary_ok",
    "btc_brti_agree5", "btc_brti_agree15", "momentum_floor15",
    "market_response_abs15", "minutes_left",
]


def typ(r: Mapping[str, Any]) -> str:
    return str(r.get("record_type") or "").strip().upper()


def cid(r: Mapping[str, Any]) -> str:
    return str(r.get("candidate_id") or "").strip()


def contract(r: Mapping[str, Any]) -> str:
    return str(r.get("contract") or "").strip()


def finite(v: Any) -> float | None:
    return union.finite(v)


def feature_summary(rows: list[Mapping[str, Any]], feature: str) -> dict[str, Any]:
    vals = [finite(r.get(feature)) for r in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0, "median": None, "mean": None, "q25": None, "q75": None}
    ordered = sorted(vals)
    def quantile(p: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        pos = (len(ordered) - 1) * p
        lo = int(math.floor(pos)); hi = int(math.ceil(pos))
        if lo == hi:
            return ordered[lo]
        frac = pos - lo
        return ordered[lo] * (1 - frac) + ordered[hi] * frac
    return {
        "n": len(vals),
        "median": statistics.median(vals),
        "mean": statistics.fmean(vals),
        "q25": quantile(.25),
        "q75": quantile(.75),
    }


def candidate_rows(rows: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    adapted = adapter.adapt_rows(rows)
    base = gap.audit(adapted)
    if "summary" not in base:
        return [], base

    reason_by_contract = {str(r["contract"]): str(r["reason"]) for r in base["ledger"]}
    uncovered = set(reason_by_contract)
    paths_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    results: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for row in adapted:
        t = typ(row)
        if t == "PATH" and cid(row):
            paths_by_id[cid(row)].append(dict(row))
        elif t == "RESULT" and cid(row):
            results.add(cid(row))
        elif t == "CANDIDATE" and contract(row) in uncovered and cid(row):
            candidates.append(dict(row))

    out: list[dict[str, Any]] = []
    for cand in candidates:
        candidate_id = cid(cand)
        if candidate_id not in results or not paths_by_id.get(candidate_id):
            continue
        outcome = q.measure_path(cand, paths_by_id[candidate_id])
        peak = finite(outcome.peak_gain)
        if peak is None:
            continue
        features = q.candidate_features(cand)
        left = finite(cand.get("seconds_left"))
        ask = finite(cand.get("entry_ask"))
        rec: dict[str, Any] = {
            "contract": contract(cand),
            "candidate_id": candidate_id,
            "gap_reason": reason_by_contract.get(contract(cand)),
            "baseline_qualified": q.baseline_qualified(cand),
            "plus5": peak >= .05,
            "plus10": peak >= .10,
            "plus20": peak >= .20,
            "peak_gain": peak,
            "early_ge120s": left is not None and left >= q.MIN_SECONDS_LEFT,
            "affordable_le50": ask is not None and ask <= .50,
            "early_affordable": left is not None and left >= q.MIN_SECONDS_LEFT and ask is not None and ask <= .50,
        }
        rec.update(features)
        out.append(rec)
    return out, base


def group_summary(rows: list[dict[str, Any]], contract_denominator: int) -> dict[str, Any]:
    contracts = {str(r.get("contract") or "") for r in rows}
    plus10_contracts = {str(r.get("contract") or "") for r in rows if r.get("plus10")}
    early_affordable_plus10 = {
        str(r.get("contract") or "") for r in rows
        if r.get("plus10") and r.get("early_affordable")
    }
    return {
        "candidate_paths": len(rows),
        "contracts": len(contracts),
        "candidate_path_plus10_rate": None if not rows else sum(bool(r.get("plus10")) for r in rows) / len(rows),
        "contracts_with_plus10": len(plus10_contracts),
        "contracts_with_early_affordable_plus10": len(early_affordable_plus10),
        "incremental_contract_coverage_ceiling_if_all_plus10_were_causally_detectable": (
            None if not contract_denominator else len(plus10_contracts) / contract_denominator
        ),
        "feature_summary_plus10": {
            feature: feature_summary([r for r in rows if r.get("plus10")], feature)
            for feature in FEATURES
        },
        "feature_summary_nonplus10": {
            feature: feature_summary([r for r in rows if not r.get("plus10")], feature)
            for feature in FEATURES
        },
    }


def analyze(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    measured, base = candidate_rows(rows)
    if "summary" not in base:
        return {
            "version": VERSION,
            "status": "FAIL_CLOSED_BASELINE_GAP_AUDIT_UNAVAILABLE",
            "orders": False,
            "automatic_promotion": False,
            "baseline_gap": base,
        }
    denom = int(base["summary"]["full_observed_contracts"])
    reasons = sorted(set(str(r.get("gap_reason") or "") for r in measured))
    by_reason = {
        reason: group_summary([r for r in measured if r.get("gap_reason") == reason], denom)
        for reason in reasons
    }
    all_summary = group_summary(measured, denom)
    plus10_rows = [r for r in measured if r.get("plus10")]
    non_rows = [r for r in measured if not r.get("plus10")]

    # Rank features by normalized median separation for descriptive inspection only.
    separations: list[dict[str, Any]] = []
    for feature in FEATURES:
        a = feature_summary(plus10_rows, feature)
        b = feature_summary(non_rows, feature)
        if a["median"] is None or b["median"] is None:
            continue
        pooled = [finite(r.get(feature)) for r in measured]
        pooled = [x for x in pooled if x is not None]
        scale = statistics.pstdev(pooled) if len(pooled) >= 2 else 0.0
        raw = a["median"] - b["median"]
        separations.append({
            "feature": feature,
            "plus10_median": a["median"],
            "nonplus10_median": b["median"],
            "raw_median_difference": raw,
            "normalized_median_difference": None if scale <= 0 else raw / scale,
            "descriptive_only": True,
        })
    separations.sort(key=lambda r: abs(r["normalized_median_difference"] or 0.0), reverse=True)

    return {
        "version": VERSION,
        "status": "READY",
        "orders": False,
        "manual_execution_only": True,
        "production_logic_changed": False,
        "full_observed_contracts": denom,
        "baseline_gap_summary": base["summary"],
        "complete_candidate_paths_in_uncovered_contracts": len(measured),
        "all_candidate_path_summary": all_summary,
        "by_gap_reason": by_reason,
        "descriptive_feature_separations": separations,
        "development_only": True,
        "hindsight_labels_used_for_description": True,
        "threshold_selection": False,
        "new_forward_window_required_before_any_promotion": True,
        "automatic_promotion": False,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({k for r in rows for k in r})
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default="/data/scalp_move_shadow_v1_events.csv")
    ap.add_argument("--outdir", default="shadow_gap_recovery_feature_out")
    args = ap.parse_args()
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    raw = q.read_rows(Path(args.csv))
    measured, _ = candidate_rows(raw)
    report = analyze(raw)
    write_csv(outdir / "scalp_gap_recovery_candidate_paths_v1.csv", measured)
    write_csv(outdir / "scalp_gap_recovery_feature_separations_v1.csv", report.get("descriptive_feature_separations", []))
    (outdir / "scalp_gap_recovery_feature_audit_v1.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "version": report.get("version"),
        "status": report.get("status"),
        "full_observed_contracts": report.get("full_observed_contracts"),
        "complete_candidate_paths_in_uncovered_contracts": report.get("complete_candidate_paths_in_uncovered_contracts"),
        "all_candidate_path_summary": report.get("all_candidate_path_summary"),
        "by_gap_reason": report.get("by_gap_reason"),
        "top_feature_separations": (report.get("descriptive_feature_separations") or [])[:10],
        "automatic_promotion": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
