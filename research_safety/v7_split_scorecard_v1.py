#!/usr/bin/env python3
"""Research-only parser and scorecard for LEAD_V7 split-ladder logs.

No network calls. No trading actions. Parses immutable log text and emits
deterministic lane/zone/style/BRTI diagnostics for replay and audit work.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

LANES = ("MOMENTUM_EXPANSION", "ULTRA_CHEAP_REVERSAL")

CANDIDATE_RE = re.compile(
    r"LEAD_V7 CANDIDATE \| lane (?P<lane>[A-Z_]+) \| (?P<ticker>[^|]+?) \| "
    r"(?P<side>UP|DOWN) \| zone (?P<zone>[^|]+?) \| ask (?P<entry>\d+(?:\.\d+)?) .*? \| left (?P<left>\d+(?:\.\d+)?)s"
)
RESULT_RE = re.compile(
    r"LEAD_V7 RESULT \| lane (?P<lane>[A-Z_]+) \| (?P<ticker>[^|]+?) \| "
    r"(?P<side>UP|DOWN) \| zone (?P<zone>[^|]+?) \| style (?P<style>[A-Z_]+) \| "
    r"entry (?P<entry>\d+(?:\.\d+)?) \| max_gain (?P<gain>[+-]?\d+(?:\.\d+)?) \| "
    r"adverse (?P<adverse>[+-]?\d+(?:\.\d+)?) \| to\+5c (?P<t5>[^|]+?) \| "
    r"to\+10c (?P<t10>[^|]+?) \| to\+20c (?P<t20>[^|]+?) \| reprice\+5c (?P<reprice>[^|\s]+)"
)
HEARTBEAT_RE = re.compile(
    r"LEAD_V7 HEARTBEAT \| (?P<ticker>[^|]+?) \| (?P<left>\d+(?:\.\d+)?)m \| "
    r"BTC (?P<btc>\d+(?:\.\d+)?) \| BRTI (?P<brti>N/A|\d+(?:\.\d+)?) \| "
    r"UP (?P<up>\d+(?:\.\d+)?) \| DOWN (?P<down>\d+(?:\.\d+)?) \| pending (?P<pending>\d+)"
)
BRTI_STATS_RE = re.compile(
    r"BRTI BRTI_RESILIENCE \| samples=(?P<samples>\d+) \| primary_ok=(?P<primary_ok>\d+) "
    r"\((?P<primary_pct>\d+(?:\.\d+)?)%\) \| retry_recovered=(?P<retry>\d+) \| "
    r"missing=(?P<missing>\d+) \| errors=(?P<errors>\d+) \| verifier_ok=(?P<verifier_ok>\d+) \| "
    r"verifier_disagree=(?P<verifier_disagree>\d+) \| diag_cache=(?P<diag_cache>\d+)"
)

def maybe_float(text: str) -> Optional[float]:
    text = text.strip()
    return None if text == "None" else float(text)

def price_zone(entry: float) -> str:
    if 0.03 <= entry < 0.07:
        return "3_7C"
    if 0.07 <= entry < 0.15:
        return "7_15C"
    if 0.15 <= entry <= 0.30:
        return "15_30C"
    if 0.30 < entry <= 0.45:
        return "30_45C"
    return "OUTSIDE_STUDY_ZONES"

@dataclass(frozen=True)
class Candidate:
    lane: str
    ticker: str
    side: str
    zone: str
    entry: float
    left: float

@dataclass(frozen=True)
class Result:
    lane: str
    ticker: str
    side: str
    zone: str
    style: str
    entry: float
    gain: float
    adverse: float
    t5: Optional[float]
    t10: Optional[float]
    t20: Optional[float]
    reprice5: Optional[float]

@dataclass(frozen=True)
class Heartbeat:
    ticker: str
    left_min: float
    brti_ok: bool
    pending: int

def parse_lines(lines: Iterable[str]):
    candidates, results, heartbeats, brti_snapshots = [], [], [], []
    for raw in lines:
        line = raw.strip()
        m = CANDIDATE_RE.search(line)
        if m:
            d = m.groupdict()
            candidates.append(Candidate(d["lane"], d["ticker"].strip(), d["side"], d["zone"].strip(), float(d["entry"]), float(d["left"])))
            continue
        m = RESULT_RE.search(line)
        if m:
            d = m.groupdict()
            results.append(Result(d["lane"], d["ticker"].strip(), d["side"], d["zone"].strip(), d["style"], float(d["entry"]), float(d["gain"]), float(d["adverse"]), maybe_float(d["t5"]), maybe_float(d["t10"]), maybe_float(d["t20"]), maybe_float(d["reprice"])))
            continue
        m = HEARTBEAT_RE.search(line)
        if m:
            d = m.groupdict()
            heartbeats.append(Heartbeat(d["ticker"].strip(), float(d["left"]), d["brti"] != "N/A", int(d["pending"])))
        if "BRTI BRTI_RESILIENCE" in line:
            m = BRTI_STATS_RE.search(line)
            if m:
                d = m.groupdict()
                brti_snapshots.append({
                    "samples": int(d["samples"]), "primary_ok": int(d["primary_ok"]), "primary_pct": float(d["primary_pct"]),
                    "retry_recovered": int(d["retry"]), "missing": int(d["missing"]), "errors": int(d["errors"]),
                    "verifier_ok": int(d["verifier_ok"]), "verifier_disagree": int(d["verifier_disagree"]), "diag_cache": int(d["diag_cache"]),
                })
    return candidates, results, heartbeats, brti_snapshots

def _mean(values):
    return None if not values else sum(values) / len(values)

def _median(values):
    return None if not values else statistics.median(values)

def _round(value, digits=4):
    return None if value is None else round(value, digits)

def summarize_results(results):
    n = len(results)
    if not n:
        return {"n": 0, "hit5_pct": None, "hit10_pct": None, "hit20_pct": None, "burst10_pct": None, "expand10_pct": None, "no_expansion_pct": None, "avg_gain": None, "avg_adverse": None, "median_t10_s": None}
    hit5 = sum(r.t5 is not None for r in results)
    hit10 = sum(r.t10 is not None for r in results)
    hit20 = sum(r.t20 is not None for r in results)
    burst10 = sum(r.t10 is not None and r.t10 <= 30 for r in results)
    expand10 = sum(r.t10 is not None and r.t10 <= 120 for r in results)
    no_exp = sum(r.style == "NO_EXPANSION" for r in results)
    t10s = [r.t10 for r in results if r.t10 is not None]
    return {
        "n": n,
        "hit5_pct": round(100 * hit5 / n, 2), "hit10_pct": round(100 * hit10 / n, 2), "hit20_pct": round(100 * hit20 / n, 2),
        "burst10_pct": round(100 * burst10 / n, 2), "expand10_pct": round(100 * expand10 / n, 2), "no_expansion_pct": round(100 * no_exp / n, 2),
        "avg_gain": _round(_mean([r.gain for r in results])), "avg_adverse": _round(_mean([r.adverse for r in results])), "median_t10_s": _round(_median(t10s), 1),
    }

def longest_false_streak(flags):
    longest = current = 0
    for flag in flags:
        if flag:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return longest

def brti_diagnostics(heartbeats, snapshots):
    total = len(heartbeats)
    ok = sum(h.brti_ok for h in heartbeats)
    transitions = sum(a.brti_ok != b.brti_ok for a, b in zip(heartbeats, heartbeats[1:]))
    latest = snapshots[-1] if snapshots else None
    if latest is None:
        failure_class = "NO_RESILIENCE_SNAPSHOT"
    elif latest["missing"] > 0:
        failure_class = "MISSING_AFTER_RETRIES"
    elif latest["errors"] > 0 and latest["retry_recovered"] > 0:
        failure_class = "PRIMARY_ERRORS_WITH_RETRY_RECOVERY"
    elif latest["errors"] > 0:
        failure_class = "PRIMARY_ERRORS"
    else:
        failure_class = "PRIMARY_HEALTHY"
    return {
        "heartbeat_samples": total,
        "heartbeat_brti_ok_pct": None if not total else round(100 * ok / total, 2),
        "heartbeat_na_count": total - ok,
        "max_consecutive_na_heartbeats": longest_false_streak([h.brti_ok for h in heartbeats]),
        "availability_transitions": transitions,
        "latest_resilience": latest,
        "failure_class": failure_class,
    }

def build_scorecard(text: str):
    candidates, results, heartbeats, snapshots = parse_lines(text.splitlines())
    lanes = {}
    for lane in LANES:
        lane_candidates = [c for c in candidates if c.lane == lane]
        lane_results = [r for r in results if r.lane == lane]
        zones = {}
        for zone in sorted(set(price_zone(r.entry) for r in lane_results)):
            zones[zone] = summarize_results([r for r in lane_results if price_zone(r.entry) == zone])
        lanes[lane] = {
            "candidate_count": len(lane_candidates),
            "resolved_count": len(lane_results),
            "unresolved_observed_lower_bound": max(0, len(lane_candidates) - len(lane_results)),
            "overall": summarize_results(lane_results),
            "price_zones": zones,
            "styles": dict(sorted(Counter(r.style for r in lane_results).items())),
            "collector_zones": dict(sorted(Counter(r.zone for r in lane_results).items())),
        }
    return {
        "schema_version": 1,
        "collector_identity": "LEAD_V7",
        "lanes": lanes,
        "resolved_contracts": dict(sorted(Counter(r.ticker for r in results).items())),
        "brti": brti_diagnostics(heartbeats, snapshots),
    }

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("logfile", nargs="?", help="UTF-8 log file; stdin when omitted")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args(argv)
    text = Path(args.logfile).read_text(encoding="utf-8") if args.logfile else sys.stdin.read()
    print(json.dumps(build_scorecard(text), indent=2 if args.pretty else None, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
