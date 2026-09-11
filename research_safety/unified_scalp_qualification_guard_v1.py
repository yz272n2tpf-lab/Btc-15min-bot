#!/usr/bin/env python3
"""Research-only invariant guard for the unified BTC 15m scalp/expansion path.

This module contains no trading actions and no production thresholds. It is an
architecture/data-quality guard: entry price may segment diagnostics, but it
must never reduce the evidence standard required for graduation.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Mapping, Any

UNIFIED_STANDARD = "UNIFIED_SCALP_EXPANSION"
LEGACY_REVERSAL_SOURCE = "ULTRA_CHEAP_REVERSAL_V7"
MIN_RESEARCH_PRICE = 0.03
MAX_RESEARCH_PRICE = 0.45


@dataclass(frozen=True)
class QualificationRecord:
    entry_price: float
    evidence_standard: str
    evidence_pass: bool
    qualified: bool
    source: str = UNIFIED_STANDARD
    max_gain: float | None = None
    adverse: float | None = None
    ticker: str | None = None


def price_zone(entry_price: float) -> str:
    """Diagnostic-only price segmentation; never used to lower evidence."""
    p = float(entry_price)
    if p < MIN_RESEARCH_PRICE or p > MAX_RESEARCH_PRICE:
        return "OUT_OF_RANGE"
    if p < 0.07:
        return "3_7C"
    if p < 0.15:
        return "7_15C"
    if p < 0.30:
        return "15_30C"
    return "30_45C"


def graduation_eligible(record: QualificationRecord) -> bool:
    """Return eligibility under unified architecture invariants.

    This intentionally does not encode the frozen signal thresholds. It checks
    only that a record passed the same upstream evidence standard used across
    3c-45c and is not from the failed research-only reversal lane.
    """
    if price_zone(record.entry_price) == "OUT_OF_RANGE":
        return False
    if record.source == LEGACY_REVERSAL_SOURCE:
        return False
    if record.evidence_standard != UNIFIED_STANDARD:
        return False
    return bool(record.evidence_pass)


def audit_record(record: QualificationRecord) -> list[str]:
    violations: list[str] = []
    eligible = graduation_eligible(record)
    if record.source == LEGACY_REVERSAL_SOURCE and record.qualified:
        violations.append("LEGACY_REVERSAL_CANNOT_GRADUATE")
    if record.evidence_standard != UNIFIED_STANDARD and record.qualified:
        violations.append("NON_UNIFIED_STANDARD_CANNOT_GRADUATE")
    if not record.evidence_pass and record.qualified:
        violations.append("PRICE_OR_OTHER_OVERRIDE_BYPASSED_EVIDENCE")
    if price_zone(record.entry_price) == "OUT_OF_RANGE" and record.qualified:
        violations.append("OUT_OF_RANGE_CANNOT_GRADUATE")
    if record.qualified != eligible:
        violations.append("QUALIFICATION_STATE_INCONSISTENT")
    return violations


def audit_architecture(config: Mapping[str, Any]) -> list[str]:
    """Fail closed on proposed configs that create a cheaper evidence path."""
    violations: list[str] = []
    lanes = list(config.get("graduation_paths", []))
    if lanes != [UNIFIED_STANDARD]:
        violations.append("GRADUATION_MUST_USE_ONE_UNIFIED_PATH")
    if bool(config.get("cheap_price_override", False)):
        violations.append("CHEAP_PRICE_OVERRIDE_FORBIDDEN")
    if bool(config.get("price_adjusts_evidence_standard", False)):
        violations.append("PRICE_DEPENDENT_EVIDENCE_STANDARD_FORBIDDEN")
    research_only = set(config.get("research_only_sources", []))
    if LEGACY_REVERSAL_SOURCE not in research_only:
        violations.append("LEGACY_REVERSAL_MUST_STAY_RESEARCH_ONLY")
    if config.get("production_promotion") not in (None, "NOT_PERFORMED"):
        violations.append("PRODUCTION_PROMOTION_FORBIDDEN")
    return violations


def summarize(records: Iterable[QualificationRecord]) -> dict[str, Any]:
    rows = list(records)
    zones: dict[str, dict[str, Any]] = {}
    violations: list[dict[str, Any]] = []
    grad = 0
    legacy = 0
    for r in rows:
        z = price_zone(r.entry_price)
        bucket = zones.setdefault(z, {
            "n": 0,
            "eligible": 0,
            "hit10": 0,
            "gain_sum": 0.0,
            "gain_n": 0,
            "adverse_sum": 0.0,
            "adverse_n": 0,
            "worst_adverse": None,
        })
        bucket["n"] += 1
        eligible = graduation_eligible(r)
        if eligible:
            grad += 1
            bucket["eligible"] += 1
        if r.source == LEGACY_REVERSAL_SOURCE:
            legacy += 1
        if r.max_gain is not None:
            g = float(r.max_gain)
            bucket["gain_sum"] += g
            bucket["gain_n"] += 1
            if g >= 0.10:
                bucket["hit10"] += 1
        if r.adverse is not None:
            a = float(r.adverse)
            bucket["adverse_sum"] += a
            bucket["adverse_n"] += 1
            if bucket["worst_adverse"] is None or a < bucket["worst_adverse"]:
                bucket["worst_adverse"] = a
        errs = audit_record(r)
        if errs:
            violations.append({"record": asdict(r), "violations": errs})

    for bucket in zones.values():
        bucket["avg_gain"] = (
            bucket["gain_sum"] / bucket["gain_n"] if bucket["gain_n"] else None
        )
        bucket["avg_adverse"] = (
            bucket["adverse_sum"] / bucket["adverse_n"] if bucket["adverse_n"] else None
        )
        bucket["hit10_rate"] = (
            bucket["hit10"] / bucket["gain_n"] if bucket["gain_n"] else None
        )
        del bucket["gain_sum"]
        del bucket["gain_n"]
        del bucket["adverse_sum"]
        del bucket["adverse_n"]

    return {
        "schema": "unified-scalp-qualification-guard-v1",
        "research_only": True,
        "production_promotion": "NOT_PERFORMED",
        "evidence_standard": UNIFIED_STANDARD,
        "records": len(rows),
        "graduation_eligible": grad,
        "legacy_reversal_research_only": legacy,
        "zones": zones,
        "violations": violations,
    }
