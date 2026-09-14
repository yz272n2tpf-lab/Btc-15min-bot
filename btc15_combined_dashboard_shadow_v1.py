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
from btc15_main_protected_state_adapter_v1 import protected_main_summary

PORT = int(os.environ.get("PORT", "8080"))
MAIN_STATE_URL = "https://btc-15min-bot-production.up.railway.app/dashboard_state.json"
COMBINED_STATE_URL = "https://scalp-move-shadow-v1-production.up.railway.app/combined-state"
VERSION = "BTC15_COMBINED_DASHBOARD_SHADOW_V1"
DASHBOARD_PATH: Path | None = None
DASHBOARD_BYTES = b""


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


def load_dashboard() -> tuple[Path, bytes]:
    global DASHBOARD_PATH, DASHBOARD_BYTES
    DASHBOARD_PATH, DASHBOARD_BYTES = _read_dashboard()
    return DASHBOARD_PATH, DASHBOARD_BYTES


def _float(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _same_num(a, b, tol=1e-9):
    aa, bb = _float(a), _float(b)
    if aa is None or bb is None:
        return aa is None and bb is None
    return abs(aa - bb) <= tol


def build_shadow_status(main_state, combined_state) -> dict:
    """Pure live acceptance summary; no signal thresholds are changed here."""
    protected = protected_main_summary(main_state)
    ce = combined_state.get("early") or {}
    cf = combined_state.get("final") or {}
    cs = combined_state.get("scalp") or {}

    early = protected["early"]
    final = protected["final"]
    early_preserved = bool(
        ce.get("state") == early.state
        and ce.get("side") == early.side
        and _same_num(ce.get("ask"), early.ask)
        and _same_num(ce.get("fair"), early.fair)
        and _same_num(ce.get("edge"), early.edge)
    )
    final_preserved = bool(
        cf.get("state") == final.state
        and cf.get("side") == final.side
        and _same_num(cf.get("fair"), final.fair)
    )

    main_left = _float(protected.get("seconds_left"))
    combined_left = _float(combined_state.get("canonical_seconds_left"))
    cross_fetch_timer_delta = (
        abs(main_left - combined_left)
        if main_left is not None and combined_left is not None
        else None
    )

    safety_envelope = bool(
        combined_state.get("version") == "BTC15_COMBINED_STATE_BRIDGE_V3"
        and combined_state.get("manual_execution_only") is True
        and combined_state.get("orders") is False
        and combined_state.get("order_action") is None
        and combined_state.get("numeric_flip_risk_validated") is False
    )
    scalp_state = str(cs.get("state") or "PASS").upper()
    scalp_actionable = scalp_state in {"ACTIVE", "PROTECT", "EXIT"}
    actionable_scalp_guarded = bool(
        not scalp_actionable
        or (
            combined_state.get("scalp_contract_aligned") is True
            and combined_state.get("scalp_source_fresh") is True
            and combined_state.get("scalp_integration_ready") is True
        )
    )
    contract_match = bool(
        protected.get("contract")
        and protected.get("contract") == combined_state.get("contract")
    )

    return {
        "ok": True,
        "version": VERSION,
        "shadow_only": True,
        "orders": False,
        "contract": protected.get("contract"),
        "combined_contract": combined_state.get("contract"),
        "contract_match": contract_match,
        "early_preserved": early_preserved,
        "final_preserved": final_preserved,
        "canonical_clock_present": main_left is not None and combined_left is not None,
        "cross_fetch_timer_delta_sec": cross_fetch_timer_delta,
        "safety_envelope": safety_envelope,
        "scalp_state": scalp_state,
        "scalp_actionable": scalp_actionable,
        "actionable_scalp_guarded": actionable_scalp_guarded,
        "scalp_source_fresh": combined_state.get("scalp_source_fresh") is True,
        "scalp_contract_aligned": combined_state.get("scalp_contract_aligned") is True,
        "scalp_block_reason": combined_state.get("scalp_block_reason"),
        "context_labels": combined_state.get("context_labels") or [],
        "management": combined_state.get("scalp_management_message"),
        "all_safety_checks_pass": bool(contract_match and safety_envelope and actionable_scalp_guarded),
    }


def _fetch_json(url: str):
    r = requests.get(url, timeout=3.0, headers={"Cache-Control": "no-cache"})
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise ValueError("upstream JSON is not an object")
    return data


def live_preflight() -> dict | None:
    """One read-only live check at startup. Failure never invents actionability."""
    try:
        combined = _fetch_json(COMBINED_STATE_URL)
        main = _fetch_json(MAIN_STATE_URL)
        status = build_shadow_status(main, combined)
        delta = status.get("cross_fetch_timer_delta_sec")
        delta_text = "—" if delta is None else f"{float(delta):.1f}s"
        labels = ",".join(status.get("context_labels") or []) or "-"
        print(
            "SHADOW LIVE PREFLIGHT | "
            f"contract={status.get('contract')} | contract_match={status.get('contract_match')} | "
            f"EARLY_preserved={status.get('early_preserved')} | FINAL_preserved={status.get('final_preserved')} | "
            f"canonical_clock={status.get('canonical_clock_present')} | cross_fetch_delta={delta_text} | "
            f"safety={status.get('safety_envelope')} | SCALP={status.get('scalp_state')} | "
            f"guarded={status.get('actionable_scalp_guarded')} | fresh={status.get('scalp_source_fresh')} | "
            f"aligned={status.get('scalp_contract_aligned')} | block={status.get('scalp_block_reason') or '-'} | "
            f"labels={labels} | management={status.get('management')} | "
            f"safety_pass={status.get('all_safety_checks_pass')} | NO ORDERS",
            flush=True,
        )
        return status
    except Exception as exc:
        print(
            f"SHADOW LIVE PREFLIGHT WARNING | {type(exc).__name__}: {exc} | "
            "FAIL CLOSED | SHADOW ONLY | NO ORDERS",
            flush=True,
        )
        return None


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
            if not DASHBOARD_BYTES:
                return self._json(503, {"ok": False, "orders": False, "error": "dashboard_not_ready"})
            self._headers(200, "text/html; charset=utf-8", len(DASHBOARD_BYTES))
            self.wfile.write(DASHBOARD_BYTES)
            return

        if path == "/dashboard_state.json":
            try:
                r = requests.get(MAIN_STATE_URL, timeout=3.0, headers={"Cache-Control": "no-cache"})
                r.raise_for_status()
                raw = r.content
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

        if path == "/shadow-status":
            try:
                combined = _fetch_json(COMBINED_STATE_URL)
                main = _fetch_json(MAIN_STATE_URL)
                self._json(200, build_shadow_status(main, combined))
            except Exception as exc:
                self._json(503, {
                    "ok": False,
                    "version": VERSION,
                    "shadow_only": True,
                    "orders": False,
                    "all_safety_checks_pass": False,
                    "error": f"shadow_status_unavailable:{type(exc).__name__}",
                })
            return

        if path == "/health":
            self._json(200, {
                "ok": bool(DASHBOARD_BYTES),
                "version": VERSION,
                "shadow_only": True,
                "orders": False,
                "dashboard_path": DASHBOARD_PATH.name if DASHBOARD_PATH else None,
                "main_state_proxy": True,
                "combined_state_probe": True,
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
    path, rendered = load_dashboard()
    print(
        f"{VERSION} START | port {PORT} | existing V13 layout | generalized SCALP card | "
        "OFF-PRODUCTION | SIGNAL ONLY | NO ORDERS",
        flush=True,
    )
    print(f"SHADOW DASHBOARD BUILT | {path} | bytes={len(rendered)}", flush=True)
    live_preflight()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
