#!/usr/bin/env python3
"""Research-only V7 data-quality incident classifier.

Consumes already-emitted LEAD_V7 log text and classifies transport warnings,
BRTI heartbeat unavailability, and observed BRTI-related qualification
suppression. It does not make network calls, import the live collector, alter
thresholds, place trades, or mutate production state.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HEARTBEAT_RE = re.compile(
    r"LEAD_V7 HEARTBEAT \| (?P<ticker>[^|]+?) \| [^|]+ \| BTC [^|]+ \| "
    r"BRTI (?P<brti>N/A|\d+(?:\.\d+)?) \|"
)
MID_RE = re.compile(r"LEAD_V7 MIDCONTRACT \| (?P<ticker>[^|]+?) \|")
REJECT_RE = re.compile(r"LEAD_V7 REJECTS \| (?P<body>\{.*\})")
WARNING_RE = re.compile(r"LEAD_V7 WARNING \| (?P<body>.+)$")


def _warning_class(body: str) -> str:
    text = body.lower()
    if "readtimeout" in text or "read timed out" in text:
        return "READ_TIMEOUT"
    if "connectionreseterror" in text or "connection reset" in text:
        return "CONNECTION_RESET"
    if "connectionerror" in text or "connection aborted" in text:
        return "CONNECTION_ERROR"
    return "OTHER_WARNING"


def _longest_false_streak(flags) -> int:
    best = cur = 0
    for flag in flags:
        if flag:
            cur = 0
        else:
            cur += 1
            best = max(best, cur)
    return best


def audit_incidents(text: str) -> dict:
    warnings = Counter()
    by_contract = defaultdict(list)
    reject_max = defaultdict(dict)
    pending_reject_ticker = None

    for raw in text.splitlines():
        line = raw.strip()

        m = WARNING_RE.search(line)
        if m:
            warnings[_warning_class(m.group("body"))] += 1

        m = HEARTBEAT_RE.search(line)
        if m:
            by_contract[m.group("ticker").strip()].append(m.group("brti") != "N/A")

        m = MID_RE.search(line)
        if m:
            pending_reject_ticker = m.group("ticker").strip()
            continue

        m = REJECT_RE.search(line)
        if m and pending_reject_ticker:
            try:
                payload = ast.literal_eval(m.group("body"))
            except (SyntaxError, ValueError):
                payload = {}
            if isinstance(payload, dict):
                dst = reject_max[pending_reject_ticker]
                for key in ("MOM_BRTI_DEGRADED", "REV_BRTI_DEGRADED"):
                    value = payload.get(key)
                    if isinstance(value, int) and value >= 0:
                        dst[key] = max(dst.get(key, 0), value)
            pending_reject_ticker = None

    contract_availability = {}
    all_flags = []
    for ticker in sorted(by_contract):
        flags = by_contract[ticker]
        all_flags.extend(flags)
        ok = sum(flags)
        contract_availability[ticker] = {
            "heartbeat_samples": len(flags),
            "brti_na_count": len(flags) - ok,
            "brti_ok_pct": None if not flags else round(100.0 * ok / len(flags), 2),
            "max_consecutive_na": _longest_false_streak(flags),
        }

    na_count = sum(not flag for flag in all_flags)
    max_streak = max(
        (summary["max_consecutive_na"] for summary in contract_availability.values()),
        default=0,
    )
    max_mom_suppression = max(
        (payload.get("MOM_BRTI_DEGRADED", 0) for payload in reject_max.values()),
        default=0,
    )
    max_rev_suppression = max(
        (payload.get("REV_BRTI_DEGRADED", 0) for payload in reject_max.values()),
        default=0,
    )

    classes = []
    if warnings:
        classes.append("TRANSPORT_WARNING_OBSERVED")
    if na_count:
        classes.append("BRTI_UNAVAILABLE_ON_HEARTBEAT")
    if max_streak >= 2:
        classes.append("BRTI_UNAVAILABLE_STREAK")
    if max_mom_suppression or max_rev_suppression:
        classes.append("BRTI_QUALIFICATION_SUPPRESSION_OBSERVED")
    if warnings and na_count and (max_mom_suppression or max_rev_suppression):
        classes.append("COMPOUND_DATA_QUALITY_INCIDENT")

    return {
        "schema_version": 1,
        "collector_identity": "LEAD_V7",
        "transport_warnings": dict(sorted(warnings.items())),
        "transport_warning_count": sum(warnings.values()),
        "heartbeat_samples": len(all_flags),
        "brti_na_count": na_count,
        "max_consecutive_na": max_streak,
        "contracts": contract_availability,
        "max_observed_brti_suppression": {
            "MOMENTUM_EXPANSION": max_mom_suppression,
            "ULTRA_CHEAP_REVERSAL": max_rev_suppression,
        },
        "incident_classes": classes or ["NO_DATA_QUALITY_INCIDENT_OBSERVED"],
        "correlation_note": (
            "Compound classification is co-occurrence evidence in the supplied log; "
            "it does not prove transport warnings caused BRTI unavailability."
        ),
        "research_only": True,
        "production_mutation": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logfile", nargs="?", help="UTF-8 V7 log file; stdin when omitted")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    text = Path(args.logfile).read_text(encoding="utf-8") if args.logfile else sys.stdin.read()
    print(json.dumps(audit_incidents(text), indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
