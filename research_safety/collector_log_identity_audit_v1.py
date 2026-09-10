#!/usr/bin/env python3
"""Read-only collector-version identity audit for Railway/replay log exports.

This guard prevents research tooling for one collector generation from silently
analyzing another generation's logs. It infers versions from startup banners
and LEAD_V<n> records, then fails closed on version mismatch, mixed-version
input, or absent version evidence. It performs no network or runtime mutation.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

LEAD_RE = re.compile(r"^LEAD_V(?P<version>\d+)\b")
START_RE = re.compile(r"^SCALP LEAD\b.*\bV(?P<version>\d+)\s+START\b")


def _messages_from_value(value) -> list[str]:
    out: list[str] = []
    if isinstance(value, dict):
        message = value.get("message")
        if isinstance(message, str):
            out.append(message)
        for key, child in value.items():
            if key == "message":
                continue
            if isinstance(child, (dict, list)):
                out.extend(_messages_from_value(child))
    elif isinstance(value, list):
        for child in value:
            out.extend(_messages_from_value(child))
    elif isinstance(value, str):
        out.append(value)
    return out


def extract_messages(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        value = None
    if value is not None:
        return _messages_from_value(value)

    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            out.append(line)
            continue
        extracted = _messages_from_value(value)
        out.extend(extracted if extracted else [line])
    return out


def infer_message_version(message: str) -> tuple[str | None, str | None]:
    lead = LEAD_RE.match(message)
    if lead:
        return lead.group("version"), "record"
    start = START_RE.match(message)
    if start:
        return start.group("version"), "startup"
    return None, None


def audit_identity(text: str, *, expected_version: int | str) -> dict:
    expected = str(expected_version).strip().upper().removeprefix("V")
    if not expected.isdigit() or int(expected) <= 0:
        raise ValueError("expected_version must be a positive integer or V-prefixed integer")

    messages = extract_messages(text)
    version_counts: Counter[str] = Counter()
    startup_counts: Counter[str] = Counter()
    record_counts: Counter[str] = Counter()

    for message in messages:
        version, source = infer_message_version(message)
        if version is None:
            continue
        version_counts[version] += 1
        if source == "startup":
            startup_counts[version] += 1
        else:
            record_counts[version] += 1

    observed = sorted(version_counts, key=lambda v: int(v))
    if not observed:
        status = "NO_VERSION_DATA"
    elif len(observed) > 1:
        status = "MIXED_VERSIONS"
    elif observed[0] != expected:
        status = "VERSION_MISMATCH"
    else:
        status = "OK"

    return {
        "ok": status == "OK",
        "status": status,
        "expected_version": expected,
        "message_count": len(messages),
        "observed_versions": observed,
        "version_counts": dict(sorted(version_counts.items(), key=lambda item: int(item[0]))),
        "startup_version_counts": dict(sorted(startup_counts.items(), key=lambda item: int(item[0]))),
        "record_version_counts": dict(sorted(record_counts.items(), key=lambda item: int(item[0]))),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("path", nargs="?", help="Railway/replay log export; omit to read stdin")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        text = Path(args.path).read_text(encoding="utf-8") if args.path else sys.stdin.read()
        result = audit_identity(text, expected_version=args.expected_version)
    except (OSError, ValueError) as exc:
        result = {"ok": False, "status": "BLOCKED", "error": str(exc)}
        print(json.dumps(result, sort_keys=True) if args.json else f"BLOCKED: {exc}")
        return 2

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(
            f"{result['status']}: expected=V{result['expected_version']} "
            f"observed={','.join('V' + v for v in result['observed_versions']) or 'none'}"
        )
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
