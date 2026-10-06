"""Durable EARLY signal authority downstream of protected HTTP publication.

No source acquisition, native callbacks, strategy evaluation, orders or fills.
The legacy pure manager is reused only AFTER explicit EARLY acceptance. Its
legacy FINAL-dependent entry branch and reviewed-danger hooks are unreachable.
"""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import uuid

import BTC15_DIRECTIONAL_POSITION_MANAGER_V1 as manager

SCHEMA = "BTC15_DIRECTIONAL_SIGNAL_V1"
BASE = "abe212b513827c8cec28a2f64e0161e79296bd82"
PROTECTED_SHA256 = "66cdbaa21daa848f261e87e1528dce5a0cadd700fe3be22567f664f968f6d1b7"
EXIT_LIMITATION = "UNAVAILABLE_NO_QUALIFIED_EXECUTABLE_EXIT_RULE"


def pack(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(pack(value).encode()).hexdigest()


def utc(value):
    # Reject precision that datetime would silently truncate. Never round clocks.
    if isinstance(value, str) and not re.fullmatch(
            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)", value):
        raise ValueError("INVALID_OR_UNSUPPORTED_TIMESTAMP_PRECISION")
    return manager._utc(value)


def protected(raw):
    # Deliberately exclude SCALP, informational estimates and our own publication.
    return json.loads(pack({k: raw.get(k) for k in (
        "display_build", "generated_utc", "source_timestamp_utc", "contract",
        "timer", "market", "health", "safety", "parity", "early", "final")}))


def snapshot_identity(raw):
    """Publication-derived key, NOT a native shared decision ID or V2 witness.

    Request/generation time, parity arrival and age-at-render are not decisions.
    A changed payload at the same source is a conflict, never another transition.
    """
    source = utc(raw.get("source_timestamp_utc")).isoformat()
    key = digest([raw.get("contract"), source])
    market = {k: v for k, v in (raw.get("market") or {}).items()
              if k != "brti_effective_age_seconds"}
    final = {k: v for k, v in (raw.get("final") or {}).items()
             if not k.startswith("recorded_")}
    timer = raw.get("timer") or {}
    content = dict(contract=raw.get("contract"), source_timestamp_utc=source,
                   early=raw.get("early"), final=final, market=market,
                   timer={k: timer.get(k) for k in ("close_utc", "close_basis", "seconds_left")})
    return key, digest(content)


def encode_state(state):
    value = asdict(state)
    for k in ("close_utc", "last_source_utc"):
        if value[k] is not None:
            value[k] = value[k].isoformat()
    if value["position"]:
        value["position"]["entry_timestamp"] = state.position.entry_timestamp.isoformat()
        value["position"]["action"] = state.position.action.value
    return pack(value)


def decode_state(text):
    value = json.loads(text)
    for k in ("close_utc", "last_source_utc"):
        if value[k] is not None:
            value[k] = utc(value[k])
    if value["position"]:
        p = value["position"]
        p["entry_timestamp"], p["action"] = utc(p["entry_timestamp"]), manager.Action(p["action"])
        value["position"] = manager.Position(**p)
    return manager.State(**value)


def unavailable(reason, *, origin=None):
    return dict(schema=SCHEMA, authority="AUTHORITATIVE_ACTION_STATE", status="UNAVAILABLE",
                reason=reason, guidance=None, event=None, origin_id=origin,
                signal_only=True, manual_execution_only=True, orders_enabled=False,
                manual_fill=None, exit_rule=EXIT_LIMITATION)


def reduce_signal(state, raw, qualified, now):
    """Pure transition using protected results; no numerical strategy gates here."""
    frame = manager.read_protected_snapshot(raw, now)
    if qualified.get("usable_frame") is not True:
        raise ValueError("PUBLICATION_WAIT")
    if state.contract_id and frame.contract_id != state.contract_id:
        if frame.close <= state.close_utc:
            raise ValueError("OLDER_OR_CONFLICTING_CONTRACT")
        state = manager.State()
    if state.close_utc and abs((frame.close - state.close_utc).total_seconds()) > manager.CLOCK_TOLERANCE_SECONDS:
        raise ValueError("CONTRACT_CLOSE_CHANGED")
    if state.last_source_utc and frame.source <= state.last_source_utc:
        raise ValueError("DUPLICATE_OR_OUT_OF_ORDER_SOURCE")
    if state.position is None:
        if not manager._early_valid(frame):
            raise ValueError("EARLY_EVIDENCE_UNAVAILABLE")
        state = replace(state, contract_id=frame.contract_id, close_utc=frame.close,
                        last_source_utc=frame.source)
        if not frame.early["ready"] or state.buy_emitted:
            return state, None, "PASS", frame
        if qualified["lanes"]["early"]["publication_eligible"] is not True:
            raise ValueError("EARLY_PUBLICATION_WAIT")
        side = frame.early["side"]
        quote, ask = manager._quote(frame, side), manager._prob(frame.early.get("ask"))
        if quote is None or ask is None or ask <= 0 or ask != quote[1]:
            raise ValueError("ENTRY_ASK_MISSING_OR_NOT_EXACT_SAME_SIDE_ASK")
        # The signal begins HERE; the older quote/source timestamp is retained
        # separately. Do not backdate signal creation to native observation time.
        p = manager.Position(frame.contract_id, side, now, ask,
                             frame.early["fair"], frame.early["edge"],
                             saw_strong_final=manager._strong(frame, side))
        return replace(state, position=p, buy_emitted=True), "BUY", "AVAILABLE", frame
    # Source/quote/final outages are operational UNAVAILABLE, never loss/HOLD/EXIT.
    # The legacy reducer's stale-BRTI deterioration path is not invoked on WAIT.
    if (not manager._early_valid(frame) or not manager._final_valid(frame)
            or qualified.get("brti_fresh") is not True
            or frame.health.get("brti_fresh") is not True
            or manager._quote(frame, state.position.side) is None):
        raise ValueError("MANAGEMENT_EVIDENCE_UNAVAILABLE")
    p = state.position
    strong = manager._strong(frame, p.side)
    opposing = frame.final['ready'] and frame.final['side'] != p.side
    material = p.saw_strong_final and not strong
    event = None
    if p.action != manager.Action.PROTECT and (opposing or material):
        p = replace(p, action=manager.Action.PROTECT,
                    reason='QUALIFIED_OPPOSITION_OR_ESTABLISHED_CONFIRMATION_LOST')
        event = 'PROTECT'
    elif p.action == manager.Action.BUY:
        p = replace(p, action=manager.Action.HOLD, reason='EXISTING_EARLY_ORIGIN')
        event = 'HOLD'
    p = replace(p, saw_strong_final=p.saw_strong_final or strong)
    return replace(state, position=p, last_source_utc=frame.source), event, 'AVAILABLE', frame
