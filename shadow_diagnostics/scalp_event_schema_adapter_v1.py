#!/usr/bin/env python3
"""BTC15 scalp event-tape schema adapter V1.

RESEARCH ONLY | READ ONLY | NO ORDERS

Maps the actual generalized collector field names into the canonical causal
feature names used by the shadow research models. Raw fields are preserved.
Only aliases/units are adapted; no future/path/result label is ever promoted to
an input feature.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

VERSION = "BTC15_SCALP_EVENT_SCHEMA_ADAPTER_V1"

# Canonical feature -> accepted source names. Order matters.
ALIASES: dict[str, tuple[str, ...]] = {
    "spread": ("spread", "entry_spread"),
    "max_possible_upside": ("max_possible_upside", "max_possible_upside_c"),
    "btc_move5_side": ("btc_move5_side", "btc5"),
    "btc_move15_side": ("btc_move15_side", "btc15"),
    "btc_move30_side": ("btc_move30_side", "btc30"),
    "brti_move5_side": ("brti_move5_side", "brti5"),
    "brti_move15_side": ("brti_move15_side", "brti15"),
    "ask_move5": ("ask_move5", "ask5"),
    "ask_move15": ("ask_move15", "ask15"),
    "acceleration": ("acceleration", "accel"),
    "recent_range60": ("recent_range60", "recent_btc_range60"),
    "btc_move5_norm": ("btc_move5_norm", "btc5_norm"),
    "btc_move15_norm": ("btc_move15_norm", "btc15_norm"),
    "brti_latency_sec": ("brti_latency_sec", "brti_latency_ms"),
}

# Candidate-time direct dependencies that must exist/populate in the real tape.
DIRECT_REQUIRED = (
    "entry_ask", "seconds_left", "confirm_count", "structure_ok",
    "btc_against_side", "brti_against_side", "dual_reversal_evidence",
    "brti_status",
)

# Explicitly outcome/future fields that this adapter must never alias into inputs.
FORBIDDEN_SOURCE_TOKENS = (
    "hit5", "hit10", "hit15", "hit20", "hit30", "horizon", "peak_exec",
    "max_adverse", "giveback", "profit_floor", "protect_armed", "result",
    "future", "outcome",
)


def present(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    return True


def number(v: Any) -> float | None:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def source_for(row: Mapping[str, Any], canonical: str) -> str | None:
    for name in ALIASES.get(canonical, (canonical,)):
        if present(row.get(name)):
            return name
    return None


def convert(canonical: str, source: str, value: Any) -> Any:
    x = number(value)
    if x is None:
        return value
    if canonical == "max_possible_upside" and source == "max_possible_upside_c":
        return x / 100.0
    if canonical == "brti_latency_sec" and source == "brti_latency_ms":
        return x / 1000.0
    return x


def adapt_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for canonical in ALIASES:
        if present(out.get(canonical)):
            continue
        source = source_for(row, canonical)
        if source is not None:
            out[canonical] = convert(canonical, source, row.get(source))
    return out


def adapt_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [adapt_row(r) for r in rows]


def candidate_schema_status(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    candidates = [r for r in rows if str(r.get("record_type") or "").strip().upper() == "CANDIDATE"]
    alias_status: dict[str, Any] = {}
    missing: list[str] = []
    for canonical, names in ALIASES.items():
        populated = [name for name in names if any(present(r.get(name)) for r in candidates)]
        alias_status[canonical] = {"accepted_sources": list(names), "populated_sources": populated}
        if not populated:
            missing.append(canonical)

    direct_status = {
        name: any(present(r.get(name)) for r in candidates)
        for name in DIRECT_REQUIRED
    }
    missing.extend(name for name, ok in direct_status.items() if not ok)

    return {
        "version": VERSION,
        "orders": False,
        "candidate_rows": len(candidates),
        "alias_status": alias_status,
        "direct_required": direct_status,
        "missing_source_dependencies": sorted(set(missing)),
        "ready": bool(candidates) and not missing,
    }


def assert_integrity() -> None:
    bad: list[tuple[str, str]] = []
    for canonical, sources in ALIASES.items():
        for source in sources:
            low = source.lower()
            if any(token in low for token in FORBIDDEN_SOURCE_TOKENS):
                bad.append((canonical, source))
    if bad:
        raise RuntimeError(f"future/outcome source leaked into schema adapter: {bad}")


assert_integrity()
