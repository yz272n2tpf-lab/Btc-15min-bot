#!/usr/bin/env python3
"""BTC15 prospective scalp opportunity-density / frequency ledger V1.

SHADOW ONLY | SIGNAL ONLY | DESCRIPTIVE ONLY | NO ORDERS | NO PROMOTION

Purpose
-------
Measure how often the unchanged serial scalp lifecycle produces usable
opportunities on a TRUE future-contract denominator. Quiet fully observed
contracts remain in the denominator with opportunity count zero.

This ledger does not filter, suppress, rescue, select, or promote signals.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

import scalp_economics_forward_v1 as econ_forward
import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_live_review_v1 as source

VERSION = "BTC15_SCALP_OPPORTUNITY_DENSITY_FORWARD_V1_FROZEN"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(60, int(os.environ.get("SCALP_DENSITY_FORWARD_POLL_SEC", "180")))
CUTOFF_TEXT = os.environ.get("SCALP_DENSITY_FORWARD_CUTOFF_UTC", "").strip()

MIN_FULL_CONTRACTS = 100
AFFORDABLE_MAX = 0.50
IDEAL_MIN = 0.25
IDEAL_MAX = 0.35
GOOD_MIN = 0.36
GOOD_MAX = 0.50

# [low, high) seconds-left bands. 900 is included in the first band by <=900.
TIMING_ZONES = (
    ("15_TO_12M", 720.0, 900.000001),
    ("12_TO_9M", 540.0, 720.0),
    ("9_TO_6M", 360.0, 540.0),
    ("6_TO_3M", 180.0, 360.0),
    ("3_TO_2M", 120.0, 180.0),
)
CUMULATIVE_THRESHOLDS = (
    ("BY_12M_LEFT", 720.0),
    ("BY_9M_LEFT", 540.0),
    ("BY_6M_LEFT", 360.0),
    ("BY_3M_LEFT", 180.0),
    ("BY_2M_LEFT", 120.0),
)

LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "status": "STARTING",
    "cutoff_utc": CUTOFF_TEXT or None,
    "descriptive_only": True,
    "automatic_promotion": False,
    "orders": False,
    "shadow_only": True,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def f(v: Any) -> float | None:
    x = q.f(v)
    return x if x is not None and math.isfinite(float(x)) else None


def mean(xs: list[float]) -> float | None:
    return None if not xs else statistics.fmean(xs)


def median(xs: list[float]) -> float | None:
    return None if not xs else statistics.median(xs)


def opportunity_zone(seconds_left: Any) -> str:
    x = f(seconds_left)
    if x is None:
        return "UNKNOWN"
    for name, low, high in TIMING_ZONES:
        if low <= x < high:
            return name
    return "OUTSIDE_15_TO_2M"


def contract_map(opps: list[dict[str, Any]], contracts: set[str]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {c: [] for c in contracts}
    for op in opps:
        c = str(op.get("contract") or "")
        if c in out:
            out[c].append(op)
    for c in out:
        out[c].sort(key=lambda r: (int(r.get("opportunity_index") or 0), q.dt(r.get("timestamp"))))
    return out


def _coverage(n: int, denominator: int) -> float | None:
    return None if not denominator else n / denominator


def _ask(op: Mapping[str, Any]) -> float | None:
    return f(op.get("entry_ask"))


def is_affordable(op: Mapping[str, Any]) -> bool:
    x = _ask(op)
    return x is not None and x <= AFFORDABLE_MAX


def is_ideal(op: Mapping[str, Any]) -> bool:
    x = _ask(op)
    return x is not None and IDEAL_MIN <= x <= IDEAL_MAX


def is_good(op: Mapping[str, Any]) -> bool:
    x = _ask(op)
    return x is not None and GOOD_MIN <= x <= GOOD_MAX


def first_matching(z: list[dict[str, Any]], predicate: Any) -> dict[str, Any] | None:
    matches = [r for r in z if predicate(r)]
    if not matches:
        return None
    # Largest seconds-left is earliest in the 15-minute contract.
    return max(matches, key=lambda r: f(r.get("seconds_left")) if f(r.get("seconds_left")) is not None else -1.0)


def timing_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    left = [f(r.get("seconds_left")) for r in rows]
    vals = [x / 60.0 for x in left if x is not None]
    return {
        "n": len(rows),
        "avg_minutes_left": mean(vals),
        "median_minutes_left": median(vals),
        "min_minutes_left": None if not vals else min(vals),
        "max_minutes_left": None if not vals else max(vals),
    }


def movement_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    return {
        "n": n,
        "plus5_rate": None if not n else sum(int(bool(r.get("plus5"))) for r in rows) / n,
        "plus10_rate": None if not n else sum(int(bool(r.get("plus10"))) for r in rows) / n,
        "plus20_rate": None if not n else sum(int(bool(r.get("plus20"))) for r in rows) / n,
        "movement_is_context_not_density_gate": True,
    }


def analyze_density(opps: list[dict[str, Any]], contracts: set[str]) -> dict[str, Any]:
    byc = contract_map(opps, contracts)
    denom = len(contracts)
    counts = {c: len(z) for c, z in byc.items()}
    covered = {c for c, n in counts.items() if n >= 1}
    affordable = {c for c, z in byc.items() if any(is_affordable(r) for r in z)}
    ideal = {c for c, z in byc.items() if any(is_ideal(r) for r in z)}
    good = {c for c, z in byc.items() if any(is_good(r) for r in z)}

    exact = Counter()
    for n in counts.values():
        exact["4_PLUS" if n >= 4 else str(n)] += 1

    cumulative_multi = {
        "AT_LEAST_1": sum(n >= 1 for n in counts.values()),
        "AT_LEAST_2": sum(n >= 2 for n in counts.values()),
        "AT_LEAST_3": sum(n >= 3 for n in counts.values()),
        "AT_LEAST_4": sum(n >= 4 for n in counts.values()),
    }

    asks = [x for x in (_ask(r) for r in opps) if x is not None]
    affordable_opps = [r for r in opps if is_affordable(r)]
    ideal_opps = [r for r in opps if is_ideal(r)]

    first_any = [x for c, z in byc.items() if (x := first_matching(z, lambda _: True)) is not None]
    first_aff = [x for c, z in byc.items() if (x := first_matching(z, is_affordable)) is not None]
    first_ideal = [x for c, z in byc.items() if (x := first_matching(z, is_ideal)) is not None]

    zones: dict[str, Any] = {}
    for name, _, _ in TIMING_ZONES:
        z = [r for r in opps if opportunity_zone(r.get("seconds_left")) == name]
        zc = {str(r.get("contract") or "") for r in z if str(r.get("contract") or "") in contracts}
        zaff = {str(r.get("contract") or "") for r in z if str(r.get("contract") or "") in contracts and is_affordable(r)}
        zones[name] = {
            "opportunities": len(z),
            "contracts": len(zc),
            "true_contract_coverage": _coverage(len(zc), denom),
            "affordable_contracts_le50": len(zaff),
            "affordable_true_contract_coverage_le50": _coverage(len(zaff), denom),
            **timing_summary(z),
            **movement_summary(z),
        }

    cumulative: dict[str, Any] = {}
    for name, threshold in CUMULATIVE_THRESHOLDS:
        zc = {
            c for c, z in byc.items()
            if any((f(r.get("seconds_left")) is not None and f(r.get("seconds_left")) >= threshold) for r in z)
        }
        zaff = {
            c for c, z in byc.items()
            if any((f(r.get("seconds_left")) is not None and f(r.get("seconds_left")) >= threshold and is_affordable(r)) for r in z)
        }
        cumulative[name] = {
            "contracts_with_any_opportunity_by_deadline": len(zc),
            "true_contract_coverage": _coverage(len(zc), denom),
            "contracts_with_affordable_opportunity_le50_by_deadline": len(zaff),
            "affordable_true_contract_coverage_le50": _coverage(len(zaff), denom),
        }

    by_index: dict[str, Any] = {}
    for idx in sorted({int(r.get("opportunity_index") or 0) for r in opps}):
        z = [r for r in opps if int(r.get("opportunity_index") or 0) == idx]
        zc = {str(r.get("contract") or "") for r in z if str(r.get("contract") or "") in contracts}
        zaff = {str(r.get("contract") or "") for r in z if str(r.get("contract") or "") in contracts and is_affordable(r)}
        by_index[str(idx)] = {
            "opportunities": len(z),
            "contracts": len(zc),
            "true_contract_coverage": _coverage(len(zc), denom),
            "affordable_contracts_le50": len(zaff),
            "affordable_true_contract_coverage_le50": _coverage(len(zaff), denom),
            "avg_entry_ask_c": None if not z else 100.0 * mean([x for x in (_ask(r) for r in z) if x is not None]) if any(_ask(r) is not None for r in z) else None,
            **timing_summary(z),
            **movement_summary(z),
        }

    return {
        "true_contract_denominator": denom,
        "total_serial_opportunities": len(opps),
        "covered_contracts": len(covered),
        "true_contract_coverage": _coverage(len(covered), denom),
        "zero_opportunity_contracts": exact.get("0", 0),
        "zero_opportunity_rate": _coverage(exact.get("0", 0), denom),
        "opportunity_count_distribution": {
            "0": exact.get("0", 0),
            "1": exact.get("1", 0),
            "2": exact.get("2", 0),
            "3": exact.get("3", 0),
            "4_PLUS": exact.get("4_PLUS", 0),
        },
        "opportunity_count_distribution_rate": {
            key: _coverage(exact.get(key, 0), denom) for key in ("0", "1", "2", "3", "4_PLUS")
        },
        "multi_opportunity_contract_counts": cumulative_multi,
        "multi_opportunity_true_contract_coverage": {
            key: _coverage(n, denom) for key, n in cumulative_multi.items()
        },
        "avg_opportunities_per_full_contract": None if not denom else len(opps) / denom,
        "avg_opportunities_per_covered_contract": None if not covered else len(opps) / len(covered),
        "max_opportunity_index": max((int(r.get("opportunity_index") or 0) for r in opps), default=0),
        "affordable_contracts_le50": len(affordable),
        "affordable_true_contract_coverage_le50": _coverage(len(affordable), denom),
        "ideal_contracts_25_35": len(ideal),
        "ideal_true_contract_coverage_25_35": _coverage(len(ideal), denom),
        "good_contracts_36_50": len(good),
        "good_true_contract_coverage_36_50": _coverage(len(good), denom),
        "affordable_opportunities_le50": len(affordable_opps),
        "ideal_opportunities_25_35": len(ideal_opps),
        "avg_entry_ask_c": None if not asks else 100.0 * mean(asks),
        "median_entry_ask_c": None if not asks else 100.0 * median(asks),
        "first_opportunity_timing": timing_summary(first_any),
        "first_affordable_opportunity_timing": timing_summary(first_aff),
        "first_ideal_opportunity_timing": timing_summary(first_ideal),
        "timing_zones": zones,
        "cumulative_timing": cumulative,
        "by_opportunity_index": by_index,
        "overall_movement_context": movement_summary(opps),
    }


def frozen_rules() -> dict[str, Any]:
    return {
        "denominator": "ALL_FULLY_OBSERVED_FUTURE_CONTRACTS_FIRST_SEEN_AT_OR_AFTER_CUTOFF",
        "quiet_contracts_count_as_zero_opportunity": True,
        "serial_lifecycle_unchanged": True,
        "entry_affordable_max_c": 50.0,
        "entry_ideal_band_c": [25.0, 35.0],
        "entry_good_band_c": [36.0, 50.0],
        "minimum_seconds_left_in_existing_baseline": q.MIN_SECONDS_LEFT,
        "timing_zones_seconds_left": {name: [low, high] for name, low, high in TIMING_ZONES},
        "density_does_not_select_or_suppress_signals": True,
        "automatic_promotion": False,
        "orders": False,
    }


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0,
                 cutoff_text: str | None = None) -> dict[str, Any]:
    text = CUTOFF_TEXT if cutoff_text is None else cutoff_text
    cutoff = econ_forward.parse_cutoff(text)
    if cutoff is None:
        return {
            "ok": False,
            "version": VERSION,
            "status": "FAIL_CLOSED_MISSING_OR_INVALID_CUTOFF",
            "cutoff_utc": text or None,
            "descriptive_only": True,
            "automatic_promotion": False,
            "orders": False,
        }

    contracts, adapted = econ_forward.future_universe(rows, cutoff)
    opps = [r for r in q.build_serial_opportunities(adapted) if str(r.get("contract") or "") in contracts]
    density = analyze_density(opps, contracts)
    sample_ready = len(contracts) >= MIN_FULL_CONTRACTS
    status = "READY_FOR_MANUAL_DENSITY_REVIEW" if sample_ready else "COLLECTING_FUTURE_OPPORTUNITY_DENSITY_V1"

    result = {
        "ok": True,
        "version": VERSION,
        "status": status,
        "updated_utc": utcnow(),
        "cutoff_utc": cutoff.isoformat(),
        "source_sha256": sha,
        "source_bytes": source_bytes,
        "source_rows": len(rows),
        "future_full_contracts": len(contracts),
        "density": density,
        "evidence_readiness": {
            "sample_ready": sample_ready,
            "observed_future_full_contracts": len(contracts),
            "required_future_full_contracts": MIN_FULL_CONTRACTS,
            "readiness_is_sample_size_only": True,
            "readiness_is_not_performance_pass_or_promotion": True,
        },
        "frozen_rules": frozen_rules(),
        "descriptive_only": True,
        "signal_filtering": False,
        "signal_suppression": False,
        "automatic_promotion": False,
        "manual_execution_only": True,
        "production_logic_changed": False,
        "shadow_only": True,
        "orders": False,
    }
    print("SCALP_DENSITY_FORWARD | " + json.dumps(compact(result), separators=(",", ":"), sort_keys=True, default=str), flush=True)
    return result


def compact(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": state.get("status"),
        "cutoff_utc": state.get("cutoff_utc"),
        "future_full_contracts": state.get("future_full_contracts"),
        "density": state.get("density"),
        "evidence_readiness": state.get("evidence_readiness"),
        "frozen_rules": frozen_rules(),
        "descriptive_only": True,
        "signal_filtering": False,
        "signal_suppression": False,
        "automatic_promotion": False,
        "orders": False,
    }


def refresh_once() -> dict[str, Any]:
    rows, sha, source_bytes = source.fetch_rows()
    with LOCK:
        old_sha = STATE.get("source_sha256")
    if old_sha == sha and STATE.get("status") != "STARTING":
        with LOCK:
            STATE["last_poll_utc"] = utcnow()
            return dict(STATE)
    result = analyze_rows(rows, sha=sha, source_bytes=source_bytes)
    result["last_poll_utc"] = utcnow()
    with LOCK:
        STATE.clear(); STATE.update(result)
        return dict(STATE)


def loop() -> None:
    while True:
        try:
            refresh_once()
        except Exception as exc:
            with LOCK:
                STATE.update({
                    "ok": False,
                    "version": VERSION,
                    "status": "FAIL_CLOSED_DENSITY_FORWARD_ERROR",
                    "last_poll_utc": utcnow(),
                    "error": f"{type(exc).__name__}:{exc}",
                    "descriptive_only": True,
                    "automatic_promotion": False,
                    "orders": False,
                    "shadow_only": True,
                })
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15DensityForwardV1/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_DENSITY_FORWARD_HTTP | request", flush=True)

    def send_json(self, code: int, obj: Mapping[str, Any]) -> None:
        raw = json.dumps(obj, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(raw)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        with LOCK:
            state = dict(STATE)
        if path == "/health":
            return self.send_json(200, {"ok": True, "analysis_ok": state.get("ok") is True,
                                        "status": state.get("status"), "cutoff_utc": state.get("cutoff_utc"),
                                        "orders": False, "version": VERSION})
        if path == "/summary":
            return self.send_json(200, compact(state))
        if path == "/state":
            return self.send_json(200, state)
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def assert_integrity() -> None:
    if q.MIN_SECONDS_LEFT != 120.0:
        raise RuntimeError("existing baseline minimum seconds-left drifted")
    if AFFORDABLE_MAX != 0.50 or IDEAL_MIN != 0.25 or IDEAL_MAX != 0.35:
        raise RuntimeError("entry-economics bands drifted")
    if tuple(name for name, _, _ in TIMING_ZONES) != ("15_TO_12M", "12_TO_9M", "9_TO_6M", "6_TO_3M", "3_TO_2M"):
        raise RuntimeError("timing zones drifted")


def main() -> int:
    assert_integrity()
    print(f"{VERSION} START | cutoff={CUTOFF_TEXT or 'MISSING'} | TRUE FUTURE DENOMINATOR | 0/1/2/3/4+ DENSITY | <=50c + 25-35c COVERAGE | DESCRIPTIVE ONLY | NO ORDERS", flush=True)
    threading.Thread(target=loop, name="density-forward-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


assert_integrity()

if __name__ == "__main__":
    raise SystemExit(main())
