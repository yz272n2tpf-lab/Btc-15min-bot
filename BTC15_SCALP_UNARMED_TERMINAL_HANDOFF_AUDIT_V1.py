#!/usr/bin/env python3
"""
BTC15 SCALP unarmed-terminal handoff audit V1.

RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Purpose
-------
Separate a state-lifecycle problem from a stop-loss problem.

The frozen scalp management remains unchanged:
- frozen qualification: seconds_left >= 120 and side-aligned btc30 >= 15;
- no entry-price filter;
- +5c arms protected management;
- 4c giveback from running executable peak triggers protected EXIT.

Known gap under test:
A frozen-qualified scalp can finish its collector observation with a RESULT row
without ever reaching +5c. The protected adapter has no terminal state for that
case, so the dashboard can remain ACTIVE even though the collector says the
candidate is complete. That stale ACTIVE state can also block a later qualified
candidate in the same 15-minute contract.

V1 introduces NO trading exit and NO stop-loss threshold. It only audits the
following read-only research projection:

  RESULT received + never armed + no protected EXIT
      -> ENDED_UNARMED (informational lifecycle terminal only)
      -> reset scanning after the RESULT timestamp
      -> measure the next frozen-qualified candidate, if any

ENDED_UNARMED is explicitly NOT a sell/exit signal. It means only that the
collector finished observing that scalp and profit protection never armed.
Nothing in this module changes production, entry qualification, profit
protection, EARLY, FINAL, price handling, or order behavior.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping

import BTC15_SCALP_LADDER_RESEARCH_V1 as research
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_UNARMED_TERMINAL_HANDOFF_AUDIT_V1_1"


def _result_times(rows: list[Mapping[str, Any]]) -> dict[str, datetime]:
    out: dict[str, datetime] = {}
    for r in rows:
        if research.typ(r) != "RESULT":
            continue
        cid = research.cid(r)
        if not cid:
            continue
        ts = research.dt(r.get("timestamp_utc"))
        if ts == datetime.min.replace(tzinfo=timezone.utc):
            continue
        prev = out.get(cid)
        if prev is None or ts < prev:
            out[cid] = ts
    return out


def _paths(rows: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if research.typ(r) == "PATH" and research.cid(r):
            out[research.cid(r)].append(dict(r))
    return out


def _qualified_by_contract(rows: list[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in forward.forward_candidates([dict(r) for r in rows]):
        if research.candidate_qualified(c):
            out[research.contract(c)].append(dict(c))
    for contract in list(out):
        out[contract].sort(key=lambda x: research.dt(x.get("timestamp_utc")))
    return out


def _next_after(candidates: list[dict[str, Any]], after: datetime, used: set[str]) -> dict[str, Any] | None:
    for c in candidates:
        if research.cid(c) in used:
            continue
        if research.dt(c.get("timestamp_utc")) > after:
            return c
    return None


def audit(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(r) for r in rows]
    results = _result_times(rows)
    paths = _paths(rows)
    by_contract = _qualified_by_contract(rows)

    projected: list[dict[str, Any]] = []
    unarmed_terminals: list[dict[str, Any]] = []
    recovered_handoffs: list[dict[str, Any]] = []

    for contract, candidates in by_contract.items():
        used: set[str] = set()
        earliest = datetime.min.replace(tzinfo=timezone.utc)
        index = 1

        while True:
            cand = _next_after(candidates, earliest, used)
            if cand is None:
                break
            cid = research.cid(cand)
            used.add(cid)

            result_time = results.get(cid)
            if result_time is None:
                # Current/incomplete candidate: do not fabricate a terminal.
                break

            pm = research.measure_path(cand, research.path_rows_for(cand, paths))
            terminal_kind: str | None = None
            terminal_time: datetime | None = None

            if pm.exit_time_utc:
                terminal_kind = "PROTECTED_EXIT"
                terminal_time = research.dt(pm.exit_time_utc)
            elif not pm.armed:
                terminal_kind = "ENDED_UNARMED"
                terminal_time = result_time
                unarmed_terminals.append({
                    "contract": contract,
                    "candidate_id": cid,
                    "opportunity_index": index,
                    "side": str(cand.get("side") or "").strip().upper(),
                    "entry_ask": research.f(cand.get("entry_ask")),
                    "peak_gain": pm.peak_gain,
                    "adverse_gain": pm.adverse_gain,
                    "result_time_utc": result_time.isoformat(),
                    "state": "ENDED_UNARMED",
                    "actionable_exit": False,
                })
            else:
                # Armed but no validated protected EXIT: preserve the block.
                terminal_kind = "ARMED_NO_VALIDATED_EXIT"
                terminal_time = None

            rec = {
                "contract": contract,
                "opportunity_index": index,
                "candidate_id": cid,
                "side": str(cand.get("side") or "").strip().upper(),
                "entry_ask": research.f(cand.get("entry_ask")),
                "seconds_left": research.f(cand.get("seconds_left")),
                "btc30": research.f(cand.get("btc30")),
                "peak_gain": pm.peak_gain,
                "adverse_gain": pm.adverse_gain,
                "plus10": bool(pm.peak_gain is not None and pm.peak_gain >= 0.10 - 1e-12),
                "plus20": bool(pm.peak_gain is not None and pm.peak_gain >= 0.20 - 1e-12),
                "terminal_kind": terminal_kind,
                "entry_price_is_telemetry_only": True,
                "orders": False,
            }
            projected.append(rec)

            if terminal_time is None:
                break

            if terminal_kind == "ENDED_UNARMED":
                nxt = _next_after(candidates, terminal_time, used)
                if nxt is not None:
                    nid = research.cid(nxt)
                    npm = research.measure_path(nxt, research.path_rows_for(nxt, paths)) if nid in results else None
                    recovered_handoffs.append({
                        "contract": contract,
                        "from_candidate_id": cid,
                        "to_candidate_id": nid,
                        "to_entry_ask": research.f(nxt.get("entry_ask")),
                        "to_side": str(nxt.get("side") or "").strip().upper(),
                        "to_completed": nid in results,
                        "to_peak_gain": None if npm is None else npm.peak_gain,
                        "to_plus10": bool(npm is not None and npm.peak_gain is not None and npm.peak_gain >= 0.10 - 1e-12),
                        "to_plus20": bool(npm is not None and npm.peak_gain is not None and npm.peak_gain >= 0.20 - 1e-12),
                        "price_is_telemetry_only": True,
                    })

            earliest = terminal_time
            index += 1

    completed_handoffs = [x for x in recovered_handoffs if x["to_completed"]]
    plus10_handoffs = [x for x in completed_handoffs if x["to_plus10"]]
    plus20_handoffs = [x for x in completed_handoffs if x["to_plus20"]]
    armed_no_validated_exit = [x for x in projected if x.get("terminal_kind") == "ARMED_NO_VALIDATED_EXIT"]

    return {
        "version": VERSION,
        "research_only": True,
        "orders": False,
        "manual_execution_only": True,
        "protected_thresholds_changed": False,
        "stop_loss_rule_selected": False,
        "ended_unarmed_is_actionable_exit": False,
        "entry_price_filter_applied": False,
        "projected_completed_serial_opportunities": len(projected),
        "ended_unarmed_n": len(unarmed_terminals),
        "ended_unarmed_records": unarmed_terminals,
        "armed_no_validated_exit_n": len(armed_no_validated_exit),
        "armed_no_validated_exit_records": armed_no_validated_exit,
        "post_unarmed_later_qualified_n": len(recovered_handoffs),
        "post_unarmed_later_completed_n": len(completed_handoffs),
        "post_unarmed_later_plus10_n": len(plus10_handoffs),
        "post_unarmed_later_plus20_n": len(plus20_handoffs),
        "post_unarmed_later_plus10_rate": None if not completed_handoffs else len(plus10_handoffs) / len(completed_handoffs),
        "post_unarmed_later_plus20_rate": None if not completed_handoffs else len(plus20_handoffs) / len(completed_handoffs),
        "recovered_handoffs": recovered_handoffs,
        "projected_ladder": projected,
        "state_definition": {
            "ENDED_UNARMED": "collector RESULT received before +5c protection arm; informational lifecycle terminal only",
            "PROTECTED_EXIT": "existing frozen +5c arm then 4c giveback exit",
            "ARMED_NO_VALIDATED_EXIT": "remain blocked; no invented terminal",
        },
        "auto_promote_allowed": False,
        "note": "Use this only to test stale-ACTIVE lifecycle and handoff coverage. It does not validate a loss-cut or sell signal.",
    }


if __name__ == "__main__":
    print(f"{VERSION} | import/use audit(rows) | RESEARCH ONLY | NO ORDERS")
