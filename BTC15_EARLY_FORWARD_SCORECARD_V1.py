#!/usr/bin/env python3
"""
BTC15 protected EARLY forward scorecard V1.

READ ONLY | SIGNAL ONLY | MANUAL EXECUTION ONLY | NO ORDERS

Purpose
-------
Confirm the already-protected production EARLY opportunity path on a fresh
forward sample without recalculating or changing its qualification rule.

Frozen producer rule (source fact, not reimplemented here)
----------------------------------------------------------
Protected EARLY can qualify only when the production producer has already set
its EARLY state ready/OPPORTUNITY. The frozen producer rule is:
- preferred-side Kalshi ask <= 45c;
- target-aware model fair >= 75%;
- model edge >= 8 percentage points;
- 2 to 10 minutes remaining;
- absolute distance from Kalshi target >= $25.

This scorecard reads only the protected adapter result. It does NOT apply those
thresholds itself.

Coverage-universe semantics
---------------------------
A contract counts toward EARLY coverage only when the collector first sees that
contract with >= 600 seconds remaining, before the protected EARLY 10-minute
eligibility window opens. The startup contract is excluded. Fresh collection
arms on the first post-start rollover, so no pre-deployment outcome can enter
the sample.

EARLY settlement correctness is reported as secondary context. EARLY is an
opportunity path, not FINAL outcome authority; settlement accuracy is therefore
kept separate from entry price, timing, fair value, and edge.
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
from urllib.parse import quote, urlparse

import requests

import btc15_main_protected_state_adapter_v1 as adapter

VERSION = "BTC15_EARLY_FORWARD_SCORECARD_V1"
PORT = 8080
MAIN_STATE_URL = "https://btc-15min-bot-production.up.railway.app/dashboard_state.json"
POLL_SEC = 5.0
TIMEOUT_SEC = 3.0
SETTLEMENT_RETRY_SEC = 60.0
SETTLEMENT_INITIAL_DELAY_SEC = 30.0
EARLY_ELIGIBILITY_OPEN_SECONDS_LEFT = 600.0
MIN_ELIGIBLE_CONTRACTS = 30
MIN_SETTLED_EARLY_CALLS = 12

LIVE_MARKET_BASE = "https://external-api.kalshi.com/trade-api/v2/markets/"
HIST_MARKET_BASE = "https://external-api.kalshi.com/trade-api/v2/historical/markets/"

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
    "first_eligible_contract": None,
    "first_seen_seconds_left": {},
    "eligible_contracts": [],
    "coverage_excluded_late": {},
    "call_records": {},
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


def _dt(raw: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
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


def _side(v: Any) -> str | None:
    x = str(v or "").strip().upper()
    if x in {"UP", "YES", "Y", "TRUE", "1"}:
        return "UP"
    if x in {"DOWN", "NO", "N", "FALSE", "0"}:
        return "DOWN"
    return None


def _mean(xs: list[float]) -> float | None:
    return statistics.fmean(xs) if xs else None


def _median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def _rate(n: int, d: int) -> float | None:
    return n / d if d else None


def _fetch_json(url: str) -> dict[str, Any]:
    r = requests.get(
        url,
        timeout=TIMEOUT_SEC,
        headers={"Cache-Control": "no-cache", "User-Agent": VERSION},
    )
    r.raise_for_status()
    d = r.json()
    if not isinstance(d, dict):
        raise ValueError("JSON payload is not an object")
    return d


def fetch_official_settlement(ticker: str) -> str | None:
    q = quote(str(ticker), safe="-")
    for base in (LIVE_MARKET_BASE, HIST_MARKET_BASE):
        try:
            d = _fetch_json(base + q)
            market = d.get("market") if isinstance(d.get("market"), Mapping) else d
            if isinstance(market, Mapping):
                result = _side(market.get("result"))
                if result:
                    return result
        except Exception:
            continue
    return None


def extract_first_early(main_state: Mapping[str, Any], observed_at: datetime | None = None) -> dict[str, Any] | None:
    protected = adapter.protected_main_summary(main_state)
    early = protected["early"]
    if early.state != "QUALIFIED" or early.side not in {"UP", "DOWN"}:
        return None
    if early.ask is None or early.fair is None or early.edge is None:
        return None
    sec = protected.get("seconds_left")
    return {
        "contract": protected["contract"],
        "observed_at_utc": _iso(observed_at),
        "side": early.side,
        "ask": float(early.ask),
        "fair": float(early.fair),
        "edge": float(early.edge),
        "seconds_left": sec,
        "minutes_left": None if sec is None else float(sec) / 60.0,
        "ask_at_or_below_50c": bool(float(early.ask) <= 0.50 + 1e-12),
        "ask_in_25_35c": bool(0.25 - 1e-12 <= float(early.ask) <= 0.35 + 1e-12),
        "ask_at_or_below_45c": bool(float(early.ask) <= 0.45 + 1e-12),
        "orders": False,
        "manual_execution_only": True,
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
            "first_eligible_contract": None,
            "first_seen_seconds_left": {},
            "eligible_contracts": [],
            "coverage_excluded_late": {},
            "call_records": {},
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
            if prior in STATE.get("call_records", {}):
                STATE["pending_settlement"].setdefault(
                    prior,
                    _iso(now + timedelta(seconds=SETTLEMENT_INITIAL_DELAY_SEC)),
                )
            STATE["current_contract"] = contract
            if STATE.get("live_scoring_armed") is not True:
                STATE["live_scoring_armed"] = True
                STATE["live_scoring_armed_at_utc"] = _iso(now)
                print(
                    f"EARLY FORWARD ARMED | rollover={prior}->{contract} | at={_iso(now)} | "
                    "FRESH SAMPLE START | NO ORDERS",
                    flush=True,
                )

        if contract not in STATE["first_seen_seconds_left"]:
            STATE["first_seen_seconds_left"][contract] = left

        if STATE.get("live_scoring_armed") is not True:
            return

        if (
            contract not in STATE["eligible_contracts"]
            and contract not in STATE["coverage_excluded_late"]
        ):
            first_left = STATE["first_seen_seconds_left"].get(contract)
            if first_left is not None and float(first_left) >= EARLY_ELIGIBILITY_OPEN_SECONDS_LEFT - 1e-12:
                STATE["eligible_contracts"].append(contract)
                if STATE.get("first_eligible_contract") is None:
                    STATE["first_eligible_contract"] = contract
                print(
                    "EARLY COVERAGE-ELIGIBLE CONTRACT | "
                    f"{contract} | first_seen_left={float(first_left):.2f}s | "
                    "SEEN BEFORE EARLY 10M WINDOW | NO ORDERS",
                    flush=True,
                )
            else:
                STATE["coverage_excluded_late"][contract] = first_left
                print(
                    "EARLY COVERAGE EXCLUDED | "
                    f"{contract} | first_seen_left={first_left} | "
                    "EARLY WINDOW MAY HAVE ALREADY OPENED | NO ORDERS",
                    flush=True,
                )

        eligible = contract in STATE["eligible_contracts"]

    if not eligible:
        return

    rec = extract_first_early(main_state, observed_at=now)
    if rec is not None:
        with LOCK:
            if contract not in STATE["call_records"]:
                STATE["call_records"][contract] = rec
                print(
                    "EARLY FIRST OPPORTUNITY | "
                    f"{contract} | {rec['side']} | fair={rec['fair']:.3f} | edge={rec['edge']:.3f} | "
                    f"left={rec['minutes_left']:.2f}m | ask={rec['ask']:.3f} | "
                    f"ideal25_35={rec['ask_in_25_35c']} | <=50c={rec['ask_at_or_below_50c']} | NO ORDERS",
                    flush=True,
                )
                log_summary()


def _maybe_settle(now: datetime | None = None) -> None:
    now = now or _now()
    with LOCK:
        pending = dict(STATE.get("pending_settlement") or {})
    for contract, next_raw in pending.items():
        next_dt = _dt(next_raw)
        if next_dt is None or now < next_dt:
            continue
        official = fetch_official_settlement(contract)
        with LOCK:
            if official:
                STATE["settlements"][contract] = official
                STATE["pending_settlement"].pop(contract, None)
                rec = STATE["call_records"].get(contract)
                if rec:
                    print(
                        "EARLY SETTLED | "
                        f"{contract} | early={rec.get('side')} | official={official} | "
                        f"same_side={rec.get('side') == official} | ask={rec.get('ask')} | "
                        f"left={rec.get('minutes_left')}m | SECONDARY DIRECTION METRIC | NO ORDERS",
                        flush=True,
                    )
            else:
                STATE["pending_settlement"][contract] = _iso(
                    now + timedelta(seconds=SETTLEMENT_RETRY_SEC)
                )


def summarize_state() -> dict[str, Any]:
    with LOCK:
        eligible = list(STATE.get("eligible_contracts") or [])
        calls = [dict(x) for x in STATE.get("call_records", {}).values()]
        settlements = dict(STATE.get("settlements") or {})
        excluded = dict(STATE.get("coverage_excluded_late") or {})
        armed = STATE.get("live_scoring_armed") is True
        first_eligible = STATE.get("first_eligible_contract")
        startup = STATE.get("startup_contract")

    settled_calls: list[dict[str, Any]] = []
    for rec in calls:
        official = _side(settlements.get(rec["contract"]))
        if official:
            row = dict(rec)
            row["official_side"] = official
            row["same_side_as_settlement"] = row["side"] == official
            settled_calls.append(row)

    asks = [float(x["ask"]) for x in calls if _f(x.get("ask")) is not None]
    lefts = [float(x["minutes_left"]) for x in calls if _f(x.get("minutes_left")) is not None]
    fairs = [float(x["fair"]) for x in calls if _f(x.get("fair")) is not None]
    edges = [float(x["edge"]) for x in calls if _f(x.get("edge")) is not None]
    le50 = [x for x in calls if x.get("ask_at_or_below_50c") is True]
    ideal = [x for x in calls if x.get("ask_in_25_35c") is True]
    same_n = sum(x.get("same_side_as_settlement") is True for x in settled_calls)

    ready = bool(
        len(eligible) >= MIN_ELIGIBLE_CONTRACTS
        and len(settled_calls) >= MIN_SETTLED_EARLY_CALLS
    )

    return {
        "version": VERSION,
        "status": "EARLY_CONFIRMATION_SAMPLE_READY" if ready else "COLLECTING_EARLY_FORWARD",
        "fresh_start_semantics": "FIRST_POST_START_ROLLOVER",
        "coverage_universe_semantics": "FIRST_SEEN_BEFORE_EARLY_10M_ELIGIBILITY_WINDOW",
        "early_eligibility_open_seconds_left": EARLY_ELIGIBILITY_OPEN_SECONDS_LEFT,
        "startup_contract_excluded": startup,
        "live_scoring_armed": armed,
        "first_eligible_contract": first_eligible,
        "eligibility_complete_contracts": len(eligible),
        "coverage_excluded_late_n": len(excluded),
        "early_calls": len(calls),
        "early_only_coverage": _rate(len(calls), len(eligible)),
        "settled_early_calls": len(settled_calls),
        "settlement_same_side_n": same_n,
        "settlement_same_side_rate_secondary": _rate(same_n, len(settled_calls)),
        "avg_ask": _mean(asks),
        "median_ask": _median(asks),
        "ask_le_50c_n": len(le50),
        "ask_le_50c_rate": _rate(len(le50), len(calls)),
        "ask_25_35c_n": len(ideal),
        "ask_25_35c_rate": _rate(len(ideal), len(calls)),
        "avg_minutes_left": _mean(lefts),
        "median_minutes_left": _median(lefts),
        "avg_fair": _mean(fairs),
        "avg_edge": _mean(edges),
        "minimum_eligible_contracts": MIN_ELIGIBLE_CONTRACTS,
        "minimum_settled_early_calls": MIN_SETTLED_EARLY_CALLS,
        "sample_ready": ready,
        "settlement_accuracy_is_secondary_not_final_authority": True,
        "protected_early_thresholds_changed": False,
        "price_filter_added": False,
        "production_behavior_changed": False,
        "numeric_flip_risk_validated": False,
        "manual_execution_only": True,
        "orders": False,
        "call_records": calls,
        "settled_records": settled_calls,
    }


def log_summary() -> None:
    s = summarize_state()
    def fmt(v: Any, d: int = 3) -> str:
        return "NA" if v is None else f"{float(v):.{d}f}"
    print(
        "EARLY FORWARD V1 | "
        f"status={s['status']} | eligible={s['eligibility_complete_contracts']} | "
        f"excluded_late={s['coverage_excluded_late_n']} | calls={s['early_calls']} | "
        f"settled={s['settled_early_calls']} | coverage={fmt(s['early_only_coverage'])} | "
        f"settlement_same_side={fmt(s['settlement_same_side_rate_secondary'])} | "
        f"avg_left={fmt(s['avg_minutes_left'],2)}m | avg_ask={fmt(s['avg_ask'])} | "
        f"<=50c={s['ask_le_50c_n']} ({fmt(s['ask_le_50c_rate'])}) | "
        f"ideal25_35={s['ask_25_35c_n']} ({fmt(s['ask_25_35c_rate'])}) | "
        f"avg_edge={fmt(s['avg_edge'])} | ready={s['sample_ready']} | READ ONLY | NO ORDERS",
        flush=True,
    )


def observer_age_seconds(now: datetime | None = None) -> float | None:
    now = (now or _now()).astimezone(timezone.utc)
    with RUNTIME_LOCK:
        d = _dt(RUNTIME.get("observer_last_iteration_utc"))
    return None if d is None else max(0.0, (now - d).total_seconds())


def runtime_health(now: datetime | None = None) -> dict[str, Any]:
    age = observer_age_seconds(now)
    with RUNTIME_LOCK:
        out = dict(RUNTIME)
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
        "observer_last_iteration_utc": out.get("observer_last_iteration_utc"),
        "observer_last_success_utc": out.get("observer_last_success_utc"),
        "observer_last_exception": out.get("observer_last_exception"),
        "active_generation": int(out.get("active_generation") or 0),
    }


def _one_observer_iteration(now: datetime) -> None:
    main = _fetch_json(MAIN_STATE_URL)
    observer_cycle(main, observed_at=now)
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
                print(f"EARLY FORWARD WARNING | {msg} | FAIL CLOSED | NO ORDERS", flush=True)
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
        name=f"btc15-early-forward-worker-{generation}",
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
        age = observer_age_seconds(now)
        alive = bool(CURRENT_WORKER and CURRENT_WORKER.is_alive())
        stale = bool(age is None or age > OBSERVER_STALE_SEC)
        if not alive or stale:
            print(
                f"EARLY SUPERVISOR | replacing observer | alive={alive} | age={age} | "
                "COLLECTOR ONLY | PROTECTED EARLY UNCHANGED | NO ORDERS",
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
                "EARLY HEARTBEAT | "
                f"healthy={h['healthy']} | age={h['observer_age_sec']}s | restarts={h['observer_restarts']} | "
                f"eligible={s['eligibility_complete_contracts']} | calls={s['early_calls']} | "
                f"settled={s['settled_early_calls']} | READ ONLY | NO ORDERS",
                flush=True,
            )
        time.sleep(SUPERVISOR_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15EarlyForwardScorecardV1/1.0"

    def log_message(self, fmt, *args):
        print("EARLY_SCORECARD_HTTP | " + (fmt % args), flush=True)

    def _json(self, code: int, obj: Any):
        raw = json.dumps(obj, separators=(",", ":"), default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            h = runtime_health()
            with LOCK:
                err = STATE.get("last_error")
                last_poll = STATE.get("last_poll_utc")
            return self._json(200 if h["healthy"] else 503, {
                "ok": h["healthy"],
                "version": VERSION,
                "watchdog": h,
                "last_poll_utc": last_poll,
                "last_error": err,
                "protected_early_thresholds_changed": False,
                "production_behavior_changed": False,
                "numeric_flip_risk_validated": False,
                "manual_execution_only": True,
                "orders": False,
            })
        if path == "/state":
            return self._json(200, {
                "ok": True,
                "version": VERSION,
                "live": summarize_state(),
                "watchdog": runtime_health(),
                "orders": False,
                "manual_execution_only": True,
            })
        return self._json(404, {"ok": False, "orders": False, "error": "not_found"})

    def _reject(self):
        return self._json(405, {"ok": False, "orders": False, "error": "read_only_scorecard"})

    do_POST = _reject
    do_PUT = _reject
    do_PATCH = _reject
    do_DELETE = _reject


def main() -> int:
    with LOCK:
        STATE["started_at_utc"] = _iso()
    print(
        f"{VERSION} START | fresh sample arms on first post-start rollover | "
        "coverage universe = first seen before EARLY 10m window | "
        "protected EARLY read-only | watchdog supervised | NO ORDERS",
        flush=True,
    )
    threading.Thread(target=supervisor_loop, name="btc15-early-supervisor", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
