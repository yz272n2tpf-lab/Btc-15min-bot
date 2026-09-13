#!/usr/bin/env python3
"""Strict consumer adapter for the isolated shared BRTI feed.

This module is intentionally boring: it exposes one qualification value from a
shared feed and never falls back to direct external BRTI. A feed/network/stale
failure returns None. Infrastructure only. SIGNAL ONLY. NO ORDERS.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict
import os

from brti_shared_client_v1 import SharedBrtiClient, qualification_value


@dataclass
class CutoverStats:
    reads: int = 0
    clean: int = 0
    rejected: int = 0
    feed_errors: int = 0
    stale_or_unqualified: int = 0


class SharedBrtiQualificationAdapter:
    def __init__(self, base_url: str, max_age_ms: float = 1500.0, timeout_s: float = 0.40) -> None:
        self.client = SharedBrtiClient(base_url, max_age_ms=max_age_ms, timeout_s=timeout_s)
        self.stats = CutoverStats()
        self.last_status: Optional[str] = None
        self.last_age_ms: Optional[float] = None
        self.last_sequence: Optional[int] = None

    @classmethod
    def from_env(cls) -> "SharedBrtiQualificationAdapter":
        url = os.environ.get("BRTI_SHARED_URL", "").strip()
        if not url:
            raise RuntimeError("BRTI_SHARED_URL missing; refusing direct fallback")
        max_age_ms = float(os.environ.get("BRTI_SHARED_CLIENT_MAX_AGE_MS", "1500"))
        timeout_s = float(os.environ.get("BRTI_SHARED_CLIENT_TIMEOUT_S", "0.40"))
        return cls(url, max_age_ms=max_age_ms, timeout_s=timeout_s)

    def fetch_value(self) -> Optional[float]:
        self.stats.reads += 1
        sample = self.client.fetch()
        self.last_status = sample.status
        self.last_age_ms = sample.effective_age_ms
        self.last_sequence = sample.sequence
        value = qualification_value(sample)
        if value is not None:
            self.stats.clean += 1
            return value
        self.stats.rejected += 1
        if sample.status == "FEED_ERROR":
            self.stats.feed_errors += 1
        else:
            self.stats.stale_or_unqualified += 1
        return None

    def snapshot(self) -> Dict[str, object]:
        d = self.stats.__dict__.copy()
        d.update({
            "last_status": self.last_status,
            "last_age_ms": self.last_age_ms,
            "last_sequence": self.last_sequence,
            "direct_fallback": False,
            "orders": False,
        })
        return d


def build_brti_callable_from_env():
    adapter = SharedBrtiQualificationAdapter.from_env()
    return adapter.fetch_value, adapter
