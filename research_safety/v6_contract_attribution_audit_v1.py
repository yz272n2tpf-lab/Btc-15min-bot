#!/usr/bin/env python3
"""Read-only V6 contract attribution auditor.

Reconstructs per-contract RESULT counts from the contract ticker embedded in each
RESULT line, independent of when summary/reset logging happens.  It also flags
(1) results emitted after their contract summary and (2) MIDCONTRACT counters
that are already non-zero before matching embedded RESULT lines exist for the
new contract.  Both patterns are useful for detecting cross-contract reporting
carryover without changing collector behavior.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from typing import Iterable

RESULT_RE = re.compile(
    r"^LEAD_V6 RESULT \| (?P<stage>V5_BASELINE|V6_QUALIFIED) \| "
    r"(?P<contract>[^| ]+) \|"
)
SUMMARY_RE = re.compile(
    r"^LEAD_V6 CONTRACT_SUMMARY \| (?P<contract>[^| ]+) \| "
    r"V5 n=(?P<v5>\d+) .*? \| V6 n=(?P<v6>\d+)"
)
MID_RE = re.compile(
    r"^LEAD_V6 MIDCONTRACT \| (?P<contract>[^| ]+) \| "
    r"V5 n=(?P<v5>\d+) .*? \| V6 n=(?P<v6>\d+)"
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
    observed = defaultdict(lambda: {"V5_BASELINE": 0, "V6_QUALIFIED": 0})
    summary_seen_at: dict[str, int] = {}
    summaries: list[dict] = []
    post_summary_results: list[dict] = []
    carryover_suspects: list[dict] = []
    result_lines = 0

    for index, message in enumerate(messages):
        match = RESULT_RE.match(message)
        if match:
            result_lines += 1
            contract = match.group("contract")
            stage = match.group("stage")
            observed[contract][stage] += 1
            if contract in summary_seen_at:
                post_summary_results.append(
                    {
                        "contract": contract,
                        "stage": stage,
                        "line_index": index,
                        "summary_line_index": summary_seen_at[contract],
                    }
                )
            continue

        match = SUMMARY_RE.match(message)
        if match:
            contract = match.group("contract")
            reported = {"V5_BASELINE": int(match.group("v5")), "V6_QUALIFIED": int(match.group("v6"))}
            summaries.append(
                {
                    "contract": contract,
                    "line_index": index,
                    "reported": reported,
                    "observed_so_far": dict(observed[contract]),
                }
            )
            summary_seen_at.setdefault(contract, index)
            continue

        match = MID_RE.match(message)
        if match:
            contract = match.group("contract")
            reported = {"V5_BASELINE": int(match.group("v5")), "V6_QUALIFIED": int(match.group("v6"))}
            obs = observed[contract]
            excess = {
                stage: reported[stage] - obs[stage]
                for stage in ("V5_BASELINE", "V6_QUALIFIED")
                if reported[stage] > obs[stage]
            }
            if excess:
                carryover_suspects.append(
                    {
                        "contract": contract,
                        "line_index": index,
                        "reported": reported,
                        "observed_so_far": dict(obs),
                        "unattributed_excess": excess,
                    }
                )

    reconstructed = {
        contract: {"v5_results": counts["V5_BASELINE"], "v6_results": counts["V6_QUALIFIED"]}
        for contract, counts in sorted(observed.items())
        if counts["V5_BASELINE"] or counts["V6_QUALIFIED"]
    }
    return {
        "ok": not post_summary_results and not carryover_suspects,
        "result_lines": result_lines,
        "contracts_with_results": len(reconstructed),
        "reconstructed": reconstructed,
        "post_summary_results": post_summary_results,
        "carryover_suspects": carryover_suspects,
        "summaries_seen": len(summaries),
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
            f"{result['result_lines']} RESULT lines across "
            f"{result['contracts_with_results']} contracts; "
            f"post-summary={len(result['post_summary_results'])}; "
            f"carryover-suspects={len(result['carryover_suspects'])}."
        )
        for item in result["post_summary_results"]:
            print(
                "POST_SUMMARY_RESULT: "
                f"{item['contract']} {item['stage']} at line {item['line_index']} "
                f"after summary line {item['summary_line_index']}"
            )
        for item in result["carryover_suspects"]:
            print(
                "CARRYOVER_SUSPECT: "
                f"{item['contract']} excess={item['unattributed_excess']}"
            )
    # This is an auditor, not a deployment gate: findings are reported, not fatal.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
