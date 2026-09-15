#!/usr/bin/env python3
"""
BTC15 combined state bridge V5 — serial SCALP lifecycle shadow integration.

READ ONLY | SIGNAL ONLY | NO ORDERS

V5 preserves the V4 incremental cache, protected-main authority, freshness and
contract fail-closed composition, then swaps only the SCALP read adapter from
integration V4 to the tested serial integration V5.

No protected EARLY/FINAL logic changes. No Kalshi execution. No threshold
changes. ENDED_UNARMED is exposed only as lifecycle metadata and is never an
order or sell action. Armed/no-exit winners remain protected/blocking.
"""
from __future__ import annotations

from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import json
import runpy
import threading
import time
from urllib.parse import urlparse

import requests

import scalp_path_export_bridge_v1 as base
import scalp_integration_state_bridge_v5 as scalp_v5
from btc15_cross_service_payload_v4 import compose_cross_service_payload
from scalp_live_event_cache_v1 import LiveEventCache, POLL_SECONDS

VERSION = "BTC15_COMBINED_STATE_BRIDGE_V5"
MAIN_STATE_URL = "https://btc-15min-bot-production.up.railway.app/dashboard_state.json"
MAIN_TIMEOUT_SEC = 2.0
OBSERVER_SEC = 1.0
CACHE = LiveEventCache(base.EVENT_CSV, poll_seconds=POLL_SECONDS)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fetch_main_state():
    r = requests.get(MAIN_STATE_URL, timeout=MAIN_TIMEOUT_SEC, headers={"Cache-Control": "no-cache"})
    r.raise_for_status()
    d = r.json()
    if not isinstance(d, dict) or not d.get("contract"):
        raise ValueError("main dashboard state missing contract")
    return d


def build_scalp_state() -> dict:
    rows = CACHE.state_rows()
    out = scalp_v5.build_state(rows)
    out["cache_mode"] = "INCREMENTAL_APPEND_ONLY_V1"
    out["cache_state_rows"] = len(rows)
    return out


def _attach_serial_metadata(out: dict, scalp: dict) -> dict:
    out["scalp_serial_bridge_version"] = scalp.get("serial_bridge_version")
    out["scalp_opportunity_index"] = scalp.get("opportunity_index")
    out["scalp_serial_opportunities_completed"] = scalp.get("serial_opportunities_completed")
    out["scalp_scanning_for_next"] = scalp.get("scanning_for_next") is True
    out["scalp_last_terminal_state"] = scalp.get("last_terminal_state")
    out["scalp_last_terminal_actionable_exit"] = scalp.get("last_terminal_actionable_exit")
    out["scalp_last_terminal_candidate_id"] = scalp.get("last_terminal_candidate_id")
    out["scalp_ended_unarmed_count"] = int(scalp.get("ended_unarmed_count") or 0)
    out["scalp_ended_unarmed_is_actionable_exit"] = False
    out["scalp_armed_no_exit_reset_allowed"] = False
    return out


def build_combined_state(main_state: dict | None = None) -> dict:
    main = main_state if main_state is not None else _fetch_main_state()
    scalp = build_scalp_state()
    out = compose_cross_service_payload(main, scalp).to_dict()
    out["version"] = VERSION
    out["generated_at_utc"] = _iso_now()
    out["orders"] = False
    out["manual_execution_only"] = True
    out["order_action"] = None
    out["numeric_flip_risk_validated"] = False
    out["scalp_bridge_version"] = scalp.get("version")
    out["scalp_cache_mode"] = scalp.get("cache_mode")
    out["scalp_cache_state_rows"] = scalp.get("cache_state_rows")
    _attach_serial_metadata(out, scalp)
    return out


