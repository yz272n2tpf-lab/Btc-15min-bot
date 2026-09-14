#!/usr/bin/env python3
"""
BTC15 combined dashboard shadow V1.

OFF-PRODUCTION DISPLAY VALIDATION ONLY | SIGNAL ONLY | NO ORDERS

Serves the existing V13 dashboard layout after applying the proven generalized
SCALP in-layout patch. The protected main dashboard JSON remains the source for
EARLY, FINAL, Kalshi quotes and the canonical clock. Generalized SCALP is read
by the injected UI from the separate read-only combined-state bridge.

This service never places orders, never accepts order actions, and does not
change protected trading thresholds.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import requests

from BTC15_DASHBOARD_COMBINED_SCALP_UI_V1 import build_dashboard

PORT = int(os.environ.get("PORT", "8080"))
MAIN_STATE_URL = "https://btc-15min-bot-production.up.railway.app/dashboard_state.json"
VERSION = "BTC15_COMBINED_DASHBOARD_SHADOW_V1"


def _read_dashboard() -> tuple[Path, bytes]:
    html = build_dashboard()
    rendered = html.read_bytes()
    required = (
        b'BTC15_COMBINED_SCALP_UI_V1',
        b'btc15-combined-scalp-script',
        b'renderCombinedScalpInline',
        b'COUNTERTREND_SCALP',
        b'validated 4',
    )
    missing = [x.decode("utf-8", "ignore") for x in required if x not in rendered]
    if missing:
        raise RuntimeError(f"shadow dashboard missing required markers: {missing}")
    if b'v81-inline-scalp-script' in rendered:
        raise RuntimeError("legacy V8.1 inline scalp script still present")
    return html, rendered


DASHBOARD_PATH, DASHBOARD_BYTES = _read_dashboard()


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15CombinedDashboardShadow/1.0"

    def log_message(self, fmt, *args):
        print("SHADOW_HTTP | " + (fmt % args), flush=True)

    def _headers(self, code: int, ctype: str, length: int | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Access-Control-Allow-Origin", "*")
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.end_headers()

    def _json(self, code: int, obj):
        raw = json.dumps(obj, separators=(",", ":")).encode()
        self._headers(code, "application/json", len(raw))
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in {"/", "/index.html", "/BTC_Kalshi_App_Live_v13.html"}:
            self._headers(200, "text/html; charset=utf-8", len(DASHBOARD_BYTES))
            self.wfile.write(DASHBOARD_BYTES)
            return

        if path == "/dashboard_state.json":
            try:
                r = requests.get(MAIN_STATE_URL, timeout=3.0, headers={"Cache-Control": "no-cache"})
                r.raise_for_status()
                raw = r.content
                # Validate JSON before relaying so malformed upstream data fails closed.
                json.loads(raw.decode("utf-8"))
                self._headers(200, "application/json", len(raw))
                self.wfile.write(raw)
            except Exception as exc:
                self._json(503, {
                    "ok": False,
                    "shadow_only": True,
                    "orders": False,
                    "error": f"main_state_unavailable:{type(exc).__name__}",
                })
            return

        if path == "/health":
            self._json(200, {
                "ok": True,
                "version": VERSION,
                "shadow_only": True,
                "orders": False,
                "dashboard_path": DASHBOARD_PATH.name,
                "main_state_proxy": True,
                "generalized_scalp_ui": True,
            })
            return

        self._json(404, {"ok": False, "orders": False, "error": "not_found"})

    def _reject_write(self):
        self._json(405, {"ok": False, "orders": False, "error": "read_only_shadow"})

    do_POST = _reject_write
    do_PUT = _reject_write
    do_PATCH = _reject_write
    do_DELETE = _reject_write


def main() -> int:
    print(
        f"{VERSION} START | port {PORT} | existing V13 layout | generalized SCALP card | "
        "OFF-PRODUCTION | SIGNAL ONLY | NO ORDERS",
        flush=True,
    )
    print(f"SHADOW DASHBOARD BUILT | {DASHBOARD_PATH} | bytes={len(DASHBOARD_BYTES)}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
