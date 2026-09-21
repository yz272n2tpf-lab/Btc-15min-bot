"""Read-only rollover timing diagnostics for BTC15 production.

This module is deliberately side-effect free except for structured stdout logs.
It must never alter market selection, quote handling, polling, or strategy state.
SIGNAL ONLY / NO ORDERS.
"""
from __future__ import annotations

import json
import math
import threading
from datetime import datetime, timezone

PREFIX = "BTC15_ROLLOVER_DIAG"
SAFE_HEADER_NAMES = (
    "age",
    "cache-control",
    "date",
    "expires",
    "etag",
    "via",
    "x-cache",
    "cf-cache-status",
)
_LOCK = threading.Lock()
_LAST = {}


def _dt(value):
    if isinstance(value, datetime):
        d = value
    else:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _iso(value):
    return _dt(value).isoformat().replace("+00:00", "Z")


def quarter_open(value):
    d = _dt(value)
    epoch = int(d.timestamp())
    return datetime.fromtimestamp(epoch - (epoch % 900), timezone.utc)


def rollover_boundary(value, pre_seconds=5.0, post_seconds=90.0):
    d = _dt(value)
    floor = quarter_open(d)
    nxt = datetime.fromtimestamp(int(floor.timestamp()) + 900, timezone.utc)
    after = (d - floor).total_seconds()
    before = (nxt - d).total_seconds()
    if 0.0 <= after <= float(post_seconds):
        return floor
    if 0.0 <= before <= float(pre_seconds):
        return nxt
    return None


def offset_ms(value, expected_open):
    return round((_dt(value) - _dt(expected_open)).total_seconds() * 1000.0, 3)


def safe_headers(headers):
    out = {}
    if headers is None:
        return out
    lower = {str(k).lower(): str(v) for k, v in dict(headers).items()}
    for name in SAFE_HEADER_NAMES:
        if name in lower:
            out[name] = lower[name]
    return out


def _safe_value(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, (list, tuple)):
        return [_safe_value(v) for v in value[:20]]
    if isinstance(value, dict):
        return {str(k)[:80]: _safe_value(v) for k, v in list(value.items())[:30]}
    return str(value)[:300]


def emit(component, event, *, at=None, expected_open=None, ticker=None,
         details=None, dedupe_key=None, force=False):
    """Emit one bounded structured diagnostic record.

    Diagnostics are fail-open: an instrumentation error returns None and never
    propagates into production behavior.
    """
    try:
        when = _dt(at or datetime.now(timezone.utc))
        boundary = _dt(expected_open) if expected_open is not None else rollover_boundary(when)
        payload = {
            "component": str(component),
            "event": str(event),
            "timestamp_utc": _iso(when),
            "ticker": None if ticker is None else str(ticker),
            "expected_open_utc": None if boundary is None else _iso(boundary),
            "ms_from_open": None if boundary is None else offset_ms(when, boundary),
            "details": _safe_value(details or {}),
            "signal_only": True,
            "orders": False,
        }
        if dedupe_key is not None and not force:
            key = str(dedupe_key)
            signature = json.dumps(payload["details"], sort_keys=True, separators=(",", ":"))
            with _LOCK:
                if _LAST.get(key) == signature:
                    return None
                _LAST[key] = signature
        print(PREFIX + " | " + json.dumps(payload, sort_keys=True, separators=(",", ":")), flush=True)
        return payload
    except Exception:
        return None


def reset_for_tests():
    with _LOCK:
        _LAST.clear()
