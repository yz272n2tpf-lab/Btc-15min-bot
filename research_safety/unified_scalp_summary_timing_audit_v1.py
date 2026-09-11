#!/usr/bin/env python3
"""Research-only summary-timing audit for the CURRENT unified BTC 15m scalp engine.

Detects unified RESULT rows emitted after the same contract's advisory
CONTRACT_SUMMARY/CUMULATIVE rows. RESULT remains the scoring authority; summaries
are diagnostic only. This tool never changes qualification thresholds, never
creates a cheaper evidence path, never places trades, and never promotes production.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

UNIFIED_LANE = "MOMENTUM_EXPANSION"
LEGACY_LANE = "ULTRA_CHEAP_REVERSAL"

RESULT_RE = re.compile(
    r"LEAD_V7 RESULT \| lane (?P<lane>[^|]+) \| (?P<ticker>[^|]+) \|"
)
SUMMARY_RE = re.compile(
    r"LEAD_V7 CONTRACT_SUMMARY \| (?P<ticker>[^|]+) \| MOM n=(?P<mom_n>\d+)"
)
CUMULATIVE_RE = re.compile(
    r"LEAD_V7 CUMULATIVE \| (?P<ticker>[^|]+) \| MOM n=(?P<mom_n>\d+)"
)


def audit_lines(lines: list[str]) -> dict:
    summary_by_ticker: dict[str, tuple[int, int]] = {}
    cumulative_by_ticker: dict[str, tuple[int, int]] = {}
    unified_results: list[tuple[int, str]] = []
    legacy_results = 0
    unknown_lanes = 0

    for index, line in enumerate(lines):
        if match := SUMMARY_RE.search(line):
            summary_by_ticker[match.group("ticker").strip()] = (index, int(match.group("mom_n")))
        if match := CUMULATIVE_RE.search(line):
            cumulative_by_ticker[match.group("ticker").strip()] = (index, int(match.group("mom_n")))
        if match := RESULT_RE.search(line):
            lane = match.group("lane").strip()
            ticker = match.group("ticker").strip()
            if lane == UNIFIED_LANE:
                unified_results.append((index, ticker))
            elif lane == LEGACY_LANE:
                legacy_results += 1
            else:
                unknown_lanes += 1

    late_after_summary = []
    late_after_cumulative = []
    for index, ticker in unified_results:
        summary = summary_by_ticker.get(ticker)
        if summary and index > summary[0]:
            late_after_summary.append({
                "ticker": ticker,
                "result_index": index,
                "summary_index": summary[0],
                "summary_mom_n": summary[1],
            })
        cumulative = cumulative_by_ticker.get(ticker)
        if cumulative and index > cumulative[0]:
            late_after_cumulative.append({
                "ticker": ticker,
                "result_index": index,
                "cumulative_index": cumulative[0],
                "cumulative_mom_n": cumulative[1],
            })

    regression = bool(late_after_summary or late_after_cumulative)
    return {
        "schema": "unified-scalp-summary-timing-audit-v1",
        "current_architecture": "ONE_UNIFIED_SCALP_EXPANSION_ENGINE",
        "research_only": True,
        "signal_only": True,
        "production_promotion": "NOT_PERFORMED",
        "qualification_thresholds_changed": False,
        "cheap_price_evidence_override": False,
        "result_stream_authority": True,
        "contract_summary_authority": False,
        "unified_results": len(unified_results),
        "legacy_reversal_research_only": legacy_results,
        "unknown_lane_results": unknown_lanes,
        "late_unified_results_after_contract_summary": len(late_after_summary),
        "late_unified_results_after_cumulative": len(late_after_cumulative),
        "late_after_contract_summary": late_after_summary,
        "late_after_cumulative": late_after_cumulative,
        "summary_timing_regression_detected": regression,
        "decision": {
            "unified_scalp_expansion_engine": "KEEP",
            "separate_ultra_cheap_graduation_path": "REJECT",
            "qualification_threshold_change": "MORE_DATA",
            "result_stream_authority": "KEEP",
            "advisory_summary_as_scoring_authority": "REJECT",
            "summary_timing_auditor": "TIGHTEN" if regression else "KEEP",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", nargs="?", help="Collector log; defaults to stdin")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    lines = (
        Path(args.log).read_text(encoding="utf-8", errors="replace").splitlines()
        if args.log else sys.stdin.read().splitlines()
    )
    report = audit_lines(lines)
    print(json.dumps(report, sort_keys=args.json, indent=None if args.json else 2))
    return 0 if report["unknown_lane_results"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
