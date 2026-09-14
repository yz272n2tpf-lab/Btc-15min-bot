#!/usr/bin/env python3
"""
BTC15 combined live smoke monitor V2.

READ ONLY | SIGNAL ONLY | NO ORDERS

V2 combines the protected main dashboard state with the generalized SCALP V4
freshness envelope and cross-service payload V3. A stale or mismatched scalp
source is visible diagnostically but cannot become actionable.
"""
from __future__ import annotations

import runpy
import threading
import time
from typing import Any, Mapping

import requests

import scalp_path_export_bridge_v1 as base
from scalp_integration_state_bridge_v4 import build_state as build_scalp_state, start_server
from btc15_cross_service_payload_v3 import compose_cross_service_payload

MAIN_STATE_URL = "https://btc-15min-bot-production.up.railway.app/dashboard_state.json"
POLL_SEC = 1.0
HEARTBEAT_SEC = 30.0


def _unwrap_state(obj: Any) -> Mapping[str, Any]:
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
    r = requests.get(MAIN_STATE_URL, timeout=3.0, headers={"Cache-Control": "no-cache"})
    r.raise_for_status()
    return _unwrap_state(r.json())


def _f(v: Any, digits=1, suffix="") -> str:
    try:
        return f"{float(v):.{digits}f}{suffix}"
    except Exception:
        return "—"


def monitor_loop():
    last_signature = None
    last_heartbeat = 0.0
    last_final_contract = None
    while True:
        try:
            main = fetch_main_state()
            rows, _ = base.read_rows()
            scalp = build_scalp_state(rows)
            combined = compose_cross_service_payload(main, scalp).to_dict()

            early_state = combined["early"]["state"]
            final_state = combined["final"]["state"]
            scalp_state = combined["scalp"]["state"]
            signature = (
                combined["contract"], early_state, final_state, scalp_state,
                combined["headline"], tuple(combined["context_labels"]),
                combined["scalp_management_message"],
                combined["scalp_contract_aligned"],
                combined["scalp_source_fresh"],
                combined["scalp_block_reason"],
            )

            now = time.time()
            changed = signature != last_signature
            heartbeat = now - last_heartbeat >= HEARTBEAT_SEC
            if changed or heartbeat:
                labels = ",".join(combined["context_labels"]) or "-"
                paths = ",".join(combined["actionable_paths"]) or "-"
                print(
                    "COMBINED_SMOKE_V2 | "
                    f"contract={combined['contract']} | "
                    f"left={_f(combined.get('canonical_seconds_left'),1,'s')} | "
                    f"EARLY={early_state} | FINAL={final_state} | SCALP={scalp_state} | "
                    f"headline={combined['headline']} | paths={paths} | labels={labels} | "
                    f"scalp_sync={combined['scalp_contract_aligned']} | "
                    f"scalp_fresh={combined['scalp_source_fresh']} | "
                    f"source_age={_f(combined.get('scalp_source_age_sec'),1,'s')} | "
                    f"timer_delta={_f(combined.get('scalp_timer_delta_sec'),1,'s')} | "
                    f"block={combined.get('scalp_block_reason') or '-'} | "
                    f"management={combined['scalp_management_message']} | NO ORDERS",
                    flush=True,
                )
                last_signature = signature
                last_heartbeat = now

            if final_state == "LOCK" and last_final_contract != combined["contract"]:
                print(
                    "COMBINED_FINAL_LIVE_TRIGGER_V2 | "
                    f"contract={combined['contract']} | "
                    f"side={combined['final']['side']} | "
                    f"fair={_f(combined['final']['fair'],3)} | "
                    f"left={_f(combined.get('canonical_seconds_left'),1,'s')} | "
                    "PROTECTED FINAL | NO ORDERS",
                    flush=True,
                )
                last_final_contract = combined["contract"]

        except Exception as exc:
            print(
                f"COMBINED_SMOKE_V2 WARNING | {type(exc).__name__}: {exc} | "
                "fail-closed | NO ORDERS",
                flush=True,
            )
        time.sleep(POLL_SEC)


def main():
    if not base.COLLECTOR.exists():
        raise SystemExit(f"collector missing: {base.COLLECTOR}")
    start_server()
    threading.Thread(
        target=monitor_loop,
        name="btc15-combined-live-smoke-v2",
        daemon=True,
    ).start()
    print(
        f"BTC15 COMBINED LIVE SMOKE V2 START | poll={POLL_SEC:.1f}s | "
        f"main={MAIN_STATE_URL} | FRESHNESS FAIL-CLOSED | SIGNAL ONLY | NO ORDERS",
        flush=True,
    )
    runpy.run_path(str(base.COLLECTOR), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
