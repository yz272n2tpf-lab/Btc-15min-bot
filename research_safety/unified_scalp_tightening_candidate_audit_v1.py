#!/usr/bin/env python3
"""Research-only evaluator for proposed unified scalp trap-tightening rules.

A proposal describes a candidate block signature using entry-time momentum/
expansion features only. The evaluator checks whether that signature would catch
observed failures while preserving successful +10c expansions, especially fast
bursts. It never changes frozen qualification thresholds, never uses cheap price
as a weaker evidence path, never places trades, and never promotes production.

Price is deliberately unavailable as a rule feature. Price zones are reported
only as diagnostics. The failed ULTRA_CHEAP_REVERSAL lane remains research-only
and is excluded from all graduation/tightening evidence by the shared trap audit.
"""
from __future__ import annotations

import argparse
import json
import operator
import sys
from pathlib import Path
from typing import Any

from unified_scalp_trap_signature_audit_v1 import audit_lines as trap_audit_lines

ALLOWED_FEATURES = {
    "btc5", "btc15", "btc30", "accel", "brti5", "brti15",
    "ask5", "ask15", "left_seconds",
}
PRICE_LIKE_FEATURES = {"entry", "entry_price", "price", "ask", "zone", "price_zone"}
LOOKAHEAD_FEATURES = {
    "adverse", "max_gain", "gain", "t5", "t10", "t20", "style", "result",
}
OPERATORS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}
FAST_EXPANSION_SECONDS = 30.0
DEFAULT_MIN_INDEPENDENT_FAILURE_CONTRACTS = 3


def validate_proposal(proposal: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    conditions = proposal.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        return ["PROPOSAL_REQUIRES_NONEMPTY_CONDITIONS"]

    for condition in conditions:
        if not isinstance(condition, dict):
            errors.append("CONDITION_MUST_BE_OBJECT")
            continue
        feature = str(condition.get("feature", "")).strip()
        op = str(condition.get("op", "")).strip()
        value = condition.get("value")
        if feature in PRICE_LIKE_FEATURES:
            errors.append("PRICE_DEPENDENT_RULE_FORBIDDEN")
        elif feature in LOOKAHEAD_FEATURES:
            errors.append("LOOKAHEAD_RESULT_FEATURE_FORBIDDEN")
        elif feature not in ALLOWED_FEATURES:
            errors.append(f"UNSUPPORTED_FEATURE:{feature or '<missing>'}")
        if op not in OPERATORS:
            errors.append(f"UNSUPPORTED_OPERATOR:{op or '<missing>'}")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"NON_NUMERIC_VALUE:{feature or '<missing>'}")
    return sorted(set(errors))


def _would_block(candidate: dict[str, Any], conditions: list[dict[str, Any]]) -> bool:
    return all(
        OPERATORS[str(condition["op"])](
            float(candidate[str(condition["feature"])]),
            float(condition["value"]),
        )
        for condition in conditions
    )


