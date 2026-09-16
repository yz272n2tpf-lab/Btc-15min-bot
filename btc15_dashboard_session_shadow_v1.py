#!/usr/bin/env python3
"""BTC15 stateful dashboard session shadow V1.

READ ONLY | PRESENTATION ONLY | SIGNAL ONLY | NO ORDERS

This branch-only shadow wrapper polls the existing GET-only V5 dashboard/scalp
sources, maps them through Scalp UI State Contract V1, then through the green
DashboardPresentationSession.

Safety hierarchy:
- both sources healthy -> normal stabilized presentation session;
- combined source healthy but direct scalp source unavailable -> FINAL/EARLY/
  TIMER remain current while SCALP alone becomes fail-closed WAIT;
- combined source unavailable -> entire wrapper fails closed. No stale
  actionable display is replayed as current;
- no POST handler, no trading credentials, no signal thresholds, no orders.
"""
from __future__ import annotations

import copy
import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import requests

from btc15_dashboard_presentation_session_v1 import DashboardPresentationSession
from btc15_scalp_ui_state_contract_v1 import build_scalp_ui_state

VERSION = "BTC15_DASHBOARD_SESSION_SHADOW_V1"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(1, int(os.environ.get("BTC15_DASHBOARD_SESSION_SHADOW_POLL_SEC", "2")))
BASE_URL = os.environ.get(
    "BTC15_SCALP_V5_BASE_URL",
    "https://scalp-move-shadow-v1-production.up.railway.app",
).rstrip("/")
COMBINED_URL = f"{BASE_URL}/combined-state"
SCALP_URL = f"{BASE_URL}/state"
HTTP_TIMEOUT_SEC = 3.0

LOCK = threading.Lock()
SESSION = DashboardPresentationSession()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "status": "STARTING",
    "manual_execution_only": True,
    "orders": False,
    "order_action": None,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_json(url: str) -> dict[str, Any]:
    r = requests.get(url, timeout=HTTP_TIMEOUT_SEC, headers={"Cache-Control": "no-cache"})
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data


def fetch_combined_state() -> dict[str, Any]:
    return _get_json(COMBINED_URL)


def fetch_direct_scalp_state() -> dict[str, Any]:
    return _get_json(SCALP_URL)


def fail_closed_scalp_ui(combined: dict[str, Any], exc: Exception) -> dict[str, Any]:
    contract = combined.get("contract")
    return {
        "version": "BTC15_SCALP_UI_STATE_CONTRACT_V1",
        "contract": contract,
        "seconds_left": combined.get("canonical_seconds_left"),
        "display_state": "WAIT",
        "lifecycle_state": "PASS",
        "side": None,
        "opportunity_index": None,
        "serial_opportunities_completed": 0,
        "scanning_for_next": False,
        "entry_guidance": {
            "tier": "UNAVAILABLE",
            "label": "WAIT FOR QUALIFIED ENTRY",
            "entry_ask_c": None,
            "within_target_le50": False,
            "ideal_25_35": False,
            "good_36_50": False,
            "presentation_only": True,
        },
        "entry_ask_c": None,
        "current_bid_c": None,
        "exec_gain_c": None,
        "peak_exec_gain_c": None,
        "giveback_from_peak_c": None,
        "management_message": "WAIT · SCALP SOURCE UNAVAILABLE",
        "protection_armed": False,
        "pullback_context": False,
        "frozen_exit_triggered": False,
        "watch_warning": {
            "visible": False,
            "certified": False,
            "status": "HIDDEN_PENDING_FORWARD_CERTIFICATION",
            "research_thresholds_exposed": False,
            "frozen_exit_remains_visible": False,
        },
        "numeric_flip_risk": {
            "visible": False,
            "value": None,
            "certified": False,
            "status": "HIDDEN_PENDING_CERTIFICATION",
        },
        "source": {
            "app_ready": False,
            "contract_aligned": True,
            "source_fresh": False,
            "integration_ready": False,
            "source_age_sec": None,
            "timer_delta_sec": None,
            "block_reason": f"SCALP_SOURCE_UNAVAILABLE:{type(exc).__name__}",
            "fail_closed": True,
        },
        "horizon_context": {
            "early": dict(combined.get("early") or {}),
            "final": dict(combined.get("final") or {}),
            "headline": combined.get("headline"),
            "context_labels": list(combined.get("context_labels") or ()),
            "blended_accuracy": None,
            "horizons_remain_separate": True,
        },
        "manual_execution_only": True,
        "order_action": None,
        "orders": False,
    }


