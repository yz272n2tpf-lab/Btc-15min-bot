#!/usr/bin/env python3
"""Read-only V6 contract coverage auditor.

Uses HEARTBEAT transitions as the active-contract clock so late RESULT records do
not create false contract changes. Reports missing summaries before a confirmed
heartbeat transition, duplicate summaries, and per-contract event coverage.
The newest heartbeat contract is treated as active and is not required to have
a summary yet.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from typing import Iterable

HEARTBEAT_RE = re.compile(r"^LEAD_V6 HEARTBEAT \| (?P<contract>[^| ]+) \|")
SIMPLE_RE = re.compile(
    r"^LEAD_V6 (?P<kind>MIDCONTRACT|CONTRACT_SUMMARY) \| (?P<contract>[^| ]+) \|"
)
STAGED_RE = re.compile(
    r"^LEAD_V6 (?P<kind>CANDIDATE|RESULT) \| "
    r"(?P<stage>V5_BASELINE|V6_QUALIFIED) \| (?P<contract>[^| ]+) \|"
)


def _messages_from_json(value) -> list[str]:
    out: list[str] = []
    if isinstance(value, dict):
        if isinstance(value.get("message"), str):
            out.append(value["message"])
        for key in ("deploy", "build", "http"):
            if isinstance(value.get(key), list):
                for item in value[key]:
                    out.extend(_messages_from_json(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(_messages_from_json(item))
    return out


def normalize_messages(text: str) -> list[str]:
    """Accept raw log lines, JSONL, or a Railway get-logs JSON payload."""
    stripped = text.strip()
    if not stripped:
        return []
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        value = None
    if value is not None:
        messages = _messages_from_json(value)
        if messages:
            return messages

    messages: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            messages.append(line)
            continue
        extracted = _messages_from_json(value)
        messages.extend(extracted or [line])
    return messages


def audit_messages(messages: Iterable[str]) -> dict:
    counts = defaultdict(
        lambda: {
            "heartbeats": 0,
            "midcontract": 0,
            "summaries": 0,
            "v5_candidates": 0,
            "v6_candidates": 0,
            "v5_results": 0,
            "v6_results": 0,
        }
    )
    summary_lines = defaultdict(list)
    heartbeat_contracts: list[str] = []
    transition_checks: list[dict] = []
    missing_summary_before_transition: list[dict] = []
    last_heartbeat_contract: str | None = None

    for index, message in enumerate(messages):
        match = HEARTBEAT_RE.match(message)
        if match:
            contract = match.group("contract")
            counts[contract]["heartbeats"] += 1
            if contract != last_heartbeat_contract:
                if last_heartbeat_contract is not None:
                    check = {
                        "from_contract": last_heartbeat_contract,
                        "to_contract": contract,
                        "line_index": index,
                        "summaries_seen_before_transition": len(
                            summary_lines[last_heartbeat_contract]
                        ),
                    }
                    transition_checks.append(check)
                    if not summary_lines[last_heartbeat_contract]:
                        missing_summary_before_transition.append(check)
                heartbeat_contracts.append(contract)
                last_heartbeat_contract = contract
            continue

        match = SIMPLE_RE.match(message)
        if match:
            contract = match.group("contract")
            kind = match.group("kind")
            if kind == "MIDCONTRACT":
                counts[contract]["midcontract"] += 1
            else:
                counts[contract]["summaries"] += 1
                summary_lines[contract].append(index)
            continue

        match = STAGED_RE.match(message)
        if match:
            contract = match.group("contract")
            stage = match.group("stage")
            kind = match.group("kind")
            key = (
                "v5_candidates"
                if kind == "CANDIDATE" and stage == "V5_BASELINE"
                else "v6_candidates"
                if kind == "CANDIDATE"
                else "v5_results"
                if stage == "V5_BASELINE"
                else "v6_results"
            )
            counts[contract][key] += 1

    duplicate_summaries = [
        {"contract": contract, "count": len(lines), "line_indexes": lines}
        for contract, lines in sorted(summary_lines.items())
        if len(lines) > 1
    ]

    per_contract = {contract: dict(values) for contract, values in sorted(counts.items())}
    newest_heartbeat_contract = heartbeat_contracts[-1] if heartbeat_contracts else None
    return {
        "ok": not missing_summary_before_transition and not duplicate_summaries,
        "contracts_seen": len(per_contract),
        "heartbeat_contract_order": heartbeat_contracts,
        "heartbeat_transitions": len(transition_checks),
        "newest_heartbeat_contract": newest_heartbeat_contract,
        "missing_summary_before_transition": missing_summary_before_transition,
        "duplicate_summaries": duplicate_summaries,
        "per_contract": per_contract,
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

    result = audit_messages(normalize_messages(text))
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(
            f"{'PASS' if result['ok'] else 'WARN'}: "
            f"{result['contracts_seen']} contracts; "
            f"heartbeat-transitions={result['heartbeat_transitions']}; "
            f"missing-summary={len(result['missing_summary_before_transition'])}; "
            f"duplicate-summary={len(result['duplicate_summaries'])}; "
            f"active={result['newest_heartbeat_contract'] or 'unknown'}."
        )
    # Research auditor only: findings are informational, not a deployment gate.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
