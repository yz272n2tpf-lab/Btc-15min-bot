#!/usr/bin/env python3
"""One-command research report for the CURRENT unified BTC 15m scalp engine.

Consumes archived/live collector text, treats RESULT rows as scoring authority,
keeps legacy ultra-cheap reversal observations audit-only, combines unified
price/speed scoring with adverse-path ordering diagnostics, and fails closed on
any architecture invariant breach. This file cannot place trades or promote
production.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from unified_scalp_adverse_path_audit_v1 import audit_lines
from unified_scalp_result_scorecard_v1 import score_lines


def build_report(lines: list[str]) -> dict:
    score = score_lines(lines)
    adverse = audit_lines(lines)

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
        "legacy_counts_agree": (
            score.get("legacy_reversal_research_only")
            == adverse.get("legacy_reversal_research_only")
        ),
        "unified_counts_agree": score.get("unified_results") == adverse.get("unified_results"),
        "unified_path_keep": (
            score.get("architecture", {}).get("unified_scalp_expansion_path") == "KEEP"
            and adverse.get("decision", {}).get("unified_scalp_expansion_path") == "KEEP"
        ),
        "separate_cheap_path_rejected": (
            score.get("architecture", {}).get("separate_ultra_cheap_graduation_path") == "REJECT"
            and adverse.get("decision", {}).get("separate_ultra_cheap_graduation_path") == "REJECT"
        ),
    }
    preflight = "PASS" if all(checks.values()) else "FAIL"

    return {
        "schema": "unified-scalp-final-report-v1",
        "current_architecture": "ONE_UNIFIED_SCALP_EXPANSION_ENGINE",
        "research_only": True,
        "signal_only": True,
        "production_promotion": "NOT_PERFORMED",
        "preflight": preflight,
        "checks": checks,
        "scorecard": score,
        "adverse_path_audit": adverse,
        "decisions": {
            "unified_scalp_expansion_engine": "KEEP",
            "separate_ultra_cheap_graduation_path": "REJECT",
            "qualification_threshold_change": score.get("architecture", {}).get(
                "qualification_threshold_change", "MORE_DATA"
            ),
            "adverse_trap_tightening": adverse.get("decision", {}).get(
                "adverse_trap_tightening", "MORE_DATA"
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