def build_ready_state(
    combined: dict[str, Any],
    direct_scalp: dict[str, Any] | None,
    *,
    direct_error: Exception | None = None,
) -> dict[str, Any]:
    if direct_scalp is not None:
        scalp_ui = build_scalp_ui_state(combined, direct_scalp).to_dict()
        direct_status = "HEALTHY"
    else:
        if direct_error is None:
            direct_error = RuntimeError("direct scalp source unavailable")
        scalp_ui = fail_closed_scalp_ui(combined, direct_error)
        direct_status = "FAIL_CLOSED"

    with LOCK:
        model = SESSION.process(combined, scalp_ui)

    return {
        "ok": True,
        "version": VERSION,
        "status": "READY" if direct_scalp is not None else "READY_SCALP_FAIL_CLOSED",
        "generated_at_utc": utcnow(),
        "source": {
            "combined_url": COMBINED_URL,
            "scalp_url": SCALP_URL,
            "transport": "GET_ONLY",
            "combined_status": "HEALTHY",
            "scalp_status": direct_status,
        },
        "dashboard": model,
        "manual_execution_only": True,
        "order_action": None,
        "orders": False,
        "production_logic_changed": False,
        "signal_thresholds_changed": False,
        "numeric_flip_risk_visible": False,
        "watch_warning_thresholds_visible": False,
    }


def fail_closed_combined(exc: Exception) -> dict[str, Any]:
    # Do not feed an invented combined frame into the session. The internal last
    # healthy context remains memory for later recovery, but no stale actionable
    # card is emitted as current while the combined authority is unavailable.
    return {
        "ok": False,
        "version": VERSION,
        "status": "FAIL_CLOSED_COMBINED_SOURCE_UNAVAILABLE",
        "generated_at_utc": utcnow(),
        "error": f"{type(exc).__name__}:{exc}",
        "source": {
            "combined_url": COMBINED_URL,
            "scalp_url": SCALP_URL,
            "transport": "GET_ONLY",
            "combined_status": "FAIL_CLOSED",
            "scalp_status": "UNKNOWN",
        },
        "dashboard": {
            "contract": None,
            "cards": {
                "FINAL_OUTCOME": {"action": "WAIT · DATA SOURCE UNAVAILABLE", "primary": "NO ACTION"},
                "EARLY_OPPORTUNITY": {"action": "WAIT · DATA SOURCE UNAVAILABLE", "primary": "NO ACTION"},
                "CONTRACT_TIME_LEFT": {"primary": "—:—", "visible_timer_count": 1},
                "SCALP_OPPORTUNITY": {"action": "WAIT · DATA SOURCE UNAVAILABLE", "primary": "NO ACTION · SOURCE NOT READY"},
                "FLIP_RISK": {"primary": "NOT CALIBRATED", "numeric_value": None, "numeric_visible": False},
            },
            "safety": {
                "manual_execution_only": True,
                "manual_position_confirmed": False,
                "numeric_flip_risk_visible": False,
                "orders": False,
                "order_action": None,
            },
        },
        "manual_execution_only": True,
        "order_action": None,
        "orders": False,
        "production_logic_changed": False,
        "signal_thresholds_changed": False,
        "numeric_flip_risk_visible": False,
        "watch_warning_thresholds_visible": False,
    }


def refresh_once() -> dict[str, Any]:
    try:
        combined = fetch_combined_state()
    except Exception as exc:
        out = fail_closed_combined(exc)
    else:
        try:
            direct = fetch_direct_scalp_state()
            out = build_ready_state(combined, direct)
        except Exception as exc:
            out = build_ready_state(combined, None, direct_error=exc)

    with LOCK:
        STATE.clear()
        STATE.update(copy.deepcopy(out))
        return copy.deepcopy(STATE)


def loop() -> None:
    while True:
        refresh_once()
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15DashboardSessionShadowV1/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("DASHBOARD_SESSION_SHADOW_HTTP | request", flush=True)

    def _send(self, code: int, obj: dict[str, Any]) -> None:
        raw = json.dumps(obj, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        with LOCK:
            state = copy.deepcopy(STATE)
        if path == "/health":
            return self._send(200, {
                "ok": True,
                "presentation_ok": state.get("ok") is True,
                "status": state.get("status"),
                "version": VERSION,
                "orders": False,
            })
        if path in {"/dashboard-session", "/state"}:
            return self._send(200 if state.get("ok") else 503, state)
        return self._send(404, {"ok": False, "error": "not_found", "orders": False})


def main() -> int:
    print(
        f"{VERSION} START | source={BASE_URL} | GET ONLY | STATEFUL PRESENTATION | "
        "NUMERIC FLIP HIDDEN | WATCH THRESHOLDS HIDDEN | NO ORDERS",
        flush=True,
    )
    refresh_once()
    threading.Thread(target=loop, name="btc15-dashboard-session-shadow-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
