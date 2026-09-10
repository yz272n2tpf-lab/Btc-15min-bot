#!/usr/bin/env python3
"""Research-only replay validator for V7 app-output state events.

Replays presentation events through v7_app_state_adapter_v1 without network,
trading, qualification, pricing, sizing, credential, or execution behavior.
Each ticker/lane/side stream is isolated so concurrent research signals cannot
silently borrow state from one another.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from v7_app_state_adapter_v1 import adapt_event

ALLOWED_SIDES = {"UP", "DOWN"}


def _identity(event):
    ticker = event.get("ticker")
    lane = event.get("lane")
    side = event.get("side")
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError("ticker is required")
    if side not in ALLOWED_SIDES:
        raise ValueError(f"unknown side: {side!r}")
    return ticker.strip(), lane, side


def replay_events(events):
    states = {}
    trace = []
    errors = []
    for index, event in enumerate(events):
        try:
            key = _identity(event)
            previous = states.get(key)
            output = adapt_event(event, previous)
            states[key] = output["state"]
            trace.append({"index": index, "identity": list(key), "previous_state": previous, "output": output})
        except Exception as exc:
            errors.append({"index": index, "error": f"{type(exc).__name__}: {exc}"})
    return {
        "schema_version": 1,
        "collector_identity": "LEAD_V7",
        "ok": not errors,
        "events_seen": len(trace) + len(errors),
        "events_accepted": len(trace),
        "errors": errors,
        "active_states": {"|".join(key): state for key, state in sorted(states.items())},
        "trace": trace,
        "research_only": True,
        "orders_enabled": False,
    }


def parse_jsonl(text):
    events = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {lineno}: invalid JSON: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"line {lineno}: event must be a JSON object")
        events.append(value)
    return events


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("event_file", nargs="?", help="JSONL app events; stdin when omitted")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args(argv)
    text = Path(args.event_file).read_text(encoding="utf-8") if args.event_file else sys.stdin.read()
    try:
        report = replay_events(parse_jsonl(text))
    except ValueError as exc:
        report = {
            "schema_version": 1,
            "collector_identity": "LEAD_V7",
            "ok": False,
            "events_seen": 0,
            "events_accepted": 0,
            "errors": [{"index": None, "error": f"ValueError: {exc}"}],
            "active_states": {},
            "trace": [],
            "research_only": True,
            "orders_enabled": False,
        }
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
