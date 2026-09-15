#!/usr/bin/env python3
"""
BTC15 protected EARLY excursion forward scorecard V1.

READ ONLY | SIGNAL ONLY | MANUAL EXECUTION ONLY | NO ORDERS

Purpose
-------
Measure whether already-protected EARLY opportunities create tradable Kalshi
price moves after entry. This collector never qualifies EARLY itself and never
changes EARLY/FINAL/SCALP logic.

Frozen measurement semantics
----------------------------
- Coverage universe: contracts first seen with >=600s remaining.
- Startup contract excluded; fresh sample starts on first post-start rollover.
- Entry price: protected EARLY preferred-side ask at first QUALIFIED state.
- Tradable excursion: later same-side Kalshi BID minus entry ask.
  Using bid is intentionally conservative because it represents an executable
  exit price rather than a midpoint/mark.
- Descriptive move checkpoints only: +5c/+10c/+15c/+20c.
  They are measurement outputs, never future qualification gates.
- FINAL, if it later locks, is recorded only as a protected downstream state.
- Official settlement is secondary context, not the EARLY success definition.
- Review readiness: >=30 eligible contracts and >=10 completed EARLY excursions.
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

VERSION = "BTC15_EARLY_EXCURSION_FORWARD_V1"
PORT = 8080
MAIN_STATE_URL = "https://btc-15min-bot-production.up.railway.app/dashboard_state.json"
POLL_SEC = 5.0
TIMEOUT_SEC = 3.0
EARLY_ELIGIBILITY_OPEN_SECONDS_LEFT = 600.0
MIN_ELIGIBLE_CONTRACTS = 30
MIN_COMPLETED_EARLY_EXCURSIONS = 10
TARGETS = (0.05, 0.10, 0.15, 0.20)
SETTLEMENT_INITIAL_DELAY_SEC = 30.0
SETTLEMENT_RETRY_SEC = 60.0
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
    "armed": False,
    "armed_at_utc": None,
    "first_seen_seconds_left": {},
    "eligible_contracts": [],
    "excluded_late": {},
    "early_calls": {},
    "final_locks": {},
    "excursions": {},
    "completed_excursions": {},
    "settlements": {},
    "pending_settlement": {},
}

RUNTIME_LOCK = threading.RLock()
RUNTIME: dict[str, Any] = {
    "generation": 0,
    "restarts": 0,
    "last_iteration_utc": None,
    "last_success_utc": None,
    "last_exception": None,
    "iterations": 0,
    "successes": 0,
    "worker_alive": False,
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


def _mean(xs: list[float]) -> float | None:
    return statistics.fmean(xs) if xs else None


def _median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def _rate(n: int, d: int) -> float | None:
    return n / d if d else None


def _side(v: Any) -> str | None:
    x = str(v or "").strip().upper()
    if x in {"UP", "YES", "Y", "TRUE", "1"}:
        return "UP"
    if x in {"DOWN", "NO", "N", "FALSE", "0"}:
        return "DOWN"
    return None


def _fetch_json(url: str) -> dict[str, Any]:
    r = requests.get(url, timeout=TIMEOUT_SEC, headers={
        "Cache-Control": "no-cache", "User-Agent": VERSION,
    })
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


def _selected_quote(protected: Mapping[str, Any], side: str, kind: str) -> float | None:
    key = ("up_" if side == "UP" else "down_") + kind
    return _f(protected.get(key))


def _extract_early(protected: Mapping[str, Any], observed_at: datetime) -> dict[str, Any] | None:
    early = protected.get("early")
    if early is None or getattr(early, "state", None) != "QUALIFIED":
        return None
    side = getattr(early, "side", None)
    ask = _f(getattr(early, "ask", None))
    fair = _f(getattr(early, "fair", None))
    edge = _f(getattr(early, "edge", None))
    sec = _f(protected.get("seconds_left"))
    if side not in {"UP", "DOWN"} or None in (ask, fair, edge):
        return None
    return {
        "contract": str(protected.get("contract") or ""),
        "observed_at_utc": _iso(observed_at),
        "side": side,
        "entry_ask": ask,
        "fair": fair,
        "edge": edge,
        "seconds_left": sec,
        "minutes_left": None if sec is None else sec / 60.0,
        "ideal_25_35c": 0.25 - 1e-12 <= ask <= 0.35 + 1e-12,
        "at_or_below_50c": ask <= 0.50 + 1e-12,
        "orders": False,
    }


def _extract_final(protected: Mapping[str, Any], observed_at: datetime) -> dict[str, Any] | None:
    final = protected.get("final")
    if final is None or getattr(final, "state", None) != "LOCK":
        return None
    side = getattr(final, "side", None)
    fair = _f(getattr(final, "fair", None))
    sec = _f(protected.get("seconds_left"))
    if side not in {"UP", "DOWN"} or fair is None:
        return None
    return {
        "observed_at_utc": _iso(observed_at),
        "side": side,
        "fair": fair,
        "ask": _selected_quote(protected, side, "ask"),
        "seconds_left": sec,
        "minutes_left": None if sec is None else sec / 60.0,
    }


def _new_excursion(call: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "contract": call["contract"],
        "side": call["side"],
        "entry_ask": float(call["entry_ask"]),
        "entry_at_utc": call["observed_at_utc"],
        "entry_seconds_left": call.get("seconds_left"),
        "peak_bid": None,
        "peak_delta": None,
        "trough_bid": None,
        "trough_delta": None,
        "last_bid": None,
        "samples": 0,
        "targets": {f"+{int(t*100)}c": None for t in TARGETS},
        "final_side": None,
        "final_agrees": None,
        "final_minutes_left": None,
        "final_ask": None,
        "completed": False,
        "completed_at_utc": None,
    }


def _update_excursion(contract: str, protected: Mapping[str, Any], now: datetime) -> None:
    with LOCK:
        x = STATE.get("excursions", {}).get(contract)
        if not x or x.get("completed"):
            return
        side = x["side"]
        entry = float(x["entry_ask"])
        bid = _selected_quote(protected, side, "bid")
        sec = _f(protected.get("seconds_left"))
        if bid is not None:
            delta = bid - entry
            x["last_bid"] = bid
            x["samples"] = int(x.get("samples") or 0) + 1
            if x.get("peak_delta") is None or delta > float(x["peak_delta"]):
                x["peak_delta"] = delta
                x["peak_bid"] = bid
            if x.get("trough_delta") is None or delta < float(x["trough_delta"]):
                x["trough_delta"] = delta
                x["trough_bid"] = bid
            for t in TARGETS:
                key = f"+{int(t*100)}c"
                if x["targets"].get(key) is None and delta >= t - 1e-12:
                    entry_dt = _dt(x.get("entry_at_utc"))
                    elapsed = None if entry_dt is None else max(0.0, (now - entry_dt).total_seconds())
                    x["targets"][key] = {
                        "hit_at_utc": _iso(now),
                        "elapsed_seconds": elapsed,
                        "seconds_left": sec,
                        "bid": bid,
                    }
                    print(
                        f"EARLY EXCURSION TARGET | {contract} | {side} | {key} | "
                        f"entry={entry:.3f} bid={bid:.3f} | elapsed={elapsed}s | NO ORDERS",
                        flush=True,
                    )
        if contract not in STATE["final_locks"]:
            frec = _extract_final(protected, now)
            if frec is not None:
                STATE["final_locks"][contract] = frec
                x["final_side"] = frec["side"]
                x["final_agrees"] = frec["side"] == side
                x["final_minutes_left"] = frec.get("minutes_left")
                x["final_ask"] = frec.get("ask")


def _finalize_contract(contract: str, now: datetime) -> None:
    with LOCK:
        x = STATE.get("excursions", {}).get(contract)
        if not x or x.get("completed"):
            return
        x["completed"] = True
        x["completed_at_utc"] = _iso(now)
        STATE["completed_excursions"][contract] = dict(x)
        STATE["pending_settlement"].setdefault(
            contract, _iso(now + timedelta(seconds=SETTLEMENT_INITIAL_DELAY_SEC))
        )
        print(
            "EARLY EXCURSION COMPLETE | "
            f"{contract} | side={x['side']} | entry={x['entry_ask']:.3f} | "
            f"MFE={x.get('peak_delta')} | MAE={x.get('trough_delta')} | "
            f"+10c={x['targets'].get('+10c') is not None} | "
            f"FINAL={x.get('final_side')} | NO ORDERS",
            flush=True,
        )
        log_summary()


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
        _finalize_contract(str(prior), now)
        with LOCK:
            STATE["current_contract"] = contract
            if STATE.get("armed") is not True:
                STATE["armed"] = True
                STATE["armed_at_utc"] = _iso(now)
                print(
                    f"EARLY EXCURSION ARMED | rollover={prior}->{contract} | "
                    f"at={_iso(now)} | STARTUP EXCLUDED | NO ORDERS",
                    flush=True,
                )

    with LOCK:
        STATE["first_seen_seconds_left"].setdefault(contract, left)
        if STATE.get("armed") is not True:
            return
        if contract not in STATE["eligible_contracts"] and contract not in STATE["excluded_late"]:
            first_left = STATE["first_seen_seconds_left"].get(contract)
            if first_left is not None and float(first_left) >= EARLY_ELIGIBILITY_OPEN_SECONDS_LEFT - 1e-12:
                STATE["eligible_contracts"].append(contract)
                print(
                    f"EARLY EXCURSION ELIGIBLE | {contract} | first_seen_left={float(first_left):.2f}s | NO ORDERS",
                    flush=True,
                )
            else:
                STATE["excluded_late"][contract] = first_left
                print(
                    f"EARLY EXCURSION EXCLUDED LATE | {contract} | first_seen_left={first_left} | NO ORDERS",
                    flush=True,
                )
        eligible = contract in STATE["eligible_contracts"]

    if not eligible:
        return

    with LOCK:
        have_call = contract in STATE["early_calls"]
    if not have_call:
        rec = _extract_early(protected, now)
        if rec is not None:
            with LOCK:
                if contract not in STATE["early_calls"]:
                    STATE["early_calls"][contract] = rec
                    STATE["excursions"][contract] = _new_excursion(rec)
                    print(
                        "EARLY EXCURSION ENTRY | "
                        f"{contract} | {rec['side']} | ask={rec['entry_ask']:.3f} | "
                        f"fair={rec['fair']:.3f} edge={rec['edge']:.3f} | "
                        f"left={rec['minutes_left']:.2f}m | NO ORDERS",
                        flush=True,
                    )
                    log_summary()

    _update_excursion(contract, protected, now)


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
                x = STATE.get("completed_excursions", {}).get(contract)
                if x:
                    print(
                        f"EARLY EXCURSION SETTLED | {contract} | early={x['side']} | "
                        f"official={official} | same_side={x['side'] == official} | "
                        "SECONDARY ONLY | NO ORDERS",
                        flush=True,
                    )
            else:
                STATE["pending_settlement"][contract] = _iso(now + timedelta(seconds=SETTLEMENT_RETRY_SEC))


def summarize_state() -> dict[str, Any]:
    with LOCK:
        eligible = list(STATE.get("eligible_contracts") or [])
        calls = [dict(x) for x in STATE.get("early_calls", {}).values()]
        completed = [dict(x) for x in STATE.get("completed_excursions", {}).values()]
        settlements = dict(STATE.get("settlements") or {})
        excluded = dict(STATE.get("excluded_late") or {})
        armed = STATE.get("armed") is True

    asks = [float(x["entry_ask"]) for x in calls]
    lefts = [float(x["minutes_left"]) for x in calls if _f(x.get("minutes_left")) is not None]
    mfes = [float(x["peak_delta"]) for x in completed if _f(x.get("peak_delta")) is not None]
    maes = [float(x["trough_delta"]) for x in completed if _f(x.get("trough_delta")) is not None]
    final_rows = [x for x in completed if x.get("final_side") in {"UP", "DOWN"}]
    settle_rows = [x for x in completed if _side(settlements.get(x["contract"]))]
    target_counts = {
        f"hit_{int(t*100)}c_n": sum(x.get("targets", {}).get(f"+{int(t*100)}c") is not None for x in completed)
        for t in TARGETS
    }
    ready = len(eligible) >= MIN_ELIGIBLE_CONTRACTS and len(completed) >= MIN_COMPLETED_EARLY_EXCURSIONS
    out = {
        "version": VERSION,
        "status": "EARLY_EXCURSION_REVIEW_SAMPLE_READY" if ready else "COLLECTING_EARLY_EXCURSION_FORWARD",
        "coverage_universe_semantics": "FIRST_SEEN_BEFORE_EARLY_10M_WINDOW",
        "fresh_start_semantics": "FIRST_POST_START_ROLLOVER",
        "eligible_contracts": len(eligible),
        "excluded_late_n": len(excluded),
        "early_calls": len(calls),
        "early_coverage": _rate(len(calls), len(eligible)),
        "completed_early_excursions": len(completed),
        "avg_entry_ask": _mean(asks),
        "median_entry_ask": _median(asks),
        "ideal_25_35c_n": sum(x.get("ideal_25_35c") is True for x in calls),
        "ideal_25_35c_rate": _rate(sum(x.get("ideal_25_35c") is True for x in calls), len(calls)),
        "avg_entry_minutes_left": _mean(lefts),
        "median_entry_minutes_left": _median(lefts),
        "avg_mfe": _mean(mfes),
        "median_mfe": _median(mfes),
        "avg_mae": _mean(maes),
        "median_mae": _median(maes),
        "final_seen_after_early_n": len(final_rows),
        "final_agreement_rate": _rate(sum(x.get("final_agrees") is True for x in final_rows), len(final_rows)),
        "settled_early_n": len(settle_rows),
        "settlement_same_side_rate_secondary": _rate(
            sum(x["side"] == _side(settlements.get(x["contract"])) for x in settle_rows), len(settle_rows)
        ),
        "sample_ready": ready,
        "orders": False,
        "manual_execution_only": True,
        "production_behavior_changed": False,
        "early_thresholds_changed": False,
    }
    for t in TARGETS:
        k = f"hit_{int(t*100)}c_n"
        out[k] = target_counts[k]
        out[f"hit_{int(t*100)}c_rate"] = _rate(target_counts[k], len(completed))
    return out


def log_summary() -> None:
    s = summarize_state()
    def fmt(v: Any, d: int = 3) -> str:
        return "NA" if v is None else f"{float(v):.{d}f}"
    print(
        "EARLY EXCURSION V1 | "
        f"status={s['status']} | eligible={s['eligible_contracts']} | calls={s['early_calls']} | "
        f"complete={s['completed_early_excursions']} | coverage={fmt(s['early_coverage'])} | "
        f"avg_ask={fmt(s['avg_entry_ask'])} | avg_mfe={fmt(s['avg_mfe'])} | avg_mae={fmt(s['avg_mae'])} | "
        f"+5={s['hit_5c_n']} +10={s['hit_10c_n']} +15={s['hit_15c_n']} +20={s['hit_20c_n']} | "
        f"ready={s['sample_ready']} | READ ONLY | NO ORDERS",
        flush=True,
    )


def reset_state_for_tests() -> None:
    global CURRENT_WORKER
    with LOCK:
        STATE.update({
            "started_at_utc": None, "last_poll_utc": None, "last_error": None,
            "current_contract": None, "startup_contract": None, "armed": False,
            "armed_at_utc": None, "first_seen_seconds_left": {},
            "eligible_contracts": [], "excluded_late": {}, "early_calls": {},
            "final_locks": {}, "excursions": {}, "completed_excursions": {},
            "settlements": {}, "pending_settlement": {},
        })
    with RUNTIME_LOCK:
        RUNTIME.update({
            "generation": 0, "restarts": 0, "last_iteration_utc": None,
            "last_success_utc": None, "last_exception": None, "iterations": 0,
            "successes": 0, "worker_alive": False, "last_heartbeat_log_monotonic": 0.0,
        })
    CURRENT_WORKER = None


def runtime_health(now: datetime | None = None) -> dict[str, Any]:
    now = now or _now()
    with RUNTIME_LOCK:
        last = _dt(RUNTIME.get("last_iteration_utc"))
        alive = bool(RUNTIME.get("worker_alive"))
        restarts = int(RUNTIME.get("restarts") or 0)
        err = RUNTIME.get("last_exception")
    age = None if last is None else max(0.0, (now - last).total_seconds())
    return {
        "healthy": bool(alive and age is not None and age <= OBSERVER_STALE_SEC),
        "observer_age_sec": age,
        "observer_stale_sec": OBSERVER_STALE_SEC,
        "observer_worker_alive": alive,
        "observer_restarts": restarts,
        "observer_last_exception": err,
    }


def _worker_loop(generation: int) -> None:
    with RUNTIME_LOCK:
        RUNTIME["worker_alive"] = True
    try:
        while True:
            with RUNTIME_LOCK:
                if generation != int(RUNTIME.get("generation") or 0):
                    return
                RUNTIME["iterations"] = int(RUNTIME.get("iterations") or 0) + 1
                RUNTIME["last_iteration_utc"] = _iso()
            now = _now()
            try:
                observer_cycle(_fetch_json(MAIN_STATE_URL), now)
                _maybe_settle(now)
                with RUNTIME_LOCK:
                    RUNTIME["successes"] = int(RUNTIME.get("successes") or 0) + 1
                    RUNTIME["last_success_utc"] = _iso(now)
                    RUNTIME["last_exception"] = None
                with LOCK:
                    STATE["last_error"] = None
            except Exception as exc:
                msg = f"{type(exc).__name__}:{exc}"
                with RUNTIME_LOCK:
                    RUNTIME["last_exception"] = msg
                with LOCK:
                    STATE["last_error"] = msg
                print(f"EARLY EXCURSION WARNING | {msg} | FAIL CLOSED | NO ORDERS", flush=True)
            time.sleep(POLL_SEC)
    finally:
        with RUNTIME_LOCK:
            if generation == int(RUNTIME.get("generation") or 0):
                RUNTIME["worker_alive"] = False


def _start_worker(*, replacement: bool) -> threading.Thread:
    global CURRENT_WORKER
    with RUNTIME_LOCK:
        RUNTIME["generation"] = int(RUNTIME.get("generation") or 0) + 1
        generation = int(RUNTIME["generation"])
        if replacement:
            RUNTIME["restarts"] = int(RUNTIME.get("restarts") or 0) + 1
        RUNTIME["worker_alive"] = True
        RUNTIME["last_iteration_utc"] = _iso()
    t = threading.Thread(target=_worker_loop, args=(generation,), daemon=True, name=f"early-excursion-v1-{generation}")
    CURRENT_WORKER = t
    t.start()
    return t


def supervisor_loop() -> None:
    global CURRENT_WORKER
    _start_worker(replacement=False)
    while True:
        now = _now()
        h = runtime_health(now)
        alive = bool(CURRENT_WORKER and CURRENT_WORKER.is_alive())
        if not alive or not h["healthy"]:
            print(
                f"EARLY EXCURSION SUPERVISOR | replacing observer | alive={alive} | age={h['observer_age_sec']} | NO ORDERS",
                flush=True,
            )
            _start_worker(replacement=True)
        mono = time.monotonic()
        with RUNTIME_LOCK:
            due = mono - float(RUNTIME.get("last_heartbeat_log_monotonic") or 0.0) >= HEARTBEAT_LOG_SEC
            if due:
                RUNTIME["last_heartbeat_log_monotonic"] = mono
        if due:
            s = summarize_state()
            h = runtime_health(now)
            print(
                "EARLY EXCURSION HEARTBEAT | "
                f"healthy={h['healthy']} restarts={h['observer_restarts']} | "
                f"eligible={s['eligible_contracts']} calls={s['early_calls']} complete={s['completed_early_excursions']} | "
                "READ ONLY | NO ORDERS",
                flush=True,
            )
        time.sleep(SUPERVISOR_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15EarlyExcursionV1/1.0"
    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"EARLY_EXCURSION_HTTP | {fmt % args}", flush=True)
    def _json(self, status: int, payload: Mapping[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            h = runtime_health()
            return self._json(200 if h["healthy"] else 503, {
                "ok": h["healthy"], "version": VERSION, "watchdog": h,
                "orders": False, "manual_execution_only": True,
                "early_thresholds_changed": False,
            })
        if path == "/state":
            return self._json(200, {
                "ok": True, "version": VERSION, "live": summarize_state(),
                "watchdog": runtime_health(), "orders": False,
                "manual_execution_only": True,
            })
        self._json(404, {"ok": False})


def main() -> int:
    with LOCK:
        STATE["started_at_utc"] = _iso()
    print(
        f"{VERSION} START | startup contract excluded | first_seen>=600s | "
        "entry=protected EARLY ask | excursion=selected-side live BID-entry ask | "
        "+5/+10/+15/+20 DESCRIPTIVE ONLY | READ ONLY | NO ORDERS",
        flush=True,
    )
    threading.Thread(target=supervisor_loop, daemon=True, name="early-excursion-supervisor").start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
