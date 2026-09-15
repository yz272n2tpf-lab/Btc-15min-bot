#!/usr/bin/env python3
"""
BTC15 SCALP candidate feature inventory V1.

RESEARCH INVENTORY ONLY | READ ONLY | SIGNAL ONLY | NO ORDERS

Purpose
-------
Inspect the candidate fields that the frozen generalized SCALP collector already
records on untouched forward data. This module does not score, select, tighten,
or promote a strategy rule. It exists only to identify which existing non-price,
non-time telemetry could be eligible for a future chronological development /
holdout diagnostic after the btc30-only tightening study was rejected by holdout.

Guardrails
----------
- No Kalshi entry-price filter is created.
- No seconds-left/time window is created.
- btc30 is reported as already-tested, not silently retested as a new feature.
- IDs, timestamps, contract fields, bid/ask/price fields, and result/path fields
  are excluded from the next-feature candidate list.
- No order capability exists.
"""
from __future__ import annotations

import json
import math
import sys
from typing import Any, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_CANDIDATE_FEATURE_INVENTORY_V1"
MIN_NONEMPTY = 10
MIN_NUMERIC_RATIO = 0.95
ALREADY_TESTED = {"btc30"}

# Exclude action/identity/price/time/result semantics from any proposed next
# signal-strength diagnostic. This inventory is intentionally conservative.
BANNED_EXACT = {
    "record_type",
    "contract",
    "candidate_id",
    "timestamp_utc",
    "side",
    "entry_ask",
    "seconds_left",
}
BANNED_TERMS = (
    "price",
    "bid",
    "ask",
    "entry",
    "second",
    "time",
    "timestamp",
    "contract",
    "candidate",
    "result",
    "exit",
    "gain",
    "peak",
    "adverse",
    "order",
)


def _nonempty(v: Any) -> bool:
    return v is not None and (not isinstance(v, str) or bool(v.strip()))


def _finite_float(v: Any) -> float | None:
    if not _nonempty(v):
        return None
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _banned_for_next(field: str) -> bool:
    f = str(field or "").strip().lower()
    return f in BANNED_EXACT or any(term in f for term in BANNED_TERMS)


def inventory_candidate_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    candidates = [dict(r) for r in rows]
    fields = sorted({str(k) for r in candidates for k in r.keys() if str(k)})
    stats: dict[str, dict[str, Any]] = {}

    for field in fields:
        vals = [r.get(field) for r in candidates]
        nonempty = [v for v in vals if _nonempty(v)]
        numeric = [_finite_float(v) for v in nonempty]
        numeric_n = sum(v is not None for v in numeric)
        nonempty_n = len(nonempty)
        ratio = None if not nonempty_n else numeric_n / nonempty_n
        stats[field] = {
            "nonempty_n": nonempty_n,
            "numeric_n": numeric_n,
            "numeric_ratio": ratio,
            "already_tested": field.lower() in ALREADY_TESTED,
            "banned_from_next_diagnostic": _banned_for_next(field),
        }

    numeric_fields = [
        f for f in fields
        if stats[f]["nonempty_n"] >= MIN_NONEMPTY
        and stats[f]["numeric_ratio"] is not None
        and float(stats[f]["numeric_ratio"]) >= MIN_NUMERIC_RATIO
    ]
    next_nonprice_numeric = [
        f for f in numeric_fields
        if not stats[f]["banned_from_next_diagnostic"]
        and not stats[f]["already_tested"]
    ]

    return {
        "version": VERSION,
        "research_only": True,
        "orders": False,
        "manual_execution_only": True,
        "candidate_n": len(candidates),
        "candidate_fields": fields,
        "numeric_fields": numeric_fields,
        "already_tested_fields": sorted(f for f in numeric_fields if stats[f]["already_tested"]),
        "next_nonprice_numeric_fields": next_nonprice_numeric,
        "field_stats": stats,
        "entry_price_filter_applied": False,
        "fixed_time_window_applied": False,
        "feature_selected": False,
        "auto_promote_allowed": False,
        "note": (
            "Inventory only. Any future feature diagnostic must use chronological "
            "development/holdout validation and remain research-only until reviewed."
        ),
    }


def audit(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    candidates = forward.forward_candidates([dict(r) for r in rows])
    return inventory_candidate_rows(candidates)


def main() -> int:
    if "--live" not in sys.argv:
        print(f"{VERSION} | use audit(rows) or --live | RESEARCH ONLY | NO ORDERS")
        return 0
    rows, sha = forward.fetch_csv_rows()
    out = audit(rows)
    out["source_sha256"] = sha
    print(
        "SCALP FEATURE INVENTORY | "
        f"candidates={out['candidate_n']} | "
        f"numeric={','.join(out['numeric_fields']) or '-'} | "
        f"already_tested={','.join(out['already_tested_fields']) or '-'} | "
        f"next_nonprice={','.join(out['next_nonprice_numeric_fields']) or '-'} | "
        "INVENTORY ONLY | NO FEATURE SELECTED | NO ORDERS",
        flush=True,
    )
    if "--json" in sys.argv:
        print(json.dumps(out, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
