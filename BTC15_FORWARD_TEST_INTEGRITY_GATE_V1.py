#!/usr/bin/env python3
"""Read-only BTC 15m forward-test integrity auditor.

This utility does not import or execute trading code. It only reads exported
Railway logs and reports whether the research collection window is complete,
where heartbeat gaps occurred, and where BRTI availability degraded.

Supported input:
- Railway get-logs JSON: {"deploy": [{"timestamp": "...", "message": "..."}]}
- a JSON list of log records with timestamp/message
- NDJSON records with timestamp/message
- plain text lines, optionally beginning with an ISO-8601 timestamp

It intentionally does NOT change V6 qualification thresholds or score trading
performance. Its job is provenance/data-quality only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

TICKER_RE = re.compile(r"\b(KXBTC15M-[A-Z0-9-]+)\b")
HEARTBEAT_RE = re.compile(
    r"LEAD_V6 HEARTBEAT\s*\|\s*(?P<ticker>KXBTC15M-[A-Z0-9-]+)"
    r".*?\|\s*BRTI\s+(?P<brti>N/A|[-+]?\d+(?:\.\d+)?)\s*\|"
)
REJECT_RE = re.compile(
    r"rejects\s+price=(?P<price>\d+)\s+degraded=(?P<degraded>\d+)"
    r"\s+base=(?P<base>\d+)\s+high=(?P<high>\d+)"
)
ISO_PREFIX_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))"
    r"\s+(?P<msg>.*)$"
)

DEFAULT_GAP_SECONDS = 75.0


def parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _event(timestamp: Any, message: Any) -> Dict[str, Any]:
    return {
        "timestamp_raw": None if timestamp is None else str(timestamp),
        "timestamp": parse_ts(timestamp),
        "message": "" if message is None else str(message),
    }


def _events_from_json(value: Any) -> Optional[List[Dict[str, Any]]]:
    if isinstance(value, dict):
        if isinstance(value.get("deploy"), list):
            value = value["deploy"]
        elif isinstance(value.get("logs"), list):
            value = value["logs"]
        elif "timestamp" in value and "message" in value:
            value = [value]
        else:
            # Some saved connector responses may wrap the Railway payload.
            for candidate in value.values():
                nested = _events_from_json(candidate)
                if nested:
                    return nested
            return None
    if not isinstance(value, list):
        return None

    out: List[Dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict) and "message" in item:
            out.append(_event(item.get("timestamp"), item.get("message")))
    return out or None


def load_events(path: Path) -> List[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if parsed is not None:
        events = _events_from_json(parsed)
        if events is not None:
            return events

    ndjson: List[Dict[str, Any]] = []
    ndjson_ok = True
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            ndjson_ok = False
            break
        if not isinstance(item, dict) or "message" not in item:
            ndjson_ok = False
            break
        ndjson.append(_event(item.get("timestamp"), item.get("message")))
    if ndjson_ok and ndjson:
        return ndjson

    out: List[Dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = ISO_PREFIX_RE.match(line)
        if m:
            out.append(_event(m.group("ts"), m.group("msg")))
        else:
            out.append(_event(None, line))
    return out


def _new_contract() -> Dict[str, Any]:
    return {
        "first_ts": None,
        "last_ts": None,
        "heartbeats": 0,
        "brti_na": 0,
        "brti_ok": 0,
        "max_brti_na_streak": 0,
        "_brti_na_streak": 0,
        "max_heartbeat_gap_seconds": 0.0,
        "_last_heartbeat_ts": None,
        "candidate_v5": 0,
        "candidate_v6": 0,
        "result_v5": 0,
        "result_v6": 0,
        "warnings": 0,
        "contract_summary": False,
        "cumulative_summary": False,
        "rejects": None,
    }


def audit(events: Iterable[Dict[str, Any]], gap_seconds: float = DEFAULT_GAP_SECONDS) -> Dict[str, Any]:
    contracts: Dict[str, Dict[str, Any]] = defaultdict(_new_contract)
    first_ts: Optional[datetime] = None
    last_ts: Optional[datetime] = None
    starts = 0
    warnings = 0
    out_of_order = 0
    previous_input_ts: Optional[datetime] = None

    for event in events:
        ts = event.get("timestamp")
        msg = str(event.get("message", ""))

        if ts is not None:
            if first_ts is None or ts < first_ts:
                first_ts = ts
            if last_ts is None or ts > last_ts:
                last_ts = ts
            if previous_input_ts is not None and ts < previous_input_ts:
                out_of_order += 1
            previous_input_ts = ts

        if "SCALP LEAD SHADOW V6 START" in msg:
            starts += 1
        if "LEAD_V6 WARNING" in msg:
            warnings += 1

        tm = TICKER_RE.search(msg)
        if not tm:
            continue
        ticker = tm.group(1)
        c = contracts[ticker]

        if ts is not None:
            if c["first_ts"] is None or ts < c["first_ts"]:
                c["first_ts"] = ts
            if c["last_ts"] is None or ts > c["last_ts"]:
                c["last_ts"] = ts

        if "LEAD_V6 WARNING" in msg:
            c["warnings"] += 1
        if "LEAD_V6 CANDIDATE" in msg:
            if "| V6_QUALIFIED |" in msg:
                c["candidate_v6"] += 1
            elif "| V5_BASELINE |" in msg:
                c["candidate_v5"] += 1
        if "LEAD_V6 RESULT" in msg:
            if "| V6_QUALIFIED |" in msg:
                c["result_v6"] += 1
            elif "| V5_BASELINE |" in msg:
                c["result_v5"] += 1
        if "LEAD_V6 CONTRACT_SUMMARY" in msg:
            c["contract_summary"] = True
            rm = REJECT_RE.search(msg)
            if rm:
                c["rejects"] = {k: int(v) for k, v in rm.groupdict().items()}
        if "LEAD_V6 CUMULATIVE" in msg:
            c["cumulative_summary"] = True

        hm = HEARTBEAT_RE.search(msg)
        if hm:
            c["heartbeats"] += 1
            brti = hm.group("brti")
            if brti == "N/A":
                c["brti_na"] += 1
                c["_brti_na_streak"] += 1
                c["max_brti_na_streak"] = max(
                    c["max_brti_na_streak"], c["_brti_na_streak"]
                )
            else:
                c["brti_ok"] += 1
                c["_brti_na_streak"] = 0

            if ts is not None and c["_last_heartbeat_ts"] is not None:
                gap = (ts - c["_last_heartbeat_ts"]).total_seconds()
                if gap >= 0:
                    c["max_heartbeat_gap_seconds"] = max(
                        c["max_heartbeat_gap_seconds"], gap
                    )
            if ts is not None:
                c["_last_heartbeat_ts"] = ts

    contract_rows: List[Dict[str, Any]] = []
    completed = 0
    open_count = 0
    degraded = 0
    gap_flagged = 0

    def sort_key(item: Tuple[str, Dict[str, Any]]) -> Tuple[datetime, str]:
        ticker, c = item
        return (c["first_ts"] or datetime.max.replace(tzinfo=timezone.utc), ticker)

    for ticker, c in sorted(contracts.items(), key=sort_key):
        hb = c["heartbeats"]
        na_ratio = (c["brti_na"] / hb) if hb else None
        flags: List[str] = []

        if not c["contract_summary"]:
            flags.append("OPEN_OR_INCOMPLETE")
            open_count += 1
        else:
            completed += 1

        if c["brti_na"] > 0 or (
            isinstance(c["rejects"], dict) and c["rejects"].get("degraded", 0) > 0
        ):
            flags.append("BRTI_DEGRADED")
            degraded += 1

        if c["max_heartbeat_gap_seconds"] > gap_seconds:
            flags.append("HEARTBEAT_GAP")
            gap_flagged += 1

        if c["warnings"]:
            flags.append("COLLECTOR_WARNING")

        # This is collection integrity only. A no-signal contract is valid data.
        collection_complete = bool(
            c["contract_summary"]
            and c["heartbeats"] > 0
            and c["max_heartbeat_gap_seconds"] <= gap_seconds
        )

        row = {
            "ticker": ticker,
            "first_ts": c["first_ts"].isoformat() if c["first_ts"] else None,
            "last_ts": c["last_ts"].isoformat() if c["last_ts"] else None,
            "heartbeats": hb,
            "brti_ok": c["brti_ok"],
            "brti_na": c["brti_na"],
            "brti_na_pct": None if na_ratio is None else round(100.0 * na_ratio, 1),
            "max_brti_na_streak": c["max_brti_na_streak"],
            "max_heartbeat_gap_seconds": round(c["max_heartbeat_gap_seconds"], 3),
            "candidate_v5": c["candidate_v5"],
            "candidate_v6": c["candidate_v6"],
            "result_v5": c["result_v5"],
            "result_v6": c["result_v6"],
            "warnings": c["warnings"],
            "contract_summary": c["contract_summary"],
            "cumulative_summary": c["cumulative_summary"],
            "rejects": c["rejects"],
            "collection_complete": collection_complete,
            "flags": flags or ["CLEAN"],
        }
        contract_rows.append(row)

    return {
        "window": {
            "first_ts": first_ts.isoformat() if first_ts else None,
            "last_ts": last_ts.isoformat() if last_ts else None,
            "collector_start_count": starts,
            "collector_warning_count": warnings,
            "input_out_of_order_count": out_of_order,
            "heartbeat_gap_threshold_seconds": gap_seconds,
        },
        "summary": {
            "contracts_seen": len(contract_rows),
            "contracts_completed": completed,
            "contracts_open_or_incomplete": open_count,
            "contracts_with_brti_degradation": degraded,
            "contracts_with_heartbeat_gap": gap_flagged,
            "completed_collection_integrity_ok": sum(
                1 for r in contract_rows if r["collection_complete"]
            ),
        },
        "contracts": contract_rows,
    }


def print_report(report: Dict[str, Any]) -> None:
    w = report["window"]
    s = report["summary"]
    print("BTC15 FORWARD TEST INTEGRITY")
    print(
        "window %s -> %s | starts=%d warnings=%d out_of_order=%d"
        % (
            w["first_ts"] or "N/A",
            w["last_ts"] or "N/A",
            w["collector_start_count"],
            w["collector_warning_count"],
            w["input_out_of_order_count"],
        )
    )
    print(
        "contracts seen=%d completed=%d open=%d integrity_ok=%d brti_degraded=%d heartbeat_gap=%d"
        % (
            s["contracts_seen"],
            s["contracts_completed"],
            s["contracts_open_or_incomplete"],
            s["completed_collection_integrity_ok"],
            s["contracts_with_brti_degradation"],
            s["contracts_with_heartbeat_gap"],
        )
    )
    for r in report["contracts"]:
        brti = "N/A" if r["brti_na_pct"] is None else "%.1f%%" % r["brti_na_pct"]
        print(
            "%s | complete=%s | hb=%d max_gap=%.1fs | BRTI_NA=%s streak=%d | "
            "cand V5/V6=%d/%d result V5/V6=%d/%d | %s"
            % (
                r["ticker"],
                r["collection_complete"],
                r["heartbeats"],
                r["max_heartbeat_gap_seconds"],
                brti,
                r["max_brti_na_streak"],
                r["candidate_v5"],
                r["candidate_v6"],
                r["result_v5"],
                r["result_v6"],
                ",".join(r["flags"]),
            )
        )


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Read-only integrity audit for BTC15 V6 Railway research logs."
    )
    p.add_argument("logfile", type=Path, help="Saved Railway log JSON/NDJSON/text file")
    p.add_argument(
        "--gap-seconds",
        type=float,
        default=DEFAULT_GAP_SECONDS,
        help="Flag heartbeat gaps larger than this value (default: 75)",
    )
    p.add_argument("--json-out", type=Path, help="Optional JSON report path")
    args = p.parse_args(argv)

    if args.gap_seconds <= 0:
        p.error("--gap-seconds must be > 0")
    if not args.logfile.exists():
        print("ERROR: log file not found: %s" % args.logfile, file=sys.stderr)
        return 2

    events = load_events(args.logfile)
    if not events:
        print("ERROR: no log events found", file=sys.stderr)
        return 2

    report = audit(events, args.gap_seconds)
    print_report(report)
    if args.json_out:
        args.json_out.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print("json_report=%s" % args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
