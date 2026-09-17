#!/usr/bin/env python3
"""Local-volume safety telemetry for the BTC15 Integrity Sentinel."""
from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any


def storage_status(path: str | Path, *, fail_free_ratio: float = 0.10,
                   warn_free_ratio: float = 0.20) -> dict[str, Any]:
    if not 0 <= fail_free_ratio < warn_free_ratio <= 1:
        raise ValueError("invalid storage thresholds")
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(target)
    free_ratio = usage.free / usage.total if usage.total else 0.0
    if free_ratio <= fail_free_ratio:
        state, ok = "FAIL", False
    elif free_ratio <= warn_free_ratio:
        state, ok = "WARN", True
    else:
        state, ok = "OK", True
    return {
        "storage_ok": ok, "state": state, "total_bytes": usage.total,
        "used_bytes": usage.used, "free_bytes": usage.free,
        "free_ratio": free_ratio, "warn_free_ratio": warn_free_ratio,
        "fail_free_ratio": fail_free_ratio,
    }
