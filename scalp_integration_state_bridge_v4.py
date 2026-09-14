#!/usr/bin/env python3
"""
BTC15 generalized scalp integration state bridge V4.

READ ONLY | SIGNAL ONLY | NO ORDERS

V4 preserves the frozen V3 scalp derivation and management states, then adds
operational freshness metadata for safe cross-service/dashboard composition.
It does NOT change any scalp qualification or management threshold.

The main protected dashboard remains the authority for contract identity and
canonical time remaining. Consumers may compose a scalp state only when:
- this source is fresh,
- the contract matches the main dashboard contract,
- the existing frozen state is otherwise valid.
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
import scalp_integration_state_bridge_v3 as v3

VERSION = "GENERALIZED_SCALP_INTEGRATION_V4"
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


def build_state(rows, *, now: datetime | None = None):
    out = dict(v3.build_state(rows))
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    stamps = [d for d in (_dt(r) for r in rows) if d is not None]
    latest = max(stamps) if stamps else None
    age = None if latest is None else max(0.0, (now - latest).total_seconds())
    fresh = bool(age is not None and age <= SOURCE_FRESH_MAX_AGE_SECONDS)

    out["version"] = VERSION
    out["generated_at_utc"] = _iso_z(now)
    out["latest_source_event_utc"] = _iso_z(latest)
    out["source_event_age_sec"] = age
    out["source_fresh"] = fresh
    out["source_fresh_max_age_sec"] = SOURCE_FRESH_MAX_AGE_SECONDS
    out["integration_ready"] = bool(
        fresh
        and out.get("contract")
        and out.get("state") in {"PASS", "ACTIVE", "PROTECT", "EXIT"}
    )
    out["actionable_for_integration"] = bool(
        fresh and out.get("state") in {"ACTIVE", "PROTECT", "EXIT"}
    )
    out["integration_block_reason"] = (
        None if fresh else "SCALP SOURCE STALE"
    )
    out["canonical_contract_authority"] = "MAIN_DASHBOARD"
    out["canonical_clock_authority"] = "MAIN_DASHBOARD"
    out["manual_execution_only"] = True
    out["order_action"] = None
    out["numeric_flip_risk_validated"] = False
    out["owns_final_outcome"] = False
    out["owns_early_opportunity"] = False
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
        name="scalp-integration-state-v4-http",
        daemon=True,
    )
    t.start()
    print(
        f"SCALP INTEGRATION STATE BRIDGE V4 START | port {base.PORT} | "
        "FRESHNESS FAIL-CLOSED | PUBLIC SIGNAL STATE | READ ONLY | NO ORDERS",
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
