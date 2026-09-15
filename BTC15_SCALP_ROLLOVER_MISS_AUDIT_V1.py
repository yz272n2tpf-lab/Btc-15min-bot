#!/usr/bin/env python3
"""
BTC15 scalp rollover miss audit V1.

READ ONLY | RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

Diagnoses whether a raw collector candidate near a 15-minute contract rollover
was eligible under the frozen V5 serial adapter but failed to become an official
numbered scalp because the cross-service contract alignment was not ready yet.

This module never changes qualification, lifecycle, price rules, timers, or
orders. It only reads the existing event export and reports facts.
"""
from __future__ import annotations

import json
import os
from typing import Any, Mapping

import btc15_scalp_blueprint_forward_v1 as forward
import BTC15_SCALP_LADDER_RESEARCH_V1 as research
from btc15_protected_module_adapter_v1 import scalp_state_from_events

VERSION = "BTC15_SCALP_ROLLOVER_MISS_AUDIT_V1"
TARGET_CONTRACT = os.environ.get("ROLLOVER_AUDIT_CONTRACT", "KXBTC15M-26SEP151000-00").strip()
TARGET_ENTRY = float(os.environ.get("ROLLOVER_AUDIT_ENTRY", "0.45"))
ENTRY_TOL = float(os.environ.get("ROLLOVER_AUDIT_ENTRY_TOL", "0.015"))


def f(v: Any) -> float | None:
    return research.f(v)


def diagnose(rows: list[Mapping[str, Any]], contract: str = TARGET_CONTRACT) -> dict[str, Any]:
    candidates = [
        dict(r) for r in rows
        if research.typ(r) == "CANDIDATE" and research.contract(r) == contract
    ]
    candidates.sort(key=lambda r: research.dt(r.get("timestamp_utc")))

    paths_by_id: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if research.typ(r) != "PATH":
            continue
        cid = research.cid(r)
        if cid:
            paths_by_id.setdefault(cid, []).append(dict(r))

    recs: list[dict[str, Any]] = []
    for c in candidates:
        ask = f(c.get("entry_ask"))
        if ask is None or abs(ask - TARGET_ENTRY) > ENTRY_TOL:
            continue
        cid = research.cid(c)
        state0 = scalp_state_from_events(c, ())
        pm = research.measure_path(c, research.path_rows_for(c, paths_by_id))
        recs.append({
            "candidate_id": cid,
            "timestamp_utc": str(c.get("timestamp_utc") or ""),
            "side": str(c.get("side") or "").upper(),
            "entry_ask": ask,
            "seconds_left": f(c.get("seconds_left")),
            "btc30": f(c.get("btc30")),
            "btc15": f(c.get("btc15")),
            "btc5": f(c.get("btc5")),
            "brti15": f(c.get("brti15")),
            "brti5": f(c.get("brti5")),
            "adapter_initial_state": state0.state,
            "v5_adapter_qualified": state0.state != "PASS",
            "peak_gain": pm.peak_gain,
            "adverse_gain": pm.adverse_gain,
            "armed_plus5": pm.armed,
            "protected_exit_gain": pm.exit_gain,
            "plus10": bool(pm.peak_gain is not None and pm.peak_gain >= 0.10),
            "plus20": bool(pm.peak_gain is not None and pm.peak_gain >= 0.20),
        })

    target = recs[0] if recs else None
    conclusion = "TARGET_NOT_FOUND"
    if target:
        if target["v5_adapter_qualified"]:
            conclusion = "V5_QUALIFIED_CANDIDATE_REQUIRES_SYNC_HANDOFF_REVIEW"
        else:
            conclusion = "CORRECTLY_REJECTED_BY_FROZEN_V5_ADAPTER"

    return {
        "version": VERSION,
        "research_only": True,
        "orders": False,
        "manual_execution_only": True,
        "contract": contract,
        "target_entry": TARGET_ENTRY,
        "entry_tolerance": ENTRY_TOL,
        "matching_candidates": recs,
        "target": target,
        "conclusion": conclusion,
        "strategy_change_selected": False,
        "price_filter_applied": False,
        "note": "If V5-qualified, compare timestamp to live contract-alignment logs before proposing any handoff fix.",
    }


def main() -> int:
    rows, sha = forward.fetch_csv_rows()
    out = diagnose(rows)
    out["source_sha256"] = sha
    t = out.get("target") or {}
    print(
        "ROLLOVER MISS AUDIT | "
        f"contract={out['contract']} | found={bool(t)} | "
        f"cid={t.get('candidate_id','-')} | side={t.get('side','-')} | "
        f"entry={t.get('entry_ask')} | left={t.get('seconds_left')} | btc30={t.get('btc30')} | "
        f"adapter={t.get('adapter_initial_state','-')} | qualified={t.get('v5_adapter_qualified')} | "
        f"peak={t.get('peak_gain')} | +10={t.get('plus10')} | +20={t.get('plus20')} | "
        f"conclusion={out['conclusion']} | READ ONLY | NO ORDERS",
        flush=True,
    )
    print(json.dumps(out, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
