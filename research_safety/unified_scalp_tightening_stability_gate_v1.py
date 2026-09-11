#!/usr/bin/env python3
"""Research-only stability gate for unified scalp tightening candidates.

Consumes JSON emitted by unified_scalp_tightening_candidate_audit_v1.py and adds
an independent-contract leave-one-out (LOCO) robustness requirement. This gate
never changes collector/production behavior or qualification thresholds. It is a
fail-closed research decision helper only.

A candidate can remain TIGHTEN only when:
- the upstream audit preserves the ONE_UNIFIED_SCALP_EXPANSION_ENGINE invariants;
- price/zone/cheap-entry overrides are forbidden;
- legacy reversal evidence is excluded from graduation;
- there are no successful-expansion counterexamples (especially <=30s winners);
- after removing any one blocked failure contract, the configured minimum number
  of independent failure contracts is still present.

This deliberately makes an upstream TIGHTEN based on exactly N independent
failure contracts become MORE_DATA when the minimum support is N. It requires
N+1 contracts to survive a one-contract holdout.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "unified-scalp-tightening-stability-gate-v1"
EXPECTED_ARCHITECTURE = "ONE_UNIFIED_SCALP_EXPANSION_ENGINE"
ALLOWED_UPSTREAM_DECISIONS = {"KEEP", "TIGHTEN", "REJECT", "MORE_DATA"}


def _int(report: dict[str, Any], key: str) -> int:
    value = report.get(key, 0)
    if isinstance(value, bool):
        raise ValueError(f"{key}:bool_not_allowed")
    return int(value)


def evaluate_report(report: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []

    if report.get("current_architecture") != EXPECTED_ARCHITECTURE:
        errors.append("ARCHITECTURE_MISMATCH")
    if report.get("research_only") is not True:
        errors.append("RESEARCH_ONLY_INVARIANT_FAILED")
    if report.get("signal_only") is not True:
        errors.append("SIGNAL_ONLY_INVARIANT_FAILED")
    if report.get("production_promotion") != "NOT_PERFORMED":
        errors.append("PRODUCTION_PROMOTION_FORBIDDEN")
    if report.get("qualification_threshold_change_performed") is not False:
        errors.append("QUALIFICATION_THRESHOLD_CHANGE_FORBIDDEN")
    if report.get("frozen_final_early_ladders_changed") is not False:
        errors.append("FROZEN_LADDER_CHANGE_FORBIDDEN")
    if report.get("price_rule_feature_allowed") is not False:
        errors.append("PRICE_RULE_FEATURE_FORBIDDEN")
    if report.get("price_zones_are_diagnostic_only") is not True:
        errors.append("PRICE_ZONE_MUST_BE_DIAGNOSTIC_ONLY")
    if report.get("cheap_price_override") is not False:
        errors.append("CHEAP_PRICE_OVERRIDE_FORBIDDEN")
    if report.get("legacy_reversal_graduation_allowed") is not False:
        errors.append("LEGACY_REVERSAL_GRADUATION_FORBIDDEN")

    proposal_errors = report.get("proposal_errors", [])
    if not isinstance(proposal_errors, list):
        errors.append("PROPOSAL_ERRORS_MALFORMED")
    elif proposal_errors:
        errors.append("UPSTREAM_PROPOSAL_REJECTED")

    try:
        unknown_lanes = _int(report, "unknown_lane_records")
        blocked_success_n = _int(report, "would_block_success_n")
        blocked_fast_success_n = _int(report, "would_block_fast_success_n")
        min_contracts = _int(report, "research_candidate_min_independent_failure_contracts")
    except (TypeError, ValueError) as exc:
        errors.append(f"NUMERIC_FIELD_MALFORMED:{exc}")
        unknown_lanes = blocked_success_n = blocked_fast_success_n = 0
        min_contracts = 0

    if unknown_lanes:
        errors.append("UNKNOWN_LANE_RECORDS_PRESENT")
    if min_contracts < 1:
        errors.append("MIN_FAILURE_CONTRACTS_INVALID")

    raw_contracts = report.get("would_block_failure_contracts", [])
    if not isinstance(raw_contracts, list):
        errors.append("FAILURE_CONTRACTS_MALFORMED")
        failure_contracts: list[str] = []
    else:
        failure_contracts = sorted({str(x).strip() for x in raw_contracts if str(x).strip()})
        if len(failure_contracts) != len(raw_contracts):
            errors.append("FAILURE_CONTRACTS_NOT_UNIQUE_OR_EMPTY")

    decision_obj = report.get("decision", {})
    upstream_decision = (
        decision_obj.get("candidate_tightening") if isinstance(decision_obj, dict) else None
    )
    if upstream_decision not in ALLOWED_UPSTREAM_DECISIONS:
        errors.append("UPSTREAM_DECISION_INVALID")

    independent_contracts = len(failure_contracts)
    leave_one_out_min_support = max(0, independent_contracts - 1)
    folds = [
        {
            "held_out_contract": ticker,
            "remaining_failure_contracts": independent_contracts - 1,
            "passes_min_support": independent_contracts - 1 >= min_contracts,
        }
        for ticker in failure_contracts
    ]

    if errors:
        verdict = "REJECT"
        reason = "Fail-closed architecture or upstream-integrity invariant failed."
    elif blocked_fast_success_n > 0:
        verdict = "REJECT"
        reason = "Candidate removes a <=30s +10c winner; fast-expansion preservation failed."
    elif blocked_success_n > 0:
        verdict = "MORE_DATA"
        reason = "Candidate removes at least one successful expansion; tightening is not stable."
    elif upstream_decision == "REJECT":
        verdict = "REJECT"
        reason = "Upstream tightening audit rejected the candidate."
    elif upstream_decision != "TIGHTEN":
        verdict = "MORE_DATA"
        reason = "Upstream audit has not reached a research TIGHTEN verdict."
    elif independent_contracts < min_contracts:
        verdict = "MORE_DATA"
        reason = "Independent failure-contract support is below the configured research minimum."
    elif leave_one_out_min_support < min_contracts:
        verdict = "MORE_DATA"
        reason = (
            "Support does not survive leave-one-contract-out validation; one contract still "
            "determines whether the research minimum is met."
        )
    else:
        verdict = "TIGHTEN"
        reason = (
            "Research-only candidate survives every one-contract holdout with no observed "
            "successful-expansion counterexample. No threshold or production change was made."
        )

    return {
        "schema": SCHEMA,
        "current_architecture": EXPECTED_ARCHITECTURE,
        "research_only": True,
        "signal_only": True,
        "production_promotion": "NOT_PERFORMED",
        "qualification_threshold_change_performed": False,
        "frozen_final_early_ladders_changed": False,
        "price_rule_feature_allowed": False,
        "price_zones_are_diagnostic_only": True,
        "cheap_price_override": False,
        "legacy_reversal_graduation_allowed": False,
        "upstream_schema": report.get("schema"),
        "upstream_decision": upstream_decision,
        "stability_errors": sorted(set(errors)),
        "min_independent_failure_contracts": min_contracts,
        "independent_blocked_failure_contracts": failure_contracts,
        "independent_blocked_failure_contract_n": independent_contracts,
        "leave_one_out_min_support": leave_one_out_min_support,
        "leave_one_out_folds": folds,
        "would_block_success_n": blocked_success_n,
        "would_block_fast_success_n": blocked_fast_success_n,
        "decision": {
            "candidate_tightening": verdict,
            "unified_scalp_expansion_engine": "KEEP",
            "separate_ultra_cheap_graduation_path": "REJECT",
            "reason": reason,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_json", help="JSON output from unified tightening candidate audit")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = json.loads(Path(args.audit_json).read_text(encoding="utf-8"))
    result = evaluate_report(report)
    print(json.dumps(result, sort_keys=args.json, indent=None if args.json else 2))
    return 2 if result["stability_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
