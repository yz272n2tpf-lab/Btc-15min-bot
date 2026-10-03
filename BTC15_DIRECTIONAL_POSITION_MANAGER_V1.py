"""Pure directional shadow reducer. SIGNAL ONLY / NO ORDERS.

No I/O, model imports, clocks, collectors, threads, orders, or live wiring.
Callers own immutable State and supply an explicit UTC clock plus an existing
protected dashboard snapshot. BUY records a hypothetical ASK, never a fill.
Management semantics are research-only; no numeric exit model is shipped.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from math import isfinite
from typing import Mapping
from zoneinfo import ZoneInfo


VERSION = "BTC15_DIRECTIONAL_POSITION_MANAGER_V1"
SOURCE_MAX_AGE_SECONDS = 15.0  # Existing dashboard freshness ceiling, not alpha.
CLOCK_TOLERANCE_SECONDS = 2.0  # Existing observer alignment tolerance.
RESEARCH = "RESEARCH / UNVALIDATED"


class Action(str, Enum):
    NO_POSITION = "NO_POSITION"
    BUY = "BUY"
    HOLD = "HOLD"
    PROTECT = "PROTECT"
    EXIT = "EXIT"


class Light(str, Enum):
    STRONG = "STRONG CONFIRMATION"
    CAUTION = "CAUTION"
    PROTECT = "PROTECT WARNING"
    EXIT = "EXIT WARNING"


@dataclass(frozen=True)
class Position:
    contract_id: str
    side: str
    entry_timestamp: datetime
    entry_ask: float
    entry_fair: float
    entry_edge: float
    action: Action = Action.BUY
    saw_strong_final: bool = False
    reason: str = "PROTECTED_EARLY_QUALIFIED"

    @property
    def position_id(self) -> str:
        return f"{self.contract_id}:{self.side}:{self.entry_timestamp.isoformat()}"


@dataclass(frozen=True)
class State:
    contract_id: str | None = None
    close_utc: datetime | None = None
    last_source_utc: datetime | None = None
    position: Position | None = None
    # At most one position per contract. State must survive caller restarts.
    buy_emitted: bool = False


@dataclass(frozen=True)
class DangerRule:
    """Caller-reviewed offline evidence reference; never self-authorized by input.

    No rules ship enabled. SYNTHETIC_ONLY checks mechanics, not market efficacy.
    HISTORICAL_DEVELOPMENT is reserved for a separately reviewed future rule.
    """
    rule_id: str
    validation_ref: str
    scope: str
    allowed_action: Action


@dataclass(frozen=True)
class DangerAssessment:
    position_id: str
    contract_id: str
    side: str
    source_timestamp: datetime
    rule_id: str
    validation_ref: str
    action: Action
    severe: bool = False


@dataclass(frozen=True)
class Frame:
    contract_id: str
    source: datetime
    close: datetime
    seconds_left: float
    early: Mapping
    final: Mapping
    market: Mapping
    health: Mapping


@dataclass(frozen=True)
class LevelContext:
    """Complete input contract for future offline development of cents rules.

    Confidence values retain their accompanying sides; an opposite-side fair
    value is never silently treated as confidence in the held position.
    """
    position_id: str
    contract_id: str
    side: str
    source_timestamp: datetime
    entry_timestamp: datetime
    entry_ask: float
    current_bid: float
    current_ask: float
    seconds_remaining: float
    entry_fair: float
    entry_edge: float
    early_side: str
    early_fair: float
    early_edge: float
    final_side: str
    final_confidence: float
    final_ready: bool
    final_recorded_call: bool
    final_recorded_side: str | None
    final_recorded_confidence: float | None
    final_conditions: Mapping
    action: Action
    safety_light: Light


def calculate_levels(context: LevelContext | None) -> dict:
    """Fail closed: no historically supported numerical model is available.

    This explicit seam is where a separately developed/reviewed calculation can
    later consume every required input. Current bid/ask are observations, never
    mislabeled as a recommended sell zone. No callback/execution hook exists.
    """
    return {"status": RESEARCH, "protect_zone_cents": None,
            "exit_zone_cents": None, "model_id": None,
            "reason": "NO_VALIDATED_CENTS_MODEL" if context else "REQUIRED_INPUTS_UNAVAILABLE"}


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if isfinite(value) else None


def _prob(value) -> float | None:
    value = _number(value)
    return value if value is not None and 0 <= value <= 1 else None


def _side(value) -> str | None:
    return value if value in ("UP", "DOWN") else None


def _utc(value) -> datetime:
    try:
        stamp = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("naive timestamp")
        return stamp.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError):
        raise ValueError("INVALID_UTC_TIMESTAMP") from None


def _map(value) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def read_protected_snapshot(raw: Mapping, now_utc: datetime) -> Frame:
    """Schema mapping only. Never reconstruct protected qualification models.

    Source labels/booleans are authoritative. Structural validation cannot
    promote PASS to qualified. SCALP and position_protection are never read.
    """
    now = _utc(now_utc)
    raw = _map(raw)
    timer, health = _map(raw.get("timer")), _map(raw.get("health"))
    source, close = _utc(raw.get("source_timestamp_utc")), _utc(timer.get("close_utc"))
    left = _number(timer.get("seconds_left"))
    if left is None or not 0 < left <= 900:
        raise ValueError("INVALID_REMAINING_TIME")
    canonical_close = datetime.fromtimestamp(round(close.timestamp() / 900) * 900, timezone.utc)
    if (abs((canonical_close - close).total_seconds()) > CLOCK_TOLERANCE_SECONDS
            or abs((source + timedelta(seconds=left) - close).total_seconds()) > CLOCK_TOLERANCE_SECONDS):
        raise ValueError("CONTRACT_CLOCK_MISMATCH")
    local = canonical_close.astimezone(ZoneInfo("America/New_York"))
    expected = "KXBTC15M-" + local.strftime("%y%b%d%H%M-%M").upper()
    if raw.get("contract") != expected:
        raise ValueError("CONTRACT_ID_CLOSE_MISMATCH")
    if not close - timedelta(seconds=900) <= source <= now < close:
        raise ValueError("OUTSIDE_CONTRACT_WINDOW")
    if not 0 <= (now - source).total_seconds() <= SOURCE_MAX_AGE_SECONDS:
        raise ValueError("STALE_SOURCE")
    if health.get("source_fresh") is not True or health.get("market_open") is not True:
        raise ValueError("SOURCE_NOT_FRESH_OR_MARKET_CLOSED")
    safety = _map(raw.get("safety"))
    if safety.get("orders_enabled") is not False or safety.get("read_only") is not True:
        raise ValueError("READ_ONLY_BOUNDARY_MISSING")
    return Frame(expected, source, close, (close - now).total_seconds(),
                 _map(raw.get("early")), _map(raw.get("final")),
                 _map(raw.get("market")), health)


def _early_valid(frame: Frame) -> bool:
    e = frame.early
    return (e.get("source") == "FROZEN_TIER1" and type(e.get("ready")) is bool
            and _side(e.get("side")) is not None and _prob(e.get("fair")) is not None
            and _number(e.get("edge")) is not None)


def _final_valid(frame: Frame) -> bool:
    f = frame.final
    return (f.get("source") == "FROZEN_V4_6_FINAL" and type(f.get("ready")) is bool
            and _side(f.get("side")) is not None and _prob(f.get("confidence")) is not None)


def _quote(frame: Frame, side: str) -> tuple[float, float] | None:
    if frame.health.get("paired_quotes") is not True:
        return None
    bid = _prob(frame.market.get(side.lower() + "_bid"))
    ask = _prob(frame.market.get(side.lower() + "_ask"))
    return (bid, ask) if bid is not None and ask is not None and bid <= ask else None


def _strong(frame: Frame, side: str) -> bool:
    # A past recorded call never masks current deterioration or missing BRTI.
    return (_final_valid(frame) and frame.final["ready"] is True
            and frame.final["side"] == side and frame.health.get("brti_fresh") is True)


def _danger_action(assessment, rules, position, frame) -> Action | None:
    if not isinstance(assessment, DangerAssessment):
        return None
    if (assessment.position_id != position.position_id
            or assessment.contract_id != position.contract_id
            or assessment.side != position.side
            or assessment.source_timestamp != frame.source
            or assessment.action not in (Action.PROTECT, Action.EXIT)
            or (assessment.action == Action.EXIT and assessment.severe is not True)):
        return None
    for rule in rules:
        if (isinstance(rule, DangerRule) and rule.rule_id and rule.validation_ref
                and rule.scope in ("SYNTHETIC_ONLY", "HISTORICAL_DEVELOPMENT")
                and rule.rule_id == assessment.rule_id
                and rule.validation_ref == assessment.validation_ref
                and rule.allowed_action == assessment.action):
            return assessment.action
    return None


def _cents(value):
    return None if value is None else round(value * 100, 8)


def level_context(position, frame, light) -> LevelContext | None:
    if position is None or frame is None or not _early_valid(frame) or not _final_valid(frame):
        return None
    quote = _quote(frame, position.side)
    if quote is None or frame.health.get("brti_fresh") is not True:
        return None
    e, f = frame.early, frame.final
    return LevelContext(position.position_id, position.contract_id, position.side,
                        frame.source, position.entry_timestamp, position.entry_ask,
                        *quote, frame.seconds_left, position.entry_fair, position.entry_edge,
                        e["side"], e["fair"], e["edge"], f["side"], f["confidence"],
                        f["ready"], f.get("recorded_final_call") is True,
                        _side(f.get("recorded_side")), _prob(f.get("recorded_confidence")),
                        deepcopy(_map(f.get("conditions"))), position.action, light)


def _view(state, frame, raw_final, *, event=None, blocked=None, rollover=False):
    p = state.position
    action = p.action if p else Action.NO_POSITION
    strong = frame is not None and p is not None and _strong(frame, p.side)
    # Render action and danger atomically. Latched danger wins over recovery.
    light = (Light.EXIT if action == Action.EXIT else Light.PROTECT if action == Action.PROTECT
             else Light.STRONG if strong and not blocked else Light.CAUTION)
    quote = _quote(frame, p.side) if frame and p else None
    context = level_context(p, frame, light) if not blocked else None
    e = frame.early if frame else {}
    display_side = p.side if p else _side(e.get("side"))
    current_quote = _quote(frame, display_side) if frame and display_side else None
    return {
        "version": VERSION, "mode": "SHADOW", "management_validation": RESEARCH,
        "signal_only": True, "manual_execution_only": True, "orders_enabled": False,
        "order_action": None, "contract_id": state.contract_id,
        "position_id": p.position_id if p else None,
        "state": action.value, "event": event,
        "action": {"label": "PROTECT PROFITS" if action == Action.PROTECT else action.value,
                   "actionable": blocked is None and p is not None,
                   "reason": blocked or (p.reason if p else "NO_EARLY_POSITION")},
        "early": {"side": display_side,
                  "entry_status": "DATA_UNAVAILABLE" if blocked else "SHADOW_POSITION" if p else "WAITING",
                  "entry_basis": "HYPOTHETICAL_OBSERVED_ASK_NO_FILL" if p else None,
                  "entry_timestamp_utc": p.entry_timestamp.isoformat() if p else None,
                  "entry_ask_cents": _cents(p.entry_ask) if p else None,
                  "current_ask_cents": _cents(current_quote[1]) if current_quote else None,
                  "current_bid_cents": _cents(current_quote[0]) if current_quote else None,
                  "confidence_evidence": {"entry_fair": p.entry_fair if p else None,
                                          "entry_edge": p.entry_edge if p else None,
                                          "current_side": e.get("side"),
                                          "current_fair": e.get("fair"), "current_edge": e.get("edge")},
                  "minutes_remaining": frame.seconds_left / 60 if frame else None},
        "final": {"visible": True, "protected_view": deepcopy(raw_final),
                  "protected_contract_id": frame.contract_id if frame else None,
                  "safety_light": light.value, "fresh": frame is not None and _final_valid(frame),
                  "light_latched_to_action": action in (Action.PROTECT, Action.EXIT)},
        "levels": calculate_levels(context),
        "level_inputs_ready": context is not None,
        "quote_basis": "EXISTING_PRODUCTION_PAIRED_SNAPSHOT" if quote else None,
        "source_timestamp_utc": frame.source.isoformat() if frame else None,
        "seconds_remaining": frame.seconds_left if frame else None,
        "rollover_cleared_position": rollover, "blocked_reason": blocked,
    }


def update(state: State, raw: Mapping, *, now_utc: datetime,
           danger: DangerAssessment | None = None,
           reviewed_rules: tuple[DangerRule, ...] = ()) -> tuple[State, dict]:
    """One deterministic observation -> one state and one atomic display.

    Transitions are monotone per position. PROTECT never automatically resumes
    HOLD; EXIT never re-enters. Danger may skip intermediate states. Replays do
    not emit events. A fresh new contract clears the old position before entry.
    """
    now = _utc(now_utc)
    # Clear expired exposure even during a feed outage; preserve the watermark.
    expired = state.close_utc is not None and now >= state.close_utc
    cleared = bool(expired and state.position)
    if expired:
        state = replace(state, position=None)
    try:
        frame = read_protected_snapshot(raw, now)
    except ValueError as exc:
        # Never place a different contract's direction under this position.
        supplied = _map(raw)
        final = _map(supplied.get("final")) if supplied.get("contract") == state.contract_id else {}
        return state, _view(state, None, final,
                            blocked=str(exc), rollover=cleared)

    if state.contract_id is not None and frame.contract_id != state.contract_id:
        if frame.close < state.close_utc:
            return state, _view(state, None, {}, blocked="OLDER_CONTRACT_REJECTED")
        if frame.close <= state.close_utc:
            return state, _view(state, None, {}, blocked="CONTRACT_ROLLOVER_MISMATCH")
        cleared = True
        state = State()
    if state.contract_id is None:
        state = replace(state, contract_id=frame.contract_id, close_utc=frame.close)
    elif abs((frame.close - state.close_utc).total_seconds()) > CLOCK_TOLERANCE_SECONDS:
        return state, _view(state, None, frame.final, blocked="CONTRACT_CLOSE_CHANGED")
    # Duplicate/reordered input cannot refresh a BUY or inject a later warning.
    if state.last_source_utc is not None and frame.source <= state.last_source_utc:
        return state, _view(state, None, frame.final, blocked="DUPLICATE_OR_OUT_OF_ORDER_SOURCE")

    state = replace(state, last_source_utc=frame.source)
    p, event, blocked = state.position, None, None
    if p is None:
        if not _early_valid(frame):
            blocked = "EARLY_EVIDENCE_UNAVAILABLE"
        elif frame.early["ready"] is True and not state.buy_emitted:
            side = frame.early["side"]
            quote, entry_ask = _quote(frame, side), _prob(frame.early.get("ask"))
            if quote is None or entry_ask is None or entry_ask <= 0 or abs(entry_ask - quote[1]) > 1e-9:
                blocked = "ENTRY_ASK_MISSING_OR_NOT_CURRENT_SIDE_ASK"
            elif not _final_valid(frame):
                blocked = "FINAL_EVIDENCE_UNAVAILABLE"
            elif frame.final["side"] != side:
                blocked = "FINAL_DISAGREES_WITH_EARLY"
            else:
                p = Position(frame.contract_id, side, frame.source, entry_ask,
                             frame.early["fair"], frame.early["edge"],
                             saw_strong_final=_strong(frame, side))
                state = replace(state, position=p, buy_emitted=True)
                event = "BUY"
    elif p.action != Action.EXIT:
        strong = _strong(frame, p.side)
        requested = _danger_action(danger, reviewed_rules, p, frame)
        # Missing evidence suppresses actionable display; it never means HOLD
        # is newly supported and never manufactures a severity classification.
        complete = _early_valid(frame) and _final_valid(frame)
        if not complete:
            blocked = "DIRECTIONAL_EVIDENCE_UNAVAILABLE"
        elif requested == Action.EXIT:
            p = replace(p, action=Action.EXIT, reason="REVIEWED_SEVERE_DANGER:" + danger.rule_id)
            event = "EXIT"
        elif p.action != Action.PROTECT and (
                requested == Action.PROTECT
                or frame.final["side"] != p.side
                or (p.saw_strong_final and not strong)):
            p = replace(p, action=Action.PROTECT, reason="FINAL_DANGER_OR_CONFIRMATION_LOST_RESEARCH")
            event = "PROTECT"
        elif p.action == Action.BUY:
            p = replace(p, action=Action.HOLD, reason="EXISTING_EARLY_POSITION")
            event = "HOLD"
        p = replace(p, saw_strong_final=p.saw_strong_final or strong)
        state = replace(state, position=p)

    if state.position and _quote(frame, state.position.side) is None:
        blocked = blocked or "CURRENT_PRICE_UNAVAILABLE"
    return state, _view(state, frame, frame.final, event=event, blocked=blocked, rollover=cleared)


__all__ = ["Action", "Light", "Position", "State", "DangerRule", "DangerAssessment",
           "Frame", "LevelContext", "read_protected_snapshot", "level_context",
           "calculate_levels", "update"]
