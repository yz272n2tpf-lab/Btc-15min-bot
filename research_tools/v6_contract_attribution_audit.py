#!/usr/bin/env python3
"""Read-only audit for V6 per-contract reporting attribution.

The collector can resolve a pending RESULT after a contract summary has already
printed. This utility reconstructs counts from each RESULT's own ticker and
compares them with the reported CONTRACT_SUMMARY count. It does not change
qualification, scoring, or any live service.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

RESULT_RE = re.compile(r"LEAD_V6 RESULT \| V6_QUALIFIED \| ([^ |]+) \|")
SUMMARY_RE = re.compile(r"LEAD_V6 CONTRACT_SUMMARY \| ([^ |]+) \|.*?\| V6 n=(\d+)(?:\s|\||$)")


def audit_lines(lines: Iterable[str]) -> dict:
    results_by_ticker: Counter[str] = Counter()
    summary_counts: dict[str, int] = {}
    summary_seen: set[str] = set()
    late_results: list[dict[str, object]] = []
    seen_result_messages: set[str] = set()

    for line_no, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue

        sm = SUMMARY_RE.search(line)
        if sm:
            ticker, n = sm.group(1), int(sm.group(2))
            summary_counts[ticker] = n
            summary_seen.add(ticker)

        rm = RESULT_RE.search(line)
        if rm:
            # Overlapping log exports can duplicate identical messages. Avoid
            # inflating the reconstructed ground-truth count in that case.
            message_key = line[line.find("LEAD_V6 RESULT") :]
            if message_key in seen_result_messages:
                continue
            seen_result_messages.add(message_key)
            ticker = rm.group(1)
            results_by_ticker[ticker] += 1
            if ticker in summary_seen:
                late_results.append({"ticker": ticker, "line": line_no})

    tickers = sorted(set(results_by_ticker) | set(summary_counts))
    mismatches: list[dict[str, object]] = []
    for ticker in tickers:
        actual = results_by_ticker.get(ticker, 0)
        reported = summary_counts.get(ticker)
        if reported is None:
            mismatches.append({
                "ticker": ticker,
                "actual_results": actual,
                "reported_summary": None,
                "delta": None,
                "kind": "MISSING_SUMMARY",
            })
        elif actual != reported:
            delta = reported - actual
            mismatches.append({
                "ticker": ticker,
                "actual_results": actual,
                "reported_summary": reported,
                "delta": delta,
                "kind": "SUMMARY_EXCESS" if delta > 0 else "SUMMARY_UNDERCOUNT",
            })

    return {
        "status": "PASS" if not mismatches else "FLAG",
        "unique_result_tickers": len(results_by_ticker),
        "v6_results_reconstructed": sum(results_by_ticker.values()),
        "summaries_seen": len(summary_counts),
        "late_results_after_own_summary": late_results,
        "mismatches": mismatches,
        "note": "Use reconstructed RESULT ticker counts for contract-level research; cumulative signal totals are not changed by this audit.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logfile", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = audit_lines(args.logfile.read_text(encoding="utf-8", errors="replace").splitlines())
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"V6_CONTRACT_ATTRIBUTION: {result['status']}")
        print(f"results={result['v6_results_reconstructed']} summaries={result['summaries_seen']}")
        for item in result["mismatches"]:
            print(
                f"{item['kind']}: {item['ticker']} actual={item['actual_results']} "
                f"reported={item['reported_summary']} delta={item['delta']}"
            )
        for item in result["late_results_after_own_summary"]:
            print(f"LATE_RESULT: {item['ticker']} line={item['line']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
