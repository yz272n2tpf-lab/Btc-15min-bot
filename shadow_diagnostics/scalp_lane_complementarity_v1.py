#!/usr/bin/env python3
"""BTC15 scalp specialist-lane complementarity audit V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Reports whether the four specialist lanes cover genuinely different contracts
or mostly duplicate one another. All non-empty lane subsets are reported; this
tool does not choose a winner or promote a production rule.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_frontier_v1 as s

VERSION = "BTC15_SCALP_LANE_COMPLEMENTARITY_V1"


def lane_contract_sets(opps: list[dict[str, Any]], denominator: set[str]) -> dict[str, set[str]]:
    out = {lane: set() for lane in s.LANES}
    for r in opps:
        c = str(r.get("contract") or "")
        if c not in denominator:
            continue
        tags = set(r.get("lane_tags") or [])
        for lane in s.LANES:
            if lane in tags:
                out[lane].add(c)
    return out


def unique_lane_coverage(opps: list[dict[str, Any]], denominator: set[str]) -> list[dict[str, Any]]:
    sets = lane_contract_sets(opps, denominator)
    denom = len(denominator)
    out: list[dict[str, Any]] = []
    for lane in s.LANES:
        others: set[str] = set()
        for other in s.LANES:
            if other != lane:
                others |= sets[other]
        unique = sets[lane] - others
        out.append({
            "lane": lane,
            "covered_contracts": len(sets[lane]),
            "contract_coverage": None if not denom else len(sets[lane]) / denom,
            "unique_contracts": len(unique),
            "unique_contract_coverage": None if not denom else len(unique) / denom,
        })
    return out


def pairwise_overlap(opps: list[dict[str, Any]], denominator: set[str]) -> list[dict[str, Any]]:
    sets = lane_contract_sets(opps, denominator)
    out: list[dict[str, Any]] = []
    for a, b in itertools.combinations(s.LANES, 2):
        inter = sets[a] & sets[b]
        union = sets[a] | sets[b]
        out.append({
            "lane_a": a,
            "lane_b": b,
            "intersection_contracts": len(inter),
            "union_contracts": len(union),
            "jaccard_overlap": None if not union else len(inter) / len(union),
        })
    return out


def subset_frontier(opps: list[dict[str, Any]], denominator: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for n in range(1, len(s.LANES) + 1):
        for subset in itertools.combinations(s.LANES, n):
            wanted = set(subset)
            rows = [r for r in opps if wanted.intersection(set(r.get("lane_tags") or []))]
            score = s.score_with_true_coverage(rows, denominator)
            score.update({
                "lanes": "+".join(subset),
                "lane_count": n,
                "descriptive_only": True,
            })
            out.append(score)
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({k for r in rows for k in r})
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def analyze(rows: list[dict[str, str]]) -> dict[str, Any]:
    universe = s.full_contract_universe(rows)
    if not universe:
        return {
            "version": VERSION,
            "status": "FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE",
            "orders": False,
            "promotion": False,
        }
    denominator = set(universe)
    split = s.split_universe(universe)
    opps = [r for r in q.build_serial_opportunities(rows) if r.get("contract") in denominator]
    for r in opps:
        r["split"] = split.get(r.get("contract"), "")
    dev = [r for r in opps if r.get("split") == "DEVELOPMENT"]
    cuts = s.calibrate_lane_cuts(dev)
    s.lane_tags(opps, cuts)
    return s.clean({
        "version": VERSION,
        "status": "READY",
        "orders": False,
        "manual_execution_only": True,
        "production_logic_changed": False,
        "full_observed_contracts": len(denominator),
        "development_only_lane_cuts": cuts,
        "unique_lane_coverage": unique_lane_coverage(opps, denominator),
        "pairwise_overlap": pairwise_overlap(opps, denominator),
        "subset_frontier": subset_frontier(opps, denominator),
        "automatic_promotion": False,
    })


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default="/data/scalp_move_shadow_v1_events.csv")
    ap.add_argument("--outdir", default="shadow_lane_complementarity_out")
    args = ap.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    report = analyze(q.read_rows(Path(args.csv)))
    if report.get("status") != "READY":
        (outdir / "scalp_lane_complementarity_v1.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2
    write_csv(outdir / "scalp_lane_unique_coverage_v1.csv", report["unique_lane_coverage"])
    write_csv(outdir / "scalp_lane_pairwise_overlap_v1.csv", report["pairwise_overlap"])
    write_csv(outdir / "scalp_lane_subset_frontier_v1.csv", report["subset_frontier"])
    (outdir / "scalp_lane_complementarity_v1.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
