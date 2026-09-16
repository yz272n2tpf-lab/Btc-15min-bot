#!/usr/bin/env python3
"""BTC15 scalp economics + exit certification V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Purpose
-------
Convert the existing executable scalp path tape into *captured* economics,
without changing the frozen detector or lifecycle.

Rules
-----
* Baseline opportunity construction is imported unchanged.
* Entry price is the candidate's executable ASK.
* Protected exit uses the already-frozen +5c arm / 4c giveback lifecycle.
* Gross protected gain = executable exit BID - entry ASK.
* A +10c touch is movement telemetry, not a realized +10c trade.
* Fee-adjusted results are reported only for opportunities with an observed
  protected exit; unresolved/unprotected paths are never fabricated.
* Current Kalshi general event-contract fee schedule is modeled explicitly:
  taker fee = ceil-cent(0.07 * C * P * (1-P)); maker fee uses 0.0175 and a
  configurable multiplier. KXBTC15M is not listed as a non-standard series in
  the July 7, 2026 schedule, so V1 uses general taker multiplier=1 and default
  maker multiplier=0. Fee scenarios are still labeled assumptions, not broker
  statements.
* Lot sizes 1/10/100 are reported separately because fee rounding matters.
* No production imports/writes. No automatic promotion. No orders.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any, Iterable, Mapping

import scalp_opportunity_quality_frontier_v1 as q

VERSION = "BTC15_SCALP_ECONOMICS_EXIT_CERT_V1"
FEE_SCHEDULE_EFFECTIVE = "2026-07-07"
TAKER_RATE = 0.07
MAKER_RATE = 0.0175
TAKER_MULTIPLIER = 1.0
DEFAULT_MAKER_MULTIPLIER = 0.0
LOT_SIZES = (1, 10, 100)


def ceil_cent(x: float) -> float:
    """Round a non-negative dollar fee upward to the next cent."""
    if x <= 0:
        return 0.0
    return math.ceil((x - 1e-12) * 100.0) / 100.0


def kalshi_fee_total(price: float, contracts: int, *, maker: bool = False,
                     maker_multiplier: float = DEFAULT_MAKER_MULTIPLIER) -> float:
    """General event-contract fee scenario from the July 7, 2026 schedule."""
    p = min(1.0, max(0.0, float(price)))
    c = max(1, int(contracts))
    if maker:
        raw = float(maker_multiplier) * MAKER_RATE * c * p * (1.0 - p)
    else:
        raw = TAKER_MULTIPLIER * TAKER_RATE * c * p * (1.0 - p)
    return ceil_cent(raw)


def fee_adjusted_per_contract(entry_ask: float, exit_bid: float, contracts: int,
                              *, entry_maker: bool = False,
                              exit_maker: bool = False,
                              maker_multiplier: float = DEFAULT_MAKER_MULTIPLIER) -> dict[str, float]:
    gross = float(exit_bid) - float(entry_ask)
    entry_fee = kalshi_fee_total(entry_ask, contracts, maker=entry_maker,
                                 maker_multiplier=maker_multiplier)
    exit_fee = kalshi_fee_total(exit_bid, contracts, maker=exit_maker,
                                maker_multiplier=maker_multiplier)
    per_contract_fees = (entry_fee + exit_fee) / contracts
    return {
        "gross_gain_dollars_per_contract": gross,
        "entry_fee_total_dollars": entry_fee,
        "exit_fee_total_dollars": exit_fee,
        "round_trip_fee_dollars_per_contract": per_contract_fees,
        "net_gain_dollars_per_contract": gross - per_contract_fees,
    }


def _op_record(op: Mapping[str, Any]) -> dict[str, Any]:
    entry = q.f(op.get("entry_ask"))
    protected_gain = q.f(op.get("protected_exit_gain"))
    peak = q.f(op.get("peak_gain"))
    adverse = q.f(op.get("adverse_gain"))
    rec: dict[str, Any] = {
        "contract": str(op.get("contract") or ""),
        "candidate_id": str(op.get("candidate_id") or ""),
        "opportunity_index": int(op.get("opportunity_index") or 0),
        "side": str(op.get("side") or ""),
        "entry_ask": entry,
        "seconds_left": q.f(op.get("seconds_left")),
        "plus5": int(bool(op.get("plus5"))),
        "plus10": int(bool(op.get("plus10"))),
        "plus20": int(bool(op.get("plus20"))),
        "peak_gain": peak,
        "adverse_gain": adverse,
        "protected_exit_gain": protected_gain,
        "protected_exit_observed": protected_gain is not None,
    }
    if entry is not None and protected_gain is not None:
        exit_bid = entry + protected_gain
        rec["protected_exit_bid"] = exit_bid
        rec["gross_protected_gain_c"] = 100.0 * protected_gain
        rec["giveback_from_peak_c"] = None if peak is None else 100.0 * (peak - protected_gain)
        rec["capture_efficiency"] = None if peak is None or peak <= 0 else protected_gain / peak
        fee_scenarios: dict[str, Any] = {}
        for lot in LOT_SIZES:
            tt = fee_adjusted_per_contract(entry, exit_bid, lot)
            mt = fee_adjusted_per_contract(entry, exit_bid, lot, entry_maker=True)
            fee_scenarios[str(lot)] = {
                "TAKER_TAKER": {
                    "round_trip_fee_c_per_contract": 100.0 * tt["round_trip_fee_dollars_per_contract"],
                    "net_gain_c_per_contract": 100.0 * tt["net_gain_dollars_per_contract"],
                },
                "MAKER_ENTRY_TAKER_EXIT": {
                    "round_trip_fee_c_per_contract": 100.0 * mt["round_trip_fee_dollars_per_contract"],
                    "net_gain_c_per_contract": 100.0 * mt["net_gain_dollars_per_contract"],
                },
            }
        rec["fee_scenarios"] = fee_scenarios
    else:
        rec["protected_exit_bid"] = None
        rec["gross_protected_gain_c"] = None
        rec["giveback_from_peak_c"] = None
        rec["capture_efficiency"] = None
        rec["fee_scenarios"] = {}
    return rec


def build_records(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Reuse frozen serial opportunity construction exactly."""
    return [_op_record(op) for op in q.build_serial_opportunities(rows)]


