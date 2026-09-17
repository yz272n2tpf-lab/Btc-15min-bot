"""Shared fail-closed validation for offline integrity measurements."""

import math
from typing import Any


def nonnegative_finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def nonnegative_integer(value: Any) -> int | None:
    # Do not truncate a fractional counter, accept bools, or round huge floats.
    if isinstance(value, int) and not isinstance(value, bool):
        return value if value >= 0 else None
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        try:
            return int(value)
        except ValueError:
            return None
    return None


MEASUREMENT_FIELDS = (
    "seconds_left", "kalshi_age_sec", "brti_age_sec", "coinbase_age_sec",
    "kalshi_max_age_sec", "brti_max_age_sec", "coinbase_max_age_sec",
    "max_source_gap_sec", "max_clock_drift_sec", "rollover_lag_sec",
    "rollover_quote_lag_sec", "exact_ticker_rollover_quote_lag_sec",
    "combined_first_seen_lag_sec",
)

ROLLOVER_FIELDS = (
    "rollover_lag_sec", "rollover_quote_lag_sec",
    "exact_ticker_rollover_quote_lag_sec", "combined_first_seen_lag_sec",
)
