#!/usr/bin/env python3
"""
BTC15 fail-closed resilient BRTI acquisition helper V1.

INFRASTRUCTURE ONLY | SIGNAL ONLY | NO ORDERS

This helper does not change the protected FINAL model. It only retries the same
Kalshi CF Benchmarks BRTI endpoint when a primary request is rate-limited or
transiently fails. It never substitutes Coinbase and never treats stale BRTI as
fresh.

The <=5 second freshness semantics remain explicit at the caller boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Callable, Mapping, Sequence

BRTI_PATH = "/trade-api/v2/cfbenchmarks/values"
BRTI_BASE = "https://external-api.kalshi.com"
BRTI_PARAMS = {"id": "BRTI", "maxResolution": "PER_SECOND"}
DEFAULT_MAX_AGE_SEC = 5.0
DEFAULT_BACKOFF_SEC = (0.0, 0.35, 0.75, 1.25)


@dataclass(frozen=True)
class BrtiObservation:
    value: float
    source_time_ms: int
    age_sec: float
    attempts: int
    recovered_after_retry: bool
    fresh: bool


class BrtiUnavailable(RuntimeError):
    pass


def parse_latest_brti(payload: Any, *, now_ts: float | None = None) -> tuple[float, int, float]:
    """Parse the newest usable BRTI item from Kalshi's /values response."""
    obj = payload
    if isinstance(obj, Mapping):
        data = obj.get("data", obj)
    else:
        data = None

    items = data.get("payload") if isinstance(data, Mapping) else None
    if not isinstance(items, list) or not items:
        raise BrtiUnavailable("BRTI payload missing")

    item = None
    for candidate in reversed(items):
        if not isinstance(candidate, Mapping):
            continue
        if candidate.get("value") is None or candidate.get("time") is None:
            continue
        item = candidate
        break

    if item is None:
        raise BrtiUnavailable("BRTI response has no usable item")

    try:
        value = float(item["value"])
        source_ms = int(item["time"])
    except (TypeError, ValueError, OverflowError) as exc:
        raise BrtiUnavailable("BRTI item has invalid value/time") from exc

    now = time.time() if now_ts is None else float(now_ts)
    age = max(0.0, now - source_ms / 1000.0)
    return value, source_ms, age


def fetch_brti_resilient(
    *,
    get: Callable[..., Any],
    headers: Callable[[str, str], Mapping[str, str]],
    max_age_sec: float = DEFAULT_MAX_AGE_SEC,
    backoff_sec: Sequence[float] = DEFAULT_BACKOFF_SEC,
    timeout_sec: float = 8.0,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
) -> BrtiObservation:
    """
    Retry the exact same BRTI endpoint and fail closed if no fresh item is found.

    `get` is injected so the helper can be unit-tested without network access.
    Any non-success response, parse problem, or stale observation proceeds to the
    next frozen retry slot. If all attempts fail, BrtiUnavailable is raised.
    """
    delays = tuple(float(x) for x in backoff_sec)
    if not delays:
        raise ValueError("at least one retry slot is required")
    if float(max_age_sec) <= 0:
        raise ValueError("max_age_sec must be positive")

    errors: list[str] = []

    for index, delay in enumerate(delays, start=1):
        if delay > 0:
            sleep(delay)
        try:
            response = get(
                BRTI_BASE + BRTI_PATH,
                headers=dict(headers("GET", BRTI_PATH)),
                params=dict(BRTI_PARAMS),
                timeout=float(timeout_sec),
            )
            status = int(getattr(response, "status_code", 0) or 0)
            if status != 200:
                errors.append(f"attempt {index}: HTTP {status}")
                continue

            value, source_ms, age = parse_latest_brti(
                response.json(), now_ts=float(now())
            )
            if age > float(max_age_sec):
                errors.append(f"attempt {index}: stale {age:.3f}s")
                continue

            return BrtiObservation(
                value=value,
                source_time_ms=source_ms,
                age_sec=age,
                attempts=index,
                recovered_after_retry=index > 1,
                fresh=True,
            )
        except Exception as exc:
            # Do not expose credentials or raw response bodies here.
            errors.append(f"attempt {index}: {type(exc).__name__}")

    raise BrtiUnavailable(
        "fresh BRTI unavailable after " + str(len(delays)) + " attempts; " + "; ".join(errors)
    )


__all__ = [
    "BRTI_PATH",
    "BRTI_BASE",
    "BRTI_PARAMS",
    "DEFAULT_MAX_AGE_SEC",
    "DEFAULT_BACKOFF_SEC",
    "BrtiObservation",
    "BrtiUnavailable",
    "parse_latest_brti",
    "fetch_brti_resilient",
]
