#!/usr/bin/env python3
"""Conservative source adapters for the BTC15 Integrity Sentinel V1.

Extract only explicitly present facts. Missing values remain missing; absence is
never converted into a healthy state.
"""
from __future__ import annotations

import math
from typing import Any, Mapping
from integrity_sentinel.identity_v1 import exact_contract


def _map(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _finite(v: Any, *, scale: float = 1.0) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v) * scale
    except (TypeError, ValueError, OverflowError):
        return None
    return x if math.isfinite(x) and x >= 0 else None


def _contract(payload: Mapping[str, Any]) -> str | None:
    return exact_contract(payload, _map(payload.get("market")), _map(payload.get("live")))


def _counter(payload, key):
    value = payload.get(key)
    if key not in payload:
        return None
    if type(value) is not int or value < 0:
        raise ValueError(f"invalid BRTI counter: {key}")
    return value


def _seconds_left(payload: Mapping[str, Any]) -> float | None:
    timer = _map(payload.get("timer"))
    for obj, key, scale in (
        (timer, "seconds_left", 1.0), (payload, "seconds_left", 1.0),
        (payload, "canonical_seconds_left", 1.0), (timer, "minutes_left", 60.0),
        (payload, "time_left_min", 60.0),
    ):
        value = _finite(obj.get(key), scale=scale)
        if value is not None:
            return value
    return None


def adapt_brti_shared(payload: Mapping[str, Any]) -> dict[str, Any]:
    age_ms = _finite(payload.get("age_ms"))
    return {
        "contract_id": _contract(payload),
        "brti_age_sec": None if age_ms is None else age_ms / 1000.0,
        "brti_feed_clean": payload.get("clean_for_qualification") if isinstance(payload.get("clean_for_qualification"), bool) else None,
        "brti_status": payload.get("status"),
        "brti_seq": _counter(payload, "sequence"),
        "brti_attempts_total": _counter(payload, "upstream_attempts"),
        "brti_upstream_ok_total": _counter(payload, "upstream_ok"),
        "brti_errors_total": _counter(payload, "upstream_errors"),
        "brti_429_total": _counter(payload, "http_429"),
        "brti_timeout_errors_total": _counter(payload, "timeout_errors"),
        "brti_http_errors_total": _counter(payload, "http_errors"),
        "brti_connection_errors_total": _counter(payload, "connection_errors"),
        "brti_other_errors_total": _counter(payload, "other_errors"),
        "brti_consecutive_errors": _counter(payload, "consecutive_errors"),
        "brti_last_error_type": payload.get("last_error_type"),
        "brti_success_timestamp_utc": payload.get("success_timestamp_utc"),
        "brti_last_attempt_timestamp_utc": payload.get("last_attempt_timestamp_utc"),
    }


def adapt_main(payload: Mapping[str, Any]) -> dict[str, Any]:
    out = {"contract_id": _contract(payload), "seconds_left": _seconds_left(payload)}
    candidates = {
        "kalshi_age_sec": ("kalshi_age_sec",),
        "coinbase_age_sec": ("coinbase_age_sec",),
        "brti_age_sec": ("brti_age_sec",),
    }
    for target, names in candidates.items():
        for name in names:
            value = _finite(payload.get(name))
            if value is not None:
                out[target] = value
                break
    for key in ("brti_fresh", "kalshi_fresh", "coinbase_fresh", "parity_ok"):
        if isinstance(payload.get(key), bool):
            out[key] = payload[key]
    for provider in ("kalshi", "coinbase"):
        key = provider + "_success_timestamp_utc"
        if isinstance(payload.get(key), str) and payload[key].strip():
            out[key] = payload[key]
        out[provider + "_freshness_status"] = (
            "EXPLICIT_EVIDENCE" if any(k in out for k in
                (provider + "_age_sec", provider + "_fresh", key)) else "UNKNOWN")
    return out


def adapt_scalp_combined(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "contract_id": _contract(payload), "seconds_left": _seconds_left(payload),
        "scalp_source_fresh": payload.get("scalp_source_fresh") if isinstance(payload.get("scalp_source_fresh"), bool) else None,
        "scalp_contract_aligned": payload.get("scalp_contract_aligned") if isinstance(payload.get("scalp_contract_aligned"), bool) else None,
        "bridge_version": payload.get("version"),
        "scalp_cache_state_rows": payload.get("scalp_cache_state_rows"),
    }


def adapt_generic(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"contract_id": _contract(payload), "seconds_left": _seconds_left(payload)}


def adapt_source(source: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    name = source.lower()
    if "brti_shared" in name:
        return adapt_brti_shared(payload)
    if "production_main" in name:
        return adapt_main(payload)
    if "scalp_combined" in name:
        return adapt_scalp_combined(payload)
    return adapt_generic(payload)
