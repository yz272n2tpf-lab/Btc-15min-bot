#!/usr/bin/env python3
"""Read-only BRTI continuity audit for BTC15 V6 research logs.

Research-only. NO ORDERS. NO production changes. NO V6 threshold changes.

The audit is deliberately descriptive: it measures BRTI heartbeat continuity,
recovery behavior, degraded-reject counters, and V6 qualification integrity
without imposing qualification thresholds or altering collector output.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

TICKER_RE = re.compile(r"KXBTC15M-[A-Z0-9-]+")
REJECT_RE = re.compile(r"rejects price=(\d+) degraded=(\d+) base=(\d+) high=(\d+)")
BRTI5_RE = re.compile(r"\bbrti5\s+(N/A|[+-]?\d+(?:\.\d+)?)")
BRTI15_RE = re.compile(r"\bbrti15\s+(N/A|[+-]?\d+(?:\.\d+)?)")


@dataclass
class BrtiContinuity:
    ticker: str
    heartbeat_count: int = 0
    brti_available_heartbeats: int = 0
    brti_na_heartbeats: int = 0
    longest_brti_na_streak: int = 0
    brti_recoveries: int = 0
    reject_degraded: int = 0
    v5_candidates: int = 0
    v5_candidates_missing_brti: int = 0
    v6_candidates: int = 0
    v6_missing_brti_integrity_violations: int = 0
    contract_summary_seen: bool = False

    _current_na_streak: int = 0
    _previous_heartbeat_was_na: Optional[bool] = None

    @property
    def brti_availability_pct(self) -> float:
        if not self.heartbeat_count:
            return 0.0
        return 100.0 * self.brti_available_heartbeats / self.heartbeat_count

    def observe_heartbeat(self, brti_is_na: bool) -> None:
        self.heartbeat_count += 1
        if brti_is_na:
            self.brti_na_heartbeats += 1
            self._current_na_streak += 1
            self.longest_brti_na_streak = max(
                self.longest_brti_na_streak, self._current_na_streak
            )
        else:
            self.brti_available_heartbeats += 1
            if self._previous_heartbeat_was_na:
                self.brti_recoveries += 1
            self._current_na_streak = 0
        self._previous_heartbeat_was_na = brti_is_na

    def serializable(self) -> dict:
        payload = asdict(self)
        payload.pop("_current_na_streak", None)
        payload.pop("_previous_heartbeat_was_na", None)
        payload["brti_availability_pct"] = round(self.brti_availability_pct, 3)
        payload["integrity_ok"] = self.v6_missing_brti_integrity_violations == 0
        return payload


def _ticker(line: str) -> Optional[str]:
    match = TICKER_RE.search(line)
    return match.group(0) if match else None


def _candidate_missing_brti(line: str) -> bool:
    m5 = BRTI5_RE.search(line)
    m15 = BRTI15_RE.search(line)
    return (
        m5 is None
        or m15 is None
        or m5.group(1) == "N/A"
        or m15.group(1) == "N/A"
    )


def parse_lines(lines: Iterable[str]) -> Dict[str, BrtiContinuity]:
    contracts: Dict[str, BrtiContinuity] = {}

    for raw in lines:
        line = raw.strip()
        ticker = _ticker(line)
        if ticker is None:
            continue
        contract = contracts.setdefault(ticker, BrtiContinuity(ticker=ticker))

        if "LEAD_V6 HEARTBEAT" in line:
            contract.observe_heartbeat("| BRTI N/A |" in line)

        if "LEAD_V6 CANDIDATE" in line:
            missing = _candidate_missing_brti(line)
            if "| V5_BASELINE |" in line:
                contract.v5_candidates += 1
                if missing:
                    contract.v5_candidates_missing_brti += 1
            elif "| V6_QUALIFIED |" in line:
                contract.v6_candidates += 1
                if missing:
                    contract.v6_missing_brti_integrity_violations += 1

        reject_match = REJECT_RE.search(line)
        if reject_match:
            # Reject summaries are cumulative snapshots; use max, never sum.
            contract.reject_degraded = max(
                contract.reject_degraded, int(reject_match.group(2))
            )

        if "LEAD_V6 CONTRACT_SUMMARY" in line:
            contract.contract_summary_seen = True

    return contracts


def compact_line(contract: BrtiContinuity) -> str:
    return (
        f"V6_BRTI_CONTINUITY | {contract.ticker} | "
        f"hb={contract.heartbeat_count} | "
        f"available={contract.brti_available_heartbeats} "
        f"({contract.brti_availability_pct:.1f}%) | "
        f"na={contract.brti_na_heartbeats} | "
        f"longestNA={contract.longest_brti_na_streak}hb | "
        f"recoveries={contract.brti_recoveries} | "
        f"rejectDegraded={contract.reject_degraded} | "
        f"V5missingBRTI={contract.v5_candidates_missing_brti} | "
        f"V6integrity={contract.v6_missing_brti_integrity_violations}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="saved V6/Railway text log")
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()

    lines = args.log.read_text(encoding="utf-8", errors="ignore").splitlines()
    contracts = parse_lines(lines)

    print("V6 BRTI CONTINUITY AUDIT V1 | RESEARCH ONLY | NO ORDERS")
    for ticker in sorted(contracts):
        print(compact_line(contracts[ticker]))

    if args.json_path:
        payload = {
            "source": str(args.log),
            "contracts": [contracts[t].serializable() for t in sorted(contracts)],
        }
        args.json_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
