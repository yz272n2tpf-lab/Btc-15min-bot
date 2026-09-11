#!/usr/bin/env python3
"""One-command research report for the CURRENT unified BTC 15m scalp engine.

Consumes archived/live collector text, treats RESULT rows as scoring authority,
keeps legacy ultra-cheap reversal observations audit-only, combines unified
price/speed scoring with adverse-path ordering, outcome-overlap, contract-balance,
candidate feature-signature, and heartbeat path-order diagnostics, and fails
closed on any architecture invariant breach. This file cannot place trades or
promote production.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from unified_scalp_adverse_path_audit_v1 import audit_lines as audit_adverse_lines
from unified_scalp_contract_balance_audit_v1 import audit_lines as audit_contract_balance_lines
from unified_scalp_heartbeat_path_audit_v1 import audit_lines as audit_heartbeat_lines
from unified_scalp_outcome_overlap_audit_v1 import audit_lines as audit_overlap_lines
from unified_scalp_result_scorecard_v1 import score_lines
from unified_scalp_trap_signature_audit_v1 import audit_lines as audit_trap_lines


def _pairing_status(report: dict) -> str:
    return (
        "COMPLETE"
        if report.get("unmatched_results", 0) == 0
        else "PARTIAL_DATA"
    )


def build_report(lines: list[str]) -> dict:
    score = score_lines(lines)
    adverse = audit_adverse_lines(lines)
    overlap = audit_overlap_lines(lines)
    balance = audit_contract_balance_lines(lines)
    trap = audit_trap_lines(lines)
    heartbeat = audit_heartbeat_lines(lines)

    checks = {
        "score_research_only": score.get("research_only") is True,
        "score_promotion_locked": score.get("production_promotion") == "NOT_PERFORMED",
        "score_result_authority": score.get("result_stream_authority") is True,
        "score_contract_summary_not_authority": score.get("contract_summary_authority") is False,
        "score_no_unknown_lane": score.get("unknown_lane_results") == 0,
        "adverse_research_only": adverse.get("research_only") is True,
        "adverse_signal_only": adverse.get("signal_only") is True,
        "adverse_promotion_locked": adverse.get("production_promotion") == "NOT_PERFORMED",
        "adverse_no_unknown_lane": adverse.get("unknown_lane_results") == 0,
        "overlap_research_only": overlap.get("research_only") is True,
        "overlap_signal_only": overlap.get("signal_only") is True,
        "overlap_promotion_locked": overlap.get("production_promotion") == "NOT_PERFORMED",
        "overlap_thresholds_unchanged": overlap.get("qualification_thresholds_changed") is False,
        "overlap_no_cheap_override": overlap.get("cheap_price_evidence_override") is False,
        "overlap_no_unknown_lane": overlap.get("unknown_lane_results") == 0,
        "balance_research_only": balance.get("research_only") is True,
        "balance_signal_only": balance.get("signal_only") is True,
        "balance_promotion_locked": balance.get("production_promotion") == "NOT_PERFORMED",
        "balance_thresholds_unchanged": balance.get("qualification_thresholds_changed") is False,
        "balance_no_cheap_override": balance.get("cheap_price_evidence_override") is False,
        "balance_price_bands_diagnostic_only": balance.get("price_bands_are_diagnostic_only") is True,
        "balance_no_unknown_lane": balance.get("unknown_lane_results") == 0,
        "trap_research_only": trap.get("research_only") is True,
        "trap_signal_only": trap.get("signal_only") is True,
        "trap_exploratory_only": trap.get("exploratory_only") is True,
        "trap_promotion_locked": trap.get("production_promotion") == "NOT_PERFORMED",
        "trap_thresholds_unchanged": trap.get("threshold_change_performed") is False,
        "trap_no_cheap_override": trap.get("cheap_price_override") is False,
        "trap_price_zone_diagnostic_only": trap.get("price_zone_is_diagnostic_only") is True,
        "trap_no_unknown_lane": trap.get("unknown_lane_records") == 0,
        "heartbeat_research_only": heartbeat.get("research_only") is True,
        "heartbeat_signal_only": heartbeat.get("signal_only") is True,
        "heartbeat_promotion_locked": heartbeat.get("production_promotion") == "NOT_PERFORMED",
        "heartbeat_coarse_lower_bound": heartbeat.get("heartbeat_path_is_coarse_lower_bound") is True,
        "heartbeat_no_unknown_lane": heartbeat.get("unknown_lane_records") == 0,
        "legacy_counts_agree": (
            score.get("legacy_reversal_research_only")
            == adverse.get("legacy_reversal_research_only")
            == overlap.get("legacy_reversal_research_only")
            == balance.get("legacy_reversal_research_only")
            == trap.get("legacy_reversal_results_research_only")
            == heartbeat.get("legacy_reversal_research_only")
        ),
        "unified_counts_agree": (
            score.get("unified_results")
            == adverse.get("unified_results")
            == overlap.get("unified_results")
            == balance.get("unified_results")
            == trap.get("unified_results")
            == heartbeat.get("unified_results")
        ),
        "unified_path_keep": (
            score.get("architecture", {}).get("unified_scalp_expansion_path") == "KEEP"
            and adverse.get("decision", {}).get("unified_scalp_expansion_path") == "KEEP"
            and overlap.get("decision", {}).get("unified_scalp_expansion_path") == "KEEP"
            and balance.get("decision", {}).get("unified_scalp_expansion_path") == "KEEP"
            and trap.get("decision", {}).get("unified_scalp_expansion_engine") == "KEEP"
            and heartbeat.get("decision", {}).get("unified_scalp_expansion_engine") == "KEEP"
        ),
        "separate_cheap_path_rejected": (
            score.get("architecture", {}).get("separate_ultra_cheap_graduation_path") == "REJECT"
            and adverse.get("decision", {}).get("separate_ultra_cheap_graduation_path") == "REJECT"
            and overlap.get("decision", {}).get("separate_ultra_cheap_graduation_path") == "REJECT"
            and balance.get("decision", {}).get("separate_ultra_cheap_graduation_path") == "REJECT"
            and trap.get("decision", {}).get("separate_ultra_cheap_graduation_path") == "REJECT"
            and heartbeat.get("decision", {}).get("separate_ultra_cheap_graduation_path") == "REJECT"
        ),
    }
    preflight = "PASS" if all(checks.values()) else "FAIL"

    return {
        "schema": "unified-scalp-final-report-v4",
        "current_architecture": "ONE_UNIFIED_SCALP_EXPANSION_ENGINE",
        "research_only": True,
        "signal_only": True,
        "production_promotion": "NOT_PERFORMED",
        "preflight": preflight,
        "checks": checks,
        "diagnostic_coverage": {
            "trap_signature_pairing": _pairing_status(trap),
            "trap_signature_unmatched_results": trap.get("unmatched_results", 0),
            "heartbeat_path_pairing": _pairing_status(heartbeat),
            "heartbeat_path_unmatched_results": heartbeat.get("unmatched_results", 0),
            "pairing_is_qualification_gate": False,
        },
        "scorecard": score,
        "adverse_path_audit": adverse,
        "outcome_overlap_audit": overlap,
        "contract_balance_audit": balance,
        "trap_signature_audit": trap,
        "heartbeat_path_audit": heartbeat,
        "decisions": {
            "unified_scalp_expansion_engine": "KEEP",
            "separate_ultra_cheap_graduation_path": "REJECT",
            "qualification_threshold_change": score.get("architecture", {}).get(
                "qualification_threshold_change", "MORE_DATA"
            ),
            "aggregate_adverse_only_tightening": overlap.get("decision", {}).get(
                "aggregate_adverse_only_tightening", "MORE_DATA"
            ),
            "path_ordered_trap_tightening": overlap.get("decision", {}).get(
                "path_ordered_trap_tightening", "MORE_DATA"
            ),
            "adverse_trap_tightening": adverse.get("decision", {}).get(
                "adverse_trap_tightening", "MORE_DATA"
            ),
            "feature_signature_threshold_change": trap.get("decision", {}).get(
                "qualification_threshold_change", "MORE_DATA"
            ),
            "heartbeat_path_trap_tightening": heartbeat.get("decision", {}).get(
                "adverse_trap_tightening", "MORE_DATA"
            ),
            "signal_count_only_zone_tightening": balance.get("decision", {}).get(
                "signal_count_only_zone_tightening", "REJECT"
            ),
            "zone_specific_threshold_change": balance.get("decision", {}).get(
                "zone_specific_threshold_change", "MORE_DATA"
            ),
            "evidence_weighting": balance.get("decision", {}).get(
                "evidence_weighting", "USE_CONTRACT_BALANCED_ALONGSIDE_RAW"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", nargs="?", help="Collector log; defaults to stdin")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.log:
        lines = Path(args.log).read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        lines = sys.stdin.read().splitlines()
    report = build_report(lines)
    print(json.dumps(report, sort_keys=args.json, indent=None if args.json else 2))
    return 0 if report["preflight"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
