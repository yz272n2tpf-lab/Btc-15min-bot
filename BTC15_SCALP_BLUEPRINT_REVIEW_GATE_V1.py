#!/usr/bin/env python3
"""
BTC15 final SCALP blueprint review gate V1.

RESEARCH REVIEW ONLY | SIGNAL ONLY | NO ORDERS

This does NOT tune or promote trading rules. It turns the live forward-validator
summary into an explicit readiness checklist so we cannot accidentally call the
scalp ladder "done" just because one attractive statistic appears.

The gate deliberately separates:
1) collection/readiness requirements (objective), from
2) performance/freeze decisions (must be reviewed after enough untouched data).

User-confirmed blueprint anchors preserved here:
- scan the whole 15-minute contract;
- after a completed scalp EXIT, reset and allow the next qualified scalp;
- no artificial scalp-count cap;
- 10c+ is the meaningful-move reporting target;
- Kalshi entry price is telemetry, not a trigger or suppression gate;
- low-price opportunities must not be suppressed;
- high-price bands are audited before any possible future cutoff;
- failed pre-arm scalps are audited, not given an invented stop;
- manual execution only / no orders;
- timer/contract alignment must be verified, including a visual check.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Mapping

VERSION = "BTC15_SCALP_BLUEPRINT_REVIEW_GATE_V1"
MIN_FORWARD_OPPORTUNITIES = 20
MIN_TIMER_VALID_SAMPLES = 20
MIN_PRICE_BAND_SAMPLE_FOR_CUTOFF_RESEARCH = 20


def _num(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def evaluate(summary: Mapping[str, Any]) -> dict[str, Any]:
    total = int(summary.get("opportunity_count") or summary.get("opportunities") or 0)
    max_idx = int(summary.get("max_opportunity_index") or 0)
    timer = summary.get("timer") or summary.get("timer_summary") or {}
    valid_timer = int(timer.get("samples_valid") or 0)
    contract_rate = _num(timer.get("contract_match_rate"))
    canonical_rate = _num(timer.get("canonical_clock_rate"))
    within5 = _num(timer.get("within_5s_rate"))
    bands = summary.get("price_bands") or {}

    structural = {
        "forward_sample_at_least_20": total >= MIN_FORWARD_OPPORTUNITIES,
        "serial_reset_observed": max_idx >= 2,
        "third_or_later_scalp_observed": max_idx >= 3,
        "signal_only_no_orders": summary.get("orders") is False,
        "manual_execution_only": summary.get("manual_execution_only") is True,
        "entry_price_is_not_gate": summary.get("entry_price_is_telemetry_only") is True,
        "failed_prearm_is_audit_only": summary.get("failed_primary_cut_actionable") is not True,
    }

    timer_checks = {
        "enough_valid_timer_samples": valid_timer >= MIN_TIMER_VALID_SAMPLES,
        "contract_match_all_valid_samples": contract_rate == 1.0 if contract_rate is not None else False,
        "canonical_clock_all_valid_samples": canonical_rate == 1.0 if canonical_rate is not None else False,
        "backend_timer_within_5s_all_valid_samples": within5 == 1.0 if within5 is not None else False,
        "visual_timer_check_still_required": True,
    }

    high_price = {}
    for band in ("70-80c", "80c+"):
        x = bands.get(band) or {}
        n = int(x.get("n") or 0)
        high_price[band] = {
            "n": n,
            "plus10_rate": x.get("plus10_rate"),
            "plus20_rate": x.get("plus20_rate"),
            "median_peak_gain": x.get("median_peak_gain"),
            "enough_sample_to_even_discuss_cutoff": n >= MIN_PRICE_BAND_SAMPLE_FOR_CUTOFF_RESEARCH,
            "price_is_telemetry_only": True,
        }

    collection_ready = all(structural.values()) and timer_checks["enough_valid_timer_samples"]
    # Never auto-freeze. Performance and UI wording remain explicit review items.
    return {
        "version": VERSION,
        "research_only": True,
        "orders": False,
        "collection_ready_for_full_review": collection_ready,
        "auto_freeze_allowed": False,
        "structural_checks": structural,
        "timer_checks": timer_checks,
        "high_price_audit": high_price,
        "performance_review_required": {
            "10c_plus_capture_quality": True,
            "serial_scalp_2_plus_quality": True,
            "failed_prearm_resolution": True,
            "profit_protection_behavior": True,
            "low_price_opportunities_not_suppressed": True,
            "high_price_cutoff_not_assumed": True,
            "plain_language_dashboard_verbiage": True,
            "visual_timer_match": True,
        },
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: BTC15_SCALP_BLUEPRINT_REVIEW_GATE_V1.py <summary.json>", file=sys.stderr)
        return 2
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        summary = json.load(f)
    print(json.dumps(evaluate(summary), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
