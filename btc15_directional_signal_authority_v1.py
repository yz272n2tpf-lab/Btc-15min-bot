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
    next_state, view = manager.update(state, raw, now_utc=now)
    if view["blocked_reason"]:
        raise ValueError(view["blocked_reason"])
    if next_state.position is None or next_state.position.action == manager.Action.EXIT:
        raise ValueError("UNAUTHORIZED_MANAGER_TRANSITION")
    return next_state, view["event"], "AVAILABLE", frame


def initialize(path, activated_utc):
    """Explicit once-only offline/operator initialization; never automatic recovery."""
    path = Path(path)
    activated = utc(activated_utc).isoformat()
    # Exclusive creation prevents accidental replacement of an existing ledger.
    with path.open("xb"):
        pass
    with sqlite3.connect(path) as db:
        db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=FULL;
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE origins(contract TEXT PRIMARY KEY, id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE seen(key TEXT PRIMARY KEY, content TEXT NOT NULL);
        CREATE TABLE records(seq INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TRIGGER immutable_origin_update BEFORE UPDATE ON origins BEGIN
          SELECT RAISE(ABORT, 'immutable origin'); END;
        CREATE TRIGGER immutable_origin_delete BEFORE DELETE ON origins BEGIN
          SELECT RAISE(ABORT, 'immutable origin'); END;
        CREATE TRIGGER immutable_record_update BEFORE UPDATE ON records BEGIN
          SELECT RAISE(ABORT, 'immutable record'); END;
        CREATE TRIGGER immutable_record_delete BEFORE DELETE ON records BEGIN
          SELECT RAISE(ABORT, 'immutable record'); END;
        """)
        db.executemany("INSERT INTO meta VALUES (?,?)", [
            ("schema", SCHEMA), ("ledger_id", str(uuid.uuid4())), ("activated_utc", activated),
            ("state", encode_state(manager.State())), ("latest", pack(unavailable("NO_OBSERVATION")))])


class Authority:
    def __init__(self, path, *, runtime_epoch, build):
        self.path, self.runtime_epoch, self.build = Path(path), runtime_epoch, build

    def consume(self, raw, qualified, *, now_utc, receipt_utc):
        now, receipt = utc(now_utc), utc(receipt_utc)
        # mode=rw refuses to create an empty ledger after loss/restart.
        db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw", uri=True, timeout=0)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            meta = dict(db.execute("SELECT key,value FROM meta"))
            if meta["schema"] != SCHEMA:
                raise ValueError("LEDGER_SCHEMA_MISMATCH")
            state = decode_state(meta["state"])
            previous_origin = db.execute("SELECT payload FROM origins WHERE contract=?", (state.contract_id,)).fetchone()
            origin = json.loads(previous_origin[0]) if previous_origin else None
            if state.position and (not origin or any((
                    origin["side"] != state.position.side,
                    utc(origin["signal_timestamp_utc"]) != state.position.entry_timestamp,
                    origin["original_ask"] != state.position.entry_ask,
                    origin["protected_early"]["fair"] != state.position.entry_fair,
                    origin["protected_early"]["edge"] != state.position.entry_edge,
                    origin["manager_signal_id"] != state.position.position_id))):
                raise ValueError("IMMUTABLE_ORIGIN_CONFLICT")
            result = unavailable("SOURCE_UNAVAILABLE", origin=origin["origin_id"] if origin else None)
            evidence, key, content, event = None, None, None, None
            original_origin = origin
            db.execute("SAVEPOINT transition")
            try:
                if raw is None:
                    raise ValueError("SOURCE_REQUEST_UNAVAILABLE")
                evidence = protected(raw)
                source = utc(raw.get("source_timestamp_utc"))
                generated = utc(raw.get("generated_utc"))
                if not utc(meta["activated_utc"]) <= source <= generated <= receipt <= now:
                    raise ValueError("PUBLICATION_CLOCK_ORDER_OR_ACTIVATION")
                if qualified.get("observed_utc") != receipt.isoformat():
                    raise ValueError("OBSERVER_RECEIPT_MISMATCH")
                key, content = snapshot_identity(raw)
                seen = db.execute("SELECT content FROM seen WHERE key=?", (key,)).fetchone()
                if seen and seen[0] != content:
                    raise ValueError("SAME_SOURCE_PAYLOAD_CONFLICT")
                if origin and raw.get("contract") == origin["contract"]["ticker"]:
                    if raw["market"].get("target") != origin["contract"]["target"]:
                        raise ValueError("CONTRACT_TARGET_CHANGED")
                target = manager._number((raw.get("market") or {}).get("target"))
                if target is None or target <= 0:
                    raise ValueError("CONTRACT_TARGET_UNAVAILABLE")
                # Recompute only existing availability at consumption time, never alpha.
                from btc15_qualified_forward_observer_v1 import observation
                current = observation(raw, now)
                if seen:
                    # Repeated HTTP reads may report retained guidance, never transition.
                    frame = manager.read_protected_snapshot(raw, now)
                    if not current["usable_frame"]:
                        raise ValueError("PUBLICATION_WAIT")
                    if state.position and (not manager._final_valid(frame) or not current["brti_fresh"]
                                           or frame.health.get("brti_fresh") is not True):
                        raise ValueError("MANAGEMENT_EVIDENCE_UNAVAILABLE")
                    if state.last_source_utc != source or state.contract_id != frame.contract_id:
                        raise ValueError("DUPLICATE_OLDER_SOURCE")
                    status = "AVAILABLE" if state.position else "PASS"
                else:
                    # Manager sees current availability without rewriting protected evidence.
                    mapped = json.loads(pack(evidence))
                    mapped["health"]["brti_fresh"] = bool(current["brti_fresh"] and raw["health"].get("brti_fresh") is True)
                    state, event, status, frame = reduce_signal(state, mapped, current, now)
                    db.execute("INSERT INTO seen VALUES (?,?)", (key, content))
                    if event == "BUY":
                        # One accepted directional origin per contract, across all epochs.
                        p = state.position
                        origin_id = digest([SCHEMA, meta["ledger_id"], p.contract_id, p.side, key])
                        origin = dict(schema=SCHEMA, origin_id=origin_id, manager_signal_id=p.position_id,
                            contract=dict(ticker=p.contract_id, target=target,
                                published_close_utc=raw["timer"]["close_utc"],
                                close_basis=raw["timer"].get("close_basis"),
                                official_open_utc=None, official_close_utc=None),
                            side=p.side, signal_timestamp_utc=now.isoformat(),
                            protected_source_timestamp_utc=raw["source_timestamp_utc"],
                            original_ask=p.entry_ask, accepted_utc=now.isoformat(),
                            protected_early=evidence["early"], protected_publication=evidence,
                            protected_snapshot_key=key, protected_content_sha256=content,
                            signal_runtime_epoch=self.runtime_epoch, signal_build=self.build,
                            producer="FROZEN_TIER1", qualified_base=BASE,
                            protected_producer_sha256=PROTECTED_SHA256,
                            protected_generated_utc=raw["generated_utc"], observer_received_utc=receipt.isoformat(),
                            native_epoch=None, native_decision_id=None, owner_source_witness=None,
                            native_receipt_utc=None, native_consumption_utc=None,
                            native_publication_utc=None, protection_origin_link_basis="EXPLICIT_LEDGER_ORIGIN",
                            v2_admitted=False, signal_only=True, manual_execution_only=True, manual_fill=None)
                        db.execute("INSERT INTO origins VALUES (?,?,?)", (p.contract_id, origin_id, pack(origin)))
                    elif state.contract_id != (origin or {}).get("contract", {}).get("ticker"):
                        origin = None
                    db.execute("UPDATE meta SET value=? WHERE key='state'", (encode_state(state),))
                result = dict(schema=SCHEMA, authority="AUTHORITATIVE_ACTION_STATE", status=status,
                    reason="REPEATED_PUBLICATION_NO_TRANSITION" if seen else "PROTECTED_PUBLICATION_CONSUMED",
                    guidance=state.position.action.value if state.position else None,
                    event=event, origin_id=origin["origin_id"] if origin else None,
                    source_timestamp_utc=raw["source_timestamp_utc"], contract=raw["contract"],
                    protected_snapshot_key=key, protected_content_sha256=content,
                    final_confirmation=bool(state.position and current["brti_fresh"] and manager._strong(frame, state.position.side)),
                    signal_only=True, manual_execution_only=True, orders_enabled=False,
                    manual_fill=None, exit_rule=EXIT_LIMITATION)
            except (ValueError, TypeError, KeyError) as exc:
                db.execute("ROLLBACK TO transition")
                origin = original_origin
                result = unavailable(str(exc), origin=origin["origin_id"] if origin else None)
            db.execute("RELEASE transition")
            # Atomic ledger transaction: no emitted event or memory mutation before COMMIT.
            seq = db.execute("SELECT coalesce(max(seq),0)+1 FROM records").fetchone()[0]
            result.update(record_id=digest([meta["ledger_id"], seq]), sequence=seq,
                          signal_runtime_epoch=self.runtime_epoch, signal_build=self.build,
                          observer_received_utc=receipt.isoformat(), consumed_utc=now.isoformat(),
                          protected_evidence=evidence, origin=origin,
                          publication_completed_utc=None,
                          five_minute_caution=None, three_minute_guard=None, flip_risk=None)
            db.execute("INSERT INTO records VALUES (?,?)", (seq, pack(result)))
            db.execute("UPDATE meta SET value=? WHERE key='latest'", (pack(result),))
            db.commit()
            return result
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()


def build_identity(root):
    names = ("btc15_directional_signal_authority_v1.py", "BTC15_DIRECTIONAL_POSITION_MANAGER_V1.py",
             "btc15_qualified_forward_observer_v1.py", "btc15_directional_signal_publication_v1.py")
    return {name: hashlib.sha256((Path(root) / name).read_bytes()).hexdigest() for name in names}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Explicit new signal ledger initialization; never resets a ledger")
    parser.add_argument("--initialize", type=Path, required=True)
    parser.add_argument("--activated-utc", required=True)
    args = parser.parse_args()
    initialize(args.initialize, args.activated_utc)
