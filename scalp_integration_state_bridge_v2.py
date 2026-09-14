#!/usr/bin/env python3
"""
BTC15 generalized scalp integration state bridge V2.

READ ONLY | SIGNAL ONLY | NO ORDERS

Adds a dashboard-friendly /state endpoint around the exact existing generalized
scalp collector without changing its payload or writing to its event tape.
The endpoint derives the frozen primary signal and its validated management path:
ACTIVE -> PROTECT after +5c arm -> EXIT after 4c giveback from running peak.
"""
from __future__ import annotations

from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse
import runpy
import threading

import scalp_path_export_bridge_v1 as base
from btc15_protected_module_adapter_v1 import (
    SCALP_ARM_GAIN,
    SCALP_GIVEBACK,
    SCALP_MIN_BTC30,
    SCALP_MIN_SECONDS_LEFT,
    scalp_state_from_events,
)

VERSION = "GENERALIZED_SCALP_INTEGRATION_V2"


def _float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, str) and not v.strip():
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dt(row: Mapping[str, Any]) -> datetime:
    raw = str(row.get("timestamp_utc") or "").strip()
    if not raw:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def build_state(rows: list[Mapping[str, Any]]) -> dict:
    snapshots = [
        r for r in rows
        if str(r.get("record_type") or "").upper() == "SNAPSHOT"
        and str(r.get("contract") or "").strip()
    ]
    candidates = [
        r for r in rows
        if str(r.get("record_type") or "").upper() == "CANDIDATE"
        and str(r.get("contract") or "").strip()
    ]

    latest_snapshot = max(snapshots, key=_dt) if snapshots else None
    if latest_snapshot is not None:
        contract = str(latest_snapshot.get("contract") or "").strip()
    elif candidates:
        contract = str(max(candidates, key=_dt).get("contract") or "").strip()
    else:
        contract = ""

    contract_seconds_left = (
        _float(latest_snapshot.get("seconds_left")) if latest_snapshot else None
    )

    contract_candidates = sorted(
        [c for c in candidates if str(c.get("contract") or "").strip() == contract],
        key=_dt,
    )

    primary = None
    for candidate in contract_candidates:
        # Empty path is sufficient to test only the already-frozen eligibility
        # gates. The first eligible candidate is the frozen primary signal.
        s0 = scalp_state_from_events(candidate, ())
        if s0.state != "PASS":
            primary = candidate
            break

    if primary is None:
        state = scalp_state_from_events(None)
        return {
            "version": VERSION,
            "contract": contract or None,
            "state": state.state,
            "side": None,
            "entry_price": None,
            "current_bid": None,
            "exec_gain": None,
            "peak_exec_gain": None,
            "giveback_from_peak": None,
            "entry_seconds_left": None,
            "contract_seconds_left": contract_seconds_left,
            "management_message": "NO QUALIFIED SCALP",
            "armed": False,
            "exit_triggered": False,
            "frozen_rule": {
                "seconds_left_min": SCALP_MIN_SECONDS_LEFT,
                "btc30_min": SCALP_MIN_BTC30,
                "arm_gain": SCALP_ARM_GAIN,
                "giveback": SCALP_GIVEBACK,
                "entry_price_filter": None,
            },
            "owns_final_outcome": False,
            "owns_early_opportunity": False,
            "manual_execution_only": True,
            "order_action": None,
            "numeric_flip_risk_validated": False,
        }

    cid = str(primary.get("candidate_id") or "").strip()
    paths = [
        r for r in rows
        if str(r.get("record_type") or "").upper() == "PATH"
        and (not cid or str(r.get("candidate_id") or "").strip() == cid)
    ]
    state = scalp_state_from_events(primary, paths)

    giveback = None
    if state.peak_exec_gain is not None and state.exec_gain is not None:
        giveback = state.peak_exec_gain - state.exec_gain

    message = {
        "ACTIVE": "SCALP ACTIVE",
        "PROTECT": "PROTECT PROFITS",
        "EXIT": "EXIT / PROTECT PROFITS NOW",
        "PASS": "NO QUALIFIED SCALP",
    }[state.state]

    signal_age_sec = max(0.0, (max((_dt(r) for r in rows), default=_dt(primary)) - _dt(primary)).total_seconds())

    return {
        "version": VERSION,
        "contract": contract or None,
        "candidate_id": cid or None,
        "state": state.state,
        "side": state.side,
        "entry_price": state.entry_ask,
        "current_bid": state.current_bid,
        "exec_gain": state.exec_gain,
        "peak_exec_gain": state.peak_exec_gain,
        "giveback_from_peak": giveback,
        "entry_seconds_left": state.seconds_left,
        "contract_seconds_left": contract_seconds_left,
        "signal_age_sec": signal_age_sec,
        "management_message": message,
        "armed": bool(state.peak_exec_gain is not None and state.peak_exec_gain >= SCALP_ARM_GAIN),
        "exit_triggered": state.state == "EXIT",
        "frozen_rule": {
            "seconds_left_min": SCALP_MIN_SECONDS_LEFT,
            "btc30_min": SCALP_MIN_BTC30,
            "arm_gain": SCALP_ARM_GAIN,
            "giveback": SCALP_GIVEBACK,
            "entry_price_filter": None,
        },
        "owns_final_outcome": False,
        "owns_early_opportunity": False,
        "manual_execution_only": True,
        "order_action": None,
        "numeric_flip_risk_validated": False,
    }


class Handler(base.Handler):
    def do_GET(self):
        if not base.authorized(self):
            return self._json(401, {"ok": False, "error": "unauthorized", "orders": False})

        path = urlparse(self.path).path
        if path == "/state":
            rows, _ = base.read_rows()
            payload = build_state(rows)
            payload["ok"] = True
            payload["orders"] = False
            return self._json(200, payload)

        return super().do_GET()


def start_server():
    srv = ThreadingHTTPServer(("0.0.0.0", base.PORT), Handler)
    t = threading.Thread(target=srv.serve_forever, name="scalp-integration-state-http", daemon=True)
    t.start()
    print(
        f"SCALP INTEGRATION STATE BRIDGE V2 START | port {base.PORT} | "
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
