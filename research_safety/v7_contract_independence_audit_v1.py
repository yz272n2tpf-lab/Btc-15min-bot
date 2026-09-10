#!/usr/bin/env python3
"""Research-only V7 contract-independence / sample-concentration auditor.

Parses immutable LEAD_V7 RESULT records only. No network calls, trading actions,
threshold changes, or production writes. The output quantifies how much apparent
lane evidence is concentrated inside a small number of 15-minute contracts.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

LANES = ("MOMENTUM_EXPANSION", "ULTRA_CHEAP_REVERSAL")

RESULT_RE = re.compile(
    r"LEAD_V7 RESULT \| lane (?P<lane>[A-Z_]+) \| (?P<ticker>[^|]+?) \| "
    r"(?P<side>UP|DOWN) \| zone (?P<zone>[^|]+?) \| style (?P<style>[A-Z_]+) \| "
    r"entry (?P<entry>\d+(?:\.\d+)?) \| max_gain (?P<gain>[+-]?\d+(?:\.\d+)?) \| "
    r"adverse (?P<adverse>[+-]?\d+(?:\.\d+)?) \| to\+5c (?P<t5>[^|]+?) \| "
    r"to\+10c (?P<t10>[^|]+?) \| to\+20c (?P<t20>[^|]+?) \| reprice\+5c (?P<reprice>[^\s|]+)"
)


def _maybe_float(text: str):
    value = text.strip()
    return None if value == "None" else float(value)


def _round(value, digits=4):
    return None if value is None else round(value, digits)


def parse_results(text: str):
    rows = []
    for raw in text.splitlines():
        m = RESULT_RE.search(raw.strip())
        if not m:
            continue
        d = m.groupdict()
        rows.append({
            "lane": d["lane"],
            "ticker": d["ticker"].strip(),
            "t10": _maybe_float(d["t10"]),
        })
    return rows


def _lane_summary(rows):
    n = len(rows)
    if not n:
        return {
            "samples": 0,
            "unique_contracts": 0,
            "per_contract_samples": {},
            "repeated_samples_beyond_one_per_contract": 0,
            "largest_contract_share_pct": None,
            "herfindahl_sample_concentration": None,
            "effective_contract_count": None,
            "effective_contract_ratio_pct": None,
            "sample_weighted_hit10_within_3m_pct": None,
            "contract_balanced_hit10_within_3m_pct": None,
            "weighted_vs_balanced_gap_pp": None,
            "per_contract_hit10_within_3m_pct": {},
            "concentration_warning": "NO_DATA",
        }

    grouped = defaultdict(list)
    for row in rows:
        grouped[row["ticker"]].append(row)

    counts = {ticker: len(grouped[ticker]) for ticker in sorted(grouped)}
    shares = [count / n for count in counts.values()]
    hhi = sum(share * share for share in shares)
    effective = 1.0 / hhi if hhi else 0.0
    unique = len(counts)

    def hit10(row):
        return row["t10"] is not None and row["t10"] <= 180.0

    total_hits = sum(hit10(row) for row in rows)
    weighted = 100.0 * total_hits / n
    per_contract_hit = {
        ticker: 100.0 * sum(hit10(row) for row in grouped[ticker]) / len(grouped[ticker])
        for ticker in sorted(grouped)
    }
    balanced = sum(per_contract_hit.values()) / unique
    largest_share = 100.0 * max(shares)

    if unique == 1:
        warning = "SINGLE_CONTRACT_ONLY"
    elif largest_share > 50.0:
        warning = "MAJORITY_FROM_ONE_CONTRACT"
    elif effective / unique < 0.75:
        warning = "MATERIAL_CONCENTRATION"
    else:
        warning = "NO_MATERIAL_CONCENTRATION"

    return {
        "samples": n,
        "unique_contracts": unique,
        "per_contract_samples": counts,
        "repeated_samples_beyond_one_per_contract": n - unique,
        "largest_contract_share_pct": _round(largest_share, 2),
        "herfindahl_sample_concentration": _round(hhi, 4),
        "effective_contract_count": _round(effective, 2),
        "effective_contract_ratio_pct": _round(100.0 * effective / unique, 2),
        "sample_weighted_hit10_within_3m_pct": _round(weighted, 2),
        "contract_balanced_hit10_within_3m_pct": _round(balanced, 2),
        "weighted_vs_balanced_gap_pp": _round(weighted - balanced, 2),
        "per_contract_hit10_within_3m_pct": {
            ticker: _round(value, 2) for ticker, value in per_contract_hit.items()
        },
        "concentration_warning": warning,
    }


def build_independence_audit(text: str):
    rows = parse_results(text)
    return {
        "schema_version": 1,
        "collector_identity": "LEAD_V7",
        "purpose": "RESEARCH_ONLY_SAMPLE_INDEPENDENCE",
        "result_count": len(rows),
        "lanes": {
            lane: _lane_summary([row for row in rows if row["lane"] == lane])
            for lane in LANES
        },
        "production_promotion": "NOT_PERFORMED",
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("logfile", nargs="?", help="UTF-8 V7 log; stdin when omitted")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args(argv)
    text = Path(args.logfile).read_text(encoding="utf-8") if args.logfile else sys.stdin.read()
    print(json.dumps(build_independence_audit(text), indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
