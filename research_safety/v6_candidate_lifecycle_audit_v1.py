#!/usr/bin/env python3
"""Read-only V6 candidate/result lifecycle auditor.

Audits the event stream without changing collector behavior. It pairs every
RESULT to the oldest matching CANDIDATE using (stage, contract, side, entry),
checks Railway HEARTBEAT pending counts against the reconstructed open-candidate
count, and verifies that V6-qualified candidates are backed by a V5 baseline
candidate for the same contract/side/entry. Unresolved candidates at the end of
a truncated log window are reported but are not fatal.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

CANDIDATE_RE = re.compile(
    r"^LEAD_V6 CANDIDATE \| (?P<stage>V5_BASELINE|V6_QUALIFIED) \| "
    r"(?P<contract>[^| ]+) \| (?P<side>UP|DOWN) \| .*? \| ask (?P<entry>\d+(?:\.\d+)?) \|"
)
RESULT_RE = re.compile(
    r"^LEAD_V6 RESULT \| (?P<stage>V5_BASELINE|V6_QUALIFIED) \| "
    r"(?P<contract>[^| ]+) \| (?P<side>UP|DOWN) \| .*? \| entry (?P<entry>\d+(?:\.\d+)?) \|"
)
HEARTBEAT_RE = re.compile(
    r"^LEAD_V6 HEARTBEAT \| (?P<contract>[^| ]+) \| .*? \| pending (?P<pending>\d+)$"
)


@dataclass(frozen=True)
class LogRecord:
    message: str
    timestamp: Optional[str] = None


def _timestamp_seconds(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _records_from_json(value) -> list[LogRecord]:
    out: list[LogRecord] = []
    if isinstance(value, dict):
        if isinstance(value.get("message"), str):
            out.append(LogRecord(value["message"], value.get("timestamp")))
        for key in ("deploy", "build", "http"):
            items = value.get(key)
            if isinstance(items, list):
                for item in items:
                    out.extend(_records_from_json(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(_records_from_json(item))
    return out


def normalize_records(text: str) -> list[LogRecord]:
    """Accept raw log lines, JSONL, or a Railway get-logs JSON payload."""
    stripped = text.strip()
    if not stripped:
        return []
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        value = None
    if value is not None:
        records = _records_from_json(value)
        if records:
            return records

    records: list[LogRecord] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            records.append(LogRecord(line))
            continue
        extracted = _records_from_json(value)
        records.extend(extracted or [LogRecord(line)])
    return records


def _key(match: re.Match[str]) -> tuple[str, str, str, str]:
    entry = f"{float(match.group('entry')):.6f}".rstrip("0").rstrip(".")
    return (
        match.group("stage"),
        match.group("contract"),
        match.group("side"),
        entry,
    )


def audit_records(records: Iterable[LogRecord]) -> dict:
    open_candidates: dict[tuple[str, str, str, str], deque[dict]] = defaultdict(deque)
    candidate_counts: dict[tuple[str, str, str, str], int] = defaultdict(int)
    paired_results = 0
    orphan_results: list[dict] = []
    pending_mismatches: list[dict] = []
    v6_without_v5_candidate: list[dict] = []
    resolution_seconds: list[float] = []
    open_total = 0
    candidate_lines = 0
    result_lines = 0
    heartbeat_lines = 0

    for index, record in enumerate(records):
        message = record.message

        match = CANDIDATE_RE.match(message)
        if match:
            candidate_lines += 1
            key = _key(match)
            candidate = {
                "line_index": index,
                "timestamp": record.timestamp,
                "stage": key[0],
                "contract": key[1],
                "side": key[2],
                "entry": key[3],
            }
            if key[0] == "V6_QUALIFIED":
                v5_key = ("V5_BASELINE", key[1], key[2], key[3])
                if candidate_counts[v5_key] <= candidate_counts[key]:
                    v6_without_v5_candidate.append(candidate)
            candidate_counts[key] += 1
            open_candidates[key].append(candidate)
            open_total += 1
            continue

        match = RESULT_RE.match(message)
        if match:
            result_lines += 1
            key = _key(match)
            if not open_candidates[key]:
                orphan_results.append(
                    {
                        "line_index": index,
                        "timestamp": record.timestamp,
                        "stage": key[0],
                        "contract": key[1],
                        "side": key[2],
                        "entry": key[3],
                    }
                )
                continue
            candidate = open_candidates[key].popleft()
            open_total -= 1
            paired_results += 1
            started = _timestamp_seconds(candidate["timestamp"])
            finished = _timestamp_seconds(record.timestamp)
            if started is not None and finished is not None and finished >= started:
                resolution_seconds.append(finished - started)
            continue

        match = HEARTBEAT_RE.match(message)
        if match:
            heartbeat_lines += 1
            reported = int(match.group("pending"))
            if reported != open_total:
                pending_mismatches.append(
                    {
                        "line_index": index,
                        "timestamp": record.timestamp,
                        "contract": match.group("contract"),
                        "reported_pending": reported,
                        "reconstructed_pending": open_total,
                    }
                )

    unresolved_candidates = [
        item
        for queue in open_candidates.values()
        for item in queue
    ]
    avg_resolution = (
        sum(resolution_seconds) / len(resolution_seconds)
        if resolution_seconds
        else None
    )
    return {
        "ok": (
            not orphan_results
            and not pending_mismatches
            and not v6_without_v5_candidate
        ),
        "candidate_lines": candidate_lines,
        "result_lines": result_lines,
        "paired_results": paired_results,
        "heartbeat_lines": heartbeat_lines,
        "unresolved_candidates": unresolved_candidates,
        "orphan_results": orphan_results,
        "pending_mismatches": pending_mismatches,
        "v6_without_v5_candidate": v6_without_v5_candidate,
        "resolution_samples": len(resolution_seconds),
        "avg_resolution_seconds": avg_resolution,
        "max_resolution_seconds": max(resolution_seconds) if resolution_seconds else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="Log file; omit to read stdin")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    if args.path:
        with open(args.path, "r", encoding="utf-8") as handle:
            text = handle.read()
    else:
        text = sys.stdin.read()
    result = audit_records(normalize_records(text))

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(
            f"{'PASS' if result['ok'] else 'WARN'}: "
            f"{result['candidate_lines']} candidates, "
            f"{result['paired_results']}/{result['result_lines']} results paired, "
            f"{result['heartbeat_lines']} heartbeats checked; "
            f"pending-mismatches={len(result['pending_mismatches'])}; "
            f"orphan-results={len(result['orphan_results'])}; "
            f"v6-without-v5={len(result['v6_without_v5_candidate'])}; "
            f"unresolved={len(result['unresolved_candidates'])}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