def _mean(values: Iterable[float]) -> float | None:
    z = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return None if not z else statistics.fmean(z)


def _median(values: Iterable[float]) -> float | None:
    z = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return None if not z else statistics.median(z)


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(records)
    protected = [r for r in records if r.get("protected_exit_observed")]
    asks = [r["entry_ask"] for r in records if r.get("entry_ask") is not None]
    left = [r["seconds_left"] / 60.0 for r in records if r.get("seconds_left") is not None]
    gross = [r["gross_protected_gain_c"] for r in protected if r.get("gross_protected_gain_c") is not None]
    giveback = [r["giveback_from_peak_c"] for r in protected if r.get("giveback_from_peak_c") is not None]
    capture = [r["capture_efficiency"] for r in protected if r.get("capture_efficiency") is not None]

    out: dict[str, Any] = {
        "signals": n,
        "contracts": len({r["contract"] for r in records}),
        "plus5_rate": None if not n else sum(r["plus5"] for r in records) / n,
        "plus10_rate": None if not n else sum(r["plus10"] for r in records) / n,
        "plus20_rate": None if not n else sum(r["plus20"] for r in records) / n,
        "protected_exit_signals": len(protected),
        "protected_exit_rate": None if not n else len(protected) / n,
        "avg_entry_ask_c": None if not asks else 100.0 * statistics.fmean(asks),
        "median_entry_ask_c": None if not asks else 100.0 * statistics.median(asks),
        "entry_le50_rate": None if not asks else sum(x <= 0.50 for x in asks) / len(asks),
        "entry_ideal_25_35_rate": None if not asks else sum(0.25 <= x <= 0.35 for x in asks) / len(asks),
        "avg_minutes_left": _mean(left),
        "avg_gross_protected_gain_c": _mean(gross),
        "median_gross_protected_gain_c": _median(gross),
        "positive_gross_protected_exit_rate": None if not gross else sum(x > 0 for x in gross) / len(gross),
        "avg_giveback_from_peak_c": _mean(giveback),
        "median_giveback_from_peak_c": _median(giveback),
        "avg_capture_efficiency": _mean(capture),
        "max_opportunity_index": max((int(r.get("opportunity_index") or 0) for r in records), default=0),
        "unprotected_signals_not_counted_as_realized": n - len(protected),
    }

    fee_summary: dict[str, Any] = {}
    for lot in LOT_SIZES:
        lot_key = str(lot)
        fee_summary[lot_key] = {}
        for scenario in ("TAKER_TAKER", "MAKER_ENTRY_TAKER_EXIT"):
            nets = [r["fee_scenarios"][lot_key][scenario]["net_gain_c_per_contract"]
                    for r in protected if lot_key in r.get("fee_scenarios", {})]
            fees = [r["fee_scenarios"][lot_key][scenario]["round_trip_fee_c_per_contract"]
                    for r in protected if lot_key in r.get("fee_scenarios", {})]
            fee_summary[lot_key][scenario] = {
                "n_protected_exits": len(nets),
                "avg_round_trip_fee_c_per_contract": _mean(fees),
                "avg_net_gain_c_per_contract": _mean(nets),
                "median_net_gain_c_per_contract": _median(nets),
                "positive_net_rate": None if not nets else sum(x > 0 for x in nets) / len(nets),
                "net_ge5_rate": None if not nets else sum(x >= 5.0 for x in nets) / len(nets),
                "net_ge10_rate": None if not nets else sum(x >= 10.0 for x in nets) / len(nets),
            }
    out["fee_adjusted_protected_exits"] = fee_summary
    return out


def analyze(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    records = build_records(rows)
    by_index: dict[str, Any] = {}
    for idx in sorted({int(r.get("opportunity_index") or 0) for r in records}):
        by_index[str(idx)] = summarize([r for r in records if int(r.get("opportunity_index") or 0) == idx])
    return {
        "version": VERSION,
        "status": "ECONOMICS_EXIT_CERT_ANALYSIS_READY",
        "fee_schedule": {
            "effective": FEE_SCHEDULE_EFFECTIVE,
            "general_taker_rate": TAKER_RATE,
            "general_maker_rate": MAKER_RATE,
            "taker_multiplier": TAKER_MULTIPLIER,
            "default_maker_multiplier": DEFAULT_MAKER_MULTIPLIER,
            "kxbtc15m_nonstandard_listing_found": False,
            "lot_sizes": list(LOT_SIZES),
        },
        "overall": summarize(records),
        "by_opportunity_index": by_index,
        "movement_vs_realized_warning": "+10 touch is not treated as realized +10",
        "unprotected_paths_are_not_fabricated": True,
        "automatic_promotion": False,
        "production_logic_changed": False,
        "shadow_only": True,
        "orders": False,
    }


def assert_integrity() -> None:
    if q.ARM_GAIN != 0.05 or q.GIVEBACK != 0.04:
        raise RuntimeError("legacy protection lifecycle drifted")
    if TAKER_RATE != 0.07 or MAKER_RATE != 0.0175:
        raise RuntimeError("fee schedule constant drift")
    if not LOT_SIZES:
        raise RuntimeError("lot size scenarios required")


assert_integrity()
