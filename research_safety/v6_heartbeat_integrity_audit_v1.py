#!/usr/bin/env python3
"""Read-only heartbeat-integrity audit for V6 Railway log exports.

Detects near-duplicate heartbeat emissions within the same contract, including
conflicting BRTI availability/value or other field conflicts. It never calls,
restarts, or mutates the collector.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

HB_RE = re.compile(
    r"^LEAD_V6 HEARTBEAT \|\s*(?P<ticker>[^|]+?)\s*\|\s*"
    r"(?P<left>[0-9]+(?:\.[0-9]+)?)m\s*\|\s*BTC\s+(?P<btc>[0-9]+(?:\.[0-9]+)?)\s*\|\s*"
    r"BRTI\s+(?P<brti>N/A|[0-9]+(?:\.[0-9]+)?)\s*\|\s*UP\s+(?P<up>[0-9]+(?:\.[0-9]+)?)\s*\|\s*"
    r"DOWN\s+(?P<down>[0-9]+(?:\.[0-9]+)?)\s*\|\s*pending\s+(?P<pending>[0-9]+)\s*$"
)


class HeartbeatIntegrityError(RuntimeError):
    pass


def parse_ts(value: str) -> datetime:
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise HeartbeatIntegrityError(f"invalid timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        raise HeartbeatIntegrityError(f"timestamp must include timezone: {value!r}")
    return dt.astimezone(timezone.utc)


def parse_records(lines: Iterable[str]) -> list[dict]:
    out = []
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise HeartbeatIntegrityError(f"line {lineno}: invalid JSON") from exc
            ts = obj.get("timestamp")
            msg = obj.get("message")
        else:
            parts = line.split(None, 1)
            if len(parts) != 2:
                raise HeartbeatIntegrityError(f"line {lineno}: expected timestamp and message")
            ts, msg = parts
        if not ts or msg is None:
            raise HeartbeatIntegrityError(f"line {lineno}: missing timestamp/message")
        m = HB_RE.match(str(msg))
        if not m:
            continue
        d = m.groupdict()
        out.append({
            "timestamp": parse_ts(str(ts)),
            "ticker": d["ticker"].strip(),
            "left": float(d["left"]),
            "btc": float(d["btc"]),
            "brti": None if d["brti"] == "N/A" else float(d["brti"]),
            "up": float(d["up"]),
            "down": float(d["down"]),
            "pending": int(d["pending"]),
        })
    return out


def audit_heartbeat_integrity(records: list[dict], *, duplicate_window_s: float = 2.0) -> dict:
    if duplicate_window_s < 0:
        raise HeartbeatIntegrityError("duplicate_window_s must be non-negative")
    rows = sorted(records, key=lambda r: (r["ticker"], r["timestamp"]))
    pairs = []
    for prev, curr in zip(rows, rows[1:]):
        if prev["ticker"] != curr["ticker"]:
            continue
        gap = (curr["timestamp"] - prev["timestamp"]).total_seconds()
        if gap < 0 or gap > duplicate_window_s:
            continue
        diffs = {}
        for key in ("left", "btc", "brti", "up", "down", "pending"):
            if prev[key] != curr[key]:
                diffs[key] = [prev[key], curr[key]]
        brti_conflict = "brti" in diffs and (prev["brti"] is None or curr["brti"] is None)
        classification = (
            "BRTI_AVAILABILITY_CONFLICT" if brti_conflict
            else "FIELD_CONFLICT" if diffs
            else "IDENTICAL_DUPLICATE"
        )
        pairs.append({
            "ticker": curr["ticker"],
            "first_utc": prev["timestamp"].isoformat(),
            "second_utc": curr["timestamp"].isoformat(),
            "gap_seconds": round(gap, 3),
            "classification": classification,
            "differences": diffs,
        })

    brti_conflicts = [p for p in pairs if p["classification"] == "BRTI_AVAILABILITY_CONFLICT"]
    field_conflicts = [p for p in pairs if p["classification"] == "FIELD_CONFLICT"]
    identical = [p for p in pairs if p["classification"] == "IDENTICAL_DUPLICATE"]
    if brti_conflicts:
        status = "BRTI_AVAILABILITY_CONFLICTS"
    elif field_conflicts:
        status = "NEAR_DUPLICATE_FIELD_CONFLICTS"
    elif identical:
        status = "IDENTICAL_NEAR_DUPLICATES"
    else:
        status = "OK"
    return {
        "ok": status == "OK",
        "status": status,
        "heartbeat_count": len(rows),
        "near_duplicate_pair_count": len(pairs),
        "brti_availability_conflict_count": len(brti_conflicts),
        "field_conflict_count": len(field_conflicts),
        "identical_duplicate_count": len(identical),
        "pairs": pairs,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", required=True, help="Railway log export (JSONL or timestamp+message lines)")
    p.add_argument("--duplicate-window-s", type=float, default=2.0)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    try:
        records = parse_records(Path(args.log).read_text(encoding="utf-8").splitlines())
        result = audit_heartbeat_integrity(records, duplicate_window_s=args.duplicate_window_s)
    except (OSError, HeartbeatIntegrityError) as exc:
        result = {"ok": False, "error": str(exc)}
        print(json.dumps(result, sort_keys=True) if args.json else f"BLOCKED: {exc}")
        return 2

    print(
        json.dumps(result, sort_keys=True)
        if args.json
        else f"{result['status']}: near_duplicates={result['near_duplicate_pair_count']}"
    )
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
