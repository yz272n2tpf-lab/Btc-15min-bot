#!/usr/bin/env python3
"""
BTC15 protected EARLY -> FINAL handoff forward auditor V1.

READ ONLY | SIGNAL ONLY | MANUAL EXECUTION ONLY | NO ORDERS

This observer does not recalculate EARLY or FINAL. It reads only the already-
protected production adapter states and records the first protected EARLY
QUALIFIED event and first protected FINAL LOCK for each fully observable fresh
contract.

Fresh/coverage semantics
------------------------
- startup contract is excluded;
- collection arms on the first post-start rollover;
- a contract is in the handoff coverage universe only when first seen with
  >=600 seconds remaining, before protected EARLY's 10-minute window opens;
- protected FINAL opens later, so this same universe is complete for both paths.

Review gate (measurement only; never auto-promotes behavior)
------------------------------------------------------------
- >=30 eligibility-complete contracts;
- >=10 contracts with both a protected EARLY and protected FINAL;
- >=12 officially settled protected FINAL locks.
"""
from __future__ import annotations

import json
import math
import statistics
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

import BTC15_EARLY_FORWARD_SCORECARD_V1 as earlymod
import btc15_main_protected_state_adapter_v1 as adapter

VERSION = "BTC15_EARLY_FINAL_HANDOFF_FORWARD_V1"
PORT = 8080
MAIN_STATE_URL = "https://btc-15min-bot-production.up.railway.app/dashboard_state.json"
POLL_SEC = 5.0
ELIGIBILITY_OPEN_SECONDS_LEFT = 600.0
MIN_ELIGIBLE_CONTRACTS = 30
MIN_HANDOFFS = 10
MIN_SETTLED_FINAL = 12
SETTLEMENT_INITIAL_DELAY_SEC = 30.0
SETTLEMENT_RETRY_SEC = 60.0
SUPERVISOR_SEC = 5.0
OBSERVER_STALE_SEC = 30.0
HEARTBEAT_LOG_SEC = 60.0

