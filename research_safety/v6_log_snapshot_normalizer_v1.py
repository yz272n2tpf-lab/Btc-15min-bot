#!/usr/bin/env python3
"""Canonicalize V6 logs into deterministic JSONL replay fixtures.

Accepts Railway get-logs JSON, JSONL records, or raw lines. Only LEAD_V6
messages are retained. Order and duplicates are intentionally preserved so
downstream integrity auditors can detect duplicate or late events instead of
having them hidden by preprocessing.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Iterable


def _records_from_json(value) -> list[dict]:
    out: list[dict] = []
    if isinstance(value, dict):
        if isinstance(value.get("message"), str):
            out.append(
                {
                    "timestamp": value.get("timestamp"),
                    "message": value["message"],
                }
            )
        for key in ("deploy", "build", "http"):
            if isinstance(value.get(key), list):
                for item in value[key]:
                    out.extend(_records_from_json(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(_records_from_json(item))
    return out


def normalize_records(text: str) -> dict:
    stripped = text.strip()
    if not stripped:
        return {"records": [], "input_records": 0, "v6_records": 0, "noise_records": 0}

    parsed_records: list[dict] = []
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        value = None

    if value is not None:
        parsed_records = _records_from_json(value)
        if not parsed_records and isinstance(value, str):
            parsed_records = [{"timestamp": None, "message": value}]
    else:
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                parsed_records.append({"timestamp": None, "message": line})
                continue
            extracted = _records_from_json(value)
            if extracted:
                parsed_records.extend(extracted)
            elif isinstance(value, str):
                parsed_records.append({"timestamp": None, "message": value})
            else:
                parsed_records.append({"timestamp": None, "message": line})

    records: list[dict] = []
    for record in parsed_records:
        message = record.get("message")
        if not isinstance(message, str) or not message.startswith("LEAD_V6 "):
            continue
        records.append(
            {
                "index": len(records),
                "timestamp": record.get("timestamp"),
                "message": message,
            }
        )

    return {
        "records": records,
        "input_records": len(parsed_records),
        "v6_records": len(records),
        "noise_records": len(parsed_records) - len(records),
    }


def render_jsonl(records: Iterable[dict]) -> str:
    return "\n".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")) for record in records
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", help="Log file; omit to read stdin")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Emit one JSON summary instead of canonical JSONL records.",
    )
    args = parser.parse_args()

    if args.path:
        with open(args.path, "r", encoding="utf-8") as handle:
            text = handle.read()
    else:
        text = sys.stdin.read()

    result = normalize_records(text)
    if args.summary:
        print(
            json.dumps(
                {key: value for key, value in result.items() if key != "records"},
                sort_keys=True,
            )
        )
    else:
        rendered = render_jsonl(result["records"])
        if rendered:
            print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
