#!/usr/bin/env python3
"""Read-only V6 log-schema drift auditor.

Validates log lines emitted by scalp_lead_shadow_v6.py without importing or
executing trading/collector code. Unknown V6 record types and missing required
fields are reported as schema drift. Unrelated runtime lines are ignored.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

KNOWN_PREFIXES = (
    "LEAD_V6 CANDIDATE",
    "LEAD_V6 RESULT",
    "LEAD_V6 CONTRACT_SUMMARY",
    "LEAD_V6 CUMULATIVE",
    "LEAD_V6 MIDCONTRACT",
    "LEAD_V6 HEARTBEAT",
    "LEAD_V6 WARNING",
    "SCALP LEAD SHADOW V6 START",
)

TOKEN_SPECS = {
    "CANDIDATE": (
        "zone ", "ask ", "btc5 ", "btc15 ", "btc30 ", "accel ",
        "brti5 ", "brti15 ", "ask5 ", "ask15 ", "left ",
    ),
    "RESULT": (
        "zone ", "style ", "entry ", "max_exec_gain ", "adverse ",
        "hit10 ", "hit20 ", "to_exec+5c ", "to_exec+10c ",
        "to_exec+20c ", "kalshi_reprice+5c ",
    ),
    "CONTRACT_SUMMARY": ("V5 ", "V6 ", "rejects price=", "degraded=", "base=", "high="),
    "CUMULATIVE": ("V5 ", "V6 "),
    "MIDCONTRACT": ("V5 ", "V6 ", "rejects price=", "degraded=", "base=", "high="),
    "HEARTBEAT": ("BTC ", "BRTI ", "UP ", "DOWN ", "pending "),
}

SCORE_FIELDS = (
    "n=", "hit5=", "hit10=", "burst10<=30s=", "expand10<=120s=",
    "hit20=", "expand20<=180s=", "avgGain=", "avgAdv=",
)


def _kind(line: str) -> str | None:
    if line.startswith("LEAD_V6 CANDIDATE |"):
        return "CANDIDATE"
    if line.startswith("LEAD_V6 RESULT |"):
        return "RESULT"
    if line.startswith("LEAD_V6 CONTRACT_SUMMARY |"):
        return "CONTRACT_SUMMARY"
    if line.startswith("LEAD_V6 CUMULATIVE |"):
        return "CUMULATIVE"
    if line.startswith("LEAD_V6 MIDCONTRACT |"):
        return "MIDCONTRACT"
    if line.startswith("LEAD_V6 HEARTBEAT |"):
        return "HEARTBEAT"
    if line.startswith("LEAD_V6 WARNING |"):
        return "WARNING"
    if line.startswith("SCALP LEAD SHADOW V6 START |"):
        return "START"
    return None


def _looks_v6(line: str) -> bool:
    return "LEAD_V6" in line or "SCALP LEAD SHADOW V6" in line


def _pipe_count(line: str) -> int:
    return len([part for part in line.split("|") if part.strip()])


def validate_line(line: str, line_no: int = 0) -> dict:
    """Return classification and any schema issues for one line."""
    raw = line.rstrip("\n")
    kind = _kind(raw)
    if kind is None:
        if _looks_v6(raw):
            return {"kind": "UNKNOWN_V6", "line": line_no, "issues": ["unknown_v6_record"], "text": raw}
        return {"kind": "IGNORED", "line": line_no, "issues": [], "text": raw}

    issues: list[str] = []
    if kind == "START":
        if "NO ORDERS" not in raw:
            issues.append("missing:NO ORDERS")
    elif kind == "WARNING":
        if not raw.partition("|")[2].strip():
            issues.append("missing:warning_payload")
    else:
        minimum_parts = {
            "CANDIDATE": 14,
            "RESULT": 15,
            "CONTRACT_SUMMARY": 5,
            "CUMULATIVE": 4,
            "MIDCONTRACT": 5,
            "HEARTBEAT": 8,
        }[kind]
        if _pipe_count(raw) < minimum_parts:
            issues.append(f"short_record:{_pipe_count(raw)}<{minimum_parts}")
        for token in TOKEN_SPECS[kind]:
            if token not in raw:
                issues.append(f"missing:{token.strip()}")
        if kind in {"CONTRACT_SUMMARY", "CUMULATIVE", "MIDCONTRACT"}:
            # n=0 intentionally has no rate fields in the collector's formatter.
            for section_name in ("V5", "V6"):
                match = re.search(rf"\| {section_name} ([^|]+)", raw)
                if not match:
                    continue
                section = match.group(1)
                if "n=0" not in section:
                    for field in SCORE_FIELDS:
                        if field not in section:
                            issues.append(f"missing:{section_name}.{field.rstrip('=')}")

    return {"kind": kind, "line": line_no, "issues": issues, "text": raw}


def audit_lines(lines) -> dict:
    counts = Counter()
    issues = []
    total = 0
    v6_lines = 0
    for line_no, line in enumerate(lines, 1):
        total += 1
        result = validate_line(line, line_no)
        counts[result["kind"]] += 1
        if result["kind"] not in {"IGNORED"}:
            v6_lines += 1
        if result["issues"]:
            issues.append(result)
    return {
        "schema": "v6-log-v1",
        "total_lines": total,
        "v6_lines": v6_lines,
        "counts": dict(sorted(counts.items())),
        "issue_count": len(issues),
        "ok": not issues,
        "issues": issues,
    }


def _iter_inputs(paths: list[str]):
    if not paths:
        yield from sys.stdin
        return
    for value in paths:
        with Path(value).open("r", encoding="utf-8", errors="replace") as handle:
            yield from handle


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Audit frozen V6 collector log schema (read-only).")
    parser.add_argument("paths", nargs="*", help="Log files. Reads stdin when omitted.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON.")
    args = parser.parse_args(argv)
    report = audit_lines(_iter_inputs(args.paths))
    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"V6_LOG_SCHEMA_AUDIT ok={report['ok']} v6_lines={report['v6_lines']} issues={report['issue_count']}")
        for kind, count in report["counts"].items():
            print(f"  {kind}: {count}")
        for item in report["issues"]:
            print(f"  line {item['line']} {item['kind']}: {', '.join(item['issues'])}")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
