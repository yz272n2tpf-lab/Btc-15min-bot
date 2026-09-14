#!/usr/bin/env python3
"""
BTC15 generalized scalp integration state bridge V3.

READ ONLY | SIGNAL ONLY | NO ORDERS

V3 keeps the exact frozen generalized collector and V2 state derivation, then
adds explicit management presentation for the dashboard:
- +5c arm at/near peak: PROTECTION ARMED · WINNER RUNNING
- first observed pullback after arm: PROTECT PROFITS · PULLBACK DETECTED
- frozen 4c giveback: EXIT / PROTECT PROFITS NOW

The /state endpoint is intentionally public and CORS-readable because it contains
signal display data only: no credentials, account data, private-key material, or
order actions. Existing research/export endpoints retain the original optional
authorization gate.
"""
from __future__ import annotations

import json
import runpy
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse

import scalp_path_export_bridge_v1 as base
import scalp_integration_state_bridge_v2 as v2
from btc15_scalp_management_presentation_v1 import management_presentation

VERSION = "GENERALIZED_SCALP_INTEGRATION_V3"


def build_state(rows):
    out = dict(v2.build_state(rows))
    present = management_presentation(
        state=out.get("state") or "PASS",
        peak_exec_gain=out.get("peak_exec_gain"),
        exec_gain=out.get("exec_gain"),
        arm_gain=float(out.get("frozen_rule", {}).get("arm_gain", .05)),
        exit_giveback=float(out.get("frozen_rule", {}).get("giveback", .04)),
    )
    out["version"] = VERSION
    out["state"] = present.state
    out["management_message"] = present.message
    out["armed"] = present.protection_armed
    out["pullback_detected"] = present.pullback_detected
    out["exit_triggered"] = present.exit_now
    out["giveback_from_peak"] = present.giveback_from_peak
    out["manual_execution_only"] = True
    out["order_action"] = None
    out["numeric_flip_risk_validated"] = False
    return out


class Handler(base.Handler):
    def _state_json(self, code, obj):
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
        if path == "/state":
            rows, _ = base.read_rows()
            payload = build_state(rows)
            payload["ok"] = True
            payload["orders"] = False
            return self._state_json(200, payload)

        # All inherited research/export routes keep the original authorization
        # behavior from PATH Export Bridge V1.
        return super().do_GET()


def start_server():
    srv = ThreadingHTTPServer(("0.0.0.0", base.PORT), Handler)
    t = threading.Thread(target=srv.serve_forever, name="scalp-integration-state-v3-http", daemon=True)
    t.start()
    print(
        f"SCALP INTEGRATION STATE BRIDGE V3 START | port {base.PORT} | "
        "PUBLIC SIGNAL STATE | READ ONLY | NO ORDERS",
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
