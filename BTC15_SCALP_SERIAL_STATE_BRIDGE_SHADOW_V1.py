#!/usr/bin/env python3
"""
BTC15 serial SCALP state bridge shadow V1.

RESEARCH / SHADOW ONLY | SIGNAL ONLY | NO ORDERS

This is a pure read-only state composer. It does not replace the existing live
bridge. It tests the user-confirmed serial scalp workflow while preserving the
frozen qualification and +5c / 4c protected management exactly.

Serial rule under shadow test:
- scan frozen-qualified candidates in chronological order;
- while a scalp is ACTIVE/PROTECT, later overlapping candidates do not replace it;
- after protected EXIT, reset and allow the next later qualified candidate;
- if a collector RESULT arrives before +5c ever armed, close only the state
  lifecycle as ENDED_UNARMED (not an actionable exit), then allow the next later
  qualified candidate;
- no artificial number-of-scalps cap;
- no Kalshi entry-price filter.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
from btc15_protected_module_adapter_v1 import (
    SCALP_ARM_GAIN,
    SCALP_GIVEBACK,
    SCALP_MIN_BTC30,
    SCALP_MIN_SECONDS_LEFT,
    scalp_state_from_events,
)

VERSION = "BTC15_SCALP_SERIAL_STATE_BRIDGE_SHADOW_V1"


def _dt(row: Mapping[str, Any]) -> datetime:
    return research.dt(row.get("timestamp_utc"))


def _float(v: Any) -> float | None:
    return research.f(v)


def _result_times(rows: list[Mapping[str, Any]]) -> dict[str, datetime]:
    out: dict[str, datetime] = {}
    for r in rows:
        if research.typ(r) != "RESULT":
            continue
        cid = research.cid(r)
        if not cid:
            continue
        ts = _dt(r)
        if ts == datetime.min.replace(tzinfo=timezone.utc):
            continue
        prev = out.get(cid)
        if prev is None or ts < prev:
            out[cid] = ts
    return out


def _contract(rows: list[Mapping[str, Any]]) -> str:
    snapshots = [r for r in rows if research.typ(r) == "SNAPSHOT" and research.contract(r)]
    if snapshots:
        return research.contract(max(snapshots, key=_dt))
    candidates = [r for r in rows if research.typ(r) == "CANDIDATE" and research.contract(r)]
    return research.contract(max(candidates, key=_dt)) if candidates else ""


def _contract_seconds_left(rows: list[Mapping[str, Any]], contract: str) -> float | None:
    snaps = [r for r in rows if research.typ(r) == "SNAPSHOT" and research.contract(r) == contract]
    if not snaps:
        return None
    return _float(max(snaps, key=_dt).get("seconds_left"))


def _paths_for(rows: list[Mapping[str, Any]], cid: str) -> list[dict[str, Any]]:
    out = [dict(r) for r in rows if research.typ(r) == "PATH" and research.cid(r) == cid]
    out.sort(key=_dt)
    return out


def _qualified(candidate: Mapping[str, Any]) -> bool:
    return scalp_state_from_events(candidate, ()).state != "PASS"


def _candidate_payload(candidate: Mapping[str, Any], state, index: int, contract_left: float | None) -> dict[str, Any]:
    giveback = None
    if state.peak_exec_gain is not None and state.exec_gain is not None:
        giveback = state.peak_exec_gain - state.exec_gain
    return {
        "candidate_id": research.cid(candidate) or None,
        "opportunity_index": index,
        "state": state.state,
        "side": state.side,
        "entry_price": state.entry_ask,
        "current_bid": state.current_bid,
        "exec_gain": state.exec_gain,
        "peak_exec_gain": state.peak_exec_gain,
        "giveback_from_peak": giveback,
        "entry_seconds_left": state.seconds_left,
        "contract_seconds_left": contract_left,
        "entry_price_is_telemetry_only": True,
    }


def build_state(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(r) for r in rows]
    contract = _contract(rows)
    contract_left = _contract_seconds_left(rows, contract)
    results = _result_times(rows)

    candidates = sorted(
        [r for r in rows if research.typ(r) == "CANDIDATE" and research.contract(r) == contract and _qualified(r)],
        key=_dt,
    )

    earliest = datetime.min.replace(tzinfo=timezone.utc)
    terminal_history: list[dict[str, Any]] = []
    index = 1

    for candidate in candidates:
        ctime = _dt(candidate)
        if ctime <= earliest:
            continue

        cid = research.cid(candidate)
        paths = _paths_for(rows, cid)
        state = scalp_state_from_events(candidate, paths)
        pm = research.measure_path(candidate, paths)

        if state.state == "EXIT" and pm.exit_time_utc:
            terminal_time = research.dt(pm.exit_time_utc)
            terminal_history.append({
                "candidate_id": cid,
                "opportunity_index": index,
                "terminal_state": "EXIT",
                "terminal_time_utc": terminal_time.isoformat(),
                "actionable_exit": True,
                "side": state.side,
                "entry_price": state.entry_ask,
                "exit_gain": state.exec_gain,
                "peak_exec_gain": state.peak_exec_gain,
            })
            earliest = terminal_time
            index += 1
            continue

        result_time = results.get(cid)
        if state.state == "ACTIVE" and result_time is not None and not pm.armed:
            terminal_history.append({
                "candidate_id": cid,
                "opportunity_index": index,
                "terminal_state": "ENDED_UNARMED",
                "terminal_time_utc": result_time.isoformat(),
                "actionable_exit": False,
                "side": state.side,
                "entry_price": state.entry_ask,
                "peak_exec_gain": pm.peak_gain,
                "adverse_exec_gain": pm.adverse_gain,
            })
            earliest = result_time
            index += 1
            continue

        current = _candidate_payload(candidate, state, index, contract_left)
        current["management_message"] = {
            "ACTIVE": "SCALP ACTIVE",
            "PROTECT": "PROTECT PROFITS",
            "EXIT": "EXIT / PROTECT PROFITS NOW",
            "PASS": "NO QUALIFIED SCALP",
        }.get(state.state, state.state)
        return {
            "version": VERSION,
            "contract": contract or None,
            "current": current,
            "terminal_history": terminal_history,
            "serial_opportunities_completed": len(terminal_history),
            "scanning_for_next": False,
            "lifecycle_ended_unarmed_is_actionable_exit": False,
            "frozen_rule": {
                "seconds_left_min": SCALP_MIN_SECONDS_LEFT,
                "btc30_min": SCALP_MIN_BTC30,
                "arm_gain": SCALP_ARM_GAIN,
                "giveback": SCALP_GIVEBACK,
                "entry_price_filter": None,
            },
            "manual_execution_only": True,
            "orders": False,
            "order_action": None,
            "research_only": True,
        }

    return {
        "version": VERSION,
        "contract": contract or None,
        "current": {
            "candidate_id": None,
            "opportunity_index": index,
            "state": "PASS",
            "management_message": "WATCHING FOR NEXT QUALIFIED SCALP",
            "contract_seconds_left": contract_left,
            "entry_price_is_telemetry_only": True,
        },
        "terminal_history": terminal_history,
        "serial_opportunities_completed": len(terminal_history),
        "scanning_for_next": True,
        "lifecycle_ended_unarmed_is_actionable_exit": False,
        "frozen_rule": {
            "seconds_left_min": SCALP_MIN_SECONDS_LEFT,
            "btc30_min": SCALP_MIN_BTC30,
            "arm_gain": SCALP_ARM_GAIN,
            "giveback": SCALP_GIVEBACK,
            "entry_price_filter": None,
        },
        "manual_execution_only": True,
        "orders": False,
        "order_action": None,
        "research_only": True,
    }


if __name__ == "__main__":
    print(f"{VERSION} | pure build_state(rows) | RESEARCH ONLY | NO ORDERS")
