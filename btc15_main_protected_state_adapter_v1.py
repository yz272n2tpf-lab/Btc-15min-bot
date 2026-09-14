#!/usr/bin/env python3
"""
BTC15 protected main dashboard state adapter V1.

PURE ADAPTER | NO NETWORK | NO ORDERS

Maps the already-protected production dashboard JSON into integration states.
It does not re-run or weaken EARLY/FINAL models. Nested production fields are
authority; legacy flat fields remain a compatibility fallback for fixtures.
"""
from __future__ import annotations

from typing import Any, Mapping

from btc15_signal_integration_v1 import EarlyState, FinalState
from btc15_protected_module_adapter_v1 import (
    early_state_from_snapshot as legacy_early,
    final_state_from_snapshot as legacy_final,
)


def _map(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _float(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _side(v: Any) -> str | None:
    x = str(v or "").strip().upper()
    return x if x in {"UP", "DOWN"} else None


def canonical_seconds_left(row: Mapping[str, Any]) -> float | None:
    timer = _map(row.get("timer"))
    value = _float(timer.get("seconds_left"))
    if value is None:
        value = _float(row.get("seconds_left"))
    if value is None:
        minutes = _float(timer.get("minutes_left"))
        if minutes is None:
            minutes = _float(row.get("time_left_min"))
        if minutes is not None:
            value = minutes * 60.0
    return None if value is None else max(0.0, value)


def market_value(row: Mapping[str, Any], key: str) -> float | None:
    market = _map(row.get("market"))
    value = _float(market.get(key))
    if value is not None:
        return value
    legacy = {
        "target": "kalshi_target",
        "up_bid": "up_bid",
        "up_ask": "up_ask",
        "down_bid": "down_bid",
        "down_ask": "down_ask",
    }.get(key, key)
    return _float(row.get(legacy))


def early_state_from_main(row: Mapping[str, Any]) -> EarlyState:
    nested = _map(row.get("early"))
    if not nested:
        return legacy_early(row)

    side = _side(nested.get("side"))
    ready = nested.get("ready") is True
    return EarlyState(
        state="QUALIFIED" if ready and side else "PASS",
        side=side,
        ask=_float(nested.get("ask")),
        fair=_float(nested.get("fair")),
        edge=_float(nested.get("edge")),
        seconds_left=canonical_seconds_left(row),
    ).normalized()


def final_state_from_main(row: Mapping[str, Any]) -> FinalState:
    nested = _map(row.get("final"))
    if not nested:
        return legacy_final(row)

    recorded = nested.get("recorded_final_call") is True
    live_ready = nested.get("ready") is True

    if recorded:
        side = _side(nested.get("recorded_side"))
        fair = _float(nested.get("recorded_confidence"))
    else:
        side = _side(nested.get("side"))
        fair = _float(nested.get("confidence"))

    # Fail closed. `ready` / `recorded_final_call` are produced by the protected
    # main service; the >=90% check is only a safety invariant, not a new rule.
    locked = bool(
        (recorded or live_ready)
        and side in {"UP", "DOWN"}
        and fair is not None
        and fair >= 0.90
    )

    return FinalState(
        state="LOCK" if locked else "WATCH",
        side=side,
        fair=fair if locked else None,
        seconds_left=canonical_seconds_left(row),
    ).normalized()


def protected_main_summary(row: Mapping[str, Any]) -> dict:
    early = early_state_from_main(row)
    final = final_state_from_main(row)
    return {
        "contract": str(row.get("contract") or "").strip(),
        "seconds_left": canonical_seconds_left(row),
        "kalshi_target": market_value(row, "target"),
        "up_bid": market_value(row, "up_bid"),
        "up_ask": market_value(row, "up_ask"),
        "down_bid": market_value(row, "down_bid"),
        "down_ask": market_value(row, "down_ask"),
        "early": early,
        "final": final,
    }


__all__ = [
    "canonical_seconds_left",
    "market_value",
    "early_state_from_main",
    "final_state_from_main",
    "protected_main_summary",
]
