#!/usr/bin/env python3
"""
BTC15 generalized scalp integration state bridge V5.

SHADOW / READ ONLY | SIGNAL ONLY | NO ORDERS

V5 wraps the already-tested serial scalp state bridge with the same freshness,
main-contract authority, and fail-closed integration envelope used by V4.

V5 does NOT change qualification, entry-price handling, +5c protection arm, or
4c giveback EXIT. It only exposes the serial lifecycle already validated in
BTC15_SCALP_SERIAL_STATE_BRIDGE_SHADOW_V1:
- protected EXIT may hand off to the next later qualified scalp;
- collector RESULT before +5c may become ENDED_UNARMED (informational only) and
  hand off to the next later qualified scalp;
- armed/no-exit winners remain current/protected and block later overlaps;
- no artificial scalp-count cap;
- no stop-loss;
- no orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import runpy
import threading
from http.server import ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

import scalp_path_export_bridge_v1 as base
import BTC15_SCALP_SERIAL_STATE_BRIDGE_SHADOW_V1 as serial
from btc15_scalp_management_presentation_v1 import management_presentation

VERSION = "GENERALIZED_SCALP_INTEGRATION_V5"
SOURCE_FRESH_MAX_AGE_SECONDS = 15.0


def _dt(row: Mapping[str, Any]) -> datetime | None:
    raw = str(row.get("timestamp_utc") or "").strip()
    if not raw:
        return None
    try:
        d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


def _iso_z(d: datetime | None) -> str | None:
    if d is None:
        return None
    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_state(rows, *, now: datetime | None = None) -> dict[str, Any]:
    rows = [dict(r) for r in rows]
    serial_state = serial.build_state(rows)
    current = dict(serial_state.get("current") or {})
    terminals = [dict(x) for x in (serial_state.get("terminal_history") or [])]

    state = str(current.get("state") or "PASS").upper()
    frozen = dict(serial_state.get("frozen_rule") or {})
    present = management_presentation(
        state=state,
        peak_exec_gain=current.get("peak_exec_gain"),
        exec_gain=current.get("exec_gain"),
        arm_gain=float(frozen.get("arm_gain", .05)),
        exit_giveback=float(frozen.get("giveback", .04)),
    )

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    stamps = [d for d in (_dt(r) for r in rows) if d is not None]
    latest = max(stamps) if stamps else None
    age = None if latest is None else max(0.0, (now - latest).total_seconds())
    fresh = bool(age is not None and age <= SOURCE_FRESH_MAX_AGE_SECONDS)

    last_terminal = terminals[-1] if terminals else {}
    ended_unarmed_count = sum(
        1 for x in terminals if str(x.get("terminal_state") or "").upper() == "ENDED_UNARMED"
    )

    out = {
        "version": VERSION,
        "serial_bridge_version": serial_state.get("version"),
        "contract": serial_state.get("contract"),
        "candidate_id": current.get("candidate_id"),
        "opportunity_index": current.get("opportunity_index"),
        "state": present.state,
        "side": current.get("side"),
        "entry_price": current.get("entry_price"),
        "current_bid": current.get("current_bid"),
        "exec_gain": current.get("exec_gain"),
        "peak_exec_gain": current.get("peak_exec_gain"),
        "giveback_from_peak": present.giveback_from_peak,
        "entry_seconds_left": current.get("entry_seconds_left"),
        "contract_seconds_left": current.get("contract_seconds_left"),
        "management_message": present.message if state != "PASS" else str(
            current.get("management_message") or "WATCHING FOR NEXT QUALIFIED SCALP"
        ),
        "armed": present.protection_armed,
        "pullback_detected": present.pullback_detected,
        "exit_triggered": present.exit_now,
        "serial_opportunities_completed": int(serial_state.get("serial_opportunities_completed") or 0),
        "scanning_for_next": bool(serial_state.get("scanning_for_next")),
        "terminal_history": terminals,
        "last_terminal_state": last_terminal.get("terminal_state"),
        "last_terminal_actionable_exit": last_terminal.get("actionable_exit"),
        "last_terminal_candidate_id": last_terminal.get("candidate_id"),
        "ended_unarmed_count": ended_unarmed_count,
        "lifecycle_ended_unarmed_is_actionable_exit": False,
        "armed_no_exit_reset_allowed": False,
        "frozen_rule": frozen,
        "generated_at_utc": _iso_z(now),
        "latest_source_event_utc": _iso_z(latest),
        "source_event_age_sec": age,
        "source_fresh": fresh,
        "source_fresh_max_age_sec": SOURCE_FRESH_MAX_AGE_SECONDS,
        "integration_ready": bool(
            fresh
            and serial_state.get("contract")
            and present.state in {"PASS", "ACTIVE", "PROTECT", "EXIT"}
        ),
        "actionable_for_integration": bool(
            fresh and present.state in {"ACTIVE", "PROTECT", "EXIT"}
        ),
        "integration_block_reason": None if fresh else "SCALP SOURCE STALE",
        "canonical_contract_authority": "MAIN_DASHBOARD",
        "canonical_clock_authority": "MAIN_DASHBOARD",
        "entry_price_is_telemetry_only": True,
        "manual_execution_only": True,
        "order_action": None,
        "orders": False,
        "numeric_flip_risk_validated": False,
        "owns_final_outcome": False,
        "owns_early_opportunity": False,
        "research_only": True,
    }
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
        return super().do_GET()


def start_server():
    srv = ThreadingHTTPServer(("0.0.0.0", base.PORT), Handler)
    t = threading.Thread(
        target=srv.serve_forever,
        name="scalp-integration-state-v5-http",
        daemon=True,
    )
    t.start()
    print(
        f"SCALP INTEGRATION STATE BRIDGE V5 START | port {base.PORT} | "
        "SERIAL EXIT + ENDED_UNARMED LIFECYCLE | FRESHNESS FAIL-CLOSED | "
        "READ ONLY | SIGNAL ONLY | NO ORDERS",
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
