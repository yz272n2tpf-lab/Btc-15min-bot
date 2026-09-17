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
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _i(v: Any) -> Optional[int]:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    try:
        x = int(v)
    except (TypeError, ValueError):
        return None
    return x


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
    vals = [_f(r.get(field)) for r in rows]
    known = [x for x in vals if x is not None]
    return max(known) if known else None


def _counter_delta(rows: Sequence[Mapping[str, Any]], field: str) -> Optional[int]:
    points: list[tuple[datetime, int]] = []
    for row in rows:
        t = _dt(row.get("observed_at_utc"))
        x = _i(row.get(field))
        if t is not None and x is not None and x >= 0:
            points.append((t, x))
    if len(points) < 2:
        return None
    points.sort(key=lambda z: z[0])
    first = points[0][1]
    last = points[-1][1]
    if last < first:
        # Counter reset means the interval cannot be safely summarized.
        return None
    return last - first


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


def _path_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    # Path evidence requires a contract clock plus at least one market/feed
    # measurement. Operational-only heartbeats cannot fill observation gaps.
    keys = {"kalshi_age_sec", "brti_age_sec", "coinbase_age_sec", "parity_ok", "parity_fail_count"}
    return [
        r for r in rows
        if _dt(r.get("observed_at_utc")) is not None
        and _f(r.get("seconds_left")) is not None
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
    if explicit_known:
        # Prefer cumulative counters when available.
        return max(explicit_known)

    parity = [r.get("parity_ok") for r in rows if isinstance(r.get("parity_ok"), bool)]
    if not parity:
        return None
    return sum(v is False for v in parity)


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

    path_rows = _path_rows(rows)
    out["path_sample_count"] = len(path_rows)
    seconds = [_f(r.get("seconds_left")) for r in path_rows]
    known_seconds = [x for x in seconds if x is not None]
    if known_seconds:
        first_seen_left = max(known_seconds)
        out["first_seen_seconds_left"] = first_seen_left
        out["rollover_lag_sec"] = max(0.0, policy.contract_length_sec - first_seen_left)
        out["has_start_observation"] = bool(out["rollover_lag_sec"] <= policy.max_rollover_lag_sec + 1e-12)
        out["has_end_observation"] = bool(min(known_seconds) <= policy.end_observation_seconds_left + 1e-12)
    else:
        out["first_seen_seconds_left"] = None
        out["rollover_lag_sec"] = None
        out["has_start_observation"] = None
        out["has_end_observation"] = None

    max_gap = _max_time_gap(path_rows)
    max_drift = _max_clock_drift(path_rows)
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

    out["kalshi_max_age_sec"] = _max_known(path_rows, "kalshi_age_sec")
    out["brti_max_age_sec"] = _max_known(path_rows, "brti_age_sec")
    out["coinbase_max_age_sec"] = _max_known(path_rows, "coinbase_age_sec")
    out["parity_fail_count"] = _parity_fail_count(path_rows)

    attempts_delta = _counter_delta(rows, "brti_attempts_total")
    errors_delta = _counter_delta(rows, "brti_429_total")
    out["brti_attempts"] = attempts_delta
    out["brti_429_count"] = errors_delta

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
