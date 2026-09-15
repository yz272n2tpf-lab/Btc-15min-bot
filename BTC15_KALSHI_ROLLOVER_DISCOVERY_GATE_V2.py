#!/usr/bin/env python3
"""
Frozen gate scorer for BTC15 Kalshi rollover discovery Probe V2.

PURE / OFFLINE | READ ONLY | NO NETWORK | NO ORDERS

Predeclared gate:
- at least 4 separate Probe V2 rollovers;
- at least 3 valid direct-vs-broad comparisons;
- exact identity and expected open/close clock correct on every reviewed direct sample;
- exact ACTIVE+USABLE-QUOTED by +5s on at least 75% of reviewed rollovers;
- median lead vs production-style broad ACTIVE discovery at least 10s.

PASS authorizes only a separate shadow fallback validation. It never authorizes
production changes or order behavior.
"""
from __future__ import annotations

import statistics
from typing import Any, Iterable, Mapping

VERSION = "BTC15_KALSHI_ROLLOVER_DISCOVERY_GATE_V2"
MIN_ROLLOVERS = 4
MIN_COMPARISONS = 3
MAX_EXACT_ACTIVE_QUOTED_SEC = 5.0
MIN_FAST_SHARE = 0.75
MIN_MEDIAN_LEAD_SEC = 10.0


def _f(v: Any) -> float | None:
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def score(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    data = [dict(r) for r in rows]
    n = len(data)
    identity_all = all(r.get("identity_all") is True for r in data) if data else False
    clock_all = all(r.get("clock_all") is True for r in data) if data else False

    exact_times = [_f(r.get("exact_active_quoted")) for r in data]
    exact_valid = [x for x in exact_times if x is not None]
    fast_n = sum(x <= MAX_EXACT_ACTIVE_QUOTED_SEC + 1e-12 for x in exact_valid)
    fast_share = fast_n / len(exact_valid) if exact_valid else None

    leads = []
    comparison_rows = 0
    for r in data:
        exact = _f(r.get("exact_active_quoted"))
        broad = _f(r.get("broad_active"))
        if exact is None or broad is None:
            continue
        comparison_rows += 1
        leads.append(broad - exact)
    median_lead = statistics.median(leads) if leads else None

    ready = bool(n >= MIN_ROLLOVERS and comparison_rows >= MIN_COMPARISONS)
    passed = bool(
        ready
        and identity_all
        and clock_all
        and fast_share is not None
        and fast_share >= MIN_FAST_SHARE - 1e-12
        and median_lead is not None
        and median_lead >= MIN_MEDIAN_LEAD_SEC - 1e-12
    )
    status = "COLLECTING" if not ready else ("READY_FOR_SHADOW_FALLBACK_TEST" if passed else "REVIEW_SAMPLE_READY_REJECTED")

    return {
        "version": VERSION,
        "status": status,
        "rollovers": n,
        "valid_comparisons": comparison_rows,
        "identity_all": identity_all,
        "clock_all": clock_all,
        "exact_active_quoted_by_5s_n": fast_n,
        "exact_active_quoted_valid_n": len(exact_valid),
        "exact_active_quoted_by_5s_share": fast_share,
        "median_lead_sec": median_lead,
        "sample_ready": ready,
        "pass": passed,
        "authorizes_shadow_fallback_test_only": passed,
        "authorizes_production_change": False,
        "orders": False,
    }


if __name__ == "__main__":
    print(f"{VERSION} | pure score(rows) | NO NETWORK | NO ORDERS")
