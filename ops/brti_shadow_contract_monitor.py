#!/usr/bin/env python3
"""Bounded read-only BRTI shadow monitor for one full 15-minute window.

Samples the isolated shadow owner's /state endpoint only. It never calls the
Kalshi upstream endpoint, never changes strategy state, and never places orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
import time
from urllib.request import urlopen

URL = os.environ["BRTI_SHADOW_STATE_URL"]
SAMPLE_S = float(os.environ.get("BRTI_SHADOW_SAMPLE_S", "0.25"))
TIMEOUT_S = float(os.environ.get("BRTI_SHADOW_TIMEOUT_S", "0.8"))
WINDOW_S = 900


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def fetch() -> dict:
    with urlopen(URL, timeout=TIMEOUT_S) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError("OVERSIZE_STATE")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("STATE_NOT_OBJECT")
    return value


now = time.time()
window_start = (math.floor(now / WINDOW_S) + 1) * WINDOW_S
window_end = window_start + WINDOW_S
print(
    "BRTI_SHADOW_MONITOR_PLAN | "
    + json.dumps(
        {
            "url": URL,
            "sample_s": SAMPLE_S,
            "timeout_s": TIMEOUT_S,
            "window_start_utc": iso(window_start),
            "window_end_utc": iso(window_end),
            "signal_only": True,
            "orders": False,
        },
        separators=(",", ":"),
    ),
    flush=True,
)

# Warmup: confirm the endpoint is reachable before the test window.
last_warmup = 0.0
while time.time() < window_start:
    started = time.monotonic()
    try:
        state = fetch()
        if time.time() - last_warmup >= 30:
            print(
                "BRTI_SHADOW_WARMUP | "
                + json.dumps(
                    {
                        "status": state.get("status"),
                        "clean": state.get("clean_for_qualification"),
                        "age_ms": state.get("age_ms"),
                        "sequence": state.get("sequence"),
                        "upstream_attempts": state.get("upstream_attempts"),
                        "upstream_ok": state.get("upstream_ok"),
                        "upstream_errors": state.get("upstream_errors"),
                        "http_429": state.get("http_429"),
                    },
                    separators=(",", ":"),
                ),
                flush=True,
            )
            last_warmup = time.time()
    except Exception as exc:
        if time.time() - last_warmup >= 30:
            print(
                "BRTI_SHADOW_WARMUP_ERROR | "
                + json.dumps({"type": type(exc).__name__}, separators=(",", ":")),
                flush=True,
            )
            last_warmup = time.time()
    elapsed = time.monotonic() - started
    time.sleep(max(0.05, min(1.0, window_start - time.time(), 1.0 - elapsed)))

ages = []
samples = 0
transport_errors = 0
schema_errors = 0
clean_false = 0
status_not_ok = 0
age_over_5s = 0
source_rollbacks = 0
sequence_rollbacks = 0
config_mismatch = 0
last_source = None
last_sequence = None
max_source_gap_ms = 0.0
unqualified_run_start = None
longest_unqualified_ms = 0.0
first_counters = None
last_counters = None
last_progress = 0.0

while time.time() < window_end:
    started_mono = time.monotonic()
    sample_wall = time.time()
    try:
        state = fetch()
        samples += 1
        required = (
            "status",
            "clean_for_qualification",
            "age_ms",
            "sequence",
            "source_ts_ms",
            "poll_interval_ms",
            "max_qualification_age_ms",
            "upstream_attempts",
            "upstream_ok",
            "upstream_errors",
            "http_429",
        )
        if any(k not in state for k in required):
            schema_errors += 1
            raise ValueError("MISSING_STATE_FIELDS")

        if abs(float(state["poll_interval_ms"]) - 1000.0) > 1e-6 or abs(float(state["max_qualification_age_ms"]) - 5000.0) > 1e-6:
            config_mismatch += 1

        age = float(state["age_ms"])
        ages.append(age)
        clean = state["clean_for_qualification"] is True
        status_ok = state["status"] == "PRIMARY_OK"
        if not clean:
            clean_false += 1
        if not status_ok:
            status_not_ok += 1
        if age > 5000.0:
            age_over_5s += 1

        qualified = clean and status_ok and 0.0 <= age <= 5000.0
        if not qualified and unqualified_run_start is None:
            unqualified_run_start = sample_wall
        if qualified and unqualified_run_start is not None:
            longest_unqualified_ms = max(
                longest_unqualified_ms, (sample_wall - unqualified_run_start) * 1000.0
            )
            unqualified_run_start = None

        source = int(state["source_ts_ms"])
        seq = int(state["sequence"])
        if last_source is not None:
            if source < last_source:
                source_rollbacks += 1
            elif source > last_source:
                max_source_gap_ms = max(max_source_gap_ms, source - last_source)
        if last_sequence is not None and seq < last_sequence:
            sequence_rollbacks += 1
        last_source = source
        last_sequence = seq

        counters = {
            "upstream_attempts": int(state["upstream_attempts"]),
            "upstream_ok": int(state["upstream_ok"]),
            "upstream_errors": int(state["upstream_errors"]),
            "http_429": int(state["http_429"]),
        }
        if first_counters is None:
            first_counters = counters
        last_counters = counters

        if sample_wall - last_progress >= 60:
            print(
                "BRTI_SHADOW_PROGRESS | "
                + json.dumps(
                    {
                        "at_utc": iso(sample_wall),
                        "samples": samples,
                        "clean_false": clean_false,
                        "status_not_ok": status_not_ok,
                        "age_over_5s": age_over_5s,
                        "transport_errors": transport_errors,
                        "schema_errors": schema_errors,
                        "max_age_ms": max(ages) if ages else None,
                        "max_source_gap_ms": max_source_gap_ms,
                        "upstream_errors": counters["upstream_errors"],
                        "http_429": counters["http_429"],
                    },
                    separators=(",", ":"),
                ),
                flush=True,
            )
            last_progress = sample_wall
    except Exception as exc:
        transport_errors += 1
        if unqualified_run_start is None:
            unqualified_run_start = sample_wall
        if sample_wall - last_progress >= 60:
            print(
                "BRTI_SHADOW_PROGRESS_ERROR | "
                + json.dumps(
                    {
                        "at_utc": iso(sample_wall),
                        "type": type(exc).__name__,
                        "samples": samples,
                        "transport_errors": transport_errors,
                    },
                    separators=(",", ":"),
                ),
                flush=True,
            )
            last_progress = sample_wall

    elapsed = time.monotonic() - started_mono
    time.sleep(max(0.0, SAMPLE_S - elapsed))

if unqualified_run_start is not None:
    longest_unqualified_ms = max(
        longest_unqualified_ms, (window_end - unqualified_run_start) * 1000.0
    )

ages_sorted = sorted(ages)
p99 = None
if ages_sorted:
    p99 = ages_sorted[min(len(ages_sorted) - 1, int(math.ceil(0.99 * len(ages_sorted))) - 1)]

delta_errors = None
delta_429 = None
delta_attempts = None
delta_ok = None
if first_counters and last_counters:
    delta_errors = last_counters["upstream_errors"] - first_counters["upstream_errors"]
    delta_429 = last_counters["http_429"] - first_counters["http_429"]
    delta_attempts = last_counters["upstream_attempts"] - first_counters["upstream_attempts"]
    delta_ok = last_counters["upstream_ok"] - first_counters["upstream_ok"]

passed = all(
    [
        samples >= 3000,
        transport_errors == 0,
        schema_errors == 0,
        clean_false == 0,
        status_not_ok == 0,
        age_over_5s == 0,
        source_rollbacks == 0,
        sequence_rollbacks == 0,
        config_mismatch == 0,
        delta_errors == 0,
        delta_429 == 0,
        max(ages) <= 5000.0 if ages else False,
    ]
)

result = {
    "schema": "BTC15_BRTI_SHADOW_CONTRACT_V1",
    "status": "PASS" if passed else "FAIL",
    "window_start_utc": iso(window_start),
    "window_end_utc": iso(window_end),
    "duration_s": WINDOW_S,
    "sample_interval_s": SAMPLE_S,
    "samples": samples,
    "transport_errors": transport_errors,
    "schema_errors": schema_errors,
    "clean_false": clean_false,
    "status_not_ok": status_not_ok,
    "age_over_5s": age_over_5s,
    "max_age_ms": max(ages) if ages else None,
    "p99_age_ms": p99,
    "max_source_gap_ms": max_source_gap_ms,
    "longest_unqualified_ms": longest_unqualified_ms,
    "source_rollbacks": source_rollbacks,
    "sequence_rollbacks": sequence_rollbacks,
    "config_mismatch": config_mismatch,
    "upstream_attempts_delta": delta_attempts,
    "upstream_ok_delta": delta_ok,
    "upstream_errors_delta": delta_errors,
    "http_429_delta": delta_429,
    "signal_only": True,
    "orders": False,
}
print("BRTI_SHADOW_RESULT | " + json.dumps(result, separators=(",", ":")), flush=True)

# Keep the bounded evidence service alive so the result remains inspectable.
while True:
    time.sleep(3600)
