#!/usr/bin/env python3
"""Research-only outcome-overlap audit for the CURRENT unified BTC 15m scalp engine.

Consumes RESULT lines only and asks one narrow question: can aggregate adverse
excursion safely separate temporary +10c expansions from failures? It never
changes qualification thresholds, never lowers evidence standards for cheap
entries, never graduates the legacy ultra-cheap reversal experiment, never
places trades, and never promotes production.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

UNIFIED_LANE = "MOMENTUM_EXPANSION"
LEGACY_LANE = "ULTRA_CHEAP_REVERSAL"
EXPANSION_WINDOW_SECONDS = 180.0
MIN_RESEARCH_PRICE = 0.03
MAX_RESEARCH_PRICE = 0.45

RESULT_RE = re.compile(
    r"LEAD_V7 RESULT \| lane (?P<lane>[^|]+) \| (?P<ticker>[^|]+) \| (?P<side>UP|DOWN) "
    r"\| zone (?P<zone>[^|]+) \| style (?P<style>[^|]+) \| entry (?P<entry>[-+0-9.]+) "
    r"\| max_gain (?P<gain>[-+0-9.]+) \| adverse (?P<adverse>[-+0-9.]+) "
    r"\| to\+5c (?P<t5>\S+) \| to\+10c (?P<t10>\S+)"
)


@dataclass(frozen=True)
class Result:
    ticker: str
    side: str
    lane: str
    entry: float
    gain: float
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


def parse_result_line(line: str) -> Result | None:
    match = RESULT_RE.search(line)
    if not match:
        return None
    return Result(
        ticker=match.group("ticker").strip(),
        side=match.group("side"),
        lane=match.group("lane").strip(),
        entry=float(match.group("entry")),
        gain=float(match.group("gain")),
        adverse=float(match.group("adverse")),
        t10=_none_or_float(match.group("t10")),
    )


def _summary(values: list[float]) -> dict[str, float | int | None]:
    return {
        "n": len(values),
        "mean": statistics.fmean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def audit_lines(lines: Iterable[str]) -> dict:
    parsed = [p for line in lines if (p := parse_result_line(line)) is not None]
    unified = [p for p in parsed if p.lane == UNIFIED_LANE]
    legacy = [p for p in parsed if p.lane == LEGACY_LANE]
    unknown = [p for p in parsed if p.lane not in {UNIFIED_LANE, LEGACY_LANE}]

    successes = [p for p in unified if p.t10 is not None and p.t10 <= EXPANSION_WINDOW_SECONDS]
    failures = [p for p in unified if not (p.t10 is not None and p.t10 <= EXPANSION_WINDOW_SECONDS)]

    success_adverse = [p.adverse for p in successes]
    failure_adverse = [p.adverse for p in failures]
    success_gain = [p.gain for p in successes]
    failure_gain = [p.gain for p in failures]

    # Because adverse values are <= 0, a more-negative value is a worse excursion.
    # Every success/failure ordering inversion is a direct counterexample to using
    # aggregate adverse magnitude as a monotonic qualification gate by itself.
    ordering_counterexamples = [
        {
            "success_ticker": s.ticker,
            "success_entry": s.entry,
            "success_adverse": s.adverse,
            "failure_ticker": f.ticker,
            "failure_entry": f.entry,
            "failure_adverse": f.adverse,
        }
        for s in successes
        for f in failures
        if s.adverse < f.adverse
    ]

    zones: dict[str, dict[str, float | int | None]] = {}
    by_zone: dict[str, list[Result]] = defaultdict(list)
    for row in unified:
        by_zone[price_zone(row.entry)].append(row)
    for zone, rows in sorted(by_zone.items()):
        hits = [r for r in rows if r.t10 is not None and r.t10 <= EXPANSION_WINDOW_SECONDS]
        zones[zone] = {
            "n": len(rows),
            "hit10": len(hits),
            "hit10_rate": len(hits) / len(rows),
            "avg_gain": statistics.fmean(r.gain for r in rows),
            "avg_adverse": statistics.fmean(r.adverse for r in rows),
            "diagnostic_only": True,
            "evidence_standard": "UNIFIED_SAME_STANDARD_ALL_PRICES",
        }

    assessment = (
        "NON_SEPARATING_COUNTEREXAMPLES_PRESENT"
        if ordering_counterexamples
        else "NO_ORDERING_COUNTEREXAMPLE_IN_CURRENT_SAMPLE"
    )

    return {
        "schema": "unified-scalp-outcome-overlap-audit-v1",
        "research_only": True,
        "signal_only": True,
        "result_stream_authority": True,
        "production_promotion": "NOT_PERFORMED",
        "qualification_thresholds_changed": False,
        "cheap_price_evidence_override": False,
        "legacy_ultra_cheap_graduation": "REJECT",
        "parsed_results": len(parsed),
        "unified_results": len(unified),
        "legacy_reversal_research_only": len(legacy),
        "unknown_lane_results": len(unknown),
        "successes_hit10_within_180s": len(successes),
        "failures_no_hit10_within_180s": len(failures),
        "success_adverse": _summary(success_adverse),
        "failure_adverse": _summary(failure_adverse),
        "success_gain": _summary(success_gain),
        "failure_gain": _summary(failure_gain),
        "aggregate_adverse_gate_assessment": assessment,
        "aggregate_adverse_ordering_counterexample_count": len(ordering_counterexamples),
        "aggregate_adverse_ordering_counterexamples": ordering_counterexamples[:25],
        "price_zones": zones,
        "decision": {
            "unified_scalp_expansion_path": "KEEP",
            "separate_ultra_cheap_graduation_path": "REJECT",
            "aggregate_adverse_only_tightening": (
                "REJECT" if ordering_counterexamples else "MORE_DATA"
            ),
            "path_ordered_trap_tightening": "MORE_DATA",
            "qualification_threshold_change": "MORE_DATA",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", nargs="?", help="Log file; defaults to stdin")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.log:
        lines = Path(args.log).read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        lines = sys.stdin.read().splitlines()
    report = audit_lines(lines)
    print(json.dumps(report, sort_keys=args.json, indent=None if args.json else 2))
    return 0 if report["unknown_lane_results"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
