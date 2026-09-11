#!/usr/bin/env python3
"""Research-only contract-balance audit for the CURRENT unified BTC 15m scalp engine.

RESULT rows from the momentum/expansion source are graduation evidence. Legacy
ultra-cheap reversal rows are retained only as audit counts. Price bands are
strictly diagnostic: no band receives a weaker evidence standard or a lower
qualification bar. The audit exposes within-contract signal concentration so
raw signal counts cannot silently masquerade as independent evidence.

This module is signal-only. It cannot place orders, alter qualification
thresholds, or promote anything to production.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

RESULT_RE = re.compile(
    r"LEAD_V7 RESULT \| lane (?P<lane>[^|]+) \| (?P<ticker>[^|]+) \| (?P<side>UP|DOWN) "
    r"\| zone (?P<collector_zone>[^|]+) \| style (?P<style>[^|]+) \| entry (?P<entry>[-+0-9.]+) "
    r"\| max_gain (?P<gain>[-+0-9.]+) \| adverse (?P<adverse>[-+0-9.]+) "
    r"\| to\+5c (?P<t5>\S+) \| to\+10c (?P<t10>\S+)"
)

UNIFIED_LANE = "MOMENTUM_EXPANSION"
LEGACY_RESEARCH_ONLY_LANE = "ULTRA_CHEAP_REVERSAL"


def _number_or_none(value: str) -> float | None:
    return None if value == "None" else float(value)


def diagnostic_price_band(entry: float) -> str:
    if 0.03 <= entry < 0.07:
        return "3_7c"
    if 0.07 <= entry < 0.15:
        return "7_15c"
    if 0.15 <= entry <= 0.30:
        return "15_30c"
    if 0.30 < entry <= 0.45:
        return "30_45c"
    return "outside_3_45c"


def _parsed_rows(lines: list[str]) -> list[dict]:
    rows: list[dict] = []
    for line in lines:
        match = RESULT_RE.search(line)
        if not match:
            continue
        rows.append(
            {
                "lane": match.group("lane").strip(),
                "ticker": match.group("ticker").strip(),
                "side": match.group("side"),
                "entry": float(match.group("entry")),
                "t10": _number_or_none(match.group("t10")),
            }
        )
    return rows


def _zone_summary(rows: list[dict]) -> dict:
    by_contract: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_contract[row["ticker"]].append(row)

    n = len(rows)
    hit10 = sum(row["t10"] is not None for row in rows)
    contract_rates = [
        sum(row["t10"] is not None for row in contract_rows) / len(contract_rows)
        for contract_rows in by_contract.values()
    ]
    signal_counts = [len(contract_rows) for contract_rows in by_contract.values()]

    repeat_counter = Counter((row["ticker"], row["side"], round(row["entry"], 6)) for row in rows)
    repeated_same_entry_observations = sum(count - 1 for count in repeat_counter.values() if count > 1)
    multi_signal_contracts = sum(count > 1 for count in signal_counts)

    return {
        "n": n,
        "hit10": hit10,
        "raw_hit10_rate": hit10 / n if n else None,
        "independent_contracts": len(by_contract),
        "contract_balanced_hit10_rate": (
            sum(contract_rates) / len(contract_rates) if contract_rates else None
        ),
        "multi_signal_contracts": multi_signal_contracts,
        "max_signals_in_one_contract": max(signal_counts) if signal_counts else 0,
        "repeated_same_entry_observations": repeated_same_entry_observations,
        "independence_assessment": (
            "CORRELATED_REPEAT_EXPOSURE_PRESENT" if multi_signal_contracts else "ONE_SIGNAL_PER_CONTRACT"
        ),
    }


def audit_lines(lines: list[str]) -> dict:
    rows = _parsed_rows(lines)
    unified = [row for row in rows if row["lane"] == UNIFIED_LANE]
    legacy = [row for row in rows if row["lane"] == LEGACY_RESEARCH_ONLY_LANE]
    unknown = [
        row for row in rows if row["lane"] not in {UNIFIED_LANE, LEGACY_RESEARCH_ONLY_LANE}
    ]

    zones: dict[str, list[dict]] = defaultdict(list)
    for row in unified:
        zones[diagnostic_price_band(row["entry"])].append(row)

    expected_bands = ("3_7c", "7_15c", "15_30c", "30_45c", "outside_3_45c")
    zone_reports = {band: _zone_summary(zones.get(band, [])) for band in expected_bands}
    overall = _zone_summary(unified)

    return {
        "schema": "unified-scalp-contract-balance-audit-v1",
        "research_only": True,
        "signal_only": True,
        "production_promotion": "NOT_PERFORMED",
        "qualification_thresholds_changed": False,
        "cheap_price_evidence_override": False,
        "price_bands_are_diagnostic_only": True,
        "unified_results": len(unified),
        "legacy_reversal_research_only": len(legacy),
        "unknown_lane_results": len(unknown),
        "overall": overall,
        "by_price_band": zone_reports,
        "decision": {
            "unified_scalp_expansion_path": "KEEP",
            "separate_ultra_cheap_graduation_path": "REJECT",
            "signal_count_only_zone_tightening": "REJECT",
            "zone_specific_threshold_change": "MORE_DATA",
            "evidence_weighting": "USE_CONTRACT_BALANCED_ALONGSIDE_RAW",
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
    report = audit_lines(lines)
    print(json.dumps(report, sort_keys=args.json, indent=None if args.json else 2))
    return 0 if report["unknown_lane_results"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
