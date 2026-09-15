#!/usr/bin/env python3
"""
BTC15 protected FINAL forward scorecard V3.

READ ONLY | SIGNAL ONLY | MANUAL EXECUTION ONLY | NO ORDERS

V3 changes collector reliability only. Protected FINAL qualification, lock
thresholds, price handling, settlement truth, and scoring semantics are reused
unchanged from V2/V1.

Why V3 exists
-------------
The V2 HTTP process could remain Railway-SUCCESS while its daemon observer
stopped advancing. V3 adds an independent supervisor/heartbeat around the
observer worker so a dead or stale worker cannot silently masquerade as a
healthy collector.

The supervisor may replace only the read-only observer worker. It never restarts
or changes production, never changes a FINAL decision, and never places orders.
State remains contract-keyed/idempotent so a brief overlap during stale-worker
replacement cannot double-count a lock or contract.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import BTC15_FINAL_FORWARD_SCORECARD_V2 as v2

VERSION = "BTC15_FINAL_FORWARD_SCORECARD_V3"
PORT = v2.PORT
POLL_SEC = v2.POLL_SEC
MAIN_STATE_URL = v2.MAIN_STATE_URL
LOCK = v2.LOCK
STATE = v2.STATE

SUPERVISOR_SEC = 5.0
OBSERVER_STALE_SEC = max(30.0, POLL_SEC * 6.0)
HEARTBEAT_LOG_SEC = 60.0

RUNTIME_LOCK = threading.RLock()
RUNTIME: dict[str, Any] = {
    "active_generation": 0,
    "observer_restarts": 0,
    "observer_last_iteration_utc": None,
    "observer_last_success_utc": None,
    "observer_last_exception": None,
    "observer_iterations": 0,
    "observer_successes": 0,
    "observer_worker_alive": False,
    "supervisor_started_utc": None,
    "last_heartbeat_log_monotonic": 0.0,
}
CURRENT_WORKER: threading.Thread | None = None

# Ensure reused V2 summaries/handlers identify this runtime correctly.
v2.VERSION = VERSION


def _iso(d: datetime | None = None) -> str:
    return (d or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _dt(raw: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


def reset_runtime_for_tests() -> None:
    global CURRENT_WORKER
    v2.reset_live_state_for_tests()
    with RUNTIME_LOCK:
        RUNTIME.update({
            "active_generation": 0,
            "observer_restarts": 0,
            "observer_last_iteration_utc": None,
            "observer_last_success_utc": None,
            "observer_last_exception": None,
            "observer_iterations": 0,
            "observer_successes": 0,
            "observer_worker_alive": False,
            "supervisor_started_utc": None,
            "last_heartbeat_log_monotonic": 0.0,
        })
    CURRENT_WORKER = None


def observer_age_seconds(now: datetime | None = None) -> float | None:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    with RUNTIME_LOCK:
        d = _dt(RUNTIME.get("observer_last_iteration_utc"))
    return None if d is None else max(0.0, (now - d).total_seconds())


def runtime_health(now: datetime | None = None) -> dict[str, Any]:
    age = observer_age_seconds(now)
    with RUNTIME_LOCK:
        worker_alive = bool(RUNTIME.get("observer_worker_alive"))
        out = dict(RUNTIME)
    healthy = bool(worker_alive and age is not None and age <= OBSERVER_STALE_SEC)
    return {
        "healthy": healthy,
        "observer_age_sec": age,
        "observer_stale_sec": OBSERVER_STALE_SEC,
        "observer_worker_alive": worker_alive,
        "observer_restarts": int(out.get("observer_restarts") or 0),
        "observer_iterations": int(out.get("observer_iterations") or 0),
        "observer_successes": int(out.get("observer_successes") or 0),
        "observer_last_iteration_utc": out.get("observer_last_iteration_utc"),
        "observer_last_success_utc": out.get("observer_last_success_utc"),
        "observer_last_exception": out.get("observer_last_exception"),
        "active_generation": int(out.get("active_generation") or 0),
    }


def _one_observer_iteration(now: datetime) -> None:
    main = v2.v1._fetch_json(MAIN_STATE_URL)
    v2.observer_cycle(main, observed_at=now)
    v2.v1._maybe_settle(now)
    with LOCK:
        STATE["last_error"] = None


def _worker_loop(generation: int) -> None:
    with RUNTIME_LOCK:
        RUNTIME["observer_worker_alive"] = True
    try:
        while True:
            with RUNTIME_LOCK:
                if generation != int(RUNTIME.get("active_generation") or 0):
                    return
                RUNTIME["observer_iterations"] = int(RUNTIME.get("observer_iterations") or 0) + 1
                RUNTIME["observer_last_iteration_utc"] = _iso()
            now = datetime.now(timezone.utc)
            try:
                _one_observer_iteration(now)
                with RUNTIME_LOCK:
                    RUNTIME["observer_successes"] = int(RUNTIME.get("observer_successes") or 0) + 1
                    RUNTIME["observer_last_success_utc"] = _iso(now)
                    RUNTIME["observer_last_exception"] = None
            except Exception as exc:
                msg = f"{type(exc).__name__}:{exc}"
                with RUNTIME_LOCK:
                    RUNTIME["observer_last_exception"] = msg
                with LOCK:
                    STATE["last_error"] = msg
                print(f"FINAL FORWARD V3 WARNING | {msg} | FAIL CLOSED | NO ORDERS", flush=True)
            time.sleep(POLL_SEC)
    finally:
        with RUNTIME_LOCK:
            if generation == int(RUNTIME.get("active_generation") or 0):
                RUNTIME["observer_worker_alive"] = False


def _start_worker(*, replacement: bool) -> threading.Thread:
    global CURRENT_WORKER
    with RUNTIME_LOCK:
        RUNTIME["active_generation"] = int(RUNTIME.get("active_generation") or 0) + 1
        generation = int(RUNTIME["active_generation"])
        if replacement:
            RUNTIME["observer_restarts"] = int(RUNTIME.get("observer_restarts") or 0) + 1
        RUNTIME["observer_worker_alive"] = True
        RUNTIME["observer_last_iteration_utc"] = _iso()
    t = threading.Thread(
        target=_worker_loop,
        args=(generation,),
        name=f"btc15-final-forward-v3-worker-{generation}",
        daemon=True,
    )
    CURRENT_WORKER = t
    t.start()
    return t


def supervisor_loop() -> None:
    global CURRENT_WORKER
    with RUNTIME_LOCK:
        RUNTIME["supervisor_started_utc"] = _iso()
    _start_worker(replacement=False)
    while True:
        now = datetime.now(timezone.utc)
        age = observer_age_seconds(now)
        alive = bool(CURRENT_WORKER and CURRENT_WORKER.is_alive())
        stale = bool(age is None or age > OBSERVER_STALE_SEC)
        if not alive or stale:
            print(
                f"FINAL V3 SUPERVISOR | replacing observer | alive={alive} | age={age} | "
                "COLLECTOR ONLY | MODEL UNCHANGED | NO ORDERS",
                flush=True,
            )
            _start_worker(replacement=True)

        mono = time.monotonic()
        with RUNTIME_LOCK:
            due = mono - float(RUNTIME.get("last_heartbeat_log_monotonic") or 0.0) >= HEARTBEAT_LOG_SEC
            if due:
                RUNTIME["last_heartbeat_log_monotonic"] = mono
        if due:
            h = runtime_health(now)
            with LOCK:
                s = v2.summarize_live_snapshot(STATE)
            print(
                "FINAL V3 HEARTBEAT | "
                f"healthy={h['healthy']} | age={h['observer_age_sec']}s | restarts={h['observer_restarts']} | "
                f"observed={s['observed_contracts']} | locks={s['lock_calls']} | settled={s['settled_lock_calls']} | "
                "READ ONLY | NO ORDERS",
                flush=True,
            )
        time.sleep(SUPERVISOR_SEC)


class Handler(v2.Handler):
    server_version = "BTC15FinalScorecardV3/1.0"

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            h = runtime_health()
            with LOCK:
                last_poll = STATE.get("last_poll_utc")
                err = STATE.get("last_error")
            return self._json(200 if h["healthy"] else 503, {
                "ok": h["healthy"],
                "version": VERSION,
                "last_poll_utc": last_poll,
                "last_error": err,
                "watchdog": h,
                "orders": False,
                "manual_execution_only": True,
                "protected_final_thresholds_changed": False,
                "numeric_flip_risk_validated": False,
                "partial_start_contract_counted": False,
            })
        if path == "/state":
            with LOCK:
                live = v2.summarize_live_snapshot(STATE)
                hist = STATE.get("historical")
                err = STATE.get("last_error")
                last_poll = STATE.get("last_poll_utc")
            return self._json(200, {
                "ok": True,
                "version": VERSION,
                "historical": hist,
                "live": live,
                "watchdog": runtime_health(),
                "last_poll_utc": last_poll,
                "last_error": err,
                "orders": False,
                "manual_execution_only": True,
            })
        return super().do_GET()


def main() -> int:
    hist = v2.v1.summarize_historical()
    with LOCK:
        STATE["started_at_utc"] = v2.v1._iso()
        STATE["historical"] = hist
    print(
        "FINAL HISTORICAL OOS | "
        f"universe={hist['universe_contracts']} | calls={hist['qualified_final_calls']} | "
        f"accuracy={hist['qualified_accuracy']} | coverage={hist['final_only_coverage']} | "
        f"avg_left={hist['avg_minutes_left']}m | median_left={hist['median_minutes_left']}m | "
        f"avg_ask={hist['avg_preferred_ask']} | median_ask={hist['median_preferred_ask']} | "
        f"ask<=50c={hist['ask_le_50c_n']} ({hist['ask_le_50c_rate']}) | "
        "HISTORICAL AUDIT ONLY | NO RULE CHANGE | NO ORDERS",
        flush=True,
    )
    print(
        f"{VERSION} START | supervised read-only collector | stale>{OBSERVER_STALE_SEC:.0f}s replaces observer worker | "
        "PROTECTED FINAL MODEL UNCHANGED | NO ORDERS",
        flush=True,
    )
    threading.Thread(target=supervisor_loop, name="btc15-final-v3-supervisor", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
