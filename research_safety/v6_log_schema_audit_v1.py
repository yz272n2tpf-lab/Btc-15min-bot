#!/usr/bin/env python3
"""Read-only schema-drift audit for normalized/live V6 research logs.

The collector's emitted LEAD_V6 record shapes are treated as a versioned
research interface. This utility fails closed when a known record type no
longer matches its expected field layout, when an unknown LEAD_V6 type appears,
or when the input contains no V6 records. It never calls or mutates Railway,
the collector, credentials, or qualification thresholds.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from v6_log_snapshot_normalizer_v1 import normalize_records

NUM = r"[+-]?\d+(?:\.\d+)?"
NONNEG = r"\d+(?:\.\d+)?"
VALUE = rf"(?:N/A|{NUM})"
TIME = rf"(?:None|{NONNEG})"

SCORE_RE = re.compile(
    rf"^(?P<label>V5|V6) n=(?P<n>\d+) "
    rf"hit5={NONNEG}% hit10={NONNEG}% burst10<=30s={NONNEG}% "
    rf"expand10<=120s={NONNEG}% hit20={NONNEG}% "
    rf"expand20<=180s={NONNEG}% avgGain={NUM} avgAdv={NUM}$"
)
ZERO_SCORE_RE = re.compile(r"^(V5|V6) n=0$")
REJECT_RE = re.compile(
    r"^rejects price=\d+ degraded=\d+ base=\d+ high=\d+$"
)


def _value(segment: str, label: str, pattern: str = NUM) -> bool:
    return re.fullmatch(rf"{re.escape(label)} {pattern}", segment) is not None


def _score(segment: str, label: str) -> bool:
    if segment == f"{label} n=0":
        return True
    match = SCORE_RE.fullmatch(segment)
    return bool(match and match.group("label") == label)


def _candidate(parts: list[str]) -> bool:
    if len(parts) != 15:
        return False
    return (
        parts[1] in {"V5_BASELINE", "V6_QUALIFIED"}
        and bool(parts[2])
        and parts[3] in {"UP", "DOWN"}
        and parts[4].startswith("zone ") and len(parts[4]) > 5
        and _value(parts[5], "ask", NONNEG)
        and _value(parts[6], "btc5")
        and _value(parts[7], "btc15")
        and _value(parts[8], "btc30", VALUE)
        and _value(parts[9], "accel")
        and _value(parts[10], "brti5", VALUE)
        and _value(parts[11], "brti15", VALUE)
        and _value(parts[12], "ask5")
        and _value(parts[13], "ask15")
        and re.fullmatch(rf"left {NONNEG}s", parts[14]) is not None
    )


def _result(parts: list[str]) -> bool:
    if len(parts) != 15:
        return False
    return (
        parts[1] in {"V5_BASELINE", "V6_QUALIFIED"}
        and bool(parts[2])
        and parts[3] in {"UP", "DOWN"}
        and parts[4].startswith("zone ") and len(parts[4]) > 5
        and parts[5] in {"style NO_EXPANSION", "style BURST", "style EXPANSION"}
        and _value(parts[6], "entry", NONNEG)
        and _value(parts[7], "max_exec_gain")
        and _value(parts[8], "adverse")
        and parts[9] in {"hit10 True", "hit10 False"}
        and parts[10] in {"hit20 True", "hit20 False"}
        and _value(parts[11], "to_exec+5c", TIME)
        and _value(parts[12], "to_exec+10c", TIME)
        and _value(parts[13], "to_exec+20c", TIME)
        and _value(parts[14], "kalshi_reprice+5c", TIME)
    )


def _heartbeat(parts: list[str]) -> bool:
    if len(parts) != 8:
        return False
    return (
        bool(parts[1])
        and re.fullmatch(rf"{NONNEG}m", parts[2]) is not None
        and _value(parts[3], "BTC", NONNEG)
        and _value(parts[4], "BRTI", rf"(?:N/A|{NONNEG})")
        and _value(parts[5], "UP", NONNEG)
        and _value(parts[6], "DOWN", NONNEG)
        and re.fullmatch(r"pending \d+", parts[7]) is not None
    )


def _compact(parts: list[str], *, rejects: bool) -> bool:
    expected = 5 if rejects else 4
    if len(parts) != expected or not parts[1]:
        return False
    if not _score(parts[2], "V5") or not _score(parts[3], "V6"):
        return False
    return not rejects or REJECT_RE.fullmatch(parts[4]) is not None


def classify_message(message: str) -> tuple[str, bool]:
    parts = message.split(" | ")
    head = parts[0]
    if head == "LEAD_V6 CANDIDATE":
        return "CANDIDATE", _candidate(parts)
    if head == "LEAD_V6 RESULT":
        return "RESULT", _result(parts)
    if head == "LEAD_V6 HEARTBEAT":
        return "HEARTBEAT", _heartbeat(parts)
    if head == "LEAD_V6 CONTRACT_SUMMARY":
        return "CONTRACT_SUMMARY", _compact(parts, rejects=True)
    if head == "LEAD_V6 MIDCONTRACT":
        return "MIDCONTRACT", _compact(parts, rejects=True)
    if head == "LEAD_V6 CUMULATIVE":
        return "CUMULATIVE", _compact(parts, rejects=False)
    if head == "LEAD_V6 WARNING":
        return "WARNING", len(parts) >= 2 and bool(" | ".join(parts[1:]).strip())
    if message.startswith("LEAD_V6 "):
        token = message[len("LEAD_V6 "):].split(" ", 1)[0].split("|", 1)[0]
        return token or "UNKNOWN", False
    return "NON_V6", True


def audit_text(text: str, *, max_examples: int = 10) -> dict:
    if max_examples < 0:
        raise ValueError("max_examples must be non-negative")
    normalized = normalize_records(text)
    type_counts: Counter[str] = Counter()
    issues: list[dict] = []
    unknown_count = 0
    malformed_count = 0
    known = {
        "CANDIDATE", "RESULT", "HEARTBEAT", "CONTRACT_SUMMARY",
        "MIDCONTRACT", "CUMULATIVE", "WARNING",
    }

    for record in normalized["records"]:
        record_type, valid = classify_message(record["message"])
        type_counts[record_type] += 1
        if valid:
            continue
        kind = "UNKNOWN_TYPE" if record_type not in known else "MALFORMED_RECORD"
        if kind == "UNKNOWN_TYPE":
            unknown_count += 1
        else:
            malformed_count += 1
        if len(issues) < max_examples:
            issues.append(
                {
                    "index": record["index"],
                    "kind": kind,
                    "record_type": record_type,
                    "message": record["message"],
                }
            )

    if normalized["v6_records"] == 0:
        status = "NO_V6_DATA"
    elif unknown_count or malformed_count:
        status = "SCHEMA_DRIFT"
    else:
        status = "OK"

    return {
        "ok": status == "OK",
        "status": status,
        "input_records": normalized["input_records"],
        "v6_records": normalized["v6_records"],
        "noise_records": normalized["noise_records"],
        "type_counts": dict(sorted(type_counts.items())),
        "malformed_count": malformed_count,
        "unknown_type_count": unknown_count,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="Railway log export; omit to read stdin")
    parser.add_argument("--max-examples", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        text = Path(args.path).read_text(encoding="utf-8") if args.path else sys.stdin.read()
        result = audit_text(text, max_examples=args.max_examples)
    except (OSError, ValueError) as exc:
        result = {"ok": False, "status": "BLOCKED", "error": str(exc)}
        print(json.dumps(result, sort_keys=True) if args.json else f"BLOCKED: {exc}")
        return 2

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(
            f"{result['status']}: v6_records={result['v6_records']} "
            f"malformed={result['malformed_count']} "
            f"unknown={result['unknown_type_count']}"
        )
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
