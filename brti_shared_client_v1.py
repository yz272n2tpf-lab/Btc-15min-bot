#!/usr/bin/env python3
"""Client for shared BRTI feed V1.

Consumers never call external BRTI through this module. A feed/network error or
stale shared sample produces no qualification value. SIGNAL ONLY. NO ORDERS.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
import math
import time
import requests


@dataclass
class SharedBrtiSample:
    value: Optional[float]
    status: str
    clean_for_qualification: bool
    feed_age_ms: Optional[float]
    effective_age_ms: Optional[float]
    sequence: Optional[int]
    client_latency_ms: float
    error_type: Optional[str] = None
    error_text: Optional[str] = None


def _num(v: Any) -> Optional[float]:
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


class SharedBrtiClient:
    def __init__(self, base_url: str, max_age_ms: float = 1500.0, timeout_s: float = 0.40) -> None:
        self.base_url = str(base_url).rstrip("/")
        self.max_age_ms = max(100.0, float(max_age_ms))
        self.timeout_s = max(0.05, float(timeout_s))
        self.http = requests.Session()

    @staticmethod
    def _err_type(exc: Exception) -> str:
        text = str(exc).lower()
        name = exc.__class__.__name__.lower()
        if "timeout" in name or "timeout" in text:
            return "feed_timeout"
        if "connection" in name or "connect" in text or "dns" in text:
            return "feed_connection"
        if "http" in name or "status code" in text:
            return "feed_http"
        return "feed_other"

    def fetch(self) -> SharedBrtiSample:
        started = time.monotonic()
        try:
            r = self.http.get(self.base_url + "/state", timeout=self.timeout_s)
            r.raise_for_status()
            obj: Dict[str, Any] = r.json()
        except Exception as exc:
            latency = (time.monotonic() - started) * 1000.0
            return SharedBrtiSample(
                value=None,
                status="FEED_ERROR",
                clean_for_qualification=False,
                feed_age_ms=None,
                effective_age_ms=None,
                sequence=None,
                client_latency_ms=latency,
                error_type=self._err_type(exc),
                error_text=str(exc)[:160],
            )

        latency = (time.monotonic() - started) * 1000.0
        value = _num(obj.get("value"))
        feed_age = _num(obj.get("age_ms"))
        effective_age = None if feed_age is None else max(0.0, feed_age + latency)
        server_clean = obj.get("clean_for_qualification") is True
        status = str(obj.get("status") or "FEED_INVALID")
        clean = (
            server_clean
            and status == "PRIMARY_OK"
            and value is not None
            and value > 0.0
            and effective_age is not None
            and effective_age <= self.max_age_ms
        )
        seq = obj.get("sequence")
        try:
            seq = int(seq)
        except Exception:
            seq = None

        return SharedBrtiSample(
            value=value if clean else None,
            status=status,
            clean_for_qualification=bool(clean),
            feed_age_ms=feed_age,
            effective_age_ms=effective_age,
            sequence=seq,
            client_latency_ms=latency,
            error_type=None if clean else str(obj.get("last_error_type") or "stale_or_unqualified"),
            error_text=None if clean else str(obj.get("last_error_text") or "")[:160],
        )


def qualification_value(sample: SharedBrtiSample) -> Optional[float]:
    return sample.value if sample.clean_for_qualification else None