LOCK = threading.RLock()
STATE: dict[str, Any] = {
    "started_at_utc": None,
    "last_poll_utc": None,
    "last_error": None,
    "current_contract": None,
    "startup_contract": None,
    "live_scoring_armed": False,
    "live_scoring_armed_at_utc": None,
    "first_seen_seconds_left": {},
    "eligible_contracts": [],
    "coverage_excluded_late": {},
    "early_records": {},
    "final_records": {},
    "settlements": {},
    "pending_settlement": {},
}

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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime | None = None) -> str:
    return (d or _now()).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _dt(v: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


def _f(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _mean(xs: list[float]) -> float | None:
    return statistics.fmean(xs) if xs else None


def _median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def _rate(n: int, d: int) -> float | None:
    return n / d if d else None


def _early_record(protected: Mapping[str, Any], observed_at: datetime) -> dict[str, Any] | None:
    e = protected.get("early")
    if e is None or getattr(e, "state", None) != "QUALIFIED":
        return None
    side = getattr(e, "side", None)
    ask = _f(getattr(e, "ask", None))
    fair = _f(getattr(e, "fair", None))
    edge = _f(getattr(e, "edge", None))
    sec = _f(protected.get("seconds_left"))
    if side not in {"UP", "DOWN"} or None in (ask, fair, edge):
        return None
    return {
        "contract": protected.get("contract"),
        "observed_at_utc": _iso(observed_at),
        "side": side,
        "ask": ask,
        "fair": fair,
        "edge": edge,
        "seconds_left": sec,
        "minutes_left": None if sec is None else sec / 60.0,
        "ask_in_25_35c": bool(0.25 - 1e-12 <= ask <= 0.35 + 1e-12),
        "ask_at_or_below_50c": bool(ask <= 0.50 + 1e-12),
    }


def _final_record(protected: Mapping[str, Any], observed_at: datetime) -> dict[str, Any] | None:
    f = protected.get("final")
    if f is None or getattr(f, "state", None) != "LOCK":
        return None
    side = getattr(f, "side", None)
    fair = _f(getattr(f, "fair", None))
    sec = _f(protected.get("seconds_left"))
    if side not in {"UP", "DOWN"} or fair is None:
        return None
    ask_key = "up_ask" if side == "UP" else "down_ask"
    ask = _f(protected.get(ask_key))
    return {
        "contract": protected.get("contract"),
        "observed_at_utc": _iso(observed_at),
        "side": side,
        "ask": ask,
        "fair": fair,
        "seconds_left": sec,
        "minutes_left": None if sec is None else sec / 60.0,
        "ask_at_or_below_50c": bool(ask is not None and ask <= 0.50 + 1e-12),
    }


def reset_state_for_tests() -> None:
    global CURRENT_WORKER
    with LOCK:
        STATE.update({
            "started_at_utc": None,
            "last_poll_utc": None,
            "last_error": None,
            "current_contract": None,
            "startup_contract": None,
            "live_scoring_armed": False,
            "live_scoring_armed_at_utc": None,
            "first_seen_seconds_left": {},
            "eligible_contracts": [],
            "coverage_excluded_late": {},
            "early_records": {},
            "final_records": {},
            "settlements": {},
            "pending_settlement": {},
        })
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


def observer_cycle(main_state: Mapping[str, Any], observed_at: datetime | None = None) -> None:
    now = (observed_at or _now()).astimezone(timezone.utc)
    protected = adapter.protected_main_summary(main_state)
    contract = str(protected.get("contract") or "").strip()
    left = _f(protected.get("seconds_left"))
    if not contract:
        raise ValueError("production dashboard state missing contract")

    with LOCK:
        STATE["last_poll_utc"] = _iso(now)
        prior = STATE.get("current_contract")
        if not prior:
            STATE["current_contract"] = contract
            STATE["startup_contract"] = contract
            STATE["first_seen_seconds_left"].setdefault(contract, left)
            return

        if prior != contract:
            if prior in STATE.get("early_records", {}) or prior in STATE.get("final_records", {}):
                STATE["pending_settlement"].setdefault(
                    prior, _iso(now + timedelta(seconds=SETTLEMENT_INITIAL_DELAY_SEC))
                )
            STATE["current_contract"] = contract
            if STATE.get("live_scoring_armed") is not True:
                STATE["live_scoring_armed"] = True
                STATE["live_scoring_armed_at_utc"] = _iso(now)
                print(
                    f"HANDOFF FORWARD ARMED | rollover={prior}->{contract} | at={_iso(now)} | "
                    "FRESH SAMPLE START | NO ORDERS",
                    flush=True,
                )

        if contract not in STATE["first_seen_seconds_left"]:
            STATE["first_seen_seconds_left"][contract] = left

        if STATE.get("live_scoring_armed") is not True:
            return

        if contract not in STATE["eligible_contracts"] and contract not in STATE["coverage_excluded_late"]:
            first_left = STATE["first_seen_seconds_left"].get(contract)
            if first_left is not None and float(first_left) >= ELIGIBILITY_OPEN_SECONDS_LEFT - 1e-12:
                STATE["eligible_contracts"].append(contract)
                print(
                    "HANDOFF COVERAGE-ELIGIBLE CONTRACT | "
                    f"{contract} | first_seen_left={float(first_left):.2f}s | "
                    "BEFORE EARLY WINDOW | NO ORDERS",
                    flush=True,
                )
            else:
                STATE["coverage_excluded_late"][contract] = first_left
                print(
                    "HANDOFF COVERAGE EXCLUDED | "
                    f"{contract} | first_seen_left={first_left} | "
                    "EARLY WINDOW MAY HAVE OPENED | NO ORDERS",
                    flush=True,
                )
        eligible = contract in STATE["eligible_contracts"]

    if not eligible:
        return

    er = _early_record(protected, now)
    fr = _final_record(protected, now)
    changed = False
    with LOCK:
        if er is not None and contract not in STATE["early_records"]:
            STATE["early_records"][contract] = er
            changed = True
            print(
                "HANDOFF EARLY | "
                f"{contract} | {er['side']} | ask={er['ask']:.3f} | fair={er['fair']:.3f} | "
                f"edge={er['edge']:.3f} | left={er['minutes_left']:.2f}m | NO ORDERS",
                flush=True,
            )
        if fr is not None and contract not in STATE["final_records"]:
            STATE["final_records"][contract] = fr
            changed = True
            print(
                "HANDOFF FINAL | "
                f"{contract} | {fr['side']} | ask={fr['ask']} | fair={fr['fair']:.3f} | "
                f"left={fr['minutes_left']:.2f}m | NO ORDERS",
                flush=True,
            )
    if changed:
        log_summary()


def _maybe_settle(now: datetime | None = None) -> None:
    now = now or _now()
    with LOCK:
        pending = dict(STATE.get("pending_settlement") or {})
    for contract, next_raw in pending.items():
        next_dt = _dt(next_raw)
        if next_dt is None or now < next_dt:
            continue
        official = earlymod.fetch_official_settlement(contract)
        with LOCK:
            if official:
                STATE["settlements"][contract] = official
                STATE["pending_settlement"].pop(contract, None)
                print(
                    f"HANDOFF SETTLED | {contract} | official={official} | NO ORDERS",
                    flush=True,
                )
                log_summary()
            else:
                STATE["pending_settlement"][contract] = _iso(
                    now + timedelta(seconds=SETTLEMENT_RETRY_SEC)
                )


def summarize_state() -> dict[str, Any]:
    with LOCK:
        eligible = list(STATE.get("eligible_contracts") or [])
        er = {k: dict(v) for k, v in STATE.get("early_records", {}).items()}
        fr = {k: dict(v) for k, v in STATE.get("final_records", {}).items()}
        st = dict(STATE.get("settlements") or {})
        excluded = dict(STATE.get("coverage_excluded_late") or {})
        armed = STATE.get("live_scoring_armed") is True
        startup = STATE.get("startup_contract")

    ekeys, fkeys = set(er), set(fr)
    both = sorted(ekeys & fkeys)
    early_only = sorted(ekeys - fkeys)
    final_only = sorted(fkeys - ekeys)
    none = [c for c in eligible if c not in ekeys and c not in fkeys]
    any_keys = ekeys | fkeys

    handoff_gaps = []
    same_side_n = 0
    same_side_price_moves = []
    for c in both:
        e, f = er[c], fr[c]
        em, fm = _f(e.get("minutes_left")), _f(f.get("minutes_left"))
        if em is not None and fm is not None:
            handoff_gaps.append(em - fm)
        if e.get("side") == f.get("side"):
            same_side_n += 1
            ea, fa = _f(e.get("ask")), _f(f.get("ask"))
            if ea is not None and fa is not None:
                same_side_price_moves.append(fa - ea)

    easks = [_f(v.get("ask")) for v in er.values()]
    easks = [x for x in easks if x is not None]
    eleft = [_f(v.get("minutes_left")) for v in er.values()]
    eleft = [x for x in eleft if x is not None]
    fasks = [_f(v.get("ask")) for v in fr.values()]
    fasks = [x for x in fasks if x is not None]
    fleft = [_f(v.get("minutes_left")) for v in fr.values()]
    fleft = [x for x in fleft if x is not None]

    early_ideal_n = sum(v.get("ask_in_25_35c") is True for v in er.values())
    early_le50_n = sum(v.get("ask_at_or_below_50c") is True for v in er.values())
    final_le50_n = sum(v.get("ask_at_or_below_50c") is True for v in fr.values())

    settled_final = [c for c in fkeys if c in st]
    final_correct_n = sum(fr[c].get("side") == st[c] for c in settled_final)
    settled_early = [c for c in ekeys if c in st]
    early_same_settlement_n = sum(er[c].get("side") == st[c] for c in settled_early)

    ready = bool(
        len(eligible) >= MIN_ELIGIBLE_CONTRACTS
        and len(both) >= MIN_HANDOFFS
        and len(settled_final) >= MIN_SETTLED_FINAL
    )

    return {
        "version": VERSION,
        "status": "HANDOFF_REVIEW_SAMPLE_READY" if ready else "COLLECTING_HANDOFF_FORWARD",
        "fresh_start_semantics": "FIRST_POST_START_ROLLOVER",
        "coverage_universe_semantics": "FIRST_SEEN_BEFORE_EARLY_10M_ELIGIBILITY_WINDOW",
        "startup_contract_excluded": startup,
        "live_scoring_armed": armed,
        "eligibility_complete_contracts": len(eligible),
        "coverage_excluded_late_n": len(excluded),
        "early_calls": len(er),
        "final_locks": len(fr),
        "handoffs": len(both),
        "early_only_contracts": len(early_only),
        "final_only_contracts": len(final_only),
        "no_anchor_contracts": len(none),
        "any_signal_coverage": _rate(len(any_keys & set(eligible)), len(eligible)),
        "early_coverage": _rate(len(ekeys & set(eligible)), len(eligible)),
        "final_coverage": _rate(len(fkeys & set(eligible)), len(eligible)),
        "dual_anchor_coverage": _rate(len(both), len(eligible)),
        "handoff_side_agreement_rate": _rate(same_side_n, len(both)),
        "avg_early_minutes_left": _mean(eleft),
        "median_early_minutes_left": _median(eleft),
        "avg_final_minutes_left": _mean(fleft),
        "median_final_minutes_left": _median(fleft),
        "avg_early_to_final_gap_minutes": _mean(handoff_gaps),
        "median_early_to_final_gap_minutes": _median(handoff_gaps),
        "avg_early_ask": _mean(easks),
        "median_early_ask": _median(easks),
        "early_ideal_25_35c_n": early_ideal_n,
        "early_ideal_25_35c_rate": _rate(early_ideal_n, len(er)),
        "early_le_50c_n": early_le50_n,
        "early_le_50c_rate": _rate(early_le50_n, len(er)),
        "avg_final_ask": _mean(fasks),
        "median_final_ask": _median(fasks),
        "final_le_50c_n": final_le50_n,
        "final_le_50c_rate": _rate(final_le50_n, len(fr)),
        "avg_same_side_ask_change_early_to_final": _mean(same_side_price_moves),
        "median_same_side_ask_change_early_to_final": _median(same_side_price_moves),
        "settled_final_locks": len(settled_final),
        "final_accuracy": _rate(final_correct_n, len(settled_final)),
        "settled_early_calls": len(settled_early),
        "early_same_side_as_settlement_rate_secondary": _rate(early_same_settlement_n, len(settled_early)),
        "sample_ready": ready,
        "review_gate": {
            "min_eligible_contracts": MIN_ELIGIBLE_CONTRACTS,
            "min_handoffs": MIN_HANDOFFS,
            "min_settled_final": MIN_SETTLED_FINAL,
        },
        "protected_early_thresholds_changed": False,
        "protected_final_thresholds_changed": False,
        "auto_promotion": False,
        "orders": False,
        "manual_execution_only": True,
    }


def runtime_health(now: datetime | None = None) -> dict[str, Any]:
    now = (now or _now()).astimezone(timezone.utc)
    with RUNTIME_LOCK:
        last = _dt(RUNTIME.get("observer_last_iteration_utc"))
        out = dict(RUNTIME)
    age = None if last is None else max(0.0, (now - last).total_seconds())
    alive = bool(out.get("observer_worker_alive"))
    healthy = bool(alive and age is not None and age <= OBSERVER_STALE_SEC)
    return {
        "healthy": healthy,
        "observer_age_sec": age,
        "observer_stale_sec": OBSERVER_STALE_SEC,
        "observer_worker_alive": alive,
        "observer_restarts": int(out.get("observer_restarts") or 0),
        "observer_iterations": int(out.get("observer_iterations") or 0),
        "observer_successes": int(out.get("observer_successes") or 0),
        "observer_last_success_utc": out.get("observer_last_success_utc"),
        "observer_last_exception": out.get("observer_last_exception"),
    }


def _one_iteration(now: datetime) -> None:
    main_state = earlymod._fetch_json(MAIN_STATE_URL)
    observer_cycle(main_state, observed_at=now)
    _maybe_settle(now)
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
            now = _now()
            try:
                _one_iteration(now)
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
                print(f"HANDOFF WARNING | {msg} | FAIL CLOSED | NO ORDERS", flush=True)
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
        name=f"btc15-handoff-worker-{generation}",
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
        now = _now()
        h = runtime_health(now)
        alive = bool(CURRENT_WORKER and CURRENT_WORKER.is_alive())
        if not alive or not h["healthy"]:
            print(
                f"HANDOFF SUPERVISOR | replacing observer | alive={alive} | age={h['observer_age_sec']} | "
                "COLLECTOR ONLY | SIGNALS UNCHANGED | NO ORDERS",
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
            s = summarize_state()
            print(
                "HANDOFF HEARTBEAT | "
                f"healthy={h['healthy']} | restarts={h['observer_restarts']} | "
                f"eligible={s['eligibility_complete_contracts']} | early={s['early_calls']} | "
                f"final={s['final_locks']} | handoffs={s['handoffs']} | settled_final={s['settled_final_locks']} | "
                "READ ONLY | NO ORDERS",
                flush=True,
            )
        time.sleep(SUPERVISOR_SEC)


def log_summary() -> None:
    s = summarize_state()
    def fmt(v: Any, d: int = 3) -> str:
        return "NA" if v is None else f"{float(v):.{d}f}"
    print(
        "HANDOFF FORWARD V1 | "
        f"status={s['status']} | eligible={s['eligibility_complete_contracts']} | "
        f"early={s['early_calls']} | final={s['final_locks']} | both={s['handoffs']} | "
        f"union={fmt(s['any_signal_coverage'])} | dual={fmt(s['dual_anchor_coverage'])} | "
        f"agree={fmt(s['handoff_side_agreement_rate'])} | gap={fmt(s['avg_early_to_final_gap_minutes'],2)}m | "
        f"early_ideal={s['early_ideal_25_35c_n']} | early<=50={s['early_le_50c_n']} | "
        f"final_acc={fmt(s['final_accuracy'])} | ready={s['sample_ready']} | NO ORDERS",
        flush=True,
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15HandoffForwardV1/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _json(self, status: int, obj: Mapping[str, Any]) -> None:
        raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            h = runtime_health()
            return self._json(200 if h["healthy"] else 503, {
                "ok": h["healthy"], "version": VERSION, "watchdog": h,
                "orders": False, "manual_execution_only": True,
            })
        if path == "/state":
            return self._json(200, {
                "ok": True, "version": VERSION, "live": summarize_state(),
                "watchdog": runtime_health(), "orders": False,
                "manual_execution_only": True,
            })
        return self._json(404, {"ok": False, "error": "not_found"})


def main() -> int:
    with LOCK:
        STATE["started_at_utc"] = _iso()
    print(
        f"{VERSION} START | startup contract excluded | coverage first_seen>=600s | "
        "PROTECTED EARLY + FINAL ONLY | READ ONLY | NO AUTO-PROMOTE | NO ORDERS",
        flush=True,
    )
    threading.Thread(target=supervisor_loop, name="btc15-handoff-supervisor", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
