"""Deterministic fabricated examples. No files, endpoints or sample loading."""
from datetime import datetime, timedelta, timezone
import json
from zoneinfo import ZoneInfo

from BTC15_DIRECTIONAL_POSITION_MANAGER_V1 import (
    Action, DangerAssessment, DangerRule, State, update,
)


START = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
SYNTHETIC_EXIT_RULE = DangerRule(
    "SYNTHETIC_SEVERE_DANGER_V1", "synthetic-fixture://directional-v1/severe",
    "SYNTHETIC_ONLY", Action.EXIT,
)


def fixture(offset=300, *, close_offset=900, side="UP", early_ready=True,
            final_ready=False, final_side=None, bid=.30, ask=.32):
    """Prices/evidence are fabricated, not learned thresholds or market samples."""
    source, close = START + timedelta(seconds=offset), START + timedelta(seconds=close_offset)
    local = close.astimezone(ZoneInfo("America/New_York"))
    return {
        "contract": "KXBTC15M-" + local.strftime("%y%b%d%H%M-%M").upper(),
        "source_timestamp_utc": source.isoformat(),
        "timer": {"close_utc": close.isoformat(), "seconds_left": close_offset - offset},
        "health": {"source_fresh": True, "paired_quotes": True,
                   "market_open": True, "brti_fresh": True},
        "safety": {"read_only": True, "orders_enabled": False},
        "market": {"up_bid": bid if side == "UP" else 1-ask,
                   "up_ask": ask if side == "UP" else 1-bid,
                   "down_bid": bid if side == "DOWN" else 1-ask,
                   "down_ask": ask if side == "DOWN" else 1-bid},
        "early": {"source": "FROZEN_TIER1", "ready": early_ready, "side": side,
                  "ask": ask, "bid": bid, "fair": .82, "edge": .50, "status": "GOOD"},
        "final": {"source": "FROZEN_V4_6_FINAL", "ready": final_ready,
                  "side": final_side or side, "confidence": .94 if final_ready else .82,
                  "recorded_final_call": False, "recorded_side": None,
                  "recorded_confidence": None, "conditions": {}},
        "scalp": {"fixture_marker": "NEVER_READ_OR_CHANGED"},
    }


def advance(state, raw, **kwargs):
    return update(state, raw, now_utc=datetime.fromisoformat(raw["source_timestamp_utc"]), **kwargs)


def examples():
    state, buy = advance(State(), fixture())
    state, hold = advance(state, fixture(305, final_ready=True, bid=.63, ask=.65))
    state, protect = advance(state, fixture(310, early_ready=False, bid=.59, ask=.61))
    raw = fixture(315, early_ready=False, final_side="DOWN", bid=.45, ask=.47)
    danger = DangerAssessment(state.position.position_id, state.contract_id, "UP",
                              datetime.fromisoformat(raw["source_timestamp_utc"]),
                              SYNTHETIC_EXIT_RULE.rule_id, SYNTHETIC_EXIT_RULE.validation_ref,
                              Action.EXIT, severe=True)
    _, exit_view = advance(state, raw, danger=danger, reviewed_rules=(SYNTHETIC_EXIT_RULE,))
    return {"data_scope": "SYNTHETIC_ONLY", "market_validation": "NONE",
            "examples": [buy, hold, protect, exit_view]}


if __name__ == "__main__":
    print(json.dumps(examples(), indent=2, allow_nan=False))
