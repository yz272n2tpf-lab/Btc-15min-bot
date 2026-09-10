#!/usr/bin/env python3
"""Research-only app-output state adapter for V7.

This is presentation/state plumbing only. It contains no qualification,
pricing, order, sizing, credential, or execution logic.
"""
from __future__ import annotations

ALLOWED_LANES = {"MOMENTUM_EXPANSION", "ULTRA_CHEAP_REVERSAL"}
EVENT_TO_STATE = {
    "watch": "SCALP WATCH",
    "entry": "ENTRY",
    "hold": "HOLD",
    "take_profit": "TAKE PROFIT",
    "exit": "EXIT",
}
ALLOWED_TRANSITIONS = {
    None: {"SCALP WATCH", "ENTRY"},
    "SCALP WATCH": {"SCALP WATCH", "ENTRY"},
    "ENTRY": {"HOLD", "TAKE PROFIT", "EXIT"},
    "HOLD": {"HOLD", "TAKE PROFIT", "EXIT"},
    "TAKE PROFIT": {"HOLD", "TAKE PROFIT", "EXIT"},
    "EXIT": {"SCALP WATCH"},
}
FORBIDDEN_KEYS = {"order_id", "place_order", "quantity", "api_key", "secret", "private_key"}

def adapt_event(event, previous_state=None):
    forbidden = FORBIDDEN_KEYS.intersection(event)
    if forbidden:
        raise ValueError("execution/secret fields forbidden: " + ",".join(sorted(forbidden)))
    kind = event.get("event")
    if kind not in EVENT_TO_STATE:
        raise ValueError(f"unknown app event: {kind!r}")
    lane = event.get("lane")
    if lane not in ALLOWED_LANES:
        raise ValueError(f"unknown V7 lane: {lane!r}")
    state = EVENT_TO_STATE[kind]
    if state not in ALLOWED_TRANSITIONS.get(previous_state, set()):
        raise ValueError(f"invalid transition: {previous_state!r} -> {state!r}")
    return {
        "state": state,
        "contract": event.get("ticker"),
        "lane": lane,
        "side": event.get("side"),
        "display_price": event.get("price"),
        "reason": event.get("reason"),
        "research_only": True,
        "orders_enabled": False,
    }