class Handler(base.Handler):
    def _public_json(self, code: int, obj):
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
            try:
                out = build_scalp_state()
                out["ok"] = True
                out["orders"] = False
                return self._public_json(200, out)
            except Exception as exc:
                return self._public_json(503, {
                    "ok": False,
                    "orders": False,
                    "manual_execution_only": True,
                    "error": f"scalp_state_unavailable:{type(exc).__name__}",
                })

        if path == "/combined-state":
            started = time.perf_counter()
            try:
                out = build_combined_state()
                out["bridge_response_build_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
                return self._public_json(200, out)
            except Exception as exc:
                return self._public_json(503, {
                    "ok": False,
                    "version": VERSION,
                    "orders": False,
                    "manual_execution_only": True,
                    "order_action": None,
                    "numeric_flip_risk_validated": False,
                    "error": f"combined_state_unavailable:{type(exc).__name__}",
                })

        if path == "/cache-health":
            d = CACHE.diagnostics()
            d.update({"ok": True, "version": VERSION, "orders": False})
            return self._public_json(200, d)

        return super().do_GET()


def _fmt(v, digits=1, suffix=""):
    try:
        return f"{float(v):.{digits}f}{suffix}"
    except Exception:
        return "—"


def observer_loop():
    last_sig = None
    while True:
        try:
            started = time.perf_counter()
            main = _fetch_main_state()
            out = build_combined_state(main)
            latency_ms = (time.perf_counter() - started) * 1000.0
            sig = (
                out.get("contract"),
                (out.get("early") or {}).get("state"),
                (out.get("final") or {}).get("state"),
                (out.get("scalp") or {}).get("state"),
                out.get("scalp_opportunity_index"),
                out.get("scalp_last_terminal_state"),
                out.get("scalp_scanning_for_next"),
                out.get("scalp_management_message"),
                tuple(out.get("context_labels") or ()),
                out.get("scalp_source_fresh"),
                out.get("scalp_contract_aligned"),
            )
            if sig != last_sig:
                print(
                    "COMBINED_BRIDGE_V5 | "
                    f"contract={out.get('contract')} | left={_fmt(out.get('canonical_seconds_left'),1,'s')} | "
                    f"EARLY={(out.get('early') or {}).get('state')} | "
                    f"FINAL={(out.get('final') or {}).get('state')} | "
                    f"SCALP={(out.get('scalp') or {}).get('state')} | "
                    f"opp={out.get('scalp_opportunity_index')} | completed={out.get('scalp_serial_opportunities_completed')} | "
                    f"last_terminal={out.get('scalp_last_terminal_state') or '-'} | "
                    f"scan_next={out.get('scalp_scanning_for_next')} | "
                    f"fresh={out.get('scalp_source_fresh')} | aligned={out.get('scalp_contract_aligned')} | "
                    f"cache_rows={out.get('scalp_cache_state_rows')} | build={latency_ms:.1f}ms | "
                    f"management={out.get('scalp_management_message')} | NO ORDERS",
                    flush=True,
                )
                last_sig = sig
        except Exception as exc:
            print(
                f"COMBINED_BRIDGE_V5 WARNING | {type(exc).__name__}: {exc} | "
                "FAIL CLOSED | NO ORDERS",
                flush=True,
            )
        time.sleep(OBSERVER_SEC)


def start_server():
    srv = ThreadingHTTPServer(("0.0.0.0", base.PORT), Handler)
    t = threading.Thread(target=srv.serve_forever, name="btc15-combined-state-v5-http", daemon=True)
    t.start()
    return srv, t


def main():
    if not base.COLLECTOR.exists():
        raise SystemExit(f"collector missing: {base.COLLECTOR}")

    started = time.perf_counter()
    rows = CACHE.initialize()
    init_ms = (time.perf_counter() - started) * 1000.0
    CACHE.start()
    start_server()
    threading.Thread(target=observer_loop, name="btc15-combined-state-v5-observer", daemon=True).start()
    diag = CACHE.diagnostics()
    print(
        f"BTC15 COMBINED STATE BRIDGE V5 START | port {base.PORT} | "
        f"SERIAL LIFECYCLE + INCREMENTAL CACHE | initial_rows={rows} | "
        f"state_rows={diag['state_rows']} | init={init_ms:.1f}ms | "
        "MAIN CONTRACT/TIMER AUTHORITY | FRESHNESS + CONTRACT FAIL-CLOSED | "
        "READ ONLY | SIGNAL ONLY | NO ORDERS",
        flush=True,
    )

    runpy.run_path(str(base.COLLECTOR), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
