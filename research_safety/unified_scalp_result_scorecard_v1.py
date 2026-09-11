#!/usr/bin/env python3
"""Research-only unified scalp scorecard for archived/live RESULT lines.

Historical split-collector RESULT lines are normalized into the current unified
research view. Momentum/expansion observations are scored across price zones;
the failed ultra-cheap reversal source is retained for audit counts but excluded
from graduation evidence. CONTRACT_SUMMARY lines are intentionally ignored.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from unified_scalp_qualification_guard_v1 import (
    LEGACY_REVERSAL_SOURCE,
    UNIFIED_STANDARD,
    QualificationRecord,
    price_zone,
    summarize,
)

RESULT_RE = re.compile(
    r"LEAD_V7 RESULT \| lane (?P<lane>[^|]+) \| (?P<ticker>[^|]+) \| (?P<side>UP|DOWN) "
    r"\| zone (?P<zone>[^|]+) \| style (?P<style>[^|]+) \| entry (?P<entry>[-+0-9.]+) "
    r"\| max_gain (?P<gain>[-+0-9.]+) \| adverse (?P<adverse>[-+0-9.]+) "
    r"\| to\+5c (?P<t5>\S+) \| to\+10c (?P<t10>\S+)"
)


@dataclass(frozen=True)
class ParsedResult:
    ticker: str
    side: str
    source: str
    entry: float
    gain: float
    adverse: float
    t10: float | None
    style: str


def _num_or_none(value: str) -> float | None:
    return None if value == "None" else float(value)


def parse_result_line(line: str) -> ParsedResult | None:
    m = RESULT_RE.search(line)
    if not m:
        return None
    lane = m.group("lane").strip()
    if lane == "MOMENTUM_EXPANSION":
        source = UNIFIED_STANDARD
    elif lane == "ULTRA_CHEAP_REVERSAL":
        source = LEGACY_REVERSAL_SOURCE
    else:
        source = f"UNKNOWN:{lane}"
    return ParsedResult(
        ticker=m.group("ticker").strip(),
        side=m.group("side"),
        source=source,
        entry=float(m.group("entry")),
        gain=float(m.group("gain")),
        adverse=float(m.group("adverse")),
        t10=_num_or_none(m.group("t10")),
        style=m.group("style").strip(),
    )


def score_lines(lines: list[str]) -> dict:
    parsed = [p for line in lines if (p := parse_result_line(line)) is not None]
    unified = [p for p in parsed if p.source == UNIFIED_STANDARD]
    legacy = [p for p in parsed if p.source == LEGACY_REVERSAL_SOURCE]
    unknown = [p for p in parsed if p.source.startswith("UNKNOWN:")]

    records = [
        QualificationRecord(
            entry_price=p.entry,
            evidence_standard=UNIFIED_STANDARD,
            evidence_pass=True,
            qualified=True,
            source=p.source,
            max_gain=p.gain,
            adverse=p.adverse,
            ticker=p.ticker,
        )
        for p in unified
    ]
    base = summarize(records)

    speed = defaultdict(lambda: {"n": 0, "hit10": 0, "burst_0_30s": 0, "expansion_31_180s": 0})
    contracts = defaultdict(lambda: {"n": 0, "hit10": 0})
    for p in unified:
        z = price_zone(p.entry)
        speed[z]["n"] += 1
        contracts[p.ticker]["n"] += 1
        if p.t10 is not None:
            speed[z]["hit10"] += 1
            contracts[p.ticker]["hit10"] += 1
            if p.t10 <= 30:
                speed[z]["burst_0_30s"] += 1
            elif p.t10 <= 180:
                speed[z]["expansion_31_180s"] += 1

    for z, s in speed.items():
        s["hit10_rate"] = s["hit10"] / s["n"] if s["n"] else None

    contract_rates = [v["hit10"] / v["n"] for v in contracts.values() if v["n"]]
    contract_balanced_hit10 = sum(contract_rates) / len(contract_rates) if contract_rates else None

    return {
        "schema": "unified-scalp-result-scorecard-v1",
        "research_only": True,
        "result_stream_authority": True,
        "contract_summary_authority": False,
        "production_promotion": "NOT_PERFORMED",
        "parsed_results": len(parsed),
        "unified_results": len(unified),
        "legacy_reversal_research_only": len(legacy),
        "unknown_lane_results": len(unknown),
        "independent_contracts": len(contracts),
        "contract_balanced_hit10_rate": contract_balanced_hit10,
        "qualification_guard": base,
        "speed_by_price_zone": dict(speed),
        "architecture": {
            "unified_scalp_expansion_path": "KEEP",
            "separate_ultra_cheap_graduation_path": "REJECT",
            "qualification_threshold_change": "MORE_DATA",
            "adverse_trap_tightening": "MORE_DATA",
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("log", nargs="?", help="Log file; defaults to stdin")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    if args.log:
        lines = Path(args.log).read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        lines = sys.stdin.read().splitlines()
    report = score_lines(lines)
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["unknown_lane_results"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
