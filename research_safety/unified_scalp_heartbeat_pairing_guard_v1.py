#!/usr/bin/env python3
"""Research-only pairing guard for the CURRENT unified BTC 15m scalp engine.

Compares the heartbeat path auditor's historical destructive FIFO candidate/result
matching pattern with a non-destructive deterministic matcher. This catches false
UNMATCHED_RESULT classifications when results complete out of entry order. The
guard is descriptive only: it never changes qualification thresholds, never lowers
the evidence standard for cheap entries, never places trades, and never promotes
production.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

from unified_scalp_heartbeat_path_audit_v1 import (
    ENTRY_MATCH_TOLERANCE,
    Candidate,
    Result,
    parse_lines,
)

UNIFIED_LANE = "MOMENTUM_EXPANSION"


def _compatible(candidate: Candidate, result: Result) -> bool:
    return (
        candidate.index < result.index
        and candidate.ticker == result.ticker
        and candidate.side == result.side
        and abs(candidate.entry - result.entry) <= ENTRY_MATCH_TOLERANCE
    )


def _robust_match(candidates: list[Candidate], results: list[Result]) -> tuple[set[int], set[int]]:
    """Return matched candidate/result indices without consuming non-matches."""
    used_candidates: set[int] = set()
    matched_results: set[int] = set()
    for result in results:
        compatible = [
            candidate
            for candidate in candidates
            if candidate.index not in used_candidates and _compatible(candidate, result)
        ]
        if not compatible:
            continue
        candidate = min(compatible, key=lambda row: row.index)
        used_candidates.add(candidate.index)
        matched_results.add(result.index)
    return used_candidates, matched_results


def _destructive_fifo_match(candidates: list[Candidate], results: list[Result]) -> tuple[set[int], set[int]]:
    """Simulate the legacy heartbeat matcher exactly enough to expose candidate loss."""
    pending: dict[tuple[str, str], deque[Candidate]] = defaultdict(deque)
    for candidate in candidates:
        pending[(candidate.ticker, candidate.side)].append(candidate)

    matched_candidates: set[int] = set()
    matched_results: set[int] = set()
    for result in results:
        queue = pending[(result.ticker, result.side)]
        while queue:
            probe = queue[0]
            if probe.index >= result.index:
                break
            queue.popleft()
            if abs(probe.entry - result.entry) <= ENTRY_MATCH_TOLERANCE:
                matched_candidates.add(probe.index)
                matched_results.add(result.index)
                break
    return matched_candidates, matched_results


def audit_lines(lines: list[str]) -> dict:
    candidates, _heartbeats, parsed_results, unknown_lanes, legacy_results = parse_lines(lines)
    results = [result for result in parsed_results if result.lane == UNIFIED_LANE]

    robust_candidates, robust_results = _robust_match(candidates, results)
    fifo_candidates, fifo_results = _destructive_fifo_match(candidates, results)

    robust_unmatched = [result for result in results if result.index not in robust_results]
    fifo_unmatched = [result for result in results if result.index not in fifo_results]
    false_unmatched = [
        result for result in results
        if result.index in robust_results and result.index not in fifo_results
    ]

    lost_candidate_indices = sorted(robust_candidates - fifo_candidates)
    false_unmatched_rows = [
        {
            "result_index": result.index,
            "ticker": result.ticker,
            "side": result.side,
            "entry": result.entry,
        }
        for result in false_unmatched
    ]

    regression_detected = bool(false_unmatched or lost_candidate_indices)
    return {
        "schema": "unified-scalp-heartbeat-pairing-guard-v1",
        "current_architecture": "ONE_UNIFIED_SCALP_EXPANSION_ENGINE",
        "research_only": True,
        "signal_only": True,
        "production_promotion": "NOT_PERFORMED",
        "qualification_thresholds_changed": False,
        "cheap_price_evidence_override": False,
        "legacy_reversal_research_only": legacy_results,
        "unknown_lane_records": unknown_lanes,
        "unified_candidates": len(candidates),
        "unified_results": len(results),
        "robust_matched_results": len(robust_results),
        "robust_unmatched_results": len(robust_unmatched),
        "destructive_fifo_matched_results": len(fifo_results),
        "destructive_fifo_unmatched_results": len(fifo_unmatched),
        "false_unmatched_results_from_destructive_fifo": len(false_unmatched),
        "lost_candidate_indices_from_destructive_fifo": lost_candidate_indices,
        "false_unmatched": false_unmatched_rows,
        "pairing_regression_detected": regression_detected,
        "decision": {
            "unified_scalp_expansion_engine": "KEEP",
            "separate_ultra_cheap_graduation_path": "REJECT",
            "qualification_threshold_change": "MORE_DATA",
            "heartbeat_pairing_auditor": "TIGHTEN" if regression_detected else "KEEP",
            "reason": (
                "Tighten research-only pairing attribution; do not change trading qualification."
                if regression_detected
                else "No destructive-FIFO pairing loss detected in this evidence set."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", nargs="?", help="Collector log; defaults to stdin")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    lines = (
        Path(args.log).read_text(encoding="utf-8", errors="replace").splitlines()
        if args.log
        else sys.stdin.read().splitlines()
    )
    report = audit_lines(lines)
    print(json.dumps(report, sort_keys=args.json, indent=None if args.json else 2))
    return 0 if report["unknown_lane_records"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
