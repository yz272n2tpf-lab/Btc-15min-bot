#!/usr/bin/env python3
"""Future-only operational gate for exact KXBTC15M rollover discovery.

PURE / OFFLINE | READ ONLY | NO NETWORK | NO ORDERS

This scorer is frozen for boundaries at/after 2026-09-15T20:00:00Z and must
never score the four Probe V2 development rows.
"""
from __future__ import annotations

import statistics
from typing import Any, Iterable, Mapping

VERSION = "BTC15_KALSHI_ROLLOVER_OPERATIONAL_GATE_V3"
CUTOFF_UTC = "2026-09-15T20:00:00Z"
MIN_ROLLOVERS = 8
MIN_COMPARISONS = 6
MAX_EXACT_USABLE_SEC = 15.0
MIN_FAST_SHARE = 0.875
MIN_MEDIAN_LEAD_SEC = 15.0


def _f(v: Any) -> float | None:
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def score(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    data = [dict(r) for r in rows]
    n = len(data)
    identity_all = bool(data) and all(r.get("identity_all") is True for r in data)
    clock_all = bool(data) and all(r.get("clock_all") is True for r in data)

    exact = [_f(r.get("exact_active_quoted")) for r in data]
    exact_valid = [x for x in exact if x is not None]
    by15 = sum(x <= MAX_EXACT_USABLE_SEC + 1e-12 for x in exact_valid)
    by15_share = by15 / n if n else None

    leads: list[float] = []
    all_direct_before_broad = True
    comparisons = 0
    for r in data:
        e = _f(r.get("exact_active_quoted"))
        b = _f(r.get("broad_active"))
        if e is None or b is None:
            continue
        comparisons += 1
        lead = b - e
        leads.append(lead)
        if lead <= 0.0:
            all_direct_before_broad = False

    median_lead = statistics.median(leads) if leads else None
    ready = bool(n >= MIN_ROLLOVERS and comparisons >= MIN_COMPARISONS)
    passed = bool(
        ready
        and identity_all
        and clock_all
        and by15_share is not None
        and by15_share >= MIN_FAST_SHARE - 1e-12
        and all_direct_before_broad
        and median_lead is not None
        and median_lead >= MIN_MEDIAN_LEAD_SEC - 1e-12
    )
    status = (
        "COLLECTING_FRESH_OPERATIONAL_REPLICATION"
        if not ready
        else "READY_FOR_EXACT_TICKER_SHADOW_VALIDATION"
        if passed
        else "OPERATIONAL_REPLICATION_REJECTED"
    )
    return {
        "version": VERSION,
        "cutoff_utc": CUTOFF_UTC,
        "status": status,
        "rollovers": n,
        "valid_comparisons": comparisons,
        "identity_all": identity_all,
        "clock_all": clock_all,
        "exact_active_quoted_by_15s_n": by15,
        "exact_active_quoted_by_15s_share": by15_share,
        "all_direct_before_broad": all_direct_before_broad,
        "median_lead_sec": median_lead,
        "sample_ready": ready,
        "pass": passed,
        "authorizes_shadow_validation_only": passed,
        "authorizes_production_change": False,
        "orders": False,
    }


if __name__ == "__main__":
    print(f"{VERSION} | pure score(rows) | FRESH CUTOFF {CUTOFF_UTC} | NO ORDERS")
