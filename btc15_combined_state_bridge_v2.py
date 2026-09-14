#!/usr/bin/env python3
"""
BTC15 combined dashboard state bridge V2.

READ ONLY | SIGNAL ONLY | NO ORDERS

Keeps V1 /state and /combined-state surfaces and adds a read-only 1-second
observer that logs cross-service state changes. This makes contract sync,
protected EARLY/FINAL preservation, SCALP management transitions, source
freshness, and timer alignment visible before the production dashboard UI is
changed.
"""
from __future__ import annotations

import runpy
import threading
import time

import btc15_combined_state_bridge_v1 as v1
import scalp_path_export_bridge_v1 as base

POLL_SEC = 1.0
HEARTBEAT_SEC = 30.0


def _f(v, digits=1, suffix=""):
    try:
        return f"{float(v):.{digits}f}{suffix}"
    except Exception:
        return "—"


def observer_loop():
    last_signature = None
    last_heartbeat = 0.0
    while True:
        try:
            main_state = v1.fetch_main_state()
            rows, _ = base.read_rows()
            x = v1.build_combined_state(main_state, rows)
            signature = (
                x.get("contract"),
                x.get("early", {}).get("state"),
                x.get("final", {}).get("state"),
                x.get("scalp", {}).get("state"),
                x.get("headline"),
                tuple(x.get("context_labels") or ()),
                x.get("scalp_management_message"),
                x.get("scalp_contract_aligned"),
                x.get("scalp_source_fresh"),
            )
            now = time.time()
            if signature != last_signature or now - last_heartbeat >= HEARTBEAT_SEC:
                print(
                    "COMBINED_BRIDGE_SMOKE | "
                    f"contract={x.get('contract')} | "
                    f"left={_f(x.get('canonical_seconds_left'),1,'s')} | "
                    f"EARLY={x.get('early',{}).get('state')} | "
                    f"FINAL={x.get('final',{}).get('state')} | "
                    f"SCALP={x.get('scalp',{}).get('state')} | "
                    f"headline={x.get('headline')} | "
                    f"sync={x.get('scalp_contract_aligned')} | "
                    f"fresh={x.get('scalp_source_fresh')} | "
                    f"source_age={_f(x.get('scalp_source_age_sec'),1,'s')} | "
                    f"timer_delta={_f(x.get('scalp_timer_delta_sec'),1,'s')} | "
                    f"management={x.get('scalp_management_message')} | NO ORDERS",
                    flush=True,
                )
                last_signature = signature
                last_heartbeat = now
        except Exception as exc:
            print(
                f"COMBINED_BRIDGE_SMOKE WARNING | {type(exc).__name__}: {exc} | "
                "FAIL CLOSED | NO ORDERS",
                flush=True,
            )
        time.sleep(POLL_SEC)


def main():
    if not base.COLLECTOR.exists():
        raise SystemExit(f"collector missing: {base.COLLECTOR}")
    v1.start_server()
    threading.Thread(
        target=observer_loop,
        name="btc15-combined-state-observer-v2",
        daemon=True,
    ).start()
    print(
        f"BTC15 COMBINED STATE BRIDGE V2 START | poll={POLL_SEC:.1f}s | "
        "READ ONLY | SIGNAL ONLY | NO ORDERS",
        flush=True,
    )
    runpy.run_path(str(base.COLLECTOR), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
