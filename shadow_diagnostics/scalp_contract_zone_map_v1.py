#!/usr/bin/env python3
"""BTC15 scalp contract-zone map V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Purpose:
- Show where inside the 15-minute contract validated serial scalp opportunities
  actually appear.
- Measure true contract coverage, not just opportunity count.
- Show cumulative coverage as the contract progresses so we can tell whether
  coverage is arriving early enough to be useful.
- Keep affordable <=50c coverage separate from raw coverage.

No zone is promoted or used as a production gate by this script.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_frontier_v1 as s

VERSION = "BTC15_SCALP_CONTRACT_ZONE_MAP_V1"

# [low seconds left, high seconds left). 15:00 is represented by 900 seconds.
ZONES = (
    ("15-12m", 720.0, 901.0),
    ("12-9m", 540.0, 720.0),
    ("9-6m", 360.0, 540.0),
    ("6-3m", 180.0, 360.0),
    ("3-2m", 120.0, 180.0),
)

# Cumulative observation checkpoints: opportunities seen from contract start
# down through the named time-left checkpoint.
CHECKPOINTS = (
    ("by_12m_left", 720.0),
    ("by_9m_left", 540.0),
    ("by_6m_left", 360.0),
    ("by_3m_left", 180.0),
    ("by_2m_left", 120.0),
)


def finite(v: Any) -> float | None:
    return s.finite(v)


def zone_for(seconds_left: Any) -> str:
    x = finite(seconds_left)
    if x is None:
        return "UNKNOWN"
    for name, low, high in ZONES:
        if low <= x < high:
            return name
    if x < 120.0:
        return "UNDER_2M_OUTSIDE_BASELINE"
    return "ABOVE_15M_INVALID"


def add_zone_tags(opps: list[dict[str, Any]]) -> None:
    for r in opps:
        r["contract_zone"] = zone_for(r.get("seconds_left"))


def zone_rows(opps: list[dict[str, Any]], zone: str) -> list[dict[str, Any]]:
    return [r for r in opps if r.get("contract_zone") == zone]


def first_opportunity_by_contract(opps: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    byc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in opps:
        c = str(r.get("contract") or "")
        if c:
            byc[c].append(r)
    out: dict[str, dict[str, Any]] = {}
    for c, rows in byc.items():
        # Earliest wall-clock scalp = highest seconds_left in a 15m countdown.
        out[c] = max(rows, key=lambda r: finite(r.get("seconds_left")) or -1.0)
    return out


def score_zone_map(opps: list[dict[str, Any]], denominator_contracts: set[str]) -> list[dict[str, Any]]:
    total = len(opps)
    first = first_opportunity_by_contract(opps)
    out: list[dict[str, Any]] = []
    for name, _, _ in ZONES:
        rows = zone_rows(opps, name)
        score = s.score_with_true_coverage(rows, denominator_contracts)
        first_contracts = {c for c, r in first.items() if r.get("contract_zone") == name}
        score.update({
            "zone": name,
            "share_of_all_opportunities": None if not total else len(rows) / total,
            "first_opportunity_contracts": len(first_contracts),
            "first_opportunity_contract_share": None if not denominator_contracts else len(first_contracts & denominator_contracts) / len(denominator_contracts),
        })
        out.append(score)
    return out


def cumulative_map(opps: list[dict[str, Any]], denominator_contracts: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for label, floor in CHECKPOINTS:
        # At checkpoint X minutes left, only opportunities that occurred earlier
        # in the countdown have been available: seconds_left >= floor.
        rows = [r for r in opps if finite(r.get("seconds_left")) is not None and float(r["seconds_left"]) >= floor]
        score = s.score_with_true_coverage(rows, denominator_contracts)
        score.update({
            "checkpoint": label,
            "seconds_left_floor": floor,
            "interpretation": "coverage accumulated from 15:00 start through this checkpoint",
        })
        out.append(score)
    return out


def lane_zone_map(opps: list[dict[str, Any]], denominator_contracts: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    lanes = list(s.LANES) + ["UNCLASSIFIED"]
    for lane in lanes:
        for zone, _, _ in ZONES:
            rows = [r for r in opps if r.get("primary_lane") == lane and r.get("contract_zone") == zone]
            score = s.score_with_true_coverage(rows, denominator_contracts)
            score.update({"lane": lane, "zone": zone})
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default="/data/scalp_move_shadow_v1_events.csv")
    ap.add_argument("--outdir", default="shadow_zone_map_out")
    args = ap.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    rows = q.read_rows(Path(args.csv))
    universe = s.full_contract_universe(rows)
    if not universe:
        report = {
            "version": VERSION,
            "orders": False,
            "status": "FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE",
            "promotion": False,
        }
        (outdir / "scalp_contract_zone_map_v1.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    denom = set(universe)
    opps = [r for r in q.build_serial_opportunities(rows) if r.get("contract") in denom]
    add_zone_tags(opps)

    # Use development-only feature distributions for lane labels, as V1 does.
    split = s.split_universe(universe)
    for r in opps:
        r["split"] = split.get(r.get("contract"), "")
    dev = [r for r in opps if r.get("split") == "DEVELOPMENT"]
    cuts = s.calibrate_lane_cuts(dev)
    s.lane_tags(opps, cuts)

    zones = score_zone_map(opps, denom)
    cumulative = cumulative_map(opps, denom)
    lanes = lane_zone_map(opps, denom)
    report = {
        "version": VERSION,
        "orders": False,
        "manual_execution_only": True,
        "production_logic_changed": False,
        "full_observed_contracts": len(denom),
        "baseline": s.score_with_true_coverage(opps, denom),
        "zone_map": zones,
        "cumulative_coverage": cumulative,
        "lane_zone_map": lanes,
        "notes": {
            "zone_is_diagnostic_only": True,
            "under_2m_is_outside_current_validated_serial_baseline": True,
            "quiet_full_contracts_remain_in_denominator": True,
            "automatic_promotion": False,
        },
    }
    write_csv(outdir / "scalp_contract_zone_map_v1.csv", zones)
    write_csv(outdir / "scalp_contract_cumulative_coverage_v1.csv", cumulative)
    write_csv(outdir / "scalp_lane_zone_map_v1.csv", lanes)
    (outdir / "scalp_contract_zone_map_v1.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print("=" * 84)
    print(VERSION)
    print("RESEARCH ONLY | SIGNAL ONLY | NO ORDERS")
    print("=" * 84)
    print("Full observed contracts:", len(denom))
    print("Cumulative coverage:", json.dumps(cumulative, sort_keys=True))
    print("Outputs:", outdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
