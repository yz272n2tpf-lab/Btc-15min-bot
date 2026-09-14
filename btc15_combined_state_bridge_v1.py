#!/usr/bin/env python3
"""
BTC15 combined dashboard state bridge V1.

READ ONLY | SIGNAL ONLY | NO ORDERS

Exposes two public signal-only surfaces from the generalized scalp service:
- /state: frozen generalized SCALP V4 state with freshness metadata
- /combined-state: protected main EARLY/FINAL/canonical clock composed with the
  fresh generalized SCALP state through the frozen cross-service composer.

No protected thresholds are recalculated or changed. The exact existing scalp
collector continues to run unchanged in-process.
"""
from __future__ import annotations

from datetime import datetime
import json
import runpy
import threading
from http.server import ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

import requests

import scalp_path_export_bridge_v1 as base
import scalp_integration_state_bridge_v4 as scalp_v4
from btc15_cross_service_payload_v3 import compose_cross_service_payload

MAIN_STATE_URL = "https://btc-15min-bot-production.up.railway.app/dashboard_state.json"
VERSION = "BTC15_COMBINED_STATE_BRIDGE_V1"


def unwrap_main_state(obj: Any) -> Mapping[str, Any]:
    if not isinstance(obj, Mapping):
        raise ValueError("main dashboard state is not a JSON object")
    if obj.get("contract"):
        return obj
    for key in ("state", "data"):
        nested = obj.get(key)
        if isinstance(nested, Mapping) and nested.get("contract"):
            return nested
    raise ValueError("main dashboard state has no contract")


def fetch_main_state() -> Mapping[str, Any]:
    r = requests.get(
        MAIN_STATE_URL,
        timeout=3.0,
        headers={"Cache-Control": "no-cache"},
    )
    r.raise_for_status()
    return unwrap_main_state(r.json())


def build_combined_state(
    main_state: Mapping[str, Any],
    rows,
    *,
    now: datetime | None = None,
) -> dict:
    scalp = scalp_v4.build_state(rows, now=now)
    combined = compose_cross_service_payload(main_state, scalp).to_dict()
    combined["version"] = VERSION
    combined["scalp_bridge_version"] = scalp.get("version")
    combined["manual_execution_only"] = True
    combined["order_action"] = None
    combined["numeric_flip_risk_validated"] = False
    combined["orders"] = False
    return combined


class Handler(scalp_v4.Handler):
    def _combined_json(self, code: int, obj: Mapping[str, Any]):
        raw = json.dumps(obj, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/combined-state":
            try:
                main_state = fetch_main_state()
                rows, _ = base.read_rows()
                payload = build_combined_state(main_state, rows)
                payload["ok"] = True
                return self._combined_json(200, payload)
            except Exception as exc:
                return self._combined_json(503, {
                    "ok": False,
                    "version": VERSION,
                    "error": f"{type(exc).__name__}: {exc}",
                    "fail_closed": True,
                    "manual_execution_only": True,
                    "order_action": None,
                    "numeric_flip_risk_validated": False,
                    "orders": False,
                })
        return super().do_GET()


def start_server():
    srv = ThreadingHTTPServer(("0.0.0.0", base.PORT), Handler)
    t = threading.Thread(
        target=srv.serve_forever,
        name="btc15-combined-state-v1-http",
        daemon=True,
    )
    t.start()
    print(
        f"BTC15 COMBINED STATE BRIDGE V1 START | port {base.PORT} | "
        "FRESHNESS + CONTRACT FAIL-CLOSED | READ ONLY | NO ORDERS",
        flush=True,
    )
    return srv, t


def main():
    if not base.COLLECTOR.exists():
        raise SystemExit(f"collector missing: {base.COLLECTOR}")
    start_server()
    runpy.run_path(str(base.COLLECTOR), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
