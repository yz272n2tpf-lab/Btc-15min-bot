#!/usr/bin/env python3
"""
BTC15 generalized scalp integration transition monitor V1.

READ ONLY | SIGNAL ONLY | NO ORDERS

Runs the exact generalized collector behind the V3 read-only state bridge and
prints state transitions plus a sparse heartbeat. This is for the short live
integration smoke only. It does not alter qualification, management, event-tape
writes, pricing, or order behavior.
"""
from __future__ import annotations

from datetime import datetime, timezone
import runpy
import threading
import time

import scalp_path_export_bridge_v1 as base
from scalp_integration_state_bridge_v3 import build_state, start_server

POLL_SEC = 0.5
HEARTBEAT_SEC = 30.0


def _parse_ts(raw):
    try:
        d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


def _latest_event_age(rows):
    stamps = [_parse_ts(r.get("timestamp_utc")) for r in rows]
    stamps = [x for x in stamps if x is not None]
    if not stamps:
        return None
    return max(0.0, (datetime.now(timezone.utc) - max(stamps)).total_seconds())


def monitor_loop():
    last_signature = None
    last_heartbeat = 0.0
    while True:
        try:
            rows, _ = base.read_rows()
            state = build_state(rows)
            signature = (
                state.get("contract"),
                state.get("state"),
                state.get("side"),
                state.get("management_message"),
                state.get("candidate_id"),
            )
            now = time.time()
            changed = signature != last_signature
            heartbeat = now - last_heartbeat >= HEARTBEAT_SEC
            if changed or heartbeat:
                age = _latest_event_age(rows)
                age_txt = "—" if age is None else f"{age:.2f}s"
                left = state.get("contract_seconds_left")
                left_txt = "—" if left is None else f"{float(left):.1f}s"
                gain = state.get("exec_gain")
                gain_txt = "—" if gain is None else f"{100*float(gain):+.1f}c"
                peak = state.get("peak_exec_gain")
                peak_txt = "—" if peak is None else f"{100*float(peak):+.1f}c"
                gb = state.get("giveback_from_peak")
                gb_txt = "—" if gb is None else f"{100*float(gb):.1f}c"
                print(
                    "INTEGRATION_SMOKE | "
                    f"contract={state.get('contract')} | left={left_txt} | "
                    f"state={state.get('state')} | side={state.get('side')} | "
                    f"gain={gain_txt} | peak={peak_txt} | giveback={gb_txt} | "
                    f"message={state.get('management_message')} | "
                    f"event_age={age_txt} | NO ORDERS",
                    flush=True,
                )
                last_signature = signature
                last_heartbeat = now
        except Exception as exc:
            print(f"INTEGRATION_SMOKE WARNING | {type(exc).__name__}: {exc} | NO ORDERS", flush=True)
        time.sleep(POLL_SEC)


def main():
    if not base.COLLECTOR.exists():
        raise SystemExit(f"collector missing: {base.COLLECTOR}")
    start_server()
    threading.Thread(target=monitor_loop, name="scalp-integration-transition-monitor", daemon=True).start()
    print(
        f"INTEGRATION TRANSITION MONITOR V1 START | poll={POLL_SEC:.1f}s | "
        f"heartbeat={HEARTBEAT_SEC:.0f}s | READ ONLY | NO ORDERS",
        flush=True,
    )
    runpy.run_path(str(base.COLLECTOR), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
