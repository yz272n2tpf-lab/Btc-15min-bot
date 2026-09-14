#!/usr/bin/env python3
"""
BTC15 SCALP protection-path audit V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Audits whether the existing frozen management behavior is doing what the
blueprint says once a scalp is active:
- arm protection after +5c executable gain,
- track the running executable peak,
- mark EXIT on the first observed sample at/through 4c giveback,
- preserve the result as descriptive evidence only.

This module does not change entry qualification, price filters, exit rules,
EARLY, FINAL, or any live service behavior.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_PROTECTION_AUDIT_V1"


def _timeline(candidate: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> list[tuple[float, float, str]]:
    ctime = research.dt(candidate.get("timestamp_utc"))
    out: list[tuple[float, float, str]] = []
    for r in rows:
        e = research.elapsed(r, ctime)
        g = research.f(r.get("exec_gain"))
        if e is None or g is None:
            continue
        out.append((e, g, str(r.get("timestamp_utc") or "")))
    out.sort(key=lambda x: x[0])
    return out


def audit_candidate(candidate: Mapping[str, Any], path_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    tl = _timeline(candidate, path_rows)
    running_peak = None
    armed = False
    arm_elapsed = None
    exit_elapsed = None
    exit_gain = None
    peak_at_exit = None
    giveback_at_exit = None
    previous_giveback = None
    first_crossing_ok = None

    for e, gain, _ in tl:
        running_peak = gain if running_peak is None else max(running_peak, gain)
        if not armed and running_peak >= research.SCALP_ARM_GAIN - 1e-12:
            armed = True
            arm_elapsed = e
        giveback = None if running_peak is None else running_peak - gain
        if armed and giveback is not None:
            if giveback >= research.SCALP_GIVEBACK - 1e-12:
                exit_elapsed = e
                exit_gain = gain
                peak_at_exit = running_peak
                giveback_at_exit = giveback
                first_crossing_ok = previous_giveback is None or previous_giveback < research.SCALP_GIVEBACK - 1e-12
                break
            previous_giveback = giveback

    full_gains = [g for _, g, _ in tl]
    full_peak = max(full_gains) if full_gains else None
    full_adverse = min(full_gains) if full_gains else None
    positive_exit = exit_gain is not None and exit_gain > 0

    return {
        "candidate_id": research.cid(candidate),
        "contract": research.contract(candidate),
        "side": str(candidate.get("side") or "").strip().upper(),
        "entry_ask": research.f(candidate.get("entry_ask")),
        "armed_plus5": armed,
        "arm_elapsed_sec": arm_elapsed,
        "protected_exit_observed": exit_elapsed is not None,
        "exit_elapsed_sec": exit_elapsed,
        "exit_gain": exit_gain,
        "peak_at_exit": peak_at_exit,
        "giveback_at_exit": giveback_at_exit,
        "first_observed_4c_crossing": first_crossing_ok,
        "positive_exit": positive_exit,
        "full_path_peak_gain": full_peak,
        "full_path_adverse_gain": full_adverse,
        "orders": False,
    }


def audit(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    done = forward.completed_ids([dict(r) for r in rows])
    candidates = forward.forward_candidates([dict(r) for r in rows])
    by_contract: dict[str, list[dict[str, Any]]] = defaultdict(list)
    paths: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in candidates:
        by_contract[research.contract(c)].append(c)
    for r in rows:
        if research.typ(r) == "PATH" and research.cid(r):
            paths[research.cid(r)].append(dict(r))

    records: list[dict[str, Any]] = []
    for contract, raw in by_contract.items():
        qualified = [
            c for c in sorted(raw, key=lambda x: research.dt(x.get("timestamp_utc")))
            if research.candidate_qualified(c)
        ]
        earliest = datetime.min.replace(tzinfo=timezone.utc)
        used: set[str] = set()
        while True:
            cand = next(
                (c for c in qualified if research.cid(c) not in used and research.dt(c.get("timestamp_utc")) > earliest),
                None,
            )
            if cand is None:
                break
            cid = research.cid(cand)
            used.add(cid)
            if cid not in done:
                break
            rec = audit_candidate(cand, research.path_rows_for(cand, paths))
            records.append(rec)
            if rec["exit_elapsed_sec"] is None:
                break
            # Use the same protected EXIT time as the frozen measurement logic.
            pm = research.measure_path(cand, research.path_rows_for(cand, paths))
            if not pm.exit_time_utc:
                break
            earliest = research.dt(pm.exit_time_utc)

    protected = [r for r in records if r["protected_exit_observed"]]
    armed = [r for r in records if r["armed_plus5"]]
    first_cross = [r for r in protected if r["first_observed_4c_crossing"] is True]
    positive = [r for r in protected if r["positive_exit"]]

    def med(key: str):
        xs = [float(r[key]) for r in protected if r.get(key) is not None]
        return statistics.median(xs) if xs else None

    return {
        "version": VERSION,
        "research_only": True,
        "orders": False,
        "selected_serial_records": len(records),
        "armed_records": len(armed),
        "protected_exit_records": len(protected),
        "first_crossing_ok_rate": None if not protected else len(first_cross) / len(protected),
        "positive_exit_rate": None if not protected else len(positive) / len(protected),
        "median_exit_gain": med("exit_gain"),
        "median_peak_at_exit": med("peak_at_exit"),
        "median_giveback_at_exit": med("giveback_at_exit"),
        "records": records,
        "rule_changed": False,
        "freeze_allowed": False,
    }


if __name__ == "__main__":
    print(f"{VERSION} | import/use audit(rows) | RESEARCH ONLY | NO ORDERS")
