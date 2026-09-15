#!/usr/bin/env python3
"""
BTC15 final SCALP blueprint review gate V1.

RESEARCH REVIEW ONLY | SIGNAL ONLY | NO ORDERS

Consumes the live forward-validator schema and, when available, the separate
coverage and protection audits. It never tunes, promotes, freezes, or places
orders. Its job is to make unresolved gaps explicit before the SCALP ladder can
be called finished.

User-confirmed anchors preserved:
- full 15-minute scan;
- after a completed protected EXIT, reset and allow the next qualified scalp;
- no artificial scalp-count cap;
- 10c+ is the meaningful-move reporting target;
- Kalshi entry price is telemetry only, not a trigger/suppression gate;
- +5c arms protection and 4c giveback from running executable peak exits;
- failed pre-arm behavior must be resolved before final freeze;
- manual execution only / no orders;
- timer/contract alignment requires backend evidence plus a visual match.
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


def _int(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def compose_review(
    forward: Mapping[str, Any],
    coverage: Mapping[str, Any] | None = None,
    protection: Mapping[str, Any] | None = None,
    *,
    timer_visual_accepted: bool = False,
) -> dict[str, Any]:
    """Combine read-only evidence into one conservative review state."""
    coverage = coverage or {}
    protection = protection or {}

    total = _int(forward.get("completed_serial_opportunities"))
    max_idx = _int(forward.get("max_opportunities_in_one_contract"))
    timer = forward.get("timer_audit") or {}
    valid_timer = _int(timer.get("samples_valid"))
    total_timer = _int(timer.get("samples_total"))
    contract_rate = _num(timer.get("contract_match_rate"))
    canonical_rate = _num(timer.get("canonical_clock_rate"))
    within5 = _num(timer.get("within_5s_rate"))
    bands = forward.get("entry_price_bands") or {}
    blueprint = forward.get("blueprint") or {}
    failed = forward.get("failed_primary") or {}
    review_gate = forward.get("review_gate") or {}

    blockers: list[str] = []
    review_items: list[str] = []

    forward_ready = (
        str(forward.get("status") or "").upper() == "READY_FOR_REVIEW"
        and review_gate.get("met") is True
        and total >= MIN_FORWARD_OPPORTUNITIES
    )
    if not forward_ready:
        blockers.append("FORWARD_SAMPLE_NOT_READY")
    if max_idx < 2:
        blockers.append("MULTI_SCALP_RESET_NOT_OBSERVED")

    # Coverage audit is optional while collecting, but once provided it becomes
    # a hard structural check.
    true_misses = _int(coverage.get("post_exit_missed_qualified"))
    if coverage and true_misses > 0:
        blockers.append("POST_EXIT_QUALIFIED_SCALP_MISSED")

    failed_primary_n = _int(failed.get("completed_failed_primary_n"))
    failed_blocked = _int(coverage.get("failed_prearm_blocked_candidates"))
    if failed_primary_n > 0 or failed_blocked > 0:
        blockers.append("FAILED_PREARM_CLOSE_RESET_RULE_UNRESOLVED")

    protected_n = _int(protection.get("protected_exit_records"))
    crossing_rate = _num(protection.get("first_crossing_ok_rate"))
    if protection:
        if protected_n <= 0:
            blockers.append("NO_PROTECTED_EXIT_EVIDENCE")
        elif crossing_rate is None or crossing_rate < 1.0 - 1e-12:
            blockers.append("PROTECTION_FIRST_4C_CROSSING_MISMATCH")
    else:
        review_items.append("PROTECTION_AUDIT_NOT_ATTACHED")

    if valid_timer < MIN_TIMER_VALID_SAMPLES:
        blockers.append("INSUFFICIENT_VALID_TIMER_SAMPLES")
    if contract_rate is not None and contract_rate < 1.0 - 1e-12:
        blockers.append("BACKEND_CONTRACT_MATCH_NOT_PERFECT")
    if canonical_rate is not None and canonical_rate < 1.0 - 1e-12:
        blockers.append("CANONICAL_CLOCK_NOT_ALWAYS_PRESENT")
    if within5 is not None and within5 < 1.0 - 1e-12:
        review_items.append("BACKEND_TIMER_NOT_WITHIN_5S_ON_EVERY_VALID_SAMPLE")
    if not timer_visual_accepted:
        blockers.append("TIMER_VISUAL_ACCEPTANCE_PENDING")

    if (
        blueprint.get("entry_price_filter_applied") is True
        or blueprint.get("price_zone_trigger") is True
        or blueprint.get("high_price_cutoff_selected") is True
    ):
        blockers.append("UNAPPROVED_PRICE_SUPPRESSION_PRESENT")

    # The current forward summary itself must stay inside the safety envelope.
    if forward.get("orders") is not False or forward.get("manual_execution_only") is not True:
        blockers.append("SIGNAL_ONLY_SAFETY_ENVELOPE_BROKEN")
    if coverage and coverage.get("orders") is not False:
        blockers.append("COVERAGE_AUDIT_ORDER_FLAG_INVALID")
    if protection and protection.get("orders") is not False:
        blockers.append("PROTECTION_AUDIT_ORDER_FLAG_INVALID")

    ten_rate = _num(forward.get("meaningful_10c_rate"))
    if ten_rate is None:
        review_items.append("TEN_CENT_TARGET_RATE_UNAVAILABLE")
    elif ten_rate < 1.0 - 1e-12:
        review_items.append("TEN_CENT_TARGET_NOT_HIT_BY_EVERY_SELECTED_SCALP")
    # We deliberately do NOT invent a required 10c hit-rate threshold here.
    review_items.append("TEN_CENT_ACCEPTANCE_PERCENTAGE_NOT_YET_FROZEN")

    if total_timer and valid_timer < total_timer:
        review_items.append("BACKEND_TIMER_SAMPLES_INCLUDE_FETCH_FAILURES")

    high_price: dict[str, dict[str, Any]] = {}
    for band in ("70-80c", "80c+"):
        x = bands.get(band) or {}
        n = _int(x.get("n"))
        high_price[band] = {
            "n": n,
            "plus10_rate": x.get("plus10_rate"),
            "plus20_rate": x.get("plus20_rate"),
            "median_peak_gain": x.get("median_peak_gain"),
            "enough_sample_to_even_discuss_cutoff": n >= MIN_PRICE_BAND_SAMPLE_FOR_CUTOFF_RESEARCH,
            "price_is_telemetry_only": True,
        }

    ready_for_manual_freeze_review = len(blockers) == 0
    status = "READY_FOR_MANUAL_FREEZE_REVIEW" if ready_for_manual_freeze_review else "NOT_READY_TO_FREEZE"

    return {
        "version": VERSION,
        "research_only": True,
        "orders": False,
        "manual_execution_only": True,
        "status": status,
        "completed_serial_opportunities": total,
        "max_opportunities_in_one_contract": max_idx,
        "meaningful_10c_rate": ten_rate,
        "post_exit_missed_qualified": true_misses,
        "failed_prearm_completed": failed_primary_n,
        "failed_prearm_blocked_candidates": failed_blocked,
        "protected_exit_records": protected_n,
        "first_crossing_ok_rate": crossing_rate,
        "timer_valid_samples": valid_timer,
        "timer_total_samples": total_timer,
        "timer_visual_accepted": bool(timer_visual_accepted),
        "high_price_audit": high_price,
        "blockers": blockers,
        "review_items": review_items,
        "ready_for_manual_freeze_review": ready_for_manual_freeze_review,
        "auto_freeze_allowed": False,
        "price_is_telemetry_only_required": True,
    }


def evaluate(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Backward-compatible single-summary evaluation for the live forward schema."""
    return compose_review(summary)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: BTC15_SCALP_BLUEPRINT_REVIEW_GATE_V1.py <forward-summary.json>", file=sys.stderr)
        return 2
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        summary = json.load(f)
    print(json.dumps(evaluate(summary), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
