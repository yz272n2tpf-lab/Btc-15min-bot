#!/usr/bin/env python3
"""Read-only integrity audit for LEAD_V6 RESULT log lines.

Research-only. NO ORDERS. This parser never imports or executes collectors.
It is intentionally conservative around values printed to 3 decimals: a
printed +0.050 or +0.100 can straddle the collector's true threshold after
rounding, so those cases are reported as boundary-ambiguous rather than
silently reclassified.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

RESULT_PREFIX = "LEAD_V6 RESULT |"
FLOAT = r"[+-]?\d+(?:\.\d+)?"
TOKEN = r"(?:None|" + FLOAT + r")"

RESULT_RE = re.compile(
    r"LEAD_V6 RESULT \| "
    r"(?P<grade>V5_BASELINE|V6_QUALIFIED) \| "
    r"(?P<ticker>[^|]+?) \| "
    r"(?P<side>UP|DOWN) \| "
    r"zone (?P<zone>[^|]+?) \| "
    r"style (?P<style>BURST|EXPANSION|NO_EXPANSION) \| "
    r"entry (?P<entry>" + FLOAT + r") \| "
    r"max_exec_gain (?P<gain>" + FLOAT + r") \| "
    r"adverse (?P<adverse>" + FLOAT + r") \| "
    r"hit10 (?P<hit10>True|False) \| "
    r"hit20 (?P<hit20>True|False) \| "
    r"to_exec\+5c (?P<t5>" + TOKEN + r") \| "
    r"to_exec\+10c (?P<t10>" + TOKEN + r") \| "
    r"to_exec\+20c (?P<t20>" + TOKEN + r") \| "
    r"kalshi_reprice\+5c (?P<ask5>" + TOKEN + r")"
)


def _num(value: str):
    return None if value == "None" else float(value)


def parse_result(line: str):
    m = RESULT_RE.search(line)
    if not m:
        return None
    d = m.groupdict()
    for key in ("entry", "gain", "adverse", "t5", "t10", "t20", "ask5"):
        d[key] = _num(d[key])
    d["hit10"] = d["hit10"] == "True"
    d["hit20"] = d["hit20"] == "True"
    return d


def _threshold_state(gain: float, timing, threshold: float):
    """Return consistent / contradiction / boundary_ambiguous.

    Collector decisions use unrounded values, but RESULT gain is printed to
    0.001. Half a print unit on either side is therefore not provably wrong.
    """
    half_print = 0.0005
    if timing is not None:
        if gain < threshold - half_print:
            return "contradiction"
        if abs(gain - threshold) <= half_print:
            return "boundary_ambiguous"
        return "consistent"
    if gain > threshold + half_print:
        return "contradiction"
    if abs(gain - threshold) <= half_print:
        return "boundary_ambiguous"
    return "consistent"


def audit_lines(lines):
    result_lines = []
    malformed = []
    rows = []

    for raw in lines:
        line = raw.rstrip("\n")
        if RESULT_PREFIX not in line:
            continue
        result_lines.append(line)
        parsed = parse_result(line)
        if parsed is None:
            malformed.append(line)
        else:
            rows.append(parsed)

    counts = Counter(result_lines)
    duplicate_lines = [
        {"line": line, "count": count}
        for line, count in sorted(counts.items())
        if count > 1
    ]

    contradictions = []
    boundary_ambiguous = []
    style_mismatches = []

    for i, row in enumerate(rows, 1):
        identity = {
            "result_index": i,
            "grade": row["grade"],
            "ticker": row["ticker"],
            "side": row["side"],
            "entry": row["entry"],
        }
        for timing_key, threshold in (("t5", 0.05), ("t10", 0.10), ("t20", 0.20)):
            state = _threshold_state(row["gain"], row[timing_key], threshold)
            item = {**identity, "check": timing_key, "gain": row["gain"], "timing": row[timing_key]}
            if state == "contradiction":
                contradictions.append(item)
            elif state == "boundary_ambiguous":
                boundary_ambiguous.append(item)

        if row["hit10"] != (row["t10"] is not None):
            contradictions.append({**identity, "check": "hit10_vs_t10"})
        if row["hit20"] != (row["t20"] is not None):
            contradictions.append({**identity, "check": "hit20_vs_t20"})

        expected_style = "NO_EXPANSION"
        if row["t10"] is not None and row["t10"] <= 30.0:
            expected_style = "BURST"
        elif row["t10"] is not None and row["t10"] <= 180.0:
            expected_style = "EXPANSION"
        if row["style"] != expected_style:
            style_mismatches.append({
                **identity,
                "observed": row["style"],
                "expected": expected_style,
                "t10": row["t10"],
            })

    by_grade = {}
    for grade in ("V5_BASELINE", "V6_QUALIFIED"):
        selected = [r for r in rows if r["grade"] == grade]
        n = len(selected)
        by_grade[grade] = {
            "n": n,
            "hit5": sum(r["t5"] is not None for r in selected),
            "hit10": sum(r["t10"] is not None for r in selected),
            "hit10_within_30s": sum(r["t10"] is not None and r["t10"] <= 30.0 for r in selected),
            "hit20": sum(r["t20"] is not None for r in selected),
            "avg_gain": None if not n else sum(r["gain"] for r in selected) / n,
            "avg_adverse": None if not n else sum(r["adverse"] for r in selected) / n,
        }

    ok = not malformed and not duplicate_lines and not contradictions and not style_mismatches
    return {
        "ok": ok,
        "result_lines": len(result_lines),
        "parsed_results": len(rows),
        "malformed_count": len(malformed),
        "duplicate_count": sum(item["count"] - 1 for item in duplicate_lines),
        "contradiction_count": len(contradictions),
        "style_mismatch_count": len(style_mismatches),
        "boundary_ambiguous_count": len(boundary_ambiguous),
        "malformed": malformed,
        "duplicates": duplicate_lines,
        "contradictions": contradictions,
        "style_mismatches": style_mismatches,
        "boundary_ambiguous": boundary_ambiguous,
        "by_grade": by_grade,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("log", nargs="?", help="V6 log path; omit to read stdin")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if args.log:
        path = Path(args.log)
        if not path.is_file():
            print(f"BLOCKED: log not found: {path}", file=sys.stderr)
            return 2
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        lines = sys.stdin.read().splitlines()

    result = audit_lines(lines)
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(
            ("PASS" if result["ok"] else "FAIL")
            + f": parsed={result['parsed_results']} malformed={result['malformed_count']}"
            + f" duplicates={result['duplicate_count']}"
            + f" contradictions={result['contradiction_count']}"
            + f" style_mismatches={result['style_mismatch_count']}"
            + f" boundary_ambiguous={result['boundary_ambiguous_count']}"
        )
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
