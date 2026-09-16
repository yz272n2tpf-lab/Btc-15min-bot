#!/usr/bin/env python3
"""Frozen deterministic fixtures for BTC15 scalp UI state contract V1.

PRESENTATION TEST DATA ONLY | NO NETWORK | NO ORDERS

These fixtures let the dashboard render every important scalp card state without
waiting for a live market transition.
"""
from __future__ import annotations

from typing import Any

from btc15_scalp_ui_state_contract_v1 import build_scalp_ui_state

VERSION = "BTC15_SCALP_UI_STATE_FIXTURES_V1"


def _combined(*, state="PASS", ask=None, bid=None, peak=None, gain=None,
              aligned=True, fresh=True, ready=True, opp=None, completed=0,
              scan_next=False, message=None, side="UP") -> dict[str, Any]:
    return {
        "contract": "KXBTC15M-FIXTURE",
        "canonical_seconds_left": 600.0,
        "headline": {
            "PASS": "FINAL_WATCH",
            "ACTIVE": "SCALP_ACTIVE",
            "PROTECT": "SCALP_PROTECT",
            "EXIT": "SCALP_EXIT",
        }[state],
        "early": {"state": "PASS", "side": None},
        "final": {"state": "WATCH", "side": None},
        "context_labels": [],
        "scalp": {
            "state": state,
            "side": None if state == "PASS" else side,
            "entry_ask": ask,
            "current_bid": bid,
            "peak_exec_gain": peak,
            "exec_gain": gain,
            "seconds_left": 599.0,
        },
        "scalp_contract_aligned": aligned,
        "scalp_source_fresh": fresh,
        "scalp_source_age_sec": 1.0 if fresh else 31.0,
        "scalp_integration_ready": ready,
        "scalp_block_reason": None if aligned and fresh and ready else "SCALP_SOURCE_STALE",
        "scalp_timer_delta_sec": 1.0,
        "scalp_management_message": message,
        "scalp_opportunity_index": opp,
        "scalp_serial_opportunities_completed": completed,
        "scalp_scanning_for_next": scan_next,
    }


def _direct(*, state="PASS", ask=None, bid=None, peak=None, gain=None,
            armed=False, pullback=False, exit_triggered=False, opp=None,
            completed=0, scan_next=False, side="UP", message=None) -> dict[str, Any]:
    return {
        "contract": "KXBTC15M-FIXTURE",
        "state": state,
        "side": None if state == "PASS" else side,
        "entry_price": ask,
        "current_bid": bid,
        "peak_exec_gain": peak,
        "exec_gain": gain,
        "armed": armed,
        "pullback_detected": pullback,
        "exit_triggered": exit_triggered,
        "opportunity_index": opp,
        "serial_opportunities_completed": completed,
        "scanning_for_next": scan_next,
        "management_message": message,
    }


def build_fixtures() -> dict[str, dict[str, Any]]:
    specs = {
        "WAIT": (
            _combined(state="PASS", aligned=True, fresh=True, ready=True, opp=None, message="NO QUALIFIED SCALP"),
            _direct(state="PASS"),
        ),
        "ACTIVE_IDEAL": (
            _combined(state="ACTIVE", ask=.31, bid=.33, opp=1, message="SCALP ACTIVE · BUILDING"),
            _direct(state="ACTIVE", ask=.31, bid=.33, opp=1),
        ),
        "ACTIVE_CAUTION_ABOVE_50": (
            _combined(state="ACTIVE", ask=.58, bid=.60, opp=1, message="SCALP ACTIVE · BUILDING"),
            _direct(state="ACTIVE", ask=.58, bid=.60, opp=1),
        ),
        "PROTECT_PULLBACK": (
            _combined(
                state="PROTECT", ask=.40, bid=.47, peak=.10, gain=.07,
                opp=2, completed=1, message="PROTECT PROFITS · PULLBACK DETECTED",
            ),
            _direct(
                state="PROTECT", ask=.40, bid=.47, peak=.10, gain=.07,
                armed=True, pullback=True, opp=2, completed=1,
                message="PROTECT PROFITS · PULLBACK DETECTED",
            ),
        ),
        "EXIT": (
            _combined(
                state="EXIT", ask=.40, bid=.46, peak=.11, gain=.06,
                opp=2, completed=1, message="EXIT / PROTECT PROFITS NOW",
            ),
            _direct(
                state="EXIT", ask=.40, bid=.46, peak=.11, gain=.06,
                armed=True, pullback=True, exit_triggered=True, opp=2, completed=1,
                message="EXIT / PROTECT PROFITS NOW",
            ),
        ),
        "SCANNING_NEXT": (
            _combined(
                state="PASS", aligned=True, fresh=True, ready=True,
                opp=None, completed=2, scan_next=True,
                message="WATCHING FOR NEXT QUALIFIED SCALP",
            ),
            _direct(state="PASS", completed=2, scan_next=True, message="WATCHING FOR NEXT QUALIFIED SCALP"),
        ),
        "STALE_FAIL_CLOSED": (
            _combined(
                state="PASS", aligned=True, fresh=False, ready=False,
                opp=None, message="SCALP WAIT · STALE SOURCE",
            ),
            _direct(state="ACTIVE", ask=.33, bid=.36, opp=1),
        ),
    }

    out: dict[str, dict[str, Any]] = {}
    for name, (combined, direct) in specs.items():
        out[name] = build_scalp_ui_state(combined, direct).to_dict()
    return out


FIXTURES = build_fixtures()


__all__ = ["VERSION", "FIXTURES", "build_fixtures"]
