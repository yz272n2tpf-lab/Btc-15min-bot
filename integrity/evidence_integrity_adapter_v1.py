#!/usr/bin/env python3
"""BTC15 Evidence Integrity Adapter V1.

Pure, read-only normalizer that turns timestamped source observations into
contract-level records consumed by evidence_integrity_reconciler_v1.

Important:
- Does not fetch external APIs.
- Does not mutate source evidence.
- Does not infer missing facts as healthy.
- Missing required measurements remain UNKNOWN downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from integrity.measurement_validation_v1 import (
    MEASUREMENT_FIELDS, ROLLOVER_FIELDS, nonnegative_finite, nonnegative_integer,
)


@dataclass(frozen=True)
class AdapterPolicy:
    contract_length_sec: float = 900.0
    max_rollover_lag_sec: float = 15.0
    end_observation_seconds_left: float = 60.0
    max_source_gap_sec: float = 10.0
    max_clock_drift_sec: float = 2.0

    # Operational fields are aggregated conservatively:
    # any False => False; known True with no False => True; no known value => None.
    operational_fields: Sequence[str] = (
        "service_deployment_ok",
        "process_alive",
        "storage_ok",
        "collector_advancing",
        "scorer_advancing",
        "runtime_config_match",
    )

    def __post_init__(self):
        for name in ("contract_length_sec", "max_rollover_lag_sec",
                     "end_observation_seconds_left", "max_source_gap_sec",
                     "max_clock_drift_sec"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or nonnegative_finite(value) is None:
                raise ValueError(f"invalid adapter policy: {name}")
        if self.contract_length_sec <= 0 or self.end_observation_seconds_left >= self.contract_length_sec:
            raise ValueError("invalid contract coverage interval")


def _dt(v: Any) -> Optional[datetime]:
    if isinstance(v, datetime):
        d = v
    else:
        try:
            d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _f(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    return x if math.isfinite(x) else None


def _i(v: Any) -> Optional[int]:
    return nonnegative_integer(v)


def _tri_bool(values: Iterable[Any]) -> Optional[bool]:
    # Fields may be emitted only by the source that owns that measurement.
    # Missing observations never become True; known False dominates; one or
    # more known True values with no False mean the supplied interval fact
    # passed. Callers must not use instantaneous booleans as interval facts.
    known = [v for v in values if isinstance(v, bool)]
    if not known:
        return None
    if any(v is False for v in known):
        return False
    return True


def _max_known(rows: Sequence[Mapping[str, Any]], field: str) -> Optional[float]:
    vals = [nonnegative_finite(r[field]) for r in rows if field in r]
    # An explicitly invalid value poisons the aggregate, even amid fresh values.
    if not vals or any(x is None for x in vals):
        return None
    return max(vals)


def _counter_summary(rows: Sequence[Mapping[str, Any]], field: str) -> Dict[str, Any]:
    points: list[tuple[datetime, int]] = []
    invalid = False
    for row in rows:
        if field not in row:
            continue
        t = _dt(row.get("observed_at_utc"))
        x = _i(row.get(field))
        if t is not None and x is not None:
            points.append((t, x))
        else:
            invalid = True
    points.sort(key=lambda z: z[0])
    resets = [
        {"before_at_utc": ta.isoformat(), "after_at_utc": tb.isoformat(),
         "before": a, "after": b}
        for (ta, a), (tb, b) in zip(points, points[1:]) if b < a
    ]
    return {
        "sample_count": len(points), "invalid_measurement": invalid,
        "reset_detected": True if resets else (False if len(points) >= 2 and not invalid else None),
        "resets": resets,
        "delta": points[-1][1] - points[0][1] if len(points) >= 2 and not resets and not invalid else None,
    }


def _counter_delta(rows: Sequence[Mapping[str, Any]], field: str) -> Optional[int]:
    return _counter_summary(rows, field)["delta"]


def _max_time_gap(rows: Sequence[Mapping[str, Any]]) -> Optional[float]:
    times = sorted({t for r in rows if (t := _dt(r.get("observed_at_utc"))) is not None})
    if len(times) < 2:
        return None
    return max((b - a).total_seconds() for a, b in zip(times, times[1:]))


def _max_clock_drift(rows: Sequence[Mapping[str, Any]]) -> Optional[float]:
    points: list[tuple[datetime, float]] = []
    for row in rows:
        t = _dt(row.get("observed_at_utc"))
        left = _f(row.get("seconds_left"))
        if t is not None and left is not None:
            points.append((t, left))
    if len(points) < 2:
        return None
    points.sort(key=lambda z: z[0])
    drifts: list[float] = []
    for (ta, la), (tb, lb) in zip(points, points[1:]):
        wall = (tb - ta).total_seconds()
        contract_clock = la - lb
        # seconds_left should decrease at approximately wall-clock speed.
        drifts.append(abs(wall - contract_clock))
    return max(drifts) if drifts else None


def _path_rows(rows: Sequence[Mapping[str, Any]], policy: AdapterPolicy) -> list[Mapping[str, Any]]:
    # Path evidence requires a contract clock plus at least one market/feed
    # measurement. Operational-only heartbeats cannot fill observation gaps.
    keys = {"kalshi_age_sec", "brti_age_sec", "coinbase_age_sec", "parity_ok", "parity_fail_count"}
    return [
        r for r in rows
        if _dt(r.get("observed_at_utc")) is not None
        and (left := nonnegative_finite(r.get("seconds_left"))) is not None
        and left <= policy.contract_length_sec
        and any(k in r for k in keys)
    ]


def _cutoff_valid(rows: Sequence[Mapping[str, Any]]) -> Optional[bool]:
    vals = [r.get("cutoff_valid") for r in rows]
    if not vals:
        return None
    return _tri_bool(vals)


def _parity_fail_count(rows: Sequence[Mapping[str, Any]]) -> Optional[int]:
    explicit = [_i(r.get("parity_fail_count")) for r in rows]
    explicit_known = [x for x in explicit if x is not None and x >= 0]
    parity = [r.get("parity_ok") for r in rows if isinstance(r.get("parity_ok"), bool)]
    if not parity and not explicit_known:
        return None
    return max(max(explicit_known, default=0), sum(v is False for v in parity))


def _feed_coverage(rows: Sequence[Mapping[str, Any]], feed: str, policy: AdapterPolicy) -> Dict[str, Any]:
    field = f"{feed}_age_sec"
    measured = [r for r in _path_rows(rows, policy)
                if field in r and nonnegative_finite(r[field]) is not None]
    times = {_dt(r["observed_at_utc"]) for r in measured}
    left = [nonnegative_finite(r["seconds_left"]) for r in measured]
    start = policy.contract_length_sec - max(left) <= policy.max_rollover_lag_sec if left else None
    end = min(left) <= policy.end_observation_seconds_left if left else None
    gap = _max_time_gap(measured)
    drift = _max_clock_drift(measured)
    invalid = any(field in r and nonnegative_finite(r[field]) is None for r in rows)
    if invalid:
        complete = False
    elif not measured:
        complete = None
    else:
        complete = bool(len(times) >= 2 and start and end and gap is not None
                        and gap <= policy.max_source_gap_sec and drift is not None
                        and drift <= policy.max_clock_drift_sec)
    return {
        f"{feed}_sample_count": len(times),
        f"{feed}_has_start_observation": start,
        f"{feed}_has_end_observation": end,
        f"{feed}_max_observation_gap_sec": gap,
        f"{feed}_coverage_complete": complete,
    }


def aggregate_contract(
    contract_id: str,
    events: Sequence[Mapping[str, Any]],
    policy: Optional[AdapterPolicy] = None,
) -> Dict[str, Any]:
    policy = policy or AdapterPolicy()
    rows = [dict(r) for r in events if str(r.get("contract_id") or r.get("ticker") or "") == contract_id]

    out: Dict[str, Any] = {
        "contract_id": contract_id,
        "adapter_version": "BTC15_EVIDENCE_INTEGRITY_ADAPTER_V1",
        "source_event_count": len(rows),
        "source_mutation": False,
    }
    if not rows:
        return out

    rows.sort(key=lambda r: _dt(r.get("observed_at_utc")) or datetime.max.replace(tzinfo=timezone.utc))

    for field in policy.operational_fields:
        out[field] = _tri_bool([r.get(field) for r in rows])

    out["cutoff_valid"] = _cutoff_valid(rows)

    invalid = set()
    for row in rows:
        for name in MEASUREMENT_FIELDS:
            if name in row and nonnegative_finite(row[name]) is None:
                invalid.add(name)
        if (left := nonnegative_finite(row.get("seconds_left"))) is not None and left > policy.contract_length_sec:
            invalid.add("seconds_left")
        if row.get("rollover_lag_invalid") is True:
            invalid.add("recorded_rollover_lag")
        invalid.update(row.get("invalid_measurements") or [])

    path_rows = _path_rows(rows, policy)
    out["path_sample_count"] = len(path_rows)
    seconds = [_f(r.get("seconds_left")) for r in path_rows]
    known_seconds = [x for x in seconds if x is not None]
    if known_seconds:
        first_seen_left = max(known_seconds)
        out["first_seen_seconds_left"] = first_seen_left
        out["rollover_lag_sec"] = policy.contract_length_sec - first_seen_left
        out["has_start_observation"] = bool(out["rollover_lag_sec"] <= policy.max_rollover_lag_sec + 1e-12)
        out["has_end_observation"] = bool(min(known_seconds) <= policy.end_observation_seconds_left + 1e-12)
    else:
        out["first_seen_seconds_left"] = None
        out["rollover_lag_sec"] = None
        out["has_start_observation"] = None
        out["has_end_observation"] = None

    # Recorded lag is contract evidence, including records outside the sampled
    # path. A later synthetic observation cannot replace it with a smaller lag.
    lags = [out["rollover_lag_sec"]] if out["rollover_lag_sec"] is not None else []
    for name in ROLLOVER_FIELDS:
        vals = [nonnegative_finite(r[name]) for r in rows if name in r]
        if vals:
            out[f"recorded_{name}"] = max(vals) if all(v is not None for v in vals) else None
            lags.extend(v for v in vals if v is not None)
    if any(name in invalid for name in (*ROLLOVER_FIELDS, "recorded_rollover_lag", "seconds_left")):
        out["rollover_lag_sec"] = None
        out["has_start_observation"] = False
    else:
        out["rollover_lag_sec"] = max(lags) if lags else None
        if out["rollover_lag_sec"] is not None and out["rollover_lag_sec"] > policy.max_rollover_lag_sec:
            out["has_start_observation"] = False

    max_gap = _max_time_gap(path_rows)
    max_drift = _max_clock_drift(path_rows)
    recorded_gaps = [nonnegative_finite(r["max_source_gap_sec"]) for r in rows if "max_source_gap_sec" in r]
    if "max_source_gap_sec" in invalid:
        max_gap = None
    elif recorded_gaps:
        max_gap = max([g for g in [max_gap, *recorded_gaps] if g is not None])
    out["max_source_gap_sec"] = max_gap
    out["max_clock_drift_sec"] = max_drift
    if (
        out.get("has_start_observation") is True
        and out.get("has_end_observation") is True
        and max_gap is not None
        and max_drift is not None
    ):
        out["continuous_path_complete"] = bool(
            max_gap <= policy.max_source_gap_sec + 1e-12
            and max_drift <= policy.max_clock_drift_sec + 1e-12
        )
    elif out.get("has_start_observation") is False or out.get("has_end_observation") is False:
        out["continuous_path_complete"] = False
    else:
        out["continuous_path_complete"] = None

    for feed in ("kalshi", "brti", "coinbase"):
        out[f"{feed}_max_age_sec"] = _max_known(rows, f"{feed}_age_sec")
        out.update(_feed_coverage(rows, feed, policy))
    out["parity_fail_count"] = _parity_fail_count(rows)
    out["parity_ok"] = _tri_bool(r.get("parity_ok") for r in rows)
    if any("parity_fail_count" in r and _i(r["parity_fail_count"]) is None for r in rows):
        invalid.add("parity_fail_count")

    out["brti_feed_clean"] = _tri_bool(r.get(k) for r in rows for k in ("brti_feed_clean", "brti_clean"))
    out["direct_brti_ready"] = _tri_bool(r.get("direct_brti_ready") for r in rows)
    timeout_values = [r["coinbase_timeout"] for r in rows if isinstance(r.get("coinbase_timeout"), bool)]
    out["coinbase_timeout"] = any(timeout_values) if timeout_values else None

    counter_fields = ("brti_attempts_total", "brti_429_total", "brti_errors_total",
                      "brti_upstream_ok_total", "brti_seq")
    counters = {name: _counter_summary(rows, name) for name in counter_fields}
    out["brti_counter_metadata"] = counters
    reset_values = [c["reset_detected"] for c in counters.values() if c["reset_detected"] is not None]
    out["brti_counter_reset"] = any(reset_values) if reset_values else None
    for name, counter in counters.items():
        if counter["invalid_measurement"]:
            invalid.add(name)
    out["brti_attempts"] = counters["brti_attempts_total"]["delta"]
    out["brti_429_count"] = counters["brti_429_total"]["delta"]
    out["invalid_measurements"] = sorted(invalid)

    times = [_dt(r.get("observed_at_utc")) for r in rows]
    known_times = [t for t in times if t is not None]
    out["first_observed_at_utc"] = known_times[0].isoformat().replace("+00:00", "Z") if known_times else None
    out["last_observed_at_utc"] = known_times[-1].isoformat().replace("+00:00", "Z") if known_times else None

    return out


def aggregate_all(
    events: Iterable[Mapping[str, Any]],
    policy: Optional[AdapterPolicy] = None,
) -> List[Dict[str, Any]]:
    rows = [dict(r) for r in events]
    ids = sorted({
        str(r.get("contract_id") or r.get("ticker") or "").strip()
        for r in rows
        if str(r.get("contract_id") or r.get("ticker") or "").strip()
    })
    return [aggregate_contract(cid, rows, policy) for cid in ids]
