#!/usr/bin/env python3
"""Read-only BRTI health/integrity auditor for V6 research logs.

Parses plain Railway log text or JSON-lines records containing a `message` field.
It never calls external services, changes runtime state, or alters qualification logic.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

HB_RE = re.compile(
    r"LEAD_V6 HEARTBEAT \| (?P<ticker>\S+) \| (?P<left>[0-9.]+)m \| .*? \| BRTI (?P<brti>N/A|[-0-9.]+) \|"
)
SUMMARY_RE = re.compile(
    r"LEAD_V6 (?:MIDCONTRACT|CONTRACT_SUMMARY) \| (?P<ticker>\S+).*?rejects price=\d+ degraded=(?P<degraded>\d+)"
)
CAND_RE = re.compile(
    r"LEAD_V6 CANDIDATE \| (?P<grade>V5_BASELINE|V6_QUALIFIED) \| (?P<ticker>\S+) \| (?P<side>UP|DOWN) \| .*?"
    r"brti5 (?P<brti5>N/A|[-+0-9.]+) \| brti15 (?P<brti15>N/A|[-+0-9.]+) \|"
)
RESULT_RE = re.compile(
    r"LEAD_V6 RESULT \| (?P<grade>V5_BASELINE|V6_QUALIFIED) \| (?P<ticker>\S+) \| (?P<side>UP|DOWN) \| .*?"
    r"max_exec_gain (?P<gain>[-+0-9.]+) \| .*? hit10 (?P<hit10>True|False)"
)


def extract_message(line: str) -> str:
    line = line.strip()
    if not line:
        return ""
    try:
        obj = json.loads(line)
    except Exception:
        return line
    if isinstance(obj, dict) and isinstance(obj.get("message"), str):
        return obj["message"]
    return line


@dataclass
class Outage:
    ticker: str
    samples: int
    start_left_min: float
    end_left_min: float
    estimated_seconds: float
    recovered: bool


class BrtiAudit:
    def __init__(self) -> None:
        self.total_hb = 0
        self.na_hb = 0
        self.recoveries = 0
        self._open = {}
        self.outages: list[Outage] = []
        self.degraded_max = defaultdict(int)
        self.v5_candidates_missing_brti = 0
        self.v6_candidates_missing_brti = 0
        self.v6_missing_brti_examples: list[str] = []
        self.hit10_boundary_anomalies: list[str] = []
        self.warning_count = 0

    def _finalize_outage(self, ticker: str, recovery_left: float | None, recovered: bool) -> None:
        s = self._open.pop(ticker, None)
        if not s:
            return
        if recovery_left is not None:
            seconds = max(0.0, (s["start_left"] - recovery_left) * 60.0)
            end_left = recovery_left
        else:
            seconds = max(30.0, (s["start_left"] - s["last_left"]) * 60.0 + 30.0)
            end_left = s["last_left"]
        self.outages.append(
            Outage(
                ticker=ticker,
                samples=s["samples"],
                start_left_min=round(s["start_left"], 3),
                end_left_min=round(end_left, 3),
                estimated_seconds=round(seconds, 1),
                recovered=recovered,
            )
        )
        if recovered:
            self.recoveries += 1

    def consume(self, message: str) -> None:
        if not message:
            return
        if "LEAD_V6 WARNING" in message:
            self.warning_count += 1

        m = HB_RE.search(message)
        if m:
            ticker = m.group("ticker")
            left = float(m.group("left"))
            brti = m.group("brti")
            self.total_hb += 1
            if brti == "N/A":
                self.na_hb += 1
                state = self._open.get(ticker)
                if state is None:
                    self._open[ticker] = {
                        "samples": 1,
                        "start_left": left,
                        "last_left": left,
                    }
                else:
                    state["samples"] += 1
                    state["last_left"] = left
            else:
                self._finalize_outage(ticker, recovery_left=left, recovered=True)

        m = SUMMARY_RE.search(message)
        if m:
            ticker = m.group("ticker")
            self.degraded_max[ticker] = max(self.degraded_max[ticker], int(m.group("degraded")))

        m = CAND_RE.search(message)
        if m:
            missing = m.group("brti5") == "N/A" or m.group("brti15") == "N/A"
            if missing and m.group("grade") == "V5_BASELINE":
                self.v5_candidates_missing_brti += 1
            if missing and m.group("grade") == "V6_QUALIFIED":
                self.v6_candidates_missing_brti += 1
                if len(self.v6_missing_brti_examples) < 20:
                    self.v6_missing_brti_examples.append(message)

        m = RESULT_RE.search(message)
        if m:
            gain = float(m.group("gain"))
            if gain >= 0.100 and m.group("hit10") == "False":
                if len(self.hit10_boundary_anomalies) < 20:
                    self.hit10_boundary_anomalies.append(message)

    def finish(self) -> None:
        for ticker in list(self._open):
            self._finalize_outage(ticker, recovery_left=None, recovered=False)

    def report(self) -> dict:
        fresh = self.total_hb - self.na_hb
        max_outage = max((o.estimated_seconds for o in self.outages), default=0.0)
        return {
            "heartbeats": {
                "total": self.total_hb,
                "brti_fresh": fresh,
                "brti_na": self.na_hb,
                "fresh_rate_pct": round((100.0 * fresh / self.total_hb), 1) if self.total_hb else None,
                "outage_streaks": len(self.outages),
                "recoveries": self.recoveries,
                "max_outage_seconds_est": max_outage,
                "streaks": [asdict(o) for o in self.outages],
            },
            "degraded_rejects": {
                "contracts_seen": len(self.degraded_max),
                "sum_contract_max": sum(self.degraded_max.values()),
                "max_per_contract": max(self.degraded_max.values(), default=0),
                "by_contract": dict(sorted(self.degraded_max.items())),
            },
            "candidate_impact": {
                "v5_candidates_missing_brti": self.v5_candidates_missing_brti,
                "v6_candidates_missing_brti": self.v6_candidates_missing_brti,
            },
            "integrity": {
                "v6_missing_brti_violations": self.v6_candidates_missing_brti,
                "v6_missing_brti_examples": self.v6_missing_brti_examples,
                "display_hit10_boundary_anomalies": len(self.hit10_boundary_anomalies),
                "display_hit10_boundary_examples": self.hit10_boundary_anomalies,
                "warnings": self.warning_count,
                "boundary_note": "A displayed +0.100 gain with hit10=False may be float/rounding boundary behavior; this auditor flags it for review without changing scoring.",
            },
        }


def audit_lines(lines: Iterable[str]) -> dict:
    audit = BrtiAudit()
    for line in lines:
        audit.consume(extract_message(line))
    audit.finish()
    return audit.report()


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only BRTI/V6 research log auditor")
    ap.add_argument("logfile", help="Plain text or JSONL Railway log export")
    ap.add_argument("--compact", action="store_true", help="Print compact JSON")
    args = ap.parse_args()
    path = Path(args.logfile)
    report = audit_lines(path.read_text(encoding="utf-8", errors="replace").splitlines())
    print(json.dumps(report, indent=None if args.compact else 2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
