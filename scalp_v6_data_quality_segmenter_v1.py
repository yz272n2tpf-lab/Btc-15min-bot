#!/usr/bin/env python3
"""Read-only V6 contract data-quality segmenter.

Research-only / signal-only. NO ORDERS. NO production changes. NO V6 threshold changes.

Purpose
-------
Parse saved Railway/V6 text logs and produce contract-level raw data-quality metrics so
clean and degraded collection periods can be analyzed separately *after* a forward test.
This tool never changes signal qualification. It intentionally has no default clean/degraded
pass threshold; optional audit cutoffs are reporting-only and must be supplied explicitly.

Key safeguards
--------------
- Cumulative reject summaries are de-duplicated by taking the maximum observed counter per
  contract, rather than summing repeated MIDCONTRACT / CONTRACT_SUMMARY snapshots.
- Any V6_QUALIFIED candidate that shows missing brti5 or brti15 is flagged as an integrity
  violation; it is never silently accepted by this audit.
- A displayed +0.100 max gain with hit10=False is recorded as a score-boundary review item,
  not rewritten or re-scored.
- Heartbeat BRTI availability and heartbeat spacing are reported as raw evidence.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

TICKER_RE = re.compile(r"KXBTC15M-[A-Z0-9-]+")
LEFT_RE = re.compile(r"\bleft\s+([0-9]+(?:\.[0-9]+)?)s\b")
HEARTBEAT_MIN_RE = re.compile(r"\|\s*([0-9]+(?:\.[0-9]+)?)m\s*\|\s*BTC\b")
REJECT_RE = re.compile(r"rejects price=(\d+) degraded=(\d+) base=(\d+) high=(\d+)")
GAIN_RE = re.compile(r"max_exec_gain\s+([+-]?\d+(?:\.\d+)?)")
BRTI5_RE = re.compile(r"\bbrti5\s+(N/A|[+-]?\d+(?:\.\d+)?)")
BRTI15_RE = re.compile(r"\bbrti15\s+(N/A|[+-]?\d+(?:\.\d+)?)")


@dataclass
class ContractQuality:
    ticker: str
    heartbeat_count: int = 0
    brti_na_heartbeats: int = 0
    heartbeat_left_s: List[float] = field(default_factory=list)
    max_heartbeat_gap_s: Optional[float] = None
    reject_price: int = 0
    reject_degraded: int = 0
    reject_base: int = 0
    reject_high: int = 0
    v5_candidates: int = 0
    v6_candidates: int = 0
    v5_results: int = 0
    v6_results: int = 0
    v5_candidate_brti_missing: int = 0
    v6_missing_brti_integrity_violations: int = 0
    score_boundary_review_items: int = 0
    warnings: int = 0
    contract_summary_seen: bool = False

    @property
    def brti_na_rate_pct(self) -> float:
        if not self.heartbeat_count:
            return 0.0
        return 100.0 * self.brti_na_heartbeats / self.heartbeat_count

    def finalize(self) -> None:
        if len(self.heartbeat_left_s) < 2:
            self.max_heartbeat_gap_s = None
            return
        gaps = []
        for previous, current in zip(self.heartbeat_left_s, self.heartbeat_left_s[1:]):
            gap = previous - current
            if gap >= 0:
                gaps.append(gap)
        self.max_heartbeat_gap_s = max(gaps) if gaps else None

    def audit_labels(self, max_brti_na_rate: Optional[float], max_heartbeat_gap: Optional[float]) -> List[str]:
        labels: List[str] = []
        if self.v6_missing_brti_integrity_violations:
            labels.append("V6_MISSING_BRTI_INTEGRITY")
        if self.warnings:
            labels.append("WARNING_PRESENT")
        if self.score_boundary_review_items:
            labels.append("SCORE_BOUNDARY_REVIEW")
        if max_brti_na_rate is not None and self.brti_na_rate_pct > max_brti_na_rate:
            labels.append("BRTI_NA_RATE_OVER_AUDIT_LIMIT")
        if (
            max_heartbeat_gap is not None
            and self.max_heartbeat_gap_s is not None
            and self.max_heartbeat_gap_s > max_heartbeat_gap
        ):
            labels.append("HEARTBEAT_GAP_OVER_AUDIT_LIMIT")
        return labels

    def serializable(self, max_brti_na_rate: Optional[float], max_heartbeat_gap: Optional[float]) -> dict:
        d = asdict(self)
        d["brti_na_rate_pct"] = round(self.brti_na_rate_pct, 3)
        d["audit_labels"] = self.audit_labels(max_brti_na_rate, max_heartbeat_gap)
        return d


def _ticker(line: str) -> Optional[str]:
    m = TICKER_RE.search(line)
    return m.group(0) if m else None


def _candidate_missing_brti(line: str) -> bool:
    m5 = BRTI5_RE.search(line)
    m15 = BRTI15_RE.search(line)
    return m5 is None or m15 is None or m5.group(1) == "N/A" or m15.group(1) == "N/A"


def parse_lines(lines: Iterable[str]) -> Dict[str, ContractQuality]:
    contracts: Dict[str, ContractQuality] = {}

    for raw in lines:
        line = raw.strip()
        ticker = _ticker(line)
        if ticker is None:
            continue
        c = contracts.setdefault(ticker, ContractQuality(ticker=ticker))

        if "LEAD_V6 HEARTBEAT" in line:
            c.heartbeat_count += 1
            if "| BRTI N/A |" in line:
                c.brti_na_heartbeats += 1
            ml = HEARTBEAT_MIN_RE.search(line)
            if ml:
                c.heartbeat_left_s.append(float(ml.group(1)) * 60.0)
            else:
                ml = LEFT_RE.search(line)
                if ml:
                    c.heartbeat_left_s.append(float(ml.group(1)))

        if "LEAD_V6 CANDIDATE" in line:
            missing = _candidate_missing_brti(line)
            if "| V5_BASELINE |" in line:
                c.v5_candidates += 1
                if missing:
                    c.v5_candidate_brti_missing += 1
            elif "| V6_QUALIFIED |" in line:
                c.v6_candidates += 1
                if missing:
                    c.v6_missing_brti_integrity_violations += 1

        if "LEAD_V6 RESULT" in line:
            if "| V5_BASELINE |" in line:
                c.v5_results += 1
            elif "| V6_QUALIFIED |" in line:
                c.v6_results += 1

            mg = GAIN_RE.search(line)
            if mg and "hit10 False" in line:
                gain = float(mg.group(1))
                if round(gain, 3) == 0.100:
                    c.score_boundary_review_items += 1

        mr = REJECT_RE.search(line)
        if mr:
            c.reject_price = max(c.reject_price, int(mr.group(1)))
            c.reject_degraded = max(c.reject_degraded, int(mr.group(2)))
            c.reject_base = max(c.reject_base, int(mr.group(3)))
            c.reject_high = max(c.reject_high, int(mr.group(4)))

        if "LEAD_V6 WARNING" in line:
            c.warnings += 1
        if "LEAD_V6 CONTRACT_SUMMARY" in line:
            c.contract_summary_seen = True

    for c in contracts.values():
        c.finalize()
    return contracts


def compact_line(c: ContractQuality, max_brti_na_rate: Optional[float], max_heartbeat_gap: Optional[float]) -> str:
    gap = "N/A" if c.max_heartbeat_gap_s is None else f"{c.max_heartbeat_gap_s:.1f}s"
    labels = c.audit_labels(max_brti_na_rate, max_heartbeat_gap)
    label_text = ",".join(labels) if labels else "NONE"
    return (
        f"V6_DATA_QUALITY | {c.ticker} | hb={c.heartbeat_count} | "
        f"brtiNA={c.brti_na_heartbeats} ({c.brti_na_rate_pct:.1f}%) | maxGap={gap} | "
        f"rejectDegraded={c.reject_degraded} | V5cand={c.v5_candidates} | V6cand={c.v6_candidates} | "
        f"V5missingBRTI={c.v5_candidate_brti_missing} | V6integrity={c.v6_missing_brti_integrity_violations} | "
        f"boundaryReview={c.score_boundary_review_items} | warnings={c.warnings} | labels={label_text}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only contract-level V6/BRTI data-quality audit")
    ap.add_argument("log", type=Path, help="saved Railway/V6 text log")
    ap.add_argument("--json", dest="json_path", type=Path, help="optional JSON output path")
    ap.add_argument(
        "--max-brti-na-rate",
        type=float,
        default=None,
        help="optional reporting-only BRTI N/A percentage cutoff; no default is imposed",
    )
    ap.add_argument(
        "--max-heartbeat-gap",
        type=float,
        default=None,
        help="optional reporting-only heartbeat-gap cutoff in seconds; no default is imposed",
    )
    args = ap.parse_args()

    lines = args.log.read_text(encoding="utf-8", errors="ignore").splitlines()
    contracts = parse_lines(lines)

    print("V6 DATA QUALITY SEGMENTER V1 | RESEARCH ONLY | NO ORDERS | RAW AUDIT")
    for ticker in sorted(contracts):
        print(compact_line(contracts[ticker], args.max_brti_na_rate, args.max_heartbeat_gap))

    if args.json_path:
        payload = {
            "source": str(args.log),
            "audit_cutoffs": {
                "max_brti_na_rate": args.max_brti_na_rate,
                "max_heartbeat_gap": args.max_heartbeat_gap,
            },
            "contracts": [
                contracts[t].serializable(args.max_brti_na_rate, args.max_heartbeat_gap)
                for t in sorted(contracts)
            ],
        }
        args.json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
