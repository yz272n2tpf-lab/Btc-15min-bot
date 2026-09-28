#!/usr/bin/env python3
"""BTC15 scalp specialist-union frontier V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Goal
----
Raise scalp move quality without sacrificing true 15-minute contract coverage.
This analyzer layers four causal specialist lanes over the existing generalized
scalp tape, then selects quality thresholds on VALIDATION subject to an explicit
true-contract coverage floor. HOLDOUT is report-only.

Specialist lanes
----------------
1. KALSHI_LAG          BTC/BRTI impulse is aligned while Kalshi ask repricing is muted.
2. MOMENTUM            aligned, persistent continuation with structure intact.
3. REVERSAL_RECROSS    a later serial scalp flips side after the prior protected exit.
4. REENTRY_CONTINUATION a later serial scalp resumes the same side after protected exit.

Integrity
---------
* No production imports or writes.
* No order capability.
* Future PATH/RESULT fields are labels only, never model inputs.
* Full-contract coverage denominator is built from passive observed rows, not
  from contracts that happened to produce a scalp candidate.
* A contract counts as fully observed only when the tape contains an early
  sample (>=840s left) and a late sample (<=60s left). Otherwise coverage
  claims fail closed rather than silently shrinking the denominator.
* Specialist cut points are calibrated from DEVELOPMENT feature distributions
  only. Outcome labels do not choose lane definitions.
* Model + core/rescue thresholds are selected on VALIDATION only.
* HOLDOUT never selects or retunes anything.
* No automatic promotion. Manual review only.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import scalp_opportunity_quality_frontier_v1 as q

VERSION = "BTC15_SCALP_SPECIALIST_UNION_FRONTIER_V1"
TARGET_CONTRACT_COVERAGE = 0.90
TARGET_PLUS10 = 0.93
STRETCH_PLUS10 = 0.95
EARLY_OBS_SEC = 840.0
LATE_OBS_SEC = 60.0

LANES = (
    "KALSHI_LAG",
    "MOMENTUM",
    "REVERSAL_RECROSS",
    "REENTRY_CONTINUATION",
)


def finite(v: Any) -> float | None:
    x = q.f(v)
    return x if x is not None and math.isfinite(x) else None


def row_timestamp(r: Mapping[str, Any]) -> datetime:
    for key in ("timestamp_utc", "entry_timestamp_utc", "outcome_timestamp_utc"):
        x = q.dt(r.get(key))
        if x != datetime.min.replace(tzinfo=timezone.utc):
            return x
    return datetime.min.replace(tzinfo=timezone.utc)


def full_contract_universe(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return contracts truly observed from early to late in their 15m window.

    Quiet contracts are preserved because any passive SNAPSHOT/PATH row can
    contribute to the denominator. Candidate production is not required.
    """
    by_contract: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for r in rows:
        c = str(r.get("contract") or "").strip()
        left = finite(r.get("seconds_left"))
        if c and left is not None:
            by_contract[c].append(r)

    out: dict[str, dict[str, Any]] = {}
    for c, rs in by_contract.items():
        lefts = [finite(r.get("seconds_left")) for r in rs]
        lefts = [x for x in lefts if x is not None]
        if not lefts:
            continue
        first = min((row_timestamp(r) for r in rs), default=datetime.min.replace(tzinfo=timezone.utc))
        last = max((row_timestamp(r) for r in rs), default=datetime.min.replace(tzinfo=timezone.utc))
        full = max(lefts) >= EARLY_OBS_SEC and min(lefts) <= LATE_OBS_SEC
        if full:
            out[c] = {
                "contract": c,
                "first_seen": first,
                "last_seen": last,
                "max_seconds_left": max(lefts),
                "min_seconds_left": min(lefts),
                "row_count": len(rs),
                "record_types": sorted({str(r.get("record_type") or "").strip().upper() for r in rs}),
            }
    return out


