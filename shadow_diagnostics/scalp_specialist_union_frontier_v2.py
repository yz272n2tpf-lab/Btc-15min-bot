#!/usr/bin/env python3
"""BTC15 scalp specialist-union frontier V2.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

V2 preserves V1's four specialist lanes and true full-contract denominator,
but changes one coverage detail deliberately:

* CORE remains specialist-only.
* If a fully observed contract has no CORE selection, COVERAGE_RESCUE may use
  the single highest-quality baseline scalp candidate from that contract even
  when that candidate is UNCLASSIFIED by the four specialist lanes.
* Rescue still requires the validation-frozen probability threshold. It never
  forces a signal into a contract with no candidate or insufficient quality.
* Validation selects thresholds; HOLDOUT is report-only.

This lets us protect contract coverage without weakening the specialist core or
pretending that quiet/no-candidate contracts are covered.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_frontier_v1 as v1

VERSION = "BTC15_SCALP_SPECIALIST_UNION_FRONTIER_V2"
TARGET_CONTRACT_COVERAGE = v1.TARGET_CONTRACT_COVERAGE
TARGET_PLUS10 = v1.TARGET_PLUS10
STRETCH_PLUS10 = v1.STRETCH_PLUS10


def finite(v: Any) -> float | None:
    return v1.finite(v)


def select_core_rescue(
    scored: list[dict[str, Any]],
    denominator_contracts: set[str],
    core_threshold: float,
    rescue_threshold: float,
) -> list[dict[str, Any]]:
    """Strict specialist CORE plus one best-candidate coverage rescue.

    CORE:
      every specialist opportunity with quality_prob >= core_threshold.

    COVERAGE_RESCUE:
      only when that contract has no CORE selection, choose the one baseline
      candidate with the highest quality probability. It may be specialist or
      unclassified, but must clear rescue_threshold.

    No baseline candidate => no rescue. Below threshold => no rescue.
    """
    all_rows = [r for r in scored if str(r.get("contract") or "") in denominator_contracts]
    by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in all_rows:
        by_contract[str(r["contract"])].append(r)

    selected: list[dict[str, Any]] = []
    for contract in denominator_contracts:
        rows = by_contract.get(contract, [])
        core = [
            r for r in rows
            if bool(r.get("specialist_union"))
            and finite(r.get("quality_prob")) is not None
            and float(r["quality_prob"]) >= core_threshold
        ]
        if core:
            for r in core:
                x = dict(r)
                x["selection_tier"] = "CORE"
                x["rescue_source_lane"] = None
                x["rescue_unclassified"] = False
                selected.append(x)
            continue

        ranked = [r for r in rows if finite(r.get("quality_prob")) is not None]
        if not ranked:
            continue
        best = max(ranked, key=lambda r: float(r["quality_prob"]))
        p = float(best["quality_prob"])
        if p < rescue_threshold:
            continue
        x = dict(best)
        x["selection_tier"] = "COVERAGE_RESCUE"
        lane = str(best.get("primary_lane") or "UNCLASSIFIED")
        x["rescue_source_lane"] = lane
        x["rescue_unclassified"] = not bool(best.get("specialist_union"))
        selected.append(x)
    return selected


def _rate(rows: list[dict[str, Any]], key: str, target: float) -> float | None:
    if not rows:
        return None
    return sum(q.label_value(r, key, target) for r in rows) / len(rows)


def tier_diagnostics(selected: list[dict[str, Any]], denominator_contracts: set[str]) -> dict[str, Any]:
    core = [r for r in selected if r.get("selection_tier") == "CORE"]
    rescue = [r for r in selected if r.get("selection_tier") == "COVERAGE_RESCUE"]
    unclassified = [r for r in rescue if r.get("rescue_unclassified")]
    specialist_rescue = [r for r in rescue if not r.get("rescue_unclassified")]
    core_contracts = {str(r.get("contract") or "") for r in core}
    rescue_contracts = {str(r.get("contract") or "") for r in rescue}
    denom = len(denominator_contracts)
    return {
        "core_n": len(core),
        "core_contracts": len(core_contracts),
        "core_true_contract_coverage": None if not denom else len(core_contracts) / denom,
        "core_plus10_rate": _rate(core, "plus10", .10),
        "coverage_rescue_n": len(rescue),
        "coverage_rescue_contracts": len(rescue_contracts),
        "coverage_gain_from_rescue": None if not denom else len(rescue_contracts - core_contracts) / denom,
        "coverage_rescue_plus10_rate": _rate(rescue, "plus10", .10),
        "unclassified_rescue_n": len(unclassified),
        "unclassified_rescue_contracts": len({str(r.get("contract") or "") for r in unclassified}),
        "unclassified_rescue_plus10_rate": _rate(unclassified, "plus10", .10),
        "specialist_rescue_n": len(specialist_rescue),
        "specialist_rescue_plus10_rate": _rate(specialist_rescue, "plus10", .10),
    }


def model_frontier(
    opps: list[dict[str, Any]],
    split: Mapping[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]]]:
    dev = [r for r in opps if split.get(r.get("contract")) == "DEVELOPMENT"]
    val = [r for r in opps if split.get(r.get("contract")) == "VALIDATION"]
    hold = [r for r in opps if split.get(r.get("contract")) == "HOLDOUT"]
    val_contracts = {c for c, s in split.items() if s == "VALIDATION"}
    hold_contracts = {c for c, s in split.items() if s == "HOLDOUT"}
    if min(len(dev), len(val), len(hold)) < 5 or not q.models() or not val_contracts or not hold_contracts:
        return [], None, None, []

    xd = q.to_frame(dev)
    xv = q.to_frame(val)
    xh = q.to_frame(hold)
    frontier: list[dict[str, Any]] = []
    fitted: dict[str, tuple[Any, np.ndarray]] = {}

    for name, model in q.models():
        try:
            model.fit(xd[q.FEATURES], xd["plus10"].astype(int))
            pv = model.predict_proba(xv[q.FEATURES])[:, 1]
            ph = model.predict_proba(xh[q.FEATURES])[:, 1]
            fitted[name] = (model, ph)
            scored_val: list[dict[str, Any]] = []
            for r, p in zip(val, pv):
                x = dict(r)
                x["quality_prob"] = float(p)
                scored_val.append(x)

            for core_th in (0.60, 0.70, 0.80, 0.85, 0.90, 0.95):
                for rescue_th in (0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80):
                    if rescue_th > core_th:
                        continue
                    selected = select_core_rescue(scored_val, val_contracts, core_th, rescue_th)
                    score = v1.score_with_true_coverage(selected, val_contracts)
                    tiers = tier_diagnostics(selected, val_contracts)
                    score.update(tiers)
                    score.update({
                        "model": name,
                        "core_threshold": core_th,
                        "rescue_threshold": rescue_th,
                        "coverage_floor_met": (score.get("true_contract_coverage") or 0.0) >= TARGET_CONTRACT_COVERAGE,
                        "plus10_target_met": (score.get("plus10_rate") or 0.0) >= TARGET_PLUS10,
                    })
                    frontier.append(score)
        except Exception as exc:
            frontier.append({"model": name, "error": f"{type(exc).__name__}:{exc}"})

    valid = [r for r in frontier if "error" not in r and r.get("coverage_floor_met")]
    if not valid:
        return frontier, None, None, []
    passing = [r for r in valid if r.get("plus10_target_met")]
    pool = passing if passing else valid
    winner = max(
        pool,
        key=lambda r: (
            r.get("plus10_rate") or 0.0,
            r.get("affordable_true_contract_coverage_le50") or 0.0,
            r.get("true_contract_coverage") or 0.0,
            r.get("coverage_rescue_plus10_rate") or 0.0,
            -(r.get("unclassified_rescue_n") or 0),
        ),
    )

    model, ph = fitted[winner["model"]]
    scored_hold: list[dict[str, Any]] = []
    for r, p in zip(hold, ph):
        x = dict(r)
        x["quality_prob"] = float(p)
        scored_hold.append(x)
    selected_hold = select_core_rescue(
        scored_hold,
        hold_contracts,
        float(winner["core_threshold"]),
        float(winner["rescue_threshold"]),
    )
    hold_score = v1.score_with_true_coverage(selected_hold, hold_contracts)
    hold_score.update(tier_diagnostics(selected_hold, hold_contracts))
    hold_score.update({
        "model": winner["model"],
        "core_threshold_frozen_from_validation": winner["core_threshold"],
        "rescue_threshold_frozen_from_validation": winner["rescue_threshold"],
        "coverage_floor_met": (hold_score.get("true_contract_coverage") or 0.0) >= TARGET_CONTRACT_COVERAGE,
        "plus10_target_met": (hold_score.get("plus10_rate") or 0.0) >= TARGET_PLUS10,
        "holdout_is_report_only": True,
    })
    return frontier, winner, hold_score, selected_hold


def clean(v: Any) -> Any:
    return v1.clean(v)


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
    ap.add_argument("--outdir", default="shadow_specialist_union_v2_out")
    args = ap.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    rows = q.read_rows(Path(args.csv))
    universe = v1.full_contract_universe(rows)
    if not universe:
        report = {
            "version": VERSION,
            "orders": False,
            "status": "FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE",
            "promotion": False,
        }
        (outdir / "scalp_specialist_union_v2_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    split = v1.split_universe(universe)
    universe_contracts = set(universe)
    opps = [r for r in q.build_serial_opportunities(rows) if r.get("contract") in universe_contracts]
    for r in opps:
        r["split"] = split.get(r.get("contract"), "")

    dev = [r for r in opps if r.get("split") == "DEVELOPMENT"]
    cuts = v1.calibrate_lane_cuts(dev)
    v1.lane_tags(opps, cuts)

    baseline = v1.score_with_true_coverage(opps, universe_contracts)
    lanes = v1.lane_breakdown(opps, universe_contracts)
    frontier, winner, holdout, selected_holdout = model_frontier(opps, split)

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
        "lane_breakdown": lanes,
        "validation_selected_candidate": winner,
        "untouched_holdout_result": holdout,
        "acceptance_markers": {
            "target_true_contract_coverage": TARGET_CONTRACT_COVERAGE,
            "target_plus10_rate": TARGET_PLUS10,
            "stretch_plus10_rate": STRETCH_PLUS10,
            "core_is_specialist_only": True,
            "rescue_can_use_unclassified_baseline_candidate": True,
            "rescue_is_single_best_candidate_per_uncovered_contract": True,
            "quiet_contracts_still_count_against_coverage": True,
            "holdout_never_selects_threshold": True,
            "automatic_promotion": False,
        },
    }

    write_csv(outdir / "scalp_specialist_union_v2_validation_frontier.csv", frontier)
    write_csv(outdir / "scalp_specialist_union_v2_holdout_selected.csv", selected_holdout)
    (outdir / "scalp_specialist_union_v2_report.json").write_text(
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
