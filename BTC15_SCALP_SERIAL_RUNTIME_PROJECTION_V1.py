#!/usr/bin/env python3
"""
BTC15 serial SCALP runtime projection V1.

RESEARCH / SHADOW ONLY | SIGNAL ONLY | NO ORDERS

Purpose
-------
Build one dashboard-friendly scalp state from the existing generalized event tape
without changing the frozen scalp qualification or profit-protection rules.

Frozen behavior preserved exactly:
- seconds_left >= 120;
- side-aligned btc30 >= 15;
- NO Kalshi entry-price eligibility filter;
- +5c running executable gain arms protection;
- first observed 4c giveback from running executable peak triggers protected EXIT.

Research-only lifecycle addition:
- if the collector emits RESULT for a qualified scalp that never armed +5c,
  classify it as ENDED_UNARMED (informational terminal only), then resume
  scanning for the next qualified candidate after that RESULT timestamp.

ENDED_UNARMED is NOT a sell/exit signal and does not create a stop-loss.
An armed candidate with no validated 4c giveback EXIT remains blocked as
ARMED_NO_VALIDATED_EXIT; V1 does not invent a terminal for it.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
from btc15_protected_module_adapter_v1 import scalp_state_from_events

VERSION = "BTC15_SCALP_SERIAL_RUNTIME_PROJECTION_V1"


def _latest_contract(rows: list[Mapping[str, Any]]) -> str:
    snapshots = [
        r for r in rows
        if research.typ(r) == "SNAPSHOT" and research.contract(r)
    ]
    if snapshots:
        return research.contract(max(snapshots, key=lambda r: research.dt(r.get("timestamp_utc"))))
    candidates = [
        r for r in rows
        if research.typ(r) == "CANDIDATE" and research.contract(r)
    ]
    if candidates:
        return research.contract(max(candidates, key=lambda r: research.dt(r.get("timestamp_utc"))))
    return ""


def _result_times(rows: list[Mapping[str, Any]]) -> dict[str, datetime]:
    out: dict[str, datetime] = {}
    for r in rows:
        if research.typ(r) != "RESULT" or not research.cid(r):
            continue
        ts = research.dt(r.get("timestamp_utc"))
        if ts == datetime.min.replace(tzinfo=timezone.utc):
            continue
        cid = research.cid(r)
        if cid not in out or ts < out[cid]:
            out[cid] = ts
    return out


def _paths(rows: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if research.typ(r) == "PATH" and research.cid(r):
            out[research.cid(r)].append(dict(r))
    return out


def _candidate_payload(candidate: Mapping[str, Any], index: int) -> dict[str, Any]:
    return {
        "candidate_id": research.cid(candidate) or None,
        "opportunity_index": index,
        "side": str(candidate.get("side") or "").strip().upper() or None,
        "entry_price": research.f(candidate.get("entry_ask")),
        "entry_seconds_left": research.f(candidate.get("seconds_left")),
        "btc30": research.f(candidate.get("btc30")),
        "entry_price_is_telemetry_only": True,
    }


def build_state(rows: list[Mapping[str, Any]], *, contract: str | None = None) -> dict[str, Any]:
    rows = [dict(r) for r in rows]
    contract = str(contract or _latest_contract(rows)).strip()
    results = _result_times(rows)
    paths = _paths(rows)

    candidates = [
        dict(r) for r in rows
        if research.typ(r) == "CANDIDATE"
        and research.contract(r) == contract
        and research.candidate_qualified(r)
    ]
    candidates.sort(key=lambda r: research.dt(r.get("timestamp_utc")))

    base = {
        "version": VERSION,
        "contract": contract or None,
        "research_only": True,
        "orders": False,
        "manual_execution_only": True,
        "protected_thresholds_changed": False,
        "stop_loss_rule_selected": False,
        "entry_price_filter_applied": False,
        "price_is_telemetry_only": True,
        "ended_unarmed_is_actionable_exit": False,
        "auto_promote_allowed": False,
    }

    if not candidates:
        return {
            **base,
            "state": "PASS",
            "management_message": "WATCHING FOR SCALP",
            "actionable": False,
            "opportunity_index": 0,
            "candidate_id": None,
            "previous_terminal": None,
            "reset_ready": True,
        }

    earliest = datetime.min.replace(tzinfo=timezone.utc)
    used: set[str] = set()
    index = 1
    previous_terminal: dict[str, Any] | None = None

    while True:
        candidate = next(
            (
                c for c in candidates
                if research.cid(c) not in used
                and research.dt(c.get("timestamp_utc")) > earliest
            ),
            None,
        )
        if candidate is None:
            if previous_terminal is not None:
                return {
                    **base,
                    "state": previous_terminal["state"],
                    "management_message": previous_terminal["management_message"],
                    "actionable": False,
                    "opportunity_index": previous_terminal["opportunity_index"],
                    "candidate_id": previous_terminal["candidate_id"],
                    "previous_terminal": previous_terminal,
                    "reset_ready": previous_terminal["state"] in {"PROTECTED_EXIT", "ENDED_UNARMED"},
                }
            return {
                **base,
                "state": "PASS",
                "management_message": "WATCHING FOR SCALP",
                "actionable": False,
                "opportunity_index": 0,
                "candidate_id": None,
                "previous_terminal": None,
                "reset_ready": True,
            }

        cid = research.cid(candidate)
        used.add(cid)
        path_rows = research.path_rows_for(candidate, paths)
        pm = research.measure_path(candidate, path_rows)
        info = _candidate_payload(candidate, index)

        # Existing protected EXIT remains the first and strongest terminal.
        if pm.exit_time_utc:
            terminal_time = research.dt(pm.exit_time_utc)
            previous_terminal = {
                **info,
                "state": "PROTECTED_EXIT",
                "management_message": "EXIT / PROTECT PROFITS NOW",
                "protected_exit_gain": pm.exit_gain,
                "protected_exit_time_utc": pm.exit_time_utc,
                "peak_exec_gain": pm.peak_gain,
                "actionable_exit": True,
            }
            earliest = terminal_time
            index += 1
            continue

        result_time = results.get(cid)
        if result_time is not None:
            if not pm.armed:
                previous_terminal = {
                    **info,
                    "state": "ENDED_UNARMED",
                    "management_message": "SCALP ENDED · PROFIT PROTECTION NEVER ARMED",
                    "result_time_utc": result_time.isoformat(),
                    "peak_exec_gain": pm.peak_gain,
                    "adverse_exec_gain": pm.adverse_gain,
                    "actionable_exit": False,
                }
                earliest = result_time
                index += 1
                continue

            # Collector is done, but frozen management never produced its 4c
            # giveback terminal. Do not fabricate an exit or advance the ladder.
            return {
                **base,
                **info,
                "state": "ARMED_NO_VALIDATED_EXIT",
                "management_message": "PROTECTION ARMED · NO VALIDATED EXIT RECORDED",
                "actionable": False,
                "armed": True,
                "peak_exec_gain": pm.peak_gain,
                "previous_terminal": previous_terminal,
                "reset_ready": False,
                "requires_rule_review": True,
            }

        # Current/incomplete candidate: preserve exact frozen management state.
        s = scalp_state_from_events(candidate, path_rows)
        message = {
            "ACTIVE": "SCALP ACTIVE · BUILDING",
            "PROTECT": "PROTECT PROFITS",
            "EXIT": "EXIT / PROTECT PROFITS NOW",
            "PASS": "WATCHING FOR SCALP",
        }.get(s.state, s.state)
        return {
            **base,
            **info,
            "state": s.state,
            "management_message": message,
            "actionable": s.state in {"ACTIVE", "PROTECT", "EXIT"},
            "armed": bool(s.peak_exec_gain is not None and s.peak_exec_gain >= research.SCALP_ARM_GAIN),
            "current_bid": s.current_bid,
            "exec_gain": s.exec_gain,
            "peak_exec_gain": s.peak_exec_gain,
            "previous_terminal": previous_terminal,
            "reset_ready": False,
        }


if __name__ == "__main__":
    print(f"{VERSION} | import/use build_state(rows) | RESEARCH ONLY | NO ORDERS")
