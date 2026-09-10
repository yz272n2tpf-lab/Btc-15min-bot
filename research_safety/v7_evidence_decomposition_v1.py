#!/usr/bin/env python3
"""Research-only V7 evidence decomposition for split-ladder logs.

This module never imports or executes the live collector. It parses immutable
LEAD_V7 RESULT/CONTRACT_SUMMARY text to expose lane, price-zone, speed, contract
clustering, and late-result attribution evidence for freeze/finalization review.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

LANES = ("MOMENTUM_EXPANSION", "ULTRA_CHEAP_REVERSAL")

RESULT_RE = re.compile(
    r"LEAD_V7 RESULT \| lane (?P<lane>[A-Z_]+) \| (?P<ticker>[^|]+?) \| "
    r"(?P<side>UP|DOWN) \| zone (?P<zone>[^|]+?) \| style (?P<style>[A-Z_]+) \| "
    r"entry (?P<entry>\d+(?:\.\d+)?) \| max_gain (?P<gain>[+-]?\d+(?:\.\d+)?) \| "
    r"adverse (?P<adverse>[+-]?\d+(?:\.\d+)?) \| to\+5c (?P<t5>[^|]+?) \| "
    r"to\+10c (?P<t10>[^|]+?) \| to\+20c (?P<t20>[^|]+?) \| reprice\+5c (?P<reprice>[^|\s]+)"
)
SUMMARY_RE = re.compile(r"LEAD_V7 CONTRACT_SUMMARY \| (?P<ticker>[^|]+?) \|")


def _maybe_float(text: str) -> Optional[float]:
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


def parse_result(line: str) -> Optional[Result]:
    m = RESULT_RE.search(line)
    if not m:
        return None
    d = m.groupdict()
    return Result(
        d["lane"], d["ticker"].strip(), d["side"], d["zone"].strip(), d["style"],
        float(d["entry"]), float(d["gain"]), float(d["adverse"]),
        _maybe_float(d["t5"]), _maybe_float(d["t10"]), _maybe_float(d["t20"]),
        _maybe_float(d["reprice"]),
    )


def parse_lines(lines: Iterable[str]):
    results = []
    summarized = set()
    late = []
    for raw in lines:
        line = raw.strip()
        sm = SUMMARY_RE.search(line)
        if sm:
            summarized.add(sm.group("ticker").strip())
        r = parse_result(line)
        if r is not None:
            results.append(r)
            if r.ticker in summarized:
                late.append(r)
    return results, late


def _pct(n: int, d: int):
    return None if d == 0 else round(100.0 * n / d, 2)


def _avg(values):
    values = list(values)
    return None if not values else round(sum(values) / len(values), 4)


def _bucket(rows):
    rows = list(rows)
    n = len(rows)
    burst = sum(r.t10 is not None and r.t10 <= 30.0 for r in rows)
    fast = sum(r.t10 is not None and 30.0 < r.t10 < 60.0 for r in rows)
    expansion_1_3m = sum(r.t10 is not None and 60.0 <= r.t10 <= 180.0 for r in rows)
    within_3m = sum(r.t10 is not None and r.t10 <= 180.0 for r in rows)
    return {
        "n": n,
        "hit5_pct": _pct(sum(r.t5 is not None for r in rows), n),
        "hit10_pct": _pct(sum(r.t10 is not None for r in rows), n),
        "hit20_pct": _pct(sum(r.t20 is not None for r in rows), n),
        "burst_0_30s_pct": _pct(burst, n),
        "fast_30_60s_pct": _pct(fast, n),
        "expansion_1_3m_pct": _pct(expansion_1_3m, n),
        "hit10_within_3m_pct": _pct(within_3m, n),
        "no_10c_within_3m_pct": _pct(n - within_3m, n),
        "avg_gain": _avg(r.gain for r in rows),
        "avg_adverse": _avg(r.adverse for r in rows),
    }


def _group(rows, key):
    groups = defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    return {name: _bucket(groups[name]) for name in sorted(groups)}


def _lane(rows):
    rows = list(rows)
    contract_counts = Counter(r.ticker for r in rows)
    return {
        "overall": _bucket(rows),
        "unique_contracts": len(contract_counts),
        "samples_per_contract": dict(sorted(contract_counts.items())),
        "repeated_within_contract": any(v > 1 for v in contract_counts.values()),
        "max_samples_in_one_contract": max(contract_counts.values(), default=0),
        "largest_contract_share_pct": None if not rows else round(100.0 * max(contract_counts.values()) / len(rows), 2),
        "price_zones": _group(rows, lambda r: price_zone(r.entry)),
        "collector_zones": _group(rows, lambda r: r.zone),
        "styles": dict(sorted(Counter(r.style for r in rows).items())),
        "contracts": _group(rows, lambda r: r.ticker),
    }


def build_decomposition(text: str):
    results, late = parse_lines(text.splitlines())
    return {
        "schema_version": 1,
        "collector_identity": "LEAD_V7",
        "lanes": {lane: _lane(r for r in results if r.lane == lane) for lane in LANES},
        "result_count": len(results),
        "unique_contracts": len({r.ticker for r in results}),
        "late_results_after_contract_summary": {
            "count": len(late),
            "by_lane": dict(sorted(Counter(r.lane for r in late).items())),
            "by_contract": dict(sorted(Counter(r.ticker for r in late).items())),
            "collector_summary_stale_risk": bool(late),
        },
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("logfile", nargs="?", help="UTF-8 V7 log file; stdin when omitted")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args(argv)
    text = Path(args.logfile).read_text(encoding="utf-8") if args.logfile else sys.stdin.read()
    print(json.dumps(build_decomposition(text), indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
