#!/usr/bin/env python3
"""
BTC15 final SCALP blueprint review gate V1.

RESEARCH REVIEW ONLY | SIGNAL ONLY | NO ORDERS

Consumes the live forward-validator schema and, when available, the separate
coverage, protection, and ENDED_UNARMED lifecycle audits. It never tunes,
promotes, freezes, or places orders. Its job is to make unresolved gaps explicit
before the SCALP ladder can be called finished.

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

A completed never-armed scalp may satisfy the failed-prearm lifecycle requirement
ONLY through explicit ENDED_UNARMED evidence proving that it is informational,
non-actionable, does not alter protection/entry rules, and preserves serial
scanning. A scalp that armed +5c without the frozen 4c giveback EXIT is a
protected winner state: it must remain blocking and must never be reclassified
as ENDED_UNARMED merely to create another scalp. No stop-loss or early loss-cut
is selected by this gate.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Mapping

VERSION = "BTC15_SCALP_BLUEPRINT_REVIEW_GATE_V1_2"
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


def _ended_unarmed_resolution(lifecycle: Mapping[str, Any] | None) -> tuple[bool, list[str]]:
    """Conservatively validate evidence that only never-armed RESULTs can reset."""
    if not lifecycle:
        return False, ["LIFECYCLE_EVIDENCE_NOT_ATTACHED"]

    reasons: list[str] = []
    if lifecycle.get("orders") is not False:
        reasons.append("LIFECYCLE_ORDER_FLAG_INVALID")
    if lifecycle.get("manual_execution_only") is not True:
        reasons.append("LIFECYCLE_MANUAL_EXECUTION_FLAG_INVALID")
    if lifecycle.get("ended_unarmed_is_actionable_exit") is not False:
        reasons.append("ENDED_UNARMED_MUST_NOT_BE_ACTIONABLE_EXIT")
    if lifecycle.get("stop_loss_rule_selected") is not False:
        reasons.append("STOP_LOSS_RULE_MUST_REMAIN_UNSELECTED")
    if lifecycle.get("protected_thresholds_changed") is not False:
        reasons.append("PROTECTED_THRESHOLDS_MUST_REMAIN_FROZEN")
    if lifecycle.get("entry_price_filter_applied") is not False:
        reasons.append("ENTRY_PRICE_FILTER_MUST_REMAIN_OFF")
    if lifecycle.get("lifecycle_reset_review_ready") is not True:
        reasons.append("LIFECYCLE_RESET_REVIEW_NOT_READY")
    if lifecycle.get("armed_no_validated_exit_preserved_blocking") is not True:
        reasons.append("ARMED_NO_EXIT_MUST_REMAIN_PROTECTED_BLOCKING")
    if _int(lifecycle.get("armed_no_validated_exit_reclassified_as_ended_unarmed_n")) != 0:
        reasons.append("ARMED_NO_EXIT_WAS_RECLASSIFIED_AS_ENDED_UNARMED")

    ended_n = _int(lifecycle.get("ended_unarmed_n"))
    baseline_n = _int(lifecycle.get("baseline_completed_serial_opportunities"))
    projected_n = _int(lifecycle.get("projected_completed_serial_opportunities"))
    true_missed_raw = lifecycle.get("true_post_exit_missed_meaningful_10c")

    if ended_n <= 0:
        reasons.append("NO_ENDED_UNARMED_EVIDENCE")
    if baseline_n <= 0:
        reasons.append("LIFECYCLE_BASELINE_SAMPLE_MISSING")
    if projected_n < baseline_n:
        reasons.append("LIFECYCLE_PROJECTION_LOSES_SERIAL_OPPORTUNITIES")
    if true_missed_raw is None:
        reasons.append("LIFECYCLE_TRUE_MISS_EVIDENCE_MISSING")
    elif _int(true_missed_raw) != 0:
        reasons.append("LIFECYCLE_TRUE_POST_EXIT_MISS_PRESENT")

    return len(reasons) == 0, reasons


def compose_review(
    forward: Mapping[str, Any],
    coverage: Mapping[str, Any] | None = None,
    protection: Mapping[str, Any] | None = None,
    lifecycle: Mapping[str, Any] | None = None,
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

    true_misses = _int(coverage.get("post_exit_missed_qualified"))
    if coverage and true_misses > 0:
        blockers.append("POST_EXIT_QUALIFIED_SCALP_MISSED")

    failed_primary_n = _int(failed.get("completed_failed_primary_n"))
    failed_blocked = _int(coverage.get("failed_prearm_blocked_candidates"))
    failed_gap_observed = failed_primary_n > 0 or failed_blocked > 0
    lifecycle_resolved = False
    lifecycle_checks: list[str] = []
    if failed_gap_observed:
        lifecycle_resolved, lifecycle_checks = _ended_unarmed_resolution(lifecycle)
        if lifecycle_resolved:
            review_items.append("FAILED_PREARM_LIFECYCLE_RESOLVED_BY_ENDED_UNARMED")
            if _int((lifecycle or {}).get("armed_no_validated_exit_n")) > 0:
                review_items.append("ARMED_NO_EXIT_WINNERS_REMAIN_PROTECTED")
        else:
            blockers.append("FAILED_PREARM_CLOSE_RESET_RULE_UNRESOLVED")
    elif lifecycle:
        lifecycle_resolved, lifecycle_checks = _ended_unarmed_resolution(lifecycle)

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

    if forward.get("orders") is not False or forward.get("manual_execution_only") is not True:
        blockers.append("SIGNAL_ONLY_SAFETY_ENVELOPE_BROKEN")
    if coverage and coverage.get("orders") is not False:
        blockers.append("COVERAGE_AUDIT_ORDER_FLAG_INVALID")
    if protection and protection.get("orders") is not False:
        blockers.append("PROTECTION_AUDIT_ORDER_FLAG_INVALID")
    if lifecycle and lifecycle.get("orders") is not False:
        blockers.append("LIFECYCLE_AUDIT_ORDER_FLAG_INVALID")

    ten_rate = _num(forward.get("meaningful_10c_rate"))
    if ten_rate is None:
        review_items.append("TEN_CENT_TARGET_RATE_UNAVAILABLE")
    elif ten_rate < 1.0 - 1e-12:
        review_items.append("TEN_CENT_TARGET_NOT_HIT_BY_EVERY_SELECTED_SCALP")
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
        "failed_prearm_lifecycle_resolved": lifecycle_resolved,
        "failed_prearm_lifecycle_checks": lifecycle_checks,
        "lifecycle_ended_unarmed_n": _int((lifecycle or {}).get("ended_unarmed_n")),
        "lifecycle_armed_no_validated_exit_n": _int((lifecycle or {}).get("armed_no_validated_exit_n")),
        "lifecycle_armed_no_exit_preserved_blocking": (lifecycle or {}).get("armed_no_validated_exit_preserved_blocking"),
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
        "ended_unarmed_must_remain_nonactionable": True,
        "armed_no_exit_must_remain_protected": True,
        "stop_loss_rule_required": False,
    }


def evaluate(summary: Mapping[str, Any]) -> dict[str, Any]:
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
