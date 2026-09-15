#!/usr/bin/env python3
"""
BTC15 SCALP manual freeze-review composer V1.

OFFLINE / MANUAL REVIEW ONLY | SIGNAL ONLY | NO ORDERS | NO AUTO-FREEZE

Purpose
-------
The live consolidated reviewer deliberately hardcodes timer visual acceptance to
False so backend telemetry can never impersonate a human visual check. This
module provides a separate, offline handoff after the user actually performs the
V10 visual timer checklist.

It does NOT redeploy the live reviewer, reset its accumulated timer evidence,
change a signal threshold, mutate production, or freeze anything automatically.
It may declare the evidence package eligible for MANUAL freeze review only when:

- the attached consolidated summary's existing blueprint review has exactly one
  blocker: TIMER_VISUAL_ACCEPTANCE_PENDING;
- the user-supplied visual acceptance input is True;
- the attached evidence still satisfies the key signal-only, timer, lifecycle,
  and protection invariants already present in the consolidated review.

The output is a review artifact only. Promotion/freeze remains a separate human
engineering decision and production remains untouched.
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Mapping

VERSION = "BTC15_SCALP_MANUAL_FREEZE_REVIEW_V1"
VISUAL_BLOCKER = "TIMER_VISUAL_ACCEPTANCE_PENDING"
MIN_TIMER_VALID_SAMPLES = 20


def _int(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _num(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def compose_manual_review(
    consolidated: Mapping[str, Any],
    *,
    timer_visual_accepted: bool,
) -> dict[str, Any]:
    """Fail-closed conversion of a live consolidated review into a manual artifact."""
    summary = dict(consolidated or {})
    review = dict(summary.get("blueprint_review") or {})
    blockers = [str(x) for x in (review.get("blockers") or [])]
    reasons: list[str] = []

    if summary.get("orders") is not False:
        reasons.append("CONSOLIDATED_ORDER_FLAG_INVALID")
    if summary.get("manual_execution_only") is not True:
        reasons.append("CONSOLIDATED_MANUAL_EXECUTION_FLAG_INVALID")
    if review.get("orders") is not False:
        reasons.append("REVIEW_ORDER_FLAG_INVALID")
    if review.get("manual_execution_only") is not True:
        reasons.append("REVIEW_MANUAL_EXECUTION_FLAG_INVALID")
    if review.get("auto_freeze_allowed") is not False:
        reasons.append("AUTO_FREEZE_MUST_REMAIN_DISABLED")

    if blockers != [VISUAL_BLOCKER]:
        reasons.append("EXISTING_REVIEW_HAS_NONVISUAL_OR_MULTIPLE_BLOCKERS")
    if not timer_visual_accepted:
        reasons.append("TIMER_VISUAL_ACCEPTANCE_NOT_CONFIRMED")

    timer_valid = _int(review.get("timer_valid_samples"))
    if timer_valid < MIN_TIMER_VALID_SAMPLES:
        reasons.append("TIMER_SAMPLE_MINIMUM_NOT_PRESERVED")

    if review.get("failed_prearm_lifecycle_resolved") is not True:
        reasons.append("FAILED_PREARM_LIFECYCLE_NOT_RESOLVED")
    if review.get("lifecycle_armed_no_exit_preserved_blocking") is not True:
        reasons.append("ARMED_NO_EXIT_BLOCKING_INVARIANT_NOT_PRESERVED")

    protected_n = _int(review.get("protected_exit_records"))
    crossing = _num(review.get("first_crossing_ok_rate"))
    if protected_n <= 0:
        reasons.append("NO_PROTECTED_EXIT_EVIDENCE")
    if crossing is None or crossing < 1.0 - 1e-12:
        reasons.append("PROTECTION_FIRST_CROSSING_NOT_PERFECT")

    if review.get("price_is_telemetry_only_required") is not True:
        reasons.append("PRICE_TELEMETRY_ONLY_REQUIREMENT_MISSING")
    if review.get("ended_unarmed_must_remain_nonactionable") is not True:
        reasons.append("ENDED_UNARMED_NONACTIONABLE_REQUIREMENT_MISSING")
    if review.get("armed_no_exit_must_remain_protected") is not True:
        reasons.append("ARMED_NO_EXIT_PROTECTION_REQUIREMENT_MISSING")
    if review.get("stop_loss_rule_required") is not False:
        reasons.append("UNEXPECTED_STOP_LOSS_REQUIREMENT")

    eligible = len(reasons) == 0
    return {
        "version": VERSION,
        "research_only": True,
        "manual_review_only": True,
        "orders": False,
        "manual_execution_only": True,
        "timer_visual_accepted": bool(timer_visual_accepted),
        "source_review_version": review.get("version"),
        "source_review_status": review.get("status"),
        "source_review_blockers": blockers,
        "timer_valid_samples": timer_valid,
        "protected_exit_records": protected_n,
        "first_crossing_ok_rate": crossing,
        "manual_freeze_review_eligible": eligible,
        "status": (
            "READY_FOR_MANUAL_FREEZE_REVIEW"
            if eligible
            else "NOT_READY_FOR_MANUAL_FREEZE_REVIEW"
        ),
        "blocking_reasons": reasons,
        "auto_freeze_allowed": False,
        "production_change_allowed": False,
        "strategy_change_allowed": False,
        "order_action": None,
        "note": (
            "This artifact only confirms that the pre-existing evidence package plus "
            "an explicit human timer visual PASS is eligible for manual freeze review. "
            "It never freezes, promotes, trades, or changes production."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("summary_json", help="Saved consolidated live-review summary JSON")
    ap.add_argument(
        "--timer-visual-accepted",
        action="store_true",
        help="Set only after the user explicitly passes the V10 visual timer checklist",
    )
    args = ap.parse_args()
    with open(args.summary_json, "r", encoding="utf-8") as f:
        summary = json.load(f)
    out = compose_manual_review(
        summary,
        timer_visual_accepted=bool(args.timer_visual_accepted),
    )
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if out["manual_freeze_review_eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
