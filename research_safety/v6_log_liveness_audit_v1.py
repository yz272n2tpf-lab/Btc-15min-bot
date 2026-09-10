#!/usr/bin/env python3
"""Read-only liveness audit for V6 Railway log exports.

Accepts JSON-lines records containing ``timestamp`` and ``message`` or simple
``<ISO timestamp> <message>`` lines. It detects heartbeat gaps and silent tails
without restarting, deploying, or calling the collector.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

HEARTBEAT_PREFIX = "LEAD_V6 HEARTBEAT |"
WARNING_PREFIX = "LEAD_V6 WARNING |"
LEFT_RE = re.compile(r"\|\s*([0-9]+(?:\.[0-9]+)?)m\s*\|")


class LivenessAuditError(RuntimeError):
    pass


def parse_ts(value: str) -> datetime:
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise LivenessAuditError(f"invalid timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        raise LivenessAuditError(f"timestamp must include timezone: {value!r}")
    return dt.astimezone(timezone.utc)


def parse_lines(lines: Iterable[str]) -> list[dict]:
    out = []
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LivenessAuditError(f"line {lineno}: invalid JSON") from exc
            ts = obj.get("timestamp")
            msg = obj.get("message")
        else:
            parts = line.split(None, 1)
            if len(parts) != 2:
                raise LivenessAuditError(f"line {lineno}: expected timestamp and message")
            ts, msg = parts
        if not ts or msg is None:
            raise LivenessAuditError(f"line {lineno}: missing timestamp/message")
        out.append({"timestamp": parse_ts(str(ts)), "message": str(msg)})
    return out


def audit_liveness(
    records: list[dict],
    *,
    as_of: datetime,
    heartbeat_gap_s: float = 90.0,
    silent_tail_s: float = 120.0,
) -> dict:
    if as_of.tzinfo is None:
        raise LivenessAuditError("as_of must include timezone")
    as_of = as_of.astimezone(timezone.utc)
    v6 = sorted(
        (r for r in records if str(r.get("message", "")).startswith("LEAD_V6 ")),
        key=lambda r: r["timestamp"],
    )
    if not v6:
        return {
            "ok": False,
            "status": "NO_V6_RECORDS",
            "record_count": 0,
            "heartbeat_count": 0,
            "warning_count": 0,
        }

    heartbeats = [r for r in v6 if r["message"].startswith(HEARTBEAT_PREFIX)]
    warnings = [r for r in v6 if r["message"].startswith(WARNING_PREFIX)]
    gaps = []
    for prev, curr in zip(heartbeats, heartbeats[1:]):
        gap = (curr["timestamp"] - prev["timestamp"]).total_seconds()
        if gap > heartbeat_gap_s:
            gaps.append({
                "from": prev["timestamp"].isoformat(),
                "to": curr["timestamp"].isoformat(),
                "seconds": round(gap, 1),
            })

    last = v6[-1]
    tail = max(0.0, (as_of - last["timestamp"]).total_seconds())
    last_hb = heartbeats[-1] if heartbeats else None
    left_minutes = None
    if last_hb:
        m = LEFT_RE.search(last_hb["message"])
        if m:
            left_minutes = float(m.group(1))

    status = "OK"
    if tail > silent_tail_s:
        if left_minutes is not None and left_minutes <= 1.5:
            status = "POST_CONTRACT_SILENCE"
        else:
            status = "IN_CONTRACT_OR_UNKNOWN_SILENCE"
    elif gaps:
        status = "HEARTBEAT_GAPS"
    elif warnings:
        status = "WARNINGS_PRESENT"

    return {
        "ok": status == "OK",
        "status": status,
        "record_count": len(v6),
        "heartbeat_count": len(heartbeats),
        "warning_count": len(warnings),
        "heartbeat_gap_count": len(gaps),
        "heartbeat_gaps": gaps,
        "last_event_utc": last["timestamp"].isoformat(),
        "last_heartbeat_utc": None if last_hb is None else last_hb["timestamp"].isoformat(),
        "last_heartbeat_left_minutes": left_minutes,
        "silent_tail_seconds": round(tail, 1),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", required=True, help="Railway log export (JSONL or timestamp+message lines)")
    p.add_argument("--as-of", required=True, help="Timezone-aware ISO timestamp")
    p.add_argument("--heartbeat-gap-s", type=float, default=90.0)
    p.add_argument("--silent-tail-s", type=float, default=120.0)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    try:
        records = parse_lines(Path(args.log).read_text(encoding="utf-8").splitlines())
        result = audit_liveness(
            records,
            as_of=parse_ts(args.as_of),
            heartbeat_gap_s=args.heartbeat_gap_s,
            silent_tail_s=args.silent_tail_s,
        )
    except (OSError, LivenessAuditError) as exc:
        result = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            print(f"BLOCKED: {exc}")
        return 2

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"{result['status']}: silent_tail={result.get('silent_tail_seconds', 'N/A')}s")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
