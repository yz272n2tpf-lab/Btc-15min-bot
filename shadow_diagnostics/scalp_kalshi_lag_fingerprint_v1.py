#!/usr/bin/env python3
"""BTC15 normalized Kalshi-lag fingerprint V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

The BTC and BRTI impulse features are in price units while Kalshi repricing is
in contract-price units. V1 therefore never subtracts them directly. Instead it
builds DEVELOPMENT-only empirical percentile scales and asks whether an
opportunity has unusually strong BTC/BRTI impulse while Kalshi's recent ask
response is unusually muted.

Outcome labels select report-only thresholds on VALIDATION. HOLDOUT is revealed
once and never retunes the fingerprint.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_frontier_v1 as s

VERSION = "BTC15_SCALP_KALSHI_LAG_FINGERPRINT_V1"


def finite(v: Any) -> float | None:
    return s.finite(v)


def sorted_values(rows: Iterable[Mapping[str, Any]], key: str, absolute: bool = False) -> list[float]:
    out: list[float] = []
    for r in rows:
        x = finite(r.get(key))
        if x is None:
            continue
        out.append(abs(x) if absolute else x)
    return sorted(out)


def percentile(x: float | None, values: list[float]) -> float | None:
    if x is None or not values:
        return None
    # Mid-rank empirical CDF in [0,1].
    lo = bisect.bisect_left(values, x)
    hi = bisect.bisect_right(values, x)
    return ((lo + hi) / 2.0) / len(values)


def build_scales(dev: list[dict[str, Any]]) -> dict[str, list[float]]:
    return {
        "momentum_floor15": sorted_values(dev, "momentum_floor15"),
        "btc30": sorted_values(dev, "btc_move30_side"),
        "acceleration": sorted_values(dev, "acceleration"),
        "ask15_abs": sorted_values(dev, "ask_move15", absolute=True),
        "ask5_abs": sorted_values(dev, "ask_move5", absolute=True),
        "spread": sorted_values(dev, "spread"),
    }


def lag_fingerprint(r: Mapping[str, Any], scales: Mapping[str, list[float]]) -> dict[str, Any]:
    floor15 = finite(r.get("momentum_floor15"))
    btc30 = finite(r.get("btc_move30_side"))
    accel = finite(r.get("acceleration"))
    ask15 = finite(r.get("ask_move15"))
    ask5 = finite(r.get("ask_move5"))
    spread = finite(r.get("spread"))

    impulse_parts = [
        percentile(floor15, scales.get("momentum_floor15", [])),
        percentile(btc30, scales.get("btc30", [])),
        percentile(accel, scales.get("acceleration", [])),
    ]
    impulse_parts = [x for x in impulse_parts if x is not None]
    response_parts = [
        percentile(None if ask15 is None else abs(ask15), scales.get("ask15_abs", [])),
        percentile(None if ask5 is None else abs(ask5), scales.get("ask5_abs", [])),
    ]
    response_parts = [x for x in response_parts if x is not None]

    impulse = None if not impulse_parts else sum(impulse_parts) / len(impulse_parts)
    response = None if not response_parts else sum(response_parts) / len(response_parts)
    lag_gap = None if impulse is None or response is None else impulse - response
    spread_pct = percentile(spread, scales.get("spread", []))
    liquidity = None if spread_pct is None else 1.0 - spread_pct

    aligned = bool(r.get("btc_brti_agree15"))
    against = bool(r.get("btc_against_side")) or bool(r.get("brti_against_side"))
    dual = bool(r.get("dual_reversal_evidence"))

    parts = []
    if impulse is not None:
        parts.append(impulse)
    if response is not None:
        parts.append(1.0 - response)
    if liquidity is not None:
        parts.append(liquidity)
    raw = None if not parts else sum(parts) / len(parts)
    if raw is not None:
        if aligned:
            raw += 0.08
        if against:
            raw -= 0.20
        if dual:
            raw -= 0.15
        raw = min(1.0, max(0.0, raw))

    return {
        "lag_impulse_percentile": impulse,
        "kalshi_response_percentile": response,
        "lag_gap": lag_gap,
        "liquidity_percentile_inverse": liquidity,
        "lag_index": raw,
        "lag_alignment": aligned,
        "lag_against_side": against,
        "lag_dual_reversal": dual,
    }


def score_frontier(
    opps: list[dict[str, Any]],
    split: Mapping[str, str],
    scales: Mapping[str, list[float]],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, dict[str, Any] | None]:
    val = [r for r in opps if split.get(r.get("contract")) == "VALIDATION"]
    hold = [r for r in opps if split.get(r.get("contract")) == "HOLDOUT"]
    val_contracts = {c for c, z in split.items() if z == "VALIDATION"}
    hold_contracts = {c for c, z in split.items() if z == "HOLDOUT"}

    def enrich(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for r in rows:
            x = dict(r)
            x.update(lag_fingerprint(r, scales))
            out.append(x)
        return out

    ev = enrich(val)
    eh = enrich(hold)
    frontier: list[dict[str, Any]] = []
    for th in (0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90):
        selected = [r for r in ev if finite(r.get("lag_index")) is not None and float(r["lag_index"]) >= th]
        score = s.score_with_true_coverage(selected, val_contracts)
        score.update({
            "lag_index_threshold": th,
            "minimum_validation_n_met": len(selected) >= max(8, int(math.ceil(max(1, len(ev)) * .15))),
        })
        frontier.append(score)

    eligible = [r for r in frontier if r.get("minimum_validation_n_met")]
    if not eligible:
        return frontier, None, None
    target = [r for r in eligible if (r.get("plus10_rate") or 0.0) >= .93]
    pool = target if target else eligible
    winner = max(
        pool,
        key=lambda r: (
            r.get("plus10_rate") or 0.0,
            r.get("affordable_true_contract_coverage_le50") or 0.0,
            r.get("true_contract_coverage") or 0.0,
            r.get("n") or 0,
        ),
    )
    threshold = float(winner["lag_index_threshold"])
    selected_hold = [r for r in eh if finite(r.get("lag_index")) is not None and float(r["lag_index"]) >= threshold]
    hold_score = s.score_with_true_coverage(selected_hold, hold_contracts)
    hold_score.update({
        "lag_index_threshold_frozen_from_validation": threshold,
        "holdout_is_report_only": True,
    })
    return frontier, winner, hold_score


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({k for r in rows for k in r if not k.startswith("_") and k != "lane_tags"})
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows([{k: s.clean(v) for k, v in r.items() if not k.startswith("_") and k != "lane_tags"} for r in rows])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default="/data/scalp_move_shadow_v1_events.csv")
    ap.add_argument("--outdir", default="shadow_kalshi_lag_out")
    args = ap.parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    rows = q.read_rows(Path(args.csv))
    universe = s.full_contract_universe(rows)
    if not universe:
        report = {"version": VERSION, "status": "FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE", "orders": False, "promotion": False}
        (outdir / "scalp_kalshi_lag_fingerprint_v1.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    denom = set(universe)
    split = s.split_universe(universe)
    opps = [r for r in q.build_serial_opportunities(rows) if r.get("contract") in denom]
    for r in opps:
        r["split"] = split.get(r.get("contract"), "")
    dev = [r for r in opps if r.get("split") == "DEVELOPMENT"]
    scales = build_scales(dev)

    enriched = []
    for r in opps:
        x = dict(r)
        x.update(lag_fingerprint(r, scales))
        enriched.append(x)
    frontier, winner, holdout = score_frontier(opps, split, scales)

    report = {
        "version": VERSION,
        "orders": False,
        "manual_execution_only": True,
        "production_logic_changed": False,
        "normalization_fit": "DEVELOPMENT_ONLY_EMPIRICAL_PERCENTILES",
        "full_observed_contracts": len(denom),
        "validation_selected_candidate": winner,
        "untouched_holdout_result": holdout,
        "automatic_promotion": False,
        "note": "BTC/BRTI price-unit impulses are never directly subtracted from Kalshi contract-price moves.",
    }
    write_csv(outdir / "scalp_kalshi_lag_opportunities_v1.csv", enriched)
    write_csv(outdir / "scalp_kalshi_lag_validation_frontier_v1.csv", frontier)
    (outdir / "scalp_kalshi_lag_fingerprint_v1.json").write_text(json.dumps(s.clean(report), indent=2, sort_keys=True), encoding="utf-8")
    print("=" * 84)
    print(VERSION)
    print("RESEARCH ONLY | SIGNAL ONLY | NO ORDERS")
    print("=" * 84)
    print("Validation winner:", json.dumps(s.clean(winner), sort_keys=True))
    print("Untouched holdout:", json.dumps(s.clean(holdout), sort_keys=True))
    print("Outputs:", outdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
