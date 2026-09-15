#!/usr/bin/env python3
"""
BTC15 combined state bridge V6 display enrichment.

OFF-PRODUCTION DISPLAY ENRICHMENT ONLY | SIGNAL ONLY | NO ORDERS

Reads the frozen V5 combined-state and V5 scalp-state endpoints. It does not
rebuild or alter qualification, lifecycle, +5c arm, 4c giveback, timer, EARLY,
FINAL, or order behavior. V6 only adds display metadata so a completed scalp
remains understandable after V5 advances to scanning the next opportunity, and
so a valid move can be visually separated from an attractive current entry.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

import requests

VERSION = "BTC15_COMBINED_STATE_BRIDGE_V6"
PORT = int(os.environ.get("PORT", "8080"))
UPSTREAM_COMBINED_URL = "https://scalp-move-shadow-v1-production.up.railway.app/combined-state"
UPSTREAM_SCALP_URL = "https://scalp-move-shadow-v1-production.up.railway.app/state"
TIMEOUT_SEC = 3.0
# Dedicated display bridge; frozen V5 remains the strategy/lifecycle authority.


def _float(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def entry_guidance(price: Any) -> dict[str, Any]:
    p = _float(price)
    if p is None:
        return {
            "zone": "WAIT",
            "label": "WAIT FOR ENTRY",
            "detail": "No current qualified scalp entry",
            "price_at_or_below_50c": False,
        }
    if p < 0.25:
        return {
            "zone": "LOW_PRICE",
            "label": "LOW PRICE · CHECK CONTEXT",
            "detail": "Below the preferred 25–35¢ zone",
            "price_at_or_below_50c": True,
        }
    if p <= 0.35 + 1e-12:
        return {
            "zone": "IDEAL",
            "label": "IDEAL ENTRY ZONE",
            "detail": "25–35¢ preferred entry range",
            "price_at_or_below_50c": True,
        }
    if p <= 0.50 + 1e-12:
        return {
            "zone": "GOOD",
            "label": "GOOD ENTRY ZONE",
            "detail": "36–50¢ acceptable entry range",
            "price_at_or_below_50c": True,
        }
    return {
        "zone": "TOO_EXPENSIVE",
        "label": "MOVE VALID · ENTRY TOO EXPENSIVE · DON'T CHASE",
        "detail": "Qualified move detected, but current entry is above 50¢",
        "price_at_or_below_50c": False,
    }


def _validate_upstreams(combined: Mapping[str, Any], scalp: Mapping[str, Any]) -> None:
    if combined.get("version") != "BTC15_COMBINED_STATE_BRIDGE_V5":
        raise ValueError("expected frozen V5 combined-state")
    if combined.get("orders") is not False or combined.get("manual_execution_only") is not True:
        raise ValueError("combined-state safety envelope invalid")
    if combined.get("order_action") is not None:
        raise ValueError("combined-state order_action must remain null")
    if combined.get("scalp_lifecycle_metadata_only") is not True:
        raise ValueError("V5 lifecycle metadata flag missing")
    if combined.get("scalp_ended_unarmed_is_actionable_exit") is not False:
        raise ValueError("ENDED_UNARMED must remain non-actionable")
    if combined.get("scalp_armed_no_exit_reset_allowed") is not False:
        raise ValueError("armed/no-exit reset must remain disabled")

    if scalp.get("version") != "GENERALIZED_SCALP_INTEGRATION_V5":
        raise ValueError("expected frozen V5 scalp-state")
    if scalp.get("orders") is not False or scalp.get("manual_execution_only") is not True:
        raise ValueError("scalp-state safety envelope invalid")
    if scalp.get("order_action") is not None:
        raise ValueError("scalp-state order_action must remain null")
    if scalp.get("armed_no_exit_reset_allowed") is not False:
        raise ValueError("scalp-state armed/no-exit reset must remain disabled")


def enrich_display_state(combined: Mapping[str, Any], scalp: Mapping[str, Any]) -> dict[str, Any]:
    _validate_upstreams(combined, scalp)
    out = dict(combined)
    c_contract = str(combined.get("contract") or "")
    s_contract = str(scalp.get("contract") or "")
    same_contract = bool(c_contract and c_contract == s_contract)
    if not same_contract:
        raise ValueError("combined/scalp contracts do not match")

    current_state = str((combined.get("scalp") or {}).get("state") or "PASS").upper()
    current_entry = _float(scalp.get("entry_price"))
    current_opp = int(scalp.get("opportunity_index") or combined.get("scalp_opportunity_index") or 1)
    terminals = [dict(x) for x in (scalp.get("terminal_history") or []) if isinstance(x, Mapping)]
    last = terminals[-1] if terminals else {}
    last_state = str(last.get("terminal_state") or "").upper()
    last_index = int(last.get("opportunity_index") or 0) if last else 0

    out["version"] = VERSION
    out["scalp_display_metadata_only"] = True
    out["scalp_display_source_bridge"] = "BTC15_COMBINED_STATE_BRIDGE_V5"
    out["scalp_display_source_scalp"] = "GENERALIZED_SCALP_INTEGRATION_V5"
    out["scalp_display_contract_match"] = True
    out["scalp_current_entry_price"] = current_entry
    out["scalp_current_entry_guidance"] = entry_guidance(current_entry)
    out["scalp_entry_guidance_is_display_only"] = True
    out["scalp_entry_price_filter_applied"] = False
    out["scalp_next_opportunity_index"] = current_opp

    out["scalp_last_completed_available"] = bool(last)
    out["scalp_last_completed_state"] = last_state or None
    out["scalp_last_completed_opportunity_index"] = last_index or None
    out["scalp_last_completed_side"] = str(last.get("side") or "").upper() or None
    out["scalp_last_completed_entry_price"] = _float(last.get("entry_price"))
    out["scalp_last_completed_exit_gain"] = _float(last.get("exit_gain"))
    out["scalp_last_completed_peak_gain"] = _float(last.get("peak_exec_gain"))
    out["scalp_last_completed_time_utc"] = last.get("terminal_time_utc")
    out["scalp_last_completed_actionable_exit"] = bool(last.get("actionable_exit") is True)
    out["scalp_last_completed_is_display_memory_only"] = True
    out["scalp_completed_display_actionable"] = False
    out["scalp_hold_completed_while_scanning"] = bool(
        last and current_state == "PASS" and scalp.get("scanning_for_next") is True
    )
    out["scalp_completed_entry_guidance"] = entry_guidance(last.get("entry_price")) if last else entry_guidance(None)

    # Reassert the safety envelope explicitly after enrichment.
    out["orders"] = False
    out["manual_execution_only"] = True
    out["order_action"] = None
    out["numeric_flip_risk_validated"] = False
    return out


def _fetch_json(url: str) -> dict[str, Any]:
    r = requests.get(url, timeout=TIMEOUT_SEC, headers={"Cache-Control": "no-cache"})
    r.raise_for_status()
    d = r.json()
    if not isinstance(d, dict):
        raise ValueError("upstream JSON is not an object")
    return d


def build_state() -> dict[str, Any]:
    combined = _fetch_json(UPSTREAM_COMBINED_URL)
    scalp = _fetch_json(UPSTREAM_SCALP_URL)
    return enrich_display_state(combined, scalp)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15DisplayBridgeV6/1.0"

    def log_message(self, fmt, *args):
        print("DISPLAY_V6_HTTP | " + (fmt % args), flush=True)

    def _json(self, code: int, obj: Any):
        raw = json.dumps(obj, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/combined-state":
            try:
                return self._json(200, build_state())
            except Exception as exc:
                return self._json(503, {
                    "ok": False,
                    "version": VERSION,
                    "orders": False,
                    "manual_execution_only": True,
                    "order_action": None,
                    "error": f"display_bridge_unavailable:{type(exc).__name__}",
                })
        if path == "/health":
            try:
                d = build_state()
                return self._json(200, {
                    "ok": True,
                    "version": VERSION,
                    "orders": False,
                    "manual_execution_only": True,
                    "contract": d.get("contract"),
                    "display_metadata_only": d.get("scalp_display_metadata_only") is True,
                })
            except Exception as exc:
                return self._json(503, {
                    "ok": False,
                    "version": VERSION,
                    "orders": False,
                    "error": f"health_upstream_unavailable:{type(exc).__name__}",
                })
        return self._json(404, {"ok": False, "orders": False, "error": "not_found"})

    def _reject(self):
        return self._json(405, {"ok": False, "orders": False, "error": "read_only_display_bridge"})

    do_POST = _reject
    do_PUT = _reject
    do_PATCH = _reject
    do_DELETE = _reject


def main() -> int:
    print(
        f"{VERSION} START | DISPLAY METADATA ONLY | FROZEN V5 UPSTREAM | "
        "SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS",
        flush=True,
    )
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
