#!/usr/bin/env python3
"""
BTC15 exact-ticker rollover fallback shadow server V1.

READ ONLY | SHADOW ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

This server is intentionally dormant until the frozen Probe V2 gate authorizes
a separate shadow fallback test. It never modifies production. It compares the
current production contract with the exact deterministic KXBTC15M contract near
a quarter-hour boundary and exposes read-only evidence only.
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

import BTC15_KALSHI_EXACT_ROLLOVER_FALLBACK_SHADOW_V1 as shadow

VERSION = "BTC15_KALSHI_EXACT_ROLLOVER_FALLBACK_SHADOW_SERVER_V1"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(1.0, float(os.environ.get("ROLLOVER_SHADOW_POLL_SEC", "1")))
TIMEOUT_SEC = 3.0
PRODUCTION_STATE_URL = os.environ.get(
    "BTC15_PRODUCTION_STATE_URL",
    "https://btc-15min-bot-production.up.railway.app/dashboard_state.json",
)

LOCK = threading.RLock()
STATE: dict[str, Any] = {
    "last_poll_utc": None,
    "last_error": None,
    "production_contract": None,
    "shadow": None,
    "available_events": [],
}


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fetch_production_contract() -> str | None:
    r = requests.get(
        PRODUCTION_STATE_URL,
        timeout=TIMEOUT_SEC,
        headers={"Cache-Control": "no-cache", "User-Agent": VERSION},
    )
    r.raise_for_status()
    d = r.json()
    if not isinstance(d, dict):
        raise ValueError("production state is not an object")
    return str(d.get("contract") or "").strip() or None


def poll_once(now: datetime | None = None) -> dict[str, Any] | None:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    production_contract = _fetch_production_contract()
    out = shadow.evaluate_live_once(now=now, production_contract=production_contract)
    with LOCK:
        STATE["last_poll_utc"] = now.isoformat().replace("+00:00", "Z")
        STATE["last_error"] = None
        STATE["production_contract"] = production_contract
        STATE["shadow"] = out
        if out and out.get("shadow_fallback_available") is True:
            key = (out.get("boundary_utc"), out.get("expected_ticker"))
            seen = {(x.get("boundary_utc"), x.get("expected_ticker")) for x in STATE["available_events"]}
            if key not in seen:
                STATE["available_events"].append(dict(out))
                print(
                    "ROLLOVER SHADOW AVAILABLE | "
                    f"boundary={out.get('boundary_utc')} | expected={out.get('expected_ticker')} | "
                    f"production={out.get('production_contract')} | book="
                    f"{out.get('exact_yes_bid')}/{out.get('exact_yes_ask')} YES "
                    f"{out.get('exact_no_bid')}/{out.get('exact_no_ask')} NO | "
                    "SHADOW ONLY | NO SWITCH | NO ORDERS",
                    flush=True,
                )
    return out


def loop() -> None:
    print(
        f"{VERSION} START | exact ticker vs production rollover handoff | "
        "READ ONLY | SHADOW ONLY | NO PRODUCTION SWITCH | NO ORDERS",
        flush=True,
    )
    while True:
        try:
            poll_once()
        except Exception as exc:
            msg = f"{type(exc).__name__}:{exc}"
            with LOCK:
                STATE["last_error"] = msg
                STATE["last_poll_utc"] = _iso()
            print(f"ROLLOVER SHADOW WARNING | {msg} | FAIL CLOSED | NO ORDERS", flush=True)
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15ExactRolloverFallbackShadowV1/1.0"

    def log_message(self, fmt, *args):
        print("ROLLOVER_SHADOW_HTTP | " + (fmt % args), flush=True)

    def _json(self, code: int, obj: Any):
        raw = json.dumps(obj, separators=(",", ":"), default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        with LOCK:
            snap = dict(STATE)
            snap["available_events"] = [dict(x) for x in STATE["available_events"]]
        if path == "/state":
            return self._json(200, {
                "ok": snap.get("last_poll_utc") is not None,
                "version": VERSION,
                "state": snap,
                "production_behavior_changed": False,
                "manual_execution_only": True,
                "orders": False,
            })
        if path == "/health":
            ok = snap.get("last_poll_utc") is not None and snap.get("last_error") is None
            return self._json(200 if ok else 503, {
                "ok": ok,
                "version": VERSION,
                "last_poll_utc": snap.get("last_poll_utc"),
                "last_error": snap.get("last_error"),
                "production_behavior_changed": False,
                "manual_execution_only": True,
                "orders": False,
            })
        return self._json(404, {"ok": False, "orders": False, "error": "not_found"})

    def _reject(self):
        return self._json(405, {"ok": False, "orders": False, "error": "read_only_shadow"})

    do_POST = _reject
    do_PUT = _reject
    do_PATCH = _reject
    do_DELETE = _reject


def main() -> int:
    threading.Thread(target=loop, name="btc15-exact-rollover-shadow", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
