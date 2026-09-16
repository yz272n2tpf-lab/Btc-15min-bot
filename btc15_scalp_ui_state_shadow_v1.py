#!/usr/bin/env python3
"""BTC15 scalp UI state shadow V1.

READ ONLY | PRESENTATION ONLY | SIGNAL ONLY | NO ORDERS

Fetches the existing Combined State Bridge V5 public GET endpoints and converts
those already-evaluated states through BTC15_SCALP_UI_STATE_CONTRACT_V1.
It owns no signal thresholds and has no order/trading credentials or write path.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import requests

from btc15_scalp_ui_state_contract_v1 import VERSION as CONTRACT_VERSION
from btc15_scalp_ui_state_contract_v1 import build_scalp_ui_state

VERSION = "BTC15_SCALP_UI_STATE_SHADOW_V1"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(1, int(os.environ.get("BTC15_SCALP_UI_SHADOW_POLL_SEC", "2")))
BASE_URL = os.environ.get(
    "BTC15_SCALP_V5_BASE_URL",
    "https://scalp-move-shadow-v1-production.up.railway.app",
).rstrip("/")
COMBINED_URL = f"{BASE_URL}/combined-state"
SCALP_URL = f"{BASE_URL}/state"
HTTP_TIMEOUT_SEC = 3.0

LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "contract_version": CONTRACT_VERSION,
    "status": "STARTING",
    "manual_execution_only": True,
    "order_action": None,
    "orders": False,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _get_json(url: str) -> dict[str, Any]:
    r = requests.get(url, timeout=HTTP_TIMEOUT_SEC, headers={"Cache-Control": "no-cache"})
    r.raise_for_status()
    d = r.json()
    if not isinstance(d, dict):
        raise ValueError("expected JSON object")
    return d


def fetch_source_states() -> tuple[dict[str, Any], dict[str, Any]]:
    return _get_json(COMBINED_URL), _get_json(SCALP_URL)


def build_shadow_state(
    combined: dict[str, Any],
    direct_scalp: dict[str, Any],
) -> dict[str, Any]:
    ui = build_scalp_ui_state(combined, direct_scalp).to_dict()
    return {
        "ok": True,
        "version": VERSION,
        "contract_version": CONTRACT_VERSION,
        "status": "READY",
        "generated_at_utc": utcnow(),
        "source": {
            "combined_url": COMBINED_URL,
            "scalp_url": SCALP_URL,
            "transport": "GET_ONLY",
        },
        "ui": ui,
        "manual_execution_only": True,
        "order_action": None,
        "orders": False,
        "production_logic_changed": False,
        "signal_thresholds_changed": False,
        "watch_warning_certified": False,
        "numeric_flip_risk_visible": False,
    }


def fail_closed(exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "version": VERSION,
        "contract_version": CONTRACT_VERSION,
        "status": "FAIL_CLOSED_SOURCE_UNAVAILABLE",
        "generated_at_utc": utcnow(),
        "error": f"{type(exc).__name__}:{exc}",
        "ui": {
            "display_state": "WAIT",
            "source": {"app_ready": False, "fail_closed": True},
            "watch_warning": {
                "visible": False,
                "certified": False,
                "status": "HIDDEN_PENDING_FORWARD_CERTIFICATION",
            },
            "numeric_flip_risk": {
                "visible": False,
                "value": None,
                "certified": False,
                "status": "HIDDEN_PENDING_CERTIFICATION",
            },
        },
        "manual_execution_only": True,
        "order_action": None,
        "orders": False,
        "production_logic_changed": False,
        "signal_thresholds_changed": False,
    }


def refresh_once() -> dict[str, Any]:
    try:
        combined, scalp = fetch_source_states()
        out = build_shadow_state(combined, scalp)
    except Exception as exc:
        out = fail_closed(exc)
    with LOCK:
        STATE.clear()
        STATE.update(out)
        return dict(STATE)


def loop() -> None:
    while True:
        refresh_once()
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15ScalpUIShadowV1/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_UI_SHADOW_HTTP | request", flush=True)

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
            state = dict(STATE)
        if path == "/health":
            return self._send(200, {
                "ok": True,
                "analysis_ok": state.get("ok") is True,
                "status": state.get("status"),
                "version": VERSION,
                "contract_version": CONTRACT_VERSION,
                "orders": False,
            })
        if path in {"/ui-state", "/state"}:
            return self._send(200 if state.get("ok") else 503, state)
        return self._send(404, {"ok": False, "error": "not_found", "orders": False})


def main() -> int:
    print(
        f"{VERSION} START | source={BASE_URL} | GET ONLY | PRESENTATION ONLY | "
        "WATCH WARNING HIDDEN | NUMERIC FLIP RISK HIDDEN | NO ORDERS",
        flush=True,
    )
    refresh_once()
    threading.Thread(target=loop, name="btc15-scalp-ui-shadow-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
