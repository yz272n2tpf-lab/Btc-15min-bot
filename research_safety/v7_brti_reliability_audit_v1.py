#!/usr/bin/env python3
"""Research-only BRTI reliability/failure audit for LEAD_V7 logs.

No network calls, credentials, trading actions, or qualification logic. The
utility only classifies already-emitted V7 telemetry so transport failures can
be separated from strategy performance during replay/reporting.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

HEARTBEAT_RE = re.compile(
    r"LEAD_V7 HEARTBEAT \| (?P<ticker>[^|]+?) \| [^|]+ \| BTC [^|]+ \| "
    r"BRTI (?P<brti>N/A|\d+(?:\.\d+)?) \|"
)
STATS_RE = re.compile(
    r"LEAD_V7 (?:MIDCONTRACT|CONTRACT_SUMMARY|CUMULATIVE) \| (?P<ticker>[^|]+?) .*?"
    r"BRTI BRTI_RESILIENCE \| samples=(?P<samples>\d+) \| primary_ok=(?P<primary_ok>\d+) "
    r"\((?P<primary_pct>\d+(?:\.\d+)?)%\) \| retry_recovered=(?P<retry>\d+) \| "
    r"missing=(?P<missing>\d+) \| errors=(?P<errors>\d+) \| "
    r"(?:timeout=(?P<timeout>\d+) \| http=(?P<http>\d+) \| connection=(?P<connection>\d+) \| other=(?P<other>\d+) \| )?"
    r"verifier_ok=(?P<verifier_ok>\d+) \| verifier_disagree=(?P<verifier_disagree>\d+) \| "
    r"diag_cache=(?P<diag_cache>\d+)"
)
MID_RE = re.compile(r"LEAD_V7 MIDCONTRACT \| (?P<ticker>[^|]+?) \|")
REJECT_RE = re.compile(r"LEAD_V7 REJECTS \| (?P<body>\{.*\})")


def _longest_false_streak(flags: Iterable[bool]) -> int:
    best = cur = 0
    for flag in flags:
        if flag:
            cur = 0
        else:
            cur += 1
            best = max(best, cur)
    return best


def parse(text: str) -> dict:
    by_contract: dict[str, list[bool]] = defaultdict(list)
    snapshots = []
    snapshot_seen = set()
    reject_max: dict[str, dict[str, int]] = defaultdict(dict)
    pending_reject_ticker = None

    for raw in text.splitlines():
        line = raw.strip()
        m = HEARTBEAT_RE.search(line)
        if m:
            by_contract[m.group("ticker").strip()].append(m.group("brti") != "N/A")

        m = STATS_RE.search(line)
        if m:
            d = m.groupdict()
            transport_breakdown_observed = d["timeout"] is not None
            snap = {
                "ticker": d["ticker"].strip(),
                "samples": int(d["samples"]),
                "primary_ok": int(d["primary_ok"]),
                "primary_pct": float(d["primary_pct"]),
                "retry_recovered": int(d["retry"]),
                "missing": int(d["missing"]),
                "errors": int(d["errors"]),
                "timeout": int(d["timeout"] or 0),
                "http": int(d["http"] or 0),
                "connection": int(d["connection"] or 0),
                "other": int(d["other"] or 0),
                "transport_breakdown_observed": transport_breakdown_observed,
                "verifier_ok": int(d["verifier_ok"]),
                "verifier_disagree": int(d["verifier_disagree"]),
                "diag_cache": int(d["diag_cache"]),
            }
            key = tuple(snap[k] for k in (
                "samples", "primary_ok", "retry_recovered", "missing", "errors",
                "timeout", "http", "connection", "other", "transport_breakdown_observed",
                "verifier_ok", "verifier_disagree", "diag_cache"
            ))
            if key not in snapshot_seen:
                snapshots.append(snap)
                snapshot_seen.add(key)

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

    return {"by_contract": by_contract, "snapshots": snapshots, "reject_max": reject_max}


def _contract_summary(flags: list[bool]) -> dict:
    n = len(flags)
    ok = sum(flags)
    transitions = sum(a != b for a, b in zip(flags, flags[1:]))
    return {
        "heartbeat_samples": n,
        "brti_ok_pct": None if n == 0 else round(100.0 * ok / n, 2),
        "na_count": n - ok,
        "max_consecutive_na": _longest_false_streak(flags),
        "availability_transitions": transitions,
    }


def audit(text: str) -> dict:
    parsed = parse(text)
    by_contract = parsed["by_contract"]
    contracts = {ticker: _contract_summary(flags) for ticker, flags in sorted(by_contract.items())}
    all_flags = [flag for ticker in sorted(by_contract) for flag in by_contract[ticker]]
    overall = _contract_summary(all_flags)
    snapshots = parsed["snapshots"]
    latest = snapshots[-1] if snapshots else None

    classes = []
    if overall["na_count"]:
        classes.append("HEARTBEAT_NA_OBSERVED")
    if overall["max_consecutive_na"] >= 2:
        classes.append("HEARTBEAT_NA_STREAK")
    if latest:
        if latest["errors"] > 0:
            classes.append("PRIMARY_ERRORS_PRESENT")
        if latest["retry_recovered"] > 0:
            classes.append("RETRY_RECOVERY_ACTIVE")
        if latest["missing"] > 0:
            classes.append("MISSING_AFTER_RESILIENCE")
        if overall["na_count"] > 0 and latest["missing"] == 0:
            classes.append("HEARTBEAT_VS_CUMULATIVE_MISSING_DIVERGENCE")
        if latest["transport_breakdown_observed"]:
            if latest["timeout"] > 0:
                classes.append("PRIMARY_TIMEOUT_ERRORS_PRESENT")
            if latest["http"] > 0:
                classes.append("PRIMARY_HTTP_ERRORS_PRESENT")
            if latest["connection"] > 0:
                classes.append("PRIMARY_CONNECTION_ERRORS_PRESENT")
            if latest["other"] > 0:
                classes.append("PRIMARY_OTHER_ERRORS_PRESENT")
            transport_total = latest["timeout"] + latest["http"] + latest["connection"] + latest["other"]
            if transport_total != latest["errors"]:
                classes.append("TRANSPORT_BREAKDOWN_MISMATCH")
        if latest["samples"] > 0 and latest["verifier_ok"] == 0 and latest["verifier_disagree"] == 0:
            classes.append("VERIFIER_ACTIVITY_UNOBSERVED")
    else:
        classes.append("NO_RESILIENCE_SNAPSHOT")

    reject_impacts = {}
    for ticker, payload in sorted(parsed["reject_max"].items()):
        reject_impacts[ticker] = {
            "momentum_brti_degraded_rejects_observed": payload.get("MOM_BRTI_DEGRADED", 0),
            "reversal_brti_degraded_rejects_observed": payload.get("REV_BRTI_DEGRADED", 0),
        }

    return {
        "schema_version": 2,
        "collector_identity": "LEAD_V7",
        "overall_heartbeats": overall,
        "contracts": contracts,
        "latest_resilience": latest,
        "resilience_snapshot_count": len(snapshots),
        "failure_classes": classes or ["NO_FAILURE_CLASS_OBSERVED"],
        "qualification_suppression_observed": reject_impacts,
        "research_only": True,
        "production_mutation": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("logfile", nargs="?", help="UTF-8 V7 log file; stdin when omitted")
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args(argv)
    text = Path(args.logfile).read_text(encoding="utf-8") if args.logfile else sys.stdin.read()
    print(json.dumps(audit(text), indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
