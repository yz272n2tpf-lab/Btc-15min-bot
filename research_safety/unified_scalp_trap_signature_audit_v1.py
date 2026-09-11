#!/usr/bin/env python3
"""Research-only trap-signature audit for the CURRENT unified BTC 15m scalp engine.

Pairs unified candidate feature snapshots with their RESULT rows and compares
successful temporary +10c expansions with failures.  The output is descriptive
only: it never changes qualification thresholds, never creates a cheaper evidence
path, never places trades, and never promotes production.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

MIN_RESEARCH_PRICE = 0.03
MAX_RESEARCH_PRICE = 0.45
EXPANSION_WINDOW_SECONDS = 180.0
ENTRY_MATCH_TOLERANCE = 0.0015
UNIFIED_LANE = "MOMENTUM_EXPANSION"
LEGACY_LANE = "ULTRA_CHEAP_REVERSAL"

CANDIDATE_RE = re.compile(
    r"LEAD_V7 CANDIDATE \| lane (?P<lane>[^|]+) \| (?P<ticker>[^|]+) \| (?P<side>UP|DOWN) "
    r"\| zone (?P<zone>[^|]+) \| ask (?P<entry>[-+0-9.]+) "
    r"\| btc5 (?P<btc5>[-+0-9.]+) \| btc15 (?P<btc15>[-+0-9.]+) "
    r"\| btc30 (?P<btc30>[-+0-9.]+) \| accel (?P<accel>[-+0-9.]+) "
    r"\| brti5 (?P<brti5>[-+0-9.]+) \| brti15 (?P<brti15>[-+0-9.]+) "
    r"\| ask5 (?P<ask5>[-+0-9.]+) \| ask15 (?P<ask15>[-+0-9.]+) "
    r"\| left (?P<left>[-+0-9.]+)s"
)
RESULT_RE = re.compile(
    r"LEAD_V7 RESULT \| lane (?P<lane>[^|]+) \| (?P<ticker>[^|]+) \| (?P<side>UP|DOWN) "
    r"\| zone (?P<zone>[^|]+) \| style (?P<style>[^|]+) \| entry (?P<entry>[-+0-9.]+) "
    r"\| max_gain (?P<gain>[-+0-9.]+) \| adverse (?P<adverse>[-+0-9.]+) "
    r"\| to\+5c (?P<t5>\S+) \| to\+10c (?P<t10>\S+)"
)

FEATURES = (
    "btc5", "btc15", "btc30", "accel", "brti5", "brti15", "ask5", "ask15", "left_seconds"
)


@dataclass(frozen=True)
class Candidate:
    index: int
    ticker: str
    side: str
    entry: float
    zone: str
    btc5: float
    btc15: float
    btc30: float
    accel: float
    brti5: float
    brti15: float
    ask5: float
    ask15: float
    left_seconds: float


@dataclass(frozen=True)
class Result:
    index: int
    ticker: str
    side: str
    entry: float
    style: str
    max_gain: float
    adverse: float
    t10: float | None


def _none_or_float(value: str) -> float | None:
    return None if value == "None" else float(value)


def price_zone(entry: float) -> str:
    if entry < MIN_RESEARCH_PRICE or entry > MAX_RESEARCH_PRICE:
        return "OUT_OF_RANGE"
    if entry < 0.07:
        return "3_7C"
    if entry < 0.15:
        return "7_15C"
    if entry < 0.30:
        return "15_30C"
    return "30_45C"


def parse_lines(lines: Iterable[str]):
    candidates: list[Candidate] = []
    results: list[Result] = []
    legacy_candidate_count = 0
    legacy_result_count = 0
    unknown_lane_records = 0

    for index, line in enumerate(lines):
        if match := CANDIDATE_RE.search(line):
            lane = match.group("lane").strip()
            if lane == LEGACY_LANE:
                legacy_candidate_count += 1
                continue
            if lane != UNIFIED_LANE:
                unknown_lane_records += 1
                continue
            candidates.append(Candidate(
                index=index,
                ticker=match.group("ticker").strip(),
                side=match.group("side"),
                entry=float(match.group("entry")),
                zone=match.group("zone").strip(),
                btc5=float(match.group("btc5")),
                btc15=float(match.group("btc15")),
                btc30=float(match.group("btc30")),
                accel=float(match.group("accel")),
                brti5=float(match.group("brti5")),
                brti15=float(match.group("brti15")),
                ask5=float(match.group("ask5")),
                ask15=float(match.group("ask15")),
                left_seconds=float(match.group("left")),
            ))
            continue

        if match := RESULT_RE.search(line):
            lane = match.group("lane").strip()
            if lane == LEGACY_LANE:
                legacy_result_count += 1
                continue
            if lane != UNIFIED_LANE:
                unknown_lane_records += 1
                continue
            results.append(Result(
                index=index,
                ticker=match.group("ticker").strip(),
                side=match.group("side"),
                entry=float(match.group("entry")),
                style=match.group("style").strip(),
                max_gain=float(match.group("gain")),
                adverse=float(match.group("adverse")),
                t10=_none_or_float(match.group("t10")),
            ))

    return candidates, results, legacy_candidate_count, legacy_result_count, unknown_lane_records


def _match_pairs(candidates: list[Candidate], results: list[Result]):
    used: set[int] = set()
    pairs: list[tuple[Candidate, Result]] = []
    unmatched_results: list[Result] = []

    for result in results:
        matches = [
            (i, candidate)
            for i, candidate in enumerate(candidates)
            if i not in used
            and candidate.index < result.index
            and candidate.ticker == result.ticker
            and candidate.side == result.side
            and abs(candidate.entry - result.entry) <= ENTRY_MATCH_TOLERANCE
        ]
        if not matches:
            unmatched_results.append(result)
            continue
        # Same-price candidates can legitimately repeat. Among exact-compatible
        # predecessors, FIFO is the least-assumptive deterministic attribution.
        match_index, candidate = min(matches, key=lambda item: item[1].index)
        used.add(match_index)
        pairs.append((candidate, result))

    unmatched_candidates = [candidate for i, candidate in enumerate(candidates) if i not in used]
    return pairs, unmatched_candidates, unmatched_results


def _feature_summary(rows: list[Candidate]) -> dict:
    out: dict[str, dict[str, float | int | None]] = {}
    for feature in FEATURES:
        values = [float(getattr(row, feature)) for row in rows]
        out[feature] = {
            "n": len(values),
            "mean": statistics.fmean(values) if values else None,
            "median": statistics.median(values) if values else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
        }
    return out


def _flag_counts(pairs: list[tuple[Candidate, Result]], predicate) -> dict[str, int | str]:
    success = failure = 0
    for candidate, result in pairs:
        if not predicate(candidate):
            continue
        is_success = result.t10 is not None and result.t10 <= EXPANSION_WINDOW_SECONDS
        if is_success:
            success += 1
        else:
            failure += 1
    if success and failure:
        separation = "NON_SEPARATING_COUNTEREXAMPLES_PRESENT"
    elif success:
        separation = "SUCCESS_ONLY_IN_CURRENT_SAMPLE"
    elif failure:
        separation = "FAILURE_ONLY_IN_CURRENT_SAMPLE"
    else:
        separation = "NO_OBSERVATIONS"
    return {"success": success, "failure": failure, "assessment": separation}


def audit_lines(lines: list[str]) -> dict:
    candidates, results, legacy_candidates, legacy_results, unknown_lanes = parse_lines(lines)
    pairs, unmatched_candidates, unmatched_results = _match_pairs(candidates, results)

    successes = [(c, r) for c, r in pairs if r.t10 is not None and r.t10 <= EXPANSION_WINDOW_SECONDS]
    failures = [(c, r) for c, r in pairs if not (r.t10 is not None and r.t10 <= EXPANSION_WINDOW_SECONDS)]
    success_candidates = [c for c, _ in successes]
    failure_candidates = [c for c, _ in failures]

    success_summary = _feature_summary(success_candidates)
    failure_summary = _feature_summary(failure_candidates)
    contrasts = {}
    for feature in FEATURES:
        success_mean = success_summary[feature]["mean"]
        failure_mean = failure_summary[feature]["mean"]
        contrasts[feature] = (
            success_mean - failure_mean
            if success_mean is not None and failure_mean is not None
            else None
        )

    zones: dict[str, dict[str, float | int | None]] = {}
    for zone in ("3_7C", "7_15C", "15_30C", "30_45C", "OUT_OF_RANGE"):
        zpairs = [(c, r) for c, r in pairs if price_zone(c.entry) == zone]
        if not zpairs:
            continue
        hits = sum(1 for _, r in zpairs if r.t10 is not None and r.t10 <= EXPANSION_WINDOW_SECONDS)
        zones[zone] = {
            "n": len(zpairs),
            "hit10": hits,
            "hit10_rate": hits / len(zpairs),
            "avg_max_gain": statistics.fmean(r.max_gain for _, r in zpairs),
            "avg_adverse": statistics.fmean(r.adverse for _, r in zpairs),
        }

    matched_rows = []
    for candidate, result in pairs:
        matched_rows.append({
            "candidate": asdict(candidate),
            "result": asdict(result),
            "diagnostic_price_zone": price_zone(candidate.entry),
            "hit10_in_180s": result.t10 is not None and result.t10 <= EXPANSION_WINDOW_SECONDS,
        })

    simple_counterexamples = {
        "ask15_negative": _flag_counts(pairs, lambda c: c.ask15 < 0),
        "brti5_below_btc5": _flag_counts(pairs, lambda c: c.brti5 < c.btc5),
        "btc5_below_btc15": _flag_counts(pairs, lambda c: c.btc5 < c.btc15),
    }

    return {
        "schema": "unified-scalp-trap-signature-audit-v1",
        "current_architecture": "ONE_UNIFIED_SCALP_EXPANSION_ENGINE",
        "research_only": True,
        "signal_only": True,
        "exploratory_only": True,
        "production_promotion": "NOT_PERFORMED",
        "threshold_change_performed": False,
        "price_zone_is_diagnostic_only": True,
        "cheap_price_override": False,
        "expansion_window_seconds": EXPANSION_WINDOW_SECONDS,
        "unified_candidates": len(candidates),
        "unified_results": len(results),
        "matched_results": len(pairs),
        "unmatched_candidates": len(unmatched_candidates),
        "unmatched_results": len(unmatched_results),
        "legacy_reversal_candidates_research_only": legacy_candidates,
        "legacy_reversal_results_research_only": legacy_results,
        "unknown_lane_records": unknown_lanes,
        "success_n": len(successes),
        "failure_n": len(failures),
        "success_feature_summary": success_summary,
        "failure_feature_summary": failure_summary,
        "success_minus_failure_mean": contrasts,
        "simple_filter_counterexamples": simple_counterexamples,
        "zones": zones,
        "matched": matched_rows,
        "decision": {
            "unified_scalp_expansion_engine": "KEEP",
            "separate_ultra_cheap_graduation_path": "REJECT",
            "qualification_threshold_change": "MORE_DATA",
            "adverse_trap_tightening": "MORE_DATA",
            "reason": (
                "Candidate/RESULT contrasts are exploratory diagnostics. A feature may describe current failures "
                "without being a safe separator; counterexamples must be preserved before any tightening proposal."
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
        if args.log else sys.stdin.read().splitlines()
    )
    report = audit_lines(lines)
    print(json.dumps(report, sort_keys=args.json, indent=None if args.json else 2))
    return 0 if report["unknown_lane_records"] == 0 and report["unmatched_results"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
