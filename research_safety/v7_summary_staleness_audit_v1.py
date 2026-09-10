#!/usr/bin/env python3
"""Research-only V7 summary-staleness audit.

Detects RESULT records emitted after the CONTRACT_SUMMARY for the same ticker,
compares per-contract reported lane counts with all parsed RESULT records for
that ticker, and surfaces malformed/ambiguous inputs without changing collector
logic or thresholds.
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

RESULT_RE = re.compile(
    r"LEAD_V7 RESULT \| lane (?P<lane>[A-Z_]+) \| (?P<ticker>[^|]+?) \| "
    r"(?P<side>UP|DOWN) \| zone (?P<zone>[^|]+?) \| style (?P<style>[A-Z_]+) \| "
    r"entry (?P<entry>\d+(?:\.\d+)?) \| max_gain (?P<gain>[+-]?\d+(?:\.\d+)?) \| "
    r"adverse (?P<adverse>[+-]?\d+(?:\.\d+)?) \| to\+5c (?P<t5>[^|]+?) \| "
    r"to\+10c (?P<t10>[^|]+?) \| to\+20c (?P<t20>[^|]+?) \| reprice\+5c (?P<reprice>[^|\s]+)"
)
SUMMARY_RE = re.compile(
    r"LEAD_V7 CONTRACT_SUMMARY \| (?P<ticker>[^|]+?) \| (?P<body>.*)"
)
MOM_N_RE = re.compile(r"(?:^|\|\s*)MOM n=(?P<n>\d+)")
REV_N_RE = re.compile(r"(?:^|\|\s*)REV n=(?P<n>\d+)")

LANE_TO_SHORT = {
    "MOMENTUM_EXPANSION": "MOM",
    "ULTRA_CHEAP_REVERSAL": "REV",
}


@dataclass(frozen=True)
class ParsedResult:
    line_no: int
    raw: str
    ticker: str
    lane: str
    side: str
    entry: float
    style: str


@dataclass(frozen=True)
class ParsedSummary:
    line_no: int
    ticker: str
    mom_n: Optional[int]
    rev_n: Optional[int]


def _parse_results_and_summaries(lines: Iterable[str]):
    results: list[ParsedResult] = []
    summaries: list[ParsedSummary] = []
    malformed_result_lines: list[int] = []
    malformed_summary_lines: list[int] = []
    raw_result_counter: Counter[str] = Counter()

    for line_no, raw in enumerate(lines, start=1):
        line = raw.strip()
        if "LEAD_V7 RESULT" in line:
            m = RESULT_RE.search(line)
            if not m:
                malformed_result_lines.append(line_no)
            else:
                d = m.groupdict()
                results.append(
                    ParsedResult(
                        line_no=line_no,
                        raw=line,
                        ticker=d["ticker"].strip(),
                        lane=d["lane"],
                        side=d["side"],
                        entry=float(d["entry"]),
                        style=d["style"],
                    )
                )
                raw_result_counter[line] += 1

        if "LEAD_V7 CONTRACT_SUMMARY" in line:
            m = SUMMARY_RE.search(line)
            if not m:
                malformed_summary_lines.append(line_no)
            else:
                body = m.group("body")
                mom = MOM_N_RE.search(body)
                rev = REV_N_RE.search(body)
                if mom is None or rev is None:
                    malformed_summary_lines.append(line_no)
                summaries.append(
                    ParsedSummary(
                        line_no=line_no,
                        ticker=m.group("ticker").strip(),
                        mom_n=int(mom.group("n")) if mom else None,
                        rev_n=int(rev.group("n")) if rev else None,
                    )
                )

    exact_duplicates = [
        {"line": raw, "count": count}
        for raw, count in sorted(raw_result_counter.items())
        if count > 1
    ]
    return results, summaries, malformed_result_lines, malformed_summary_lines, exact_duplicates


def audit(log_text: str):
    results, summaries, malformed_results, malformed_summaries, duplicates = _parse_results_and_summaries(log_text.splitlines())

    results_by_ticker: dict[str, list[ParsedResult]] = defaultdict(list)
    for result in results:
        results_by_ticker[result.ticker].append(result)

    summary_rows = []
    late_rows = []
    duplicate_summary_tickers = [
        ticker for ticker, count in Counter(s.ticker for s in summaries).items() if count > 1
    ]

    for summary in summaries:
        ticker_results = results_by_ticker.get(summary.ticker, [])
        observed = Counter(LANE_TO_SHORT.get(r.lane, r.lane) for r in ticker_results)
        late = [r for r in ticker_results if r.line_no > summary.line_no]
        late_counts = Counter(LANE_TO_SHORT.get(r.lane, r.lane) for r in late)
        reported = {"MOM": summary.mom_n, "REV": summary.rev_n}
        observed_known = {"MOM": observed.get("MOM", 0), "REV": observed.get("REV", 0)}
        mismatches = [
            lane for lane in ("MOM", "REV")
            if reported[lane] is not None and reported[lane] != observed_known[lane]
        ]
        status = "STALE" if late or mismatches else "MATCH"
        if summary.mom_n is None or summary.rev_n is None:
            status = "MALFORMED"

        summary_rows.append(
            {
                "ticker": summary.ticker,
                "summary_line": summary.line_no,
                "reported": reported,
                "observed_full_log": observed_known,
                "late_after_summary": {"MOM": late_counts.get("MOM", 0), "REV": late_counts.get("REV", 0)},
                "mismatch_lanes": mismatches,
                "status": status,
            }
        )
        for result in late:
            late_rows.append(
                {
                    "ticker": result.ticker,
                    "lane": result.lane,
                    "side": result.side,
                    "entry": result.entry,
                    "style": result.style,
                    "result_line": result.line_no,
                    "summary_line": summary.line_no,
                }
            )

    status = "CLEAN"
    if malformed_results or malformed_summaries:
        status = "FAIL_CLOSED_MALFORMED"
    elif duplicate_summary_tickers:
        status = "FAIL_CLOSED_AMBIGUOUS_SUMMARIES"
    elif duplicates:
        status = "REVIEW_DUPLICATE_RESULT_LINES"
    elif late_rows or any(row["mismatch_lanes"] for row in summary_rows):
        status = "SUMMARY_STALE_FINDINGS"

    return {
        "schema_version": 1,
        "collector_identity": "LEAD_V7",
        "status": status,
        "result_inventory": {
            "parsed_result_lines": len(results),
            "parsed_contract_summaries": len(summaries),
            "malformed_result_lines": malformed_results,
            "malformed_summary_lines": malformed_summaries,
            "exact_duplicate_result_lines": duplicates,
            "duplicate_contract_summary_tickers": sorted(duplicate_summary_tickers),
        },
        "contract_summaries": summary_rows,
        "late_results": late_rows,
        "notes": [
            "Observed counts use all parsed RESULT lines for each ticker in the supplied log snapshot.",
            "Exact duplicate RESULT text is reported but not silently deduplicated because distinct signals can share fields.",
            "This audit does not alter V7 thresholds, collector behavior, or production state.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("logfile", nargs="?", help="UTF-8 V7 log file; stdin when omitted")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args(argv)
    text = Path(args.logfile).read_text(encoding="utf-8") if args.logfile else sys.stdin.read()
    print(json.dumps(audit(text), indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
