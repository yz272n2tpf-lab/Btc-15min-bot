#!/usr/bin/env python3
"""
Offline decision scorer for BTC15 rollover discovery probe summaries.

PURE EVALUATION | NO NETWORK | NO SERVICE MUTATION | NO ORDERS | NO AUTO-PROMOTION
"""
from __future__ import annotations

import math
import statistics
from typing import Any, Iterable, Mapping

MIN_ROLLOVERS = 4
MIN_VALID_COMPARISONS = 3
MAX_EXACT_ACTIVE_QUOTED_SEC = 5.0
MIN_FAST_RATE = 0.75
MIN_MEDIAN_LEAD_SEC = 10.0


def _f(v: Any) -> float | None:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def score(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(r) for r in rows]
    total = len(rows)

    identity_all = all(r.get("identity_all") is True and r.get("wrong_identity") is not True for r in rows) if rows else False
    clock_all = all(r.get("clock_all") is True and r.get("wrong_clock") is not True for r in rows) if rows else False

    exact_fast = []
    valid = []
    leads = []
    for r in rows:
        exact = _f(r.get("exact_active_quoted"))
        broad = _f(r.get("broad_active"))
        direct_integrity = bool(
            r.get("identity_all") is True
            and r.get("clock_all") is True
            and r.get("wrong_identity") is not True
            and r.get("wrong_clock") is not True
        )
        exact_fast.append(bool(direct_integrity and exact is not None and exact <= MAX_EXACT_ACTIVE_QUOTED_SEC))
        if direct_integrity and exact is not None and broad is not None:
            valid.append(r)
            leads.append(broad - exact)

    fast_n = sum(exact_fast)
    fast_rate = fast_n / total if total else None
    median_lead = statistics.median(leads) if leads else None
    sample_ready = bool(total >= MIN_ROLLOVERS and len(valid) >= MIN_VALID_COMPARISONS)

    criteria = {
        "identity_correct_all": identity_all,
        "clock_correct_all": clock_all,
        "exact_active_quoted_by_5s_rate_ge_75pct": bool(fast_rate is not None and fast_rate >= MIN_FAST_RATE),
        "median_direct_lead_ge_10s": bool(median_lead is not None and median_lead >= MIN_MEDIAN_LEAD_SEC),
        "valid_comparisons_ge_3": len(valid) >= MIN_VALID_COMPARISONS,
        "rollovers_ge_4": total >= MIN_ROLLOVERS,
    }
    passed = bool(sample_ready and all(criteria.values()))
    status = (
        "READY_FOR_SHADOW_FALLBACK_TEST"
        if passed
        else "REVIEW_SAMPLE_READY_REJECTED"
        if sample_ready
        else "COLLECTING_ROLLOVER_PROBE"
    )
    return {
        "version": "BTC15_ROLLOVER_DISCOVERY_GATE_V1",
        "status": status,
        "rollovers": total,
        "valid_comparisons": len(valid),
        "exact_fast_n": fast_n,
        "exact_fast_rate": fast_rate,
        "median_direct_lead_sec": median_lead,
        "lead_seconds": leads,
        "sample_ready": sample_ready,
        "pass": passed,
        "criteria": criteria,
        "auto_promote": False,
        "production_change_allowed": False,
        "strategy_change_allowed": False,
        "orders": False,
    }


if __name__ == "__main__":
    print("BTC15_ROLLOVER_DISCOVERY_GATE_V1 | import score(rows) | OFFLINE ONLY | NO ORDERS")