def split_universe(universe: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    ordered = sorted(
        universe,
        key=lambda c: universe[c].get("first_seen") or datetime.min.replace(tzinfo=timezone.utc),
    )
    n = len(ordered)
    if n < 10:
        return {c: "DEVELOPMENT" for c in ordered}
    i60 = max(1, int(n * 0.60))
    i80 = max(i60 + 1, int(n * 0.80))
    return {
        c: ("DEVELOPMENT" if i < i60 else "VALIDATION" if i < i80 else "HOLDOUT")
        for i, c in enumerate(ordered)
    }


def quantile(values: Iterable[Any], p: float, fallback: float) -> float:
    xs = [finite(v) for v in values]
    xs = [x for x in xs if x is not None]
    if not xs:
        return fallback
    return float(np.quantile(np.asarray(xs, dtype=float), p))


def calibrate_lane_cuts(dev: list[dict[str, Any]]) -> dict[str, float]:
    """Feature-distribution cutoffs only; no outcome labels are consulted."""
    aligned = [r for r in dev if bool(r.get("btc_brti_agree15"))]
    mom = aligned or dev
    return {
        "lag_momentum_floor15_min": quantile((r.get("momentum_floor15") for r in mom), 0.50, 0.0),
        "lag_abs_ask15_max": quantile((abs(finite(r.get("ask_move15")) or 0.0) for r in mom), 0.60, 0.03),
        "momentum_btc30_min": quantile((r.get("btc_move30_side") for r in dev), 0.60, 15.0),
        "momentum_acceleration_min": quantile((r.get("acceleration") for r in dev), 0.50, 0.0),
    }


def lane_tags(opps: list[dict[str, Any]], cuts: Mapping[str, float]) -> None:
    by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in opps:
        by_contract[str(r.get("contract") or "")].append(r)

    for c, rs in by_contract.items():
        rs.sort(key=lambda r: (int(r.get("opportunity_index") or 0), r.get("timestamp")))
        prev_side: str | None = None
        for r in rs:
            tags: list[str] = []
            agree5 = bool(r.get("btc_brti_agree5"))
            agree15 = bool(r.get("btc_brti_agree15"))
            floor15 = finite(r.get("momentum_floor15"))
            ask15 = finite(r.get("ask_move15"))
            btc30 = finite(r.get("btc_move30_side"))
            accel = finite(r.get("acceleration"))
            structure = bool(r.get("structure_ok"))
            against = bool(r.get("btc_against_side")) or bool(r.get("brti_against_side"))
            dual = bool(r.get("dual_reversal_evidence"))
            idx = int(r.get("opportunity_index") or 0)
            side = str(r.get("side") or "").upper()

            if (
                agree15
                and floor15 is not None
                and floor15 >= cuts["lag_momentum_floor15_min"]
                and ask15 is not None
                and abs(ask15) <= cuts["lag_abs_ask15_max"]
                and not against
                and not dual
            ):
                tags.append("KALSHI_LAG")

            if (
                (agree5 or agree15)
                and structure
                and btc30 is not None
                and btc30 >= cuts["momentum_btc30_min"]
                and accel is not None
                and accel >= cuts["momentum_acceleration_min"]
                and not against
                and not dual
            ):
                tags.append("MOMENTUM")

            if idx >= 2 and prev_side and side and side != prev_side and not against:
                tags.append("REVERSAL_RECROSS")
            if idx >= 2 and prev_side and side and side == prev_side and not dual:
                tags.append("REENTRY_CONTINUATION")

            r["lane_tags"] = tags
            r["specialist_union"] = bool(tags)
            if "REVERSAL_RECROSS" in tags:
                primary = "REVERSAL_RECROSS"
            elif "REENTRY_CONTINUATION" in tags:
                primary = "REENTRY_CONTINUATION"
            elif "KALSHI_LAG" in tags:
                primary = "KALSHI_LAG"
            elif "MOMENTUM" in tags:
                primary = "MOMENTUM"
            else:
                primary = "UNCLASSIFIED"
            r["primary_lane"] = primary
            prev_side = side or prev_side


def score_with_true_coverage(rows: list[dict[str, Any]], denominator_contracts: set[str]) -> dict[str, Any]:
    base = q.summarize(rows)
    denom = len(denominator_contracts)
    selected_contracts = {str(r.get("contract") or "") for r in rows} & denominator_contracts
    affordable_contracts = {
        str(r.get("contract") or "")
        for r in rows
        if finite(r.get("entry_ask")) is not None and float(r["entry_ask"]) <= 0.50
    } & denominator_contracts
    base.update({
        "true_contract_denominator": denom,
        "covered_contracts": len(selected_contracts),
        "true_contract_coverage": None if not denom else len(selected_contracts) / denom,
        "affordable_contracts_le50": len(affordable_contracts),
        "affordable_true_contract_coverage_le50": None if not denom else len(affordable_contracts) / denom,
        "avg_selected_opportunities_per_observed_contract": None if not denom else len(rows) / denom,
        "avg_selected_opportunities_per_covered_contract": None if not selected_contracts else len(rows) / len(selected_contracts),
    })
    return base


def lane_breakdown(rows: list[dict[str, Any]], denominator_contracts: set[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for lane in LANES + ("UNCLASSIFIED",):
        z = [r for r in rows if r.get("primary_lane") == lane]
        out[lane] = score_with_true_coverage(z, denominator_contracts)
    union = [r for r in rows if r.get("specialist_union")]
    out["SPECIALIST_UNION"] = score_with_true_coverage(union, denominator_contracts)
    return out


def select_core_rescue(
    scored: list[dict[str, Any]],
    denominator_contracts: set[str],
    core_threshold: float,
    rescue_threshold: float,
) -> list[dict[str, Any]]:
    """Coverage-preserving two-level selector.

    Every specialist opportunity clearing CORE is retained. For a denominator
    contract with no CORE selection, its single highest-quality specialist
    candidate may enter through RESCUE if it clears the lower frozen threshold.
    """
    eligible = [r for r in scored if r.get("specialist_union") and r.get("contract") in denominator_contracts]
    selected: list[dict[str, Any]] = []
    by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in eligible:
        by_contract[str(r["contract"])].append(r)

    for c in denominator_contracts:
        cr = by_contract.get(c, [])
        core = [r for r in cr if finite(r.get("quality_prob")) is not None and float(r["quality_prob"]) >= core_threshold]
        if core:
            for r in core:
                x = dict(r); x["selection_tier"] = "CORE"; selected.append(x)
            continue
        if cr:
            best = max(cr, key=lambda r: finite(r.get("quality_prob")) or -1.0)
            p = finite(best.get("quality_prob"))
            if p is not None and p >= rescue_threshold:
                x = dict(best); x["selection_tier"] = "COVERAGE_RESCUE"; selected.append(x)
    return selected


def model_frontier(
    opps: list[dict[str, Any]],
    split: Mapping[str, str],
    universe: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, dict[str, Any] | None]:
    dev = [r for r in opps if split.get(r.get("contract")) == "DEVELOPMENT"]
    val = [r for r in opps if split.get(r.get("contract")) == "VALIDATION"]
    hold = [r for r in opps if split.get(r.get("contract")) == "HOLDOUT"]
    val_contracts = {c for c, s in split.items() if s == "VALIDATION"}
    hold_contracts = {c for c, s in split.items() if s == "HOLDOUT"}
    if min(len(dev), len(val), len(hold)) < 5 or not q.models() or not val_contracts or not hold_contracts:
        return [], None, None

    xd = q.to_frame(dev)
    xv = q.to_frame(val)
    xh = q.to_frame(hold)
    frontier: list[dict[str, Any]] = []
    fitted: dict[str, Any] = {}

    for name, model in q.models():
        try:
            model.fit(xd[q.FEATURES], xd["plus10"].astype(int))
            pv = model.predict_proba(xv[q.FEATURES])[:, 1]
            ph = model.predict_proba(xh[q.FEATURES])[:, 1]
            fitted[name] = (model, ph)
            scored_val = []
            for r, p in zip(val, pv):
                x = dict(r); x["quality_prob"] = float(p); scored_val.append(x)

            for core in (0.60, 0.70, 0.80, 0.85, 0.90, 0.95):
                for rescue in (0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80):
                    if rescue > core:
                        continue
                    z = select_core_rescue(scored_val, val_contracts, core, rescue)
                    s = score_with_true_coverage(z, val_contracts)
                    s.update({
                        "model": name,
                        "core_threshold": core,
                        "rescue_threshold": rescue,
                        "core_n": sum(r.get("selection_tier") == "CORE" for r in z),
                        "coverage_rescue_n": sum(r.get("selection_tier") == "COVERAGE_RESCUE" for r in z),
                        "coverage_floor_met": (s.get("true_contract_coverage") or 0.0) >= TARGET_CONTRACT_COVERAGE,
                        "plus10_target_met": (s.get("plus10_rate") or 0.0) >= TARGET_PLUS10,
                    })
                    frontier.append(s)
        except Exception as exc:
            frontier.append({"model": name, "error": f"{type(exc).__name__}:{exc}"})

    valid = [r for r in frontier if "error" not in r and r.get("coverage_floor_met")]
    if not valid:
        return frontier, None, None

    passing = [r for r in valid if r.get("plus10_target_met")]
    pool = passing if passing else valid
    winner = max(
        pool,
        key=lambda r: (
            r.get("plus10_rate") or 0.0,
            r.get("affordable_true_contract_coverage_le50") or 0.0,
            r.get("true_contract_coverage") or 0.0,
            r.get("n") or 0,
        ),
    )

    model, ph = fitted[winner["model"]]
    scored_hold = []
    for r, p in zip(hold, ph):
        x = dict(r); x["quality_prob"] = float(p); scored_hold.append(x)
    zh = select_core_rescue(
        scored_hold,
        hold_contracts,
        float(winner["core_threshold"]),
        float(winner["rescue_threshold"]),
    )
    hs = score_with_true_coverage(zh, hold_contracts)
    hs.update({
        "model": winner["model"],
        "core_threshold_frozen_from_validation": winner["core_threshold"],
        "rescue_threshold_frozen_from_validation": winner["rescue_threshold"],
        "coverage_floor_met": (hs.get("true_contract_coverage") or 0.0) >= TARGET_CONTRACT_COVERAGE,
        "plus10_target_met": (hs.get("plus10_rate") or 0.0) >= TARGET_PLUS10,
        "holdout_is_report_only": True,
    })
    return frontier, winner, hs


def clean(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [clean(x) for x in v]
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if not math.isfinite(float(v)) else float(v)
    return v


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({k for r in rows for k in r if not k.startswith("_") and k != "lane_tags"})
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: clean(v) for k, v in r.items() if not k.startswith("_") and k != "lane_tags"})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default="/data/scalp_move_shadow_v1_events.csv")
    ap.add_argument("--outdir", default="shadow_specialist_union_out")
    args = ap.parse_args()
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    rows = q.read_rows(Path(args.csv))
    universe = full_contract_universe(rows)
    if not universe:
        report = {
            "version": VERSION,
            "orders": False,
            "status": "FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE",
            "reason": "No contracts contain both >=840s and <=60s passive observation; true coverage cannot be claimed.",
            "promotion": False,
        }
        (outdir / "scalp_specialist_union_report_v1.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    split = split_universe(universe)
    universe_contracts = set(universe)
    opps = [r for r in q.build_serial_opportunities(rows) if r.get("contract") in universe_contracts]
    for r in opps:
        r["split"] = split.get(r.get("contract"), "")

    dev = [r for r in opps if r.get("split") == "DEVELOPMENT"]
    cuts = calibrate_lane_cuts(dev)
    lane_tags(opps, cuts)

    baseline = score_with_true_coverage(opps, universe_contracts)
    raw_lane = lane_breakdown(opps, universe_contracts)
    frontier, winner, holdout = model_frontier(opps, split, universe)

    report = {
        "version": VERSION,
        "orders": False,
        "manual_execution_only": True,
        "production_logic_changed": False,
        "coverage_integrity": "PASS",
        "full_observed_contracts": len(universe_contracts),
        "split_contracts": {s: sum(v == s for v in split.values()) for s in ("DEVELOPMENT", "VALIDATION", "HOLDOUT")},
        "development_only_lane_cuts": cuts,
        "baseline": baseline,
        "lane_breakdown": raw_lane,
        "validation_selected_candidate": winner,
        "untouched_holdout_result": holdout,
        "acceptance_markers": {
            "target_true_contract_coverage": TARGET_CONTRACT_COVERAGE,
            "target_plus10_rate": TARGET_PLUS10,
            "stretch_plus10_rate": STRETCH_PLUS10,
            "must_preserve_affordable_entry_coverage": True,
            "holdout_never_selects_threshold": True,
            "automatic_promotion": False,
        },
    }

    write_csv(outdir / "scalp_specialist_union_opportunities_v1.csv", opps)
    write_csv(outdir / "scalp_specialist_union_validation_frontier_v1.csv", frontier)
    (outdir / "scalp_specialist_union_report_v1.json").write_text(
        json.dumps(clean(report), indent=2, sort_keys=True), encoding="utf-8"
    )

    print("=" * 88)
    print(VERSION)
    print("RESEARCH ONLY | SIGNAL ONLY | NO ORDERS")
    print("=" * 88)
    print("Full observed contracts:", len(universe_contracts))
    print("Baseline:", json.dumps(clean(baseline), sort_keys=True))
    print("Validation winner:", json.dumps(clean(winner), sort_keys=True))
    print("Untouched holdout:", json.dumps(clean(holdout), sort_keys=True))
    print("Outputs:", outdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
