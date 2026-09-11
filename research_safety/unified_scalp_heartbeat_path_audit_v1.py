#!/usr/bin/env python3
"""Research-only heartbeat path-order audit for the CURRENT unified BTC 15m scalp engine.

Reconstructs a coarse, timestamp-free path from candidate time-left and heartbeat
time-left fields. This lets research distinguish adverse movement sampled before a
+10c expansion from adverse movement that may have happened later. Heartbeats are
only a coarse lower-bound sample of the true path, so this auditor never changes
qualification thresholds or promotes production.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

MIN_RESEARCH_PRICE = 0.03
MAX_RESEARCH_PRICE = 0.45
EXPANSION_WINDOW_SECONDS = 180.0
ENTRY_MATCH_TOLERANCE = 0.0015

CANDIDATE_RE = re.compile(
    r"LEAD_V7 CANDIDATE \| lane (?P<lane>[^|]+) \| (?P<ticker>[^|]+) \| (?P<side>UP|DOWN) "
    r"\| zone (?P<zone>[^|]+) \| ask (?P<entry>[-+0-9.]+).*?\| left (?P<left>[-+0-9.]+)s"
)
HEARTBEAT_RE = re.compile(
    r"LEAD_V7 HEARTBEAT \| (?P<ticker>[^|]+) \| (?P<left>[-+0-9.]+)m .*?"
    r"\| UP (?P<up>[-+0-9.]+) \| DOWN (?P<down>[-+0-9.]+) \| pending"
)
RESULT_RE = re.compile(
    r"LEAD_V7 RESULT \| lane (?P<lane>[^|]+) \| (?P<ticker>[^|]+) \| (?P<side>UP|DOWN) "
    r"\| zone (?P<zone>[^|]+) \| style (?P<style>[^|]+) \| entry (?P<entry>[-+0-9.]+) "
    r"\| max_gain (?P<gain>[-+0-9.]+) \| adverse (?P<adverse>[-+0-9.]+) "
    r"\| to\+5c (?P<t5>\S+) \| to\+10c (?P<t10>\S+)"
)

@dataclass(frozen=True)
class Candidate:
    index: int
    ticker: str
    side: str
    entry: float
    left_seconds: float

@dataclass(frozen=True)
class Heartbeat:
    index: int
    ticker: str
    left_seconds: float
    up: float
    down: float

@dataclass(frozen=True)
class Result:
    index: int
    lane: str
    ticker: str
    side: str
    entry: float
    t10: float | None
    gain: float
    adverse: float


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


def parse_lines(lines: list[str]):
    candidates: list[Candidate] = []
    heartbeats: list[Heartbeat] = []
    results: list[Result] = []
    unknown_lanes = 0
    legacy_results = 0
    for i, line in enumerate(lines):
        if m := CANDIDATE_RE.search(line):
            lane = m.group("lane").strip()
            if lane == "MOMENTUM_EXPANSION":
                candidates.append(Candidate(i, m.group("ticker").strip(), m.group("side"), float(m.group("entry")), float(m.group("left"))))
            elif lane == "ULTRA_CHEAP_REVERSAL":
                pass
            else:
                unknown_lanes += 1
            continue
        if m := HEARTBEAT_RE.search(line):
            heartbeats.append(Heartbeat(i, m.group("ticker").strip(), float(m.group("left")) * 60.0, float(m.group("up")), float(m.group("down"))))
            continue
        if m := RESULT_RE.search(line):
            lane = m.group("lane").strip()
            if lane == "ULTRA_CHEAP_REVERSAL":
                legacy_results += 1
            elif lane != "MOMENTUM_EXPANSION":
                unknown_lanes += 1
            results.append(Result(i, lane, m.group("ticker").strip(), m.group("side"), float(m.group("entry")), _none_or_float(m.group("t10")), float(m.group("gain")), float(m.group("adverse"))))
    return candidates, heartbeats, results, unknown_lanes, legacy_results


def audit_lines(lines: list[str]) -> dict:
    candidates, heartbeats, results, unknown_lanes, legacy_results = parse_lines(lines)
    pending: dict[tuple[str, str], deque[Candidate]] = defaultdict(deque)
    for c in candidates:
        pending[(c.ticker, c.side)].append(c)

    samples_by_ticker: dict[str, list[Heartbeat]] = defaultdict(list)
    for h in heartbeats:
        samples_by_ticker[h.ticker].append(h)

    classifications = defaultdict(int)
    zones = defaultdict(lambda: {
        "matched": 0,
        "success": 0,
        "failure": 0,
        "success_with_sampled_pre_target_adverse": 0,
        "success_without_sampled_pre_target_adverse": 0,
        "failure_with_sampled_adverse": 0,
        "observed_pre_target_adverse_sum": 0.0,
        "observed_pre_target_adverse_n": 0,
        "worst_observed_pre_target_adverse": None,
    })
    matched_rows = []
    unmatched_results = 0

    for r in results:
        if r.lane != "MOMENTUM_EXPANSION":
            continue
        q = pending[(r.ticker, r.side)]
        c = None
        while q:
            probe = q[0]
            if probe.index >= r.index:
                break
            q.popleft()
            if abs(probe.entry - r.entry) <= ENTRY_MATCH_TOLERANCE:
                c = probe
                break
        if c is None:
            unmatched_results += 1
            classifications["UNMATCHED_RESULT"] += 1
            continue

        success = r.t10 is not None and r.t10 <= EXPANSION_WINDOW_SECONDS
        horizon = r.t10 if success else EXPANSION_WINDOW_SECONDS
        observed = []
        for h in samples_by_ticker.get(r.ticker, []):
            if not (c.index < h.index < r.index):
                continue
            elapsed = c.left_seconds - h.left_seconds
            if elapsed < -1.0 or elapsed > horizon + 1.0:
                continue
            side_price = h.up if r.side == "UP" else h.down
            observed.append((elapsed, side_price - c.entry))

        z = price_zone(r.entry)
        bucket = zones[z]
        bucket["matched"] += 1
        if success:
            bucket["success"] += 1
        else:
            bucket["failure"] += 1

        worst = min((delta for _, delta in observed), default=None)
        if worst is not None and worst < 0:
            bucket["observed_pre_target_adverse_sum"] += worst
            bucket["observed_pre_target_adverse_n"] += 1
            prev = bucket["worst_observed_pre_target_adverse"]
            if prev is None or worst < prev:
                bucket["worst_observed_pre_target_adverse"] = worst

        if success:
            if not observed:
                cls = "SUCCESS_NO_PRETARGET_HEARTBEAT"
            elif worst is not None and worst < 0:
                cls = "SUCCESS_PRETARGET_ADVERSE_OBSERVED"
                bucket["success_with_sampled_pre_target_adverse"] += 1
            else:
                cls = "SUCCESS_NO_PRETARGET_ADVERSE_OBSERVED"
                bucket["success_without_sampled_pre_target_adverse"] += 1
        else:
            if not observed:
                cls = "FAILED_NO_WINDOW_HEARTBEAT"
            elif worst is not None and worst < 0:
                cls = "FAILED_WITH_SAMPLED_ADVERSE"
                bucket["failure_with_sampled_adverse"] += 1
            else:
                cls = "FAILED_NO_SAMPLED_ADVERSE"
        classifications[cls] += 1
        matched_rows.append({
            "ticker": r.ticker,
            "side": r.side,
            "entry": r.entry,
            "zone": z,
            "hit10_in_180s": success,
            "t10": r.t10,
            "heartbeat_samples_in_horizon": len(observed),
            "worst_sampled_pre_target_delta": worst,
            "aggregate_result_adverse": r.adverse,
            "classification": cls,
        })

    normalized_zones = {}
    for z, row in zones.items():
        out = dict(row)
        n = out["observed_pre_target_adverse_n"]
        out["avg_observed_pre_target_adverse"] = out["observed_pre_target_adverse_sum"] / n if n else None
        del out["observed_pre_target_adverse_sum"]
        del out["observed_pre_target_adverse_n"]
        normalized_zones[z] = out

    return {
        "schema": "unified-scalp-heartbeat-path-audit-v1",
        "current_architecture": "ONE_UNIFIED_SCALP_EXPANSION_ENGINE",
        "research_only": True,
        "signal_only": True,
        "production_promotion": "NOT_PERFORMED",
        "heartbeat_path_is_coarse_lower_bound": True,
        "expansion_window_seconds": EXPANSION_WINDOW_SECONDS,
        "unified_candidates": len(candidates),
        "unified_results": sum(1 for r in results if r.lane == "MOMENTUM_EXPANSION"),
        "legacy_reversal_research_only": legacy_results,
        "unknown_lane_records": unknown_lanes,
        "matched_results": len(matched_rows),
        "unmatched_results": unmatched_results,
        "classifications": dict(classifications),
        "zones": normalized_zones,
        "matched": matched_rows,
        "decision": {
            "unified_scalp_expansion_engine": "KEEP",
            "separate_ultra_cheap_graduation_path": "REJECT",
            "adverse_trap_tightening": "MORE_DATA",
            "reason": "Heartbeat reconstruction adds pre-target ordering evidence but is only a coarse sampled lower bound; use it to target research, not to alter frozen qualification logic.",
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("log", nargs="?", help="Collector log; defaults to stdin")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    lines = Path(args.log).read_text(encoding="utf-8", errors="replace").splitlines() if args.log else sys.stdin.read().splitlines()
    report = audit_lines(lines)
    print(json.dumps(report, sort_keys=args.json, indent=None if args.json else 2))
    return 0 if report["unknown_lane_records"] == 0 and report["unmatched_results"] == 0 else 2

if __name__ == "__main__":
    raise SystemExit(main())
