#!/usr/bin/env python3
"""BTC15 reversal/recross + re-entry serial scalp ladder V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

This analyzer keeps the frozen generalized scalp candidate gate and legacy
+5c-arm / 4c-giveback protection lifecycle unchanged. It studies only serial
opportunities that occur AFTER an actually observed protected exit.

Causal lane identity:
- REENTRY_CONTINUATION: later qualified candidate is the same side as prior scalp.
- REVERSAL_RECROSS: later qualified candidate flips side vs prior scalp.

Integrity:
- index-1 scalps are never classified as serial lanes;
- a serial opportunity cannot exist without a prior observed protection exit;
- candidate must occur strictly after the prior exit;
- RESULT/PATH fields score outcomes but never determine lane identity;
- chronological DEVELOPMENT / VALIDATION / HOLDOUT by contract;
- no automatic selection/promotion and no orders.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

import scalp_opportunity_quality_frontier_v1 as q

VERSION = "BTC15_SCALP_REVERSAL_REENTRY_LADDER_V1"
LANES = ("REENTRY_CONTINUATION", "REVERSAL_RECROSS")


def finite(v: Any) -> float | None:
    x = q.f(v)
    return x if x is not None and math.isfinite(x) else None


def prepare(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    done: set[str] = set()
    paths: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    first_seen: dict[str, datetime] = {}

    for r0 in rows:
        r = dict(r0)
        typ = q.typ(r)
        candidate_id = q.cid(r)
        contract = q.contract(r)
        if typ == "RESULT" and candidate_id:
            done.add(candidate_id)
        elif typ == "PATH" and candidate_id:
            paths[candidate_id].append(r)
        elif typ == "CANDIDATE" and candidate_id and contract and q.baseline_qualified(r):
            by_contract[contract].append(r)
            t = q.dt(r.get("timestamp_utc"))
            first_seen[contract] = min(first_seen.get(contract, t), t)

    for contract in by_contract:
        by_contract[contract].sort(key=lambda r: q.dt(r.get("timestamp_utc")))
    for candidate_id in paths:
        # q.measure_path sorts again by elapsed, but stable timestamp ordering
        # makes raw diagnostics deterministic as well.
        paths[candidate_id].sort(key=lambda r: q.dt(r.get("timestamp_utc")))

    return {
        "done": done,
        "paths": paths,
        "by_contract": by_contract,
        "first_seen": first_seen,
    }


def split_contracts(first_seen: Mapping[str, datetime]) -> dict[str, str]:
    ordered = sorted(first_seen, key=lambda c: first_seen[c])
    n = len(ordered)
    if n < 10:
        return {c: "DEVELOPMENT" for c in ordered}
    i60 = max(1, int(n * 0.60))
    i80 = max(i60 + 1, int(n * 0.80))
    return {
        c: ("DEVELOPMENT" if i < i60 else "VALIDATION" if i < i80 else "HOLDOUT")
        for i, c in enumerate(ordered)
    }


def _lane(prior_side: str | None, side: str, opportunity_index: int) -> str:
    if opportunity_index <= 1 or not prior_side:
        return "FIRST"
    return "REENTRY_CONTINUATION" if side == prior_side else "REVERSAL_RECROSS"


def build_serial(prepared: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    done: set[str] = prepared["done"]
    paths: Mapping[str, list[dict[str, Any]]] = prepared["paths"]
    by_contract: Mapping[str, list[dict[str, Any]]] = prepared["by_contract"]

    records: list[dict[str, Any]] = []
    serial_eligible_contracts: set[str] = set()
    serial_candidate_count = 0
    unresolved_serial_candidates = 0
    blocked_without_exit = 0

    for contract, candidates in by_contract.items():
        earliest = datetime.min.replace(tzinfo=timezone.utc)
        prior_side: str | None = None
        used: set[str] = set()
        idx = 1

        while True:
            cand = next((
                r for r in candidates
                if q.cid(r) not in used and q.dt(r.get("timestamp_utc")) > earliest
            ), None)
            if cand is None:
                break

            candidate_id = q.cid(cand)
            used.add(candidate_id)
            side = str(cand.get("side") or "").strip().upper()
            lane = _lane(prior_side, side, idx)

            if idx >= 2:
                serial_eligible_contracts.add(contract)
                serial_candidate_count += 1

            scoreable = candidate_id in done and bool(paths.get(candidate_id))
            if not scoreable:
                if idx >= 2:
                    unresolved_serial_candidates += 1
                # Without a completed path/result we cannot prove the next
                # protection exit, so the serial chain fails closed here.
                break

            pm = q.measure_path(cand, paths.get(candidate_id, []))
            ask = finite(cand.get("entry_ask"))
            left = finite(cand.get("seconds_left"))
            rec = {
                "contract": contract,
                "candidate_id": candidate_id,
                "timestamp": q.dt(cand.get("timestamp_utc")),
                "opportunity_index": idx,
                "side": side,
                "prior_side": prior_side,
                "lane": lane,
                "entry_ask": ask,
                "seconds_left": left,
                "minutes_left": None if left is None else left / 60.0,
                "plus5": int(pm.peak_gain is not None and pm.peak_gain >= 0.05),
                "plus10": int(pm.peak_gain is not None and pm.peak_gain >= 0.10),
                "plus20": int(pm.peak_gain is not None and pm.peak_gain >= 0.20),
                "mfe": pm.peak_gain,
                "mae": pm.adverse_gain,
                "protected_exit": pm.exit_time_utc is not None,
                "protected_exit_gain": pm.exit_gain,
                "protected_exit_timestamp": None if pm.exit_time_utc is None else q.dt(pm.exit_time_utc),
                "t10_sec": pm.t10_sec,
                "scoreable": True,
                "orders": False,
            }
            records.append(rec)

            if pm.exit_time_utc is None:
                # This scalp never generated a real protection exit, so any
                # later candidate cannot be causally unlocked in this ladder.
                if any(q.dt(r.get("timestamp_utc")) > q.dt(cand.get("timestamp_utc")) for r in candidates if q.cid(r) not in used):
                    blocked_without_exit += 1
                break

            prior_side = side
            earliest = q.dt(pm.exit_time_utc)
            idx += 1

    meta = {
        "serial_eligible_contracts": sorted(serial_eligible_contracts),
        "serial_candidate_count": serial_candidate_count,
        "unresolved_serial_candidates": unresolved_serial_candidates,
        "contracts_blocked_without_prior_protected_exit": blocked_without_exit,
    }
    return records, meta


def _mean(values: Iterable[Any]) -> float | None:
    xs = [finite(v) for v in values]
    xs = [x for x in xs if x is not None]
    return None if not xs else statistics.fmean(xs)


def _median(values: Iterable[Any]) -> float | None:
    xs = [finite(v) for v in values]
    xs = [x for x in xs if x is not None]
    return None if not xs else statistics.median(xs)


def summarize(records: list[Mapping[str, Any]], serial_eligible_contracts: set[str]) -> dict[str, Any]:
    n = len(records)
    contracts = {str(r.get("contract") or "") for r in records}
    denom = len(serial_eligible_contracts)
    if not n:
        return {
            "signals": 0,
            "contracts": 0,
            "serial_eligible_contract_denominator": denom,
            "serial_contract_retention": None if not denom else 0.0,
            "orders": False,
        }

    asks = [finite(r.get("entry_ask")) for r in records]
    asks = [x for x in asks if x is not None]
    exit_gains = [finite(r.get("protected_exit_gain")) for r in records]
    exit_gains = [x for x in exit_gains if x is not None]
    return {
        "signals": n,
        "contracts": len(contracts),
        "serial_eligible_contract_denominator": denom,
        "serial_contract_retention": None if not denom else len(contracts & serial_eligible_contracts) / denom,
        "plus5_rate": sum(int(bool(r.get("plus5"))) for r in records) / n,
        "plus10_rate": sum(int(bool(r.get("plus10"))) for r in records) / n,
        "plus20_rate": sum(int(bool(r.get("plus20"))) for r in records) / n,
        "entry_le50_rate": None if not asks else sum(x <= 0.50 for x in asks) / len(asks),
        "entry_ideal_25_35_rate": None if not asks else sum(0.25 <= x <= 0.35 for x in asks) / len(asks),
        "avg_entry_ask_c": None if not asks else 100 * statistics.fmean(asks),
        "median_entry_ask_c": None if not asks else 100 * statistics.median(asks),
        "avg_minutes_left": _mean(r.get("minutes_left") for r in records),
        "median_minutes_left": _median(r.get("minutes_left") for r in records),
        "avg_mfe_c": None if _mean(r.get("mfe") for r in records) is None else 100 * float(_mean(r.get("mfe") for r in records)),
        "avg_mae_c": None if _mean(r.get("mae") for r in records) is None else 100 * float(_mean(r.get("mae") for r in records)),
        "protected_exit_rate": sum(bool(r.get("protected_exit")) for r in records) / n,
        "avg_protected_exit_gain_c": None if not exit_gains else 100 * statistics.fmean(exit_gains),
        "positive_protected_exit_rate": None if not exit_gains else sum(x > 0 for x in exit_gains) / len(exit_gains),
        "avg_t10_sec_when_hit": _mean(r.get("t10_sec") for r in records if r.get("t10_sec") is not None),
        "max_opportunity_index": max(int(r.get("opportunity_index") or 0) for r in records),
        "orders": False,
    }


def index_breakdown(records: list[Mapping[str, Any]], serial_eligible_contracts: set[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    indices = sorted({int(r.get("opportunity_index") or 0) for r in records if int(r.get("opportunity_index") or 0) >= 2})
    for idx in indices:
        out[str(idx)] = summarize([r for r in records if int(r.get("opportunity_index") or 0) == idx], serial_eligible_contracts)
    return out


def lane_report(records: list[Mapping[str, Any]], serial_eligible_contracts: set[str]) -> dict[str, Any]:
    serial = [r for r in records if int(r.get("opportunity_index") or 0) >= 2]
    out = {
        lane: summarize([r for r in serial if r.get("lane") == lane], serial_eligible_contracts)
        for lane in LANES
    }
    out["SERIAL_UNION"] = summarize(serial, serial_eligible_contracts)
    out["BY_INDEX"] = index_breakdown(serial, serial_eligible_contracts)

    reentry_contracts = {str(r.get("contract") or "") for r in serial if r.get("lane") == "REENTRY_CONTINUATION"}
    reversal_contracts = {str(r.get("contract") or "") for r in serial if r.get("lane") == "REVERSAL_RECROSS"}
    out["COMPLEMENTARITY"] = {
        "reentry_contracts": len(reentry_contracts),
        "reversal_contracts": len(reversal_contracts),
        "both_lane_contracts": len(reentry_contracts & reversal_contracts),
        "union_lane_contracts": len(reentry_contracts | reversal_contracts),
        "serial_eligible_contracts": len(serial_eligible_contracts),
        "union_serial_contract_retention": None if not serial_eligible_contracts else len((reentry_contracts | reversal_contracts) & serial_eligible_contracts) / len(serial_eligible_contracts),
    }
    return out


def analyze(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    prepared = prepare(rows)
    split = split_contracts(prepared["first_seen"])
    records, meta = build_serial(prepared)
    all_serial_eligible = set(meta["serial_eligible_contracts"])

    reports: dict[str, Any] = {}
    for part in ("DEVELOPMENT", "VALIDATION", "HOLDOUT"):
        contracts = {c for c, s in split.items() if s == part}
        part_records = [r for r in records if r.get("contract") in contracts]
        part_serial_eligible = all_serial_eligible & contracts
        reports[part.lower()] = lane_report(part_records, part_serial_eligible)
        reports[part.lower()]["serial_eligible_contracts"] = len(part_serial_eligible)

    return {
        "version": VERSION,
        "status": "REVERSAL_REENTRY_LADDER_READY",
        "baseline_candidate_gate_unchanged": True,
        "legacy_protection_lifecycle_unchanged": True,
        "coverage_scope": "SERIAL_ELIGIBLE_CONTRACTS_ONLY",
        "development": reports["development"],
        "validation": reports["validation"],
        "holdout": reports["holdout"],
        "serial_meta": {
            "serial_candidate_count": meta["serial_candidate_count"],
            "unresolved_serial_candidates": meta["unresolved_serial_candidates"],
            "contracts_blocked_without_prior_protected_exit": meta["contracts_blocked_without_prior_protected_exit"],
        },
        "holdout_report_only": True,
        "automatic_selection": False,
        "automatic_promotion": False,
        "orders": False,
    }


def assert_integrity() -> None:
    if q.ARM_GAIN != 0.05 or q.GIVEBACK != 0.04:
        raise RuntimeError("legacy protection lifecycle drifted")
    if q.MIN_BTC30 != 15.0 or q.MIN_SECONDS_LEFT != 120.0:
        raise RuntimeError("baseline candidate gate drifted")


assert_integrity()