def evaluate_lines(
    lines: list[str],
    proposal: dict[str, Any],
    min_independent_failure_contracts: int = DEFAULT_MIN_INDEPENDENT_FAILURE_CONTRACTS,
) -> dict[str, Any]:
    proposal_errors = validate_proposal(proposal)
    trap = trap_audit_lines(lines)
    matched = list(trap.get("matched", []))
    unknown_lanes = int(trap.get("unknown_lane_records", 0))

    successes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    fast_successes: list[dict[str, Any]] = []
    blocked_successes: list[dict[str, Any]] = []
    blocked_failures: list[dict[str, Any]] = []
    blocked_fast_successes: list[dict[str, Any]] = []
    by_zone: dict[str, dict[str, int]] = {}

    for row in matched:
        candidate = row["candidate"]
        result = row["result"]
        success = bool(row.get("hit10_in_180s"))
        fast_success = (
            success
            and result.get("t10") is not None
            and float(result["t10"]) <= FAST_EXPANSION_SECONDS
        )
        blocked = (
            False if proposal_errors
            else _would_block(candidate, proposal["conditions"])
        )

        if success:
            successes.append(row)
            if fast_success:
                fast_successes.append(row)
            if blocked:
                blocked_successes.append(row)
                if fast_success:
                    blocked_fast_successes.append(row)
        else:
            failures.append(row)
            if blocked:
                blocked_failures.append(row)

        zone = str(row.get("diagnostic_price_zone", "UNKNOWN"))
        bucket = by_zone.setdefault(
            zone, {"n": 0, "success": 0, "failure": 0, "would_block": 0}
        )
        bucket["n"] += 1
        bucket["success" if success else "failure"] += 1
        if blocked:
            bucket["would_block"] += 1

    blocked_failure_contracts = sorted({r["candidate"]["ticker"] for r in blocked_failures})
    blocked_success_contracts = sorted({r["candidate"]["ticker"] for r in blocked_successes})
    blocked_fast_contracts = sorted({r["candidate"]["ticker"] for r in blocked_fast_successes})

    if proposal_errors or unknown_lanes:
        decision = "REJECT"
        reason = "Proposal or input violates fail-closed architecture invariants."
    elif not matched or not failures:
        decision = "MORE_DATA"
        reason = "Matched unified evidence lacks enough failure outcomes to evaluate tightening."
    elif blocked_fast_successes:
        decision = "REJECT"
        reason = "Candidate removes at least one <=30s +10c expansion; fast-winner preservation failed."
    elif blocked_successes:
        decision = "MORE_DATA"
        reason = "Candidate catches failures but also removes successful expansions; more evidence is required."
    elif len(blocked_failure_contracts) >= int(min_independent_failure_contracts):
        decision = "TIGHTEN"
        reason = (
            "Research candidate caught failures across the independent-contract check with no observed "
            "successful-expansion counterexample. This is not a threshold change or production promotion."
        )
    else:
        decision = "MORE_DATA"
        reason = "No winner counterexample, but independent failure-contract evidence is still too shallow."

    return {
        "schema": "unified-scalp-tightening-candidate-audit-v1",
        "current_architecture": "ONE_UNIFIED_SCALP_EXPANSION_ENGINE",
        "research_only": True,
        "signal_only": True,
        "production_promotion": "NOT_PERFORMED",
        "qualification_threshold_change_performed": False,
        "frozen_final_early_ladders_changed": False,
        "price_rule_feature_allowed": False,
        "price_zones_are_diagnostic_only": True,
        "cheap_price_override": False,
        "legacy_reversal_graduation_allowed": False,
        "fast_expansion_seconds": FAST_EXPANSION_SECONDS,
        "research_candidate_min_independent_failure_contracts": int(min_independent_failure_contracts),
        "proposal": proposal,
        "proposal_errors": proposal_errors,
        "unknown_lane_records": unknown_lanes,
        "unified_candidates": trap.get("unified_candidates", 0),
        "unified_results": trap.get("unified_results", 0),
        "matched_results": trap.get("matched_results", 0),
        "unmatched_candidates": trap.get("unmatched_candidates", 0),
        "unmatched_results": trap.get("unmatched_results", 0),
        "legacy_reversal_candidates_research_only": trap.get(
            "legacy_reversal_candidates_research_only", 0
        ),
        "legacy_reversal_results_research_only": trap.get(
            "legacy_reversal_results_research_only", 0
        ),
        "success_n": len(successes),
        "failure_n": len(failures),
        "fast_success_n": len(fast_successes),
        "would_block_success_n": len(blocked_successes),
        "would_block_failure_n": len(blocked_failures),
        "would_block_fast_success_n": len(blocked_fast_successes),
        "would_block_failure_contracts": blocked_failure_contracts,
        "would_block_success_contracts": blocked_success_contracts,
        "would_block_fast_success_contracts": blocked_fast_contracts,
        "by_diagnostic_price_zone": by_zone,
        "decision": {
            "candidate_tightening": decision,
            "unified_scalp_expansion_engine": "KEEP",
            "separate_ultra_cheap_graduation_path": "REJECT",
            "reason": reason,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal", help="JSON file describing candidate block conditions")
    parser.add_argument("log", nargs="?", help="Collector log; defaults to stdin")
    parser.add_argument(
        "--min-failure-contracts",
        type=int,
        default=DEFAULT_MIN_INDEPENDENT_FAILURE_CONTRACTS,
        help="Research-only independent-contract support needed before TIGHTEN (default: 3)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.min_failure_contracts < 1:
        parser.error("--min-failure-contracts must be >= 1")
    proposal = json.loads(Path(args.proposal).read_text(encoding="utf-8"))
    lines = (
        Path(args.log).read_text(encoding="utf-8", errors="replace").splitlines()
        if args.log else sys.stdin.read().splitlines()
    )
    report = evaluate_lines(lines, proposal, args.min_failure_contracts)
    print(json.dumps(report, sort_keys=args.json, indent=None if args.json else 2))
    return 0 if report["unknown_lane_records"] == 0 and not report["proposal_errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
