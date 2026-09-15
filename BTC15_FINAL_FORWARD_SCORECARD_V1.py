#!/usr/bin/env python3
"""
BTC15 protected FINAL forward scorecard V1.

READ ONLY | SIGNAL ONLY | MANUAL EXECUTION ONLY | NO ORDERS

Purpose
-------
1) Re-score the already-frozen fresh OOS protected FINAL calls across all four
   finished-product dimensions: accuracy, coverage, Kalshi ask/economics, timing.
2) Collect a NEW live forward confirmation sample from the production dashboard
   JSON without changing protected FINAL thresholds or production code.
3) Record only the FIRST protected FINAL LOCK per contract and later resolve it
   against official Kalshi settlement truth.

Important semantics
-------------------
- Protected FINAL remains selective. FINAL-only coverage is reported; it is NOT
  substituted for UNION actionable coverage.
- A directionally correct 90%+ lock at 90c+ is counted correct, but separately
  marked as an expensive/non-preferred entry. Accuracy and entry economics are
  intentionally not blended into one misleading metric.
- No numeric flip-risk percentage is emitted; that remains unvalidated.
- No orders. No auto-promotion. No threshold search.
"""
from __future__ import annotations

import csv
import json
import math
import os
import statistics
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote, urlparse

import requests

import btc15_main_protected_state_adapter_v1 as adapter

VERSION = "BTC15_FINAL_FORWARD_SCORECARD_V1"
PORT = int(os.environ.get("PORT", "8080"))
MAIN_STATE_URL = os.environ.get(
    "BTC15_MAIN_STATE_URL",
    "https://btc-15min-bot-production.up.railway.app/dashboard_state.json",
)
POLL_SEC = max(2.0, float(os.environ.get("FINAL_SCORECARD_POLL_SEC", "5")))
SETTLEMENT_RETRY_SEC = max(30.0, float(os.environ.get("FINAL_SETTLEMENT_RETRY_SEC", "60")))
TIMEOUT_SEC = 3.0

# Predeclared before live outcomes are inspected. The service is expected to be
# deployed during the 16:30-16:45 UTC contract; the first complete scored live
# contract begins at the next boundary.
LIVE_CUTOFF_RAW = "2026-09-15T16:45:00Z"
MIN_LIVE_OBSERVED_SMOKE = 30
MIN_LIVE_SETTLED_LOCKS_SMOKE = 12

HIST_CALLS = Path("fresh_oos_locked_final_calls.csv")
HIST_MANIFEST = Path("fresh_oos_market_manifest.csv")

LIVE_MARKET_BASE = "https://external-api.kalshi.com/trade-api/v2/markets/"
HIST_MARKET_BASE = "https://external-api.kalshi.com/trade-api/v2/historical/markets/"

LOCK = threading.RLock()
STATE: dict[str, Any] = {
    "started_at_utc": None,
    "last_poll_utc": None,
    "last_error": None,
    "current_contract": None,
    "observed_contracts": [],
    "lock_records": {},
    "settlements": {},
    "pending_settlement": {},
    "historical": None,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _dt(raw: Any) -> datetime:
    s = str(raw or "").strip()
    if not s:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


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
    return None if not xs else statistics.fmean(xs)


def _median(xs: list[float]) -> float | None:
    return None if not xs else statistics.median(xs)


def _rate(n: int, d: int) -> float | None:
    return None if not d else n / d


def price_band(ask: float | None) -> str:
    if ask is None:
        return "UNKNOWN"
    if ask < 0.25:
        return "<25C"
    if ask <= 0.35 + 1e-12:
        return "25-35C"
    if ask <= 0.50 + 1e-12:
        return "36-50C"
    if ask <= 0.70 + 1e-12:
        return "51-70C"
    if ask <= 0.85 + 1e-12:
        return "71-85C"
    return ">85C"


def timing_band(minutes_left: float | None) -> str:
    if minutes_left is None:
        return "UNKNOWN"
    if minutes_left >= 6:
        return ">=6M"
    if minutes_left >= 5:
        return "5-6M"
    if minutes_left >= 3:
        return "3-5M"
    return "<3M"


def _historical_universe_count(path: Path) -> int:
    if not path.exists():
        return 0
    seen: set[str] = set()
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as fh:
        for r in csv.DictReader(fh):
            t = str(r.get("ticker") or "").strip()
            if t:
                seen.add(t)
    return len(seen)


def summarize_historical(
    calls_path: Path = HIST_CALLS,
    manifest_path: Path = HIST_MANIFEST,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if calls_path.exists():
        with calls_path.open(newline="", encoding="utf-8-sig", errors="replace") as fh:
            for r in csv.DictReader(fh):
                ask = _f(r.get("preferred_ask"))
                left = _f(r.get("remaining"))
                fair = _f(r.get("preferred_fair"))
                correct = str(r.get("correct") or "").strip().lower() in {"1", "true", "yes", "y"}
                rows.append({
                    "ticker": str(r.get("ticker") or "").strip(),
                    "ask": ask,
                    "minutes_left": left,
                    "fair": fair,
                    "correct": correct,
                    "price_band": price_band(ask),
                    "timing_band": timing_band(left),
                })

    universe = _historical_universe_count(manifest_path)
    n = len(rows)
    correct_n = sum(bool(r["correct"]) for r in rows)
    asks = [float(r["ask"]) for r in rows if r["ask"] is not None]
    lefts = [float(r["minutes_left"]) for r in rows if r["minutes_left"] is not None]
    le50 = [r for r in rows if r["ask"] is not None and r["ask"] <= 0.50 + 1e-12]
    ideal = [r for r in rows if r["ask"] is not None and 0.25 - 1e-12 <= r["ask"] <= 0.35 + 1e-12]
    attractive = [r for r in rows if r["ask"] is not None and 0.20 - 1e-12 <= r["ask"] <= 0.40 + 1e-12]
    ge5 = [r for r in rows if r["minutes_left"] is not None and r["minutes_left"] >= 5.0 - 1e-12]

    by_price: dict[str, dict[str, Any]] = {}
    for band in ("<25C", "25-35C", "36-50C", "51-70C", "71-85C", ">85C"):
        z = [r for r in rows if r["price_band"] == band]
        by_price[band] = {
            "n": len(z),
            "correct_n": sum(bool(r["correct"]) for r in z),
            "accuracy": _rate(sum(bool(r["correct"]) for r in z), len(z)),
        }

    by_timing: dict[str, dict[str, Any]] = {}
    for band in (">=6M", "5-6M", "3-5M", "<3M"):
        z = [r for r in rows if r["timing_band"] == band]
        by_timing[band] = {
            "n": len(z),
            "correct_n": sum(bool(r["correct"]) for r in z),
            "accuracy": _rate(sum(bool(r["correct"]) for r in z), len(z)),
        }

    return {
        "source": "fresh_oos_locked_final_calls.csv",
        "universe_contracts": universe,
        "qualified_final_calls": n,
        "qualified_accuracy": _rate(correct_n, n),
        "qualified_correct_n": correct_n,
        "final_only_coverage": _rate(n, universe),
        "avg_minutes_left": _mean(lefts),
        "median_minutes_left": _median(lefts),
        "calls_ge_5m_n": len(ge5),
        "calls_ge_5m_rate": _rate(len(ge5), n),
        "avg_preferred_ask": _mean(asks),
        "median_preferred_ask": _median(asks),
        "ask_le_50c_n": len(le50),
        "ask_le_50c_rate": _rate(len(le50), n),
        "ask_le_50c_accuracy": _rate(sum(bool(r["correct"]) for r in le50), len(le50)),
        "ask_25_35c_n": len(ideal),
        "ask_20_40c_n": len(attractive),
        "ask_20_40c_rate": _rate(len(attractive), n),
        "by_price_band": by_price,
        "by_timing_band": by_timing,
        "target_accuracy_93_95_met": bool(n and correct_n / n >= 0.93),
        "price_preference_is_evaluation_only": True,
        "final_only_coverage_is_not_union_coverage": True,
        "rows": rows,
    }


def extract_first_lock(main_state: Mapping[str, Any], observed_at: datetime | None = None) -> dict[str, Any] | None:
    protected = adapter.protected_main_summary(main_state)
    final = protected["final"]
    if final.state != "LOCK" or final.side not in {"UP", "DOWN"} or final.fair is None:
        return None

    side = final.side
    ask = protected["up_ask"] if side == "UP" else protected["down_ask"]
    bid = protected["up_bid"] if side == "UP" else protected["down_bid"]
    sec = protected["seconds_left"]
    raw_final = main_state.get("final") if isinstance(main_state.get("final"), Mapping) else {}
    market = main_state.get("market") if isinstance(main_state.get("market"), Mapping) else {}

    return {
        "contract": protected["contract"],
        "observed_at_utc": _iso(observed_at),
        "side": side,
        "fair": float(final.fair),
        "seconds_left": sec,
        "minutes_left": None if sec is None else sec / 60.0,
        "preferred_ask": ask,
        "preferred_bid": bid,
        "price_band": price_band(ask),
        "timing_band": timing_band(None if sec is None else sec / 60.0),
        "ask_at_or_below_50c": bool(ask is not None and ask <= 0.50 + 1e-12),
        "ask_in_25_35c": bool(ask is not None and 0.25 - 1e-12 <= ask <= 0.35 + 1e-12),
        "kalshi_target": protected["kalshi_target"],
        "raw_recorded_final_call": raw_final.get("recorded_final_call") is True,
        "raw_final_ready": raw_final.get("ready") is True,
        "raw_recorded_side": _side(raw_final.get("recorded_side")),
        "raw_recorded_confidence": _f(raw_final.get("recorded_confidence")),
        "up_ask": protected["up_ask"],
        "down_ask": protected["down_ask"],
        "market_status": market.get("status"),
        "orders": False,
        "manual_execution_only": True,
    }


def _fetch_json(url: str) -> dict[str, Any]:
    r = requests.get(url, timeout=TIMEOUT_SEC, headers={"Cache-Control": "no-cache", "User-Agent": "BTC15-Final-Scorecard-V1"})
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
                s = _side(market.get("result"))
                if s:
                    return s
        except Exception:
            continue
    return None


def summarize_live_snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    observed = list(state.get("observed_contracts") or [])
    records = dict(state.get("lock_records") or {})
    settlements = dict(state.get("settlements") or {})

    settled_rows: list[dict[str, Any]] = []
    for contract, rec_any in records.items():
        rec = dict(rec_any)
        official = _side(settlements.get(contract))
        if official:
            rec["official_side"] = official
            rec["correct"] = rec.get("side") == official
            settled_rows.append(rec)

    lock_rows = [dict(x) for x in records.values()]
    asks = [float(x["preferred_ask"]) for x in lock_rows if _f(x.get("preferred_ask")) is not None]
    lefts = [float(x["minutes_left"]) for x in lock_rows if _f(x.get("minutes_left")) is not None]
    correct_n = sum(bool(x.get("correct")) for x in settled_rows)
    le50 = [x for x in lock_rows if x.get("ask_at_or_below_50c") is True]
    settled_le50 = [x for x in settled_rows if x.get("ask_at_or_below_50c") is True]

    sample_ready = bool(
        len(observed) >= MIN_LIVE_OBSERVED_SMOKE
        and len(settled_rows) >= MIN_LIVE_SETTLED_LOCKS_SMOKE
    )

    return {
        "version": VERSION,
        "status": "LIVE_SMOKE_SAMPLE_READY" if sample_ready else "COLLECTING_LIVE_FORWARD",
        "live_cutoff_utc": LIVE_CUTOFF_RAW,
        "observed_contracts": len(observed),
        "lock_calls": len(lock_rows),
        "settled_lock_calls": len(settled_rows),
        "settled_correct_n": correct_n,
        "qualified_accuracy": _rate(correct_n, len(settled_rows)),
        "final_only_coverage": _rate(len(lock_rows), len(observed)),
        "avg_minutes_left": _mean(lefts),
        "median_minutes_left": _median(lefts),
        "avg_preferred_ask": _mean(asks),
        "median_preferred_ask": _median(asks),
        "ask_le_50c_n": len(le50),
        "ask_le_50c_rate": _rate(len(le50), len(lock_rows)),
        "settled_ask_le_50c_n": len(settled_le50),
        "settled_ask_le_50c_accuracy": _rate(sum(bool(x.get("correct")) for x in settled_le50), len(settled_le50)),
        "calls_ge_5m_n": sum(bool(_f(x.get("minutes_left")) is not None and float(x["minutes_left"]) >= 5.0 - 1e-12) for x in lock_rows),
        "sample_ready": sample_ready,
        "minimum_observed_for_smoke": MIN_LIVE_OBSERVED_SMOKE,
        "minimum_settled_locks_for_smoke": MIN_LIVE_SETTLED_LOCKS_SMOKE,
        "numeric_flip_risk_validated": False,
        "protected_final_thresholds_changed": False,
        "price_filter_applied": False,
        "auto_promote_allowed": False,
        "production_behavior_changed": False,
        "orders": False,
        "manual_execution_only": True,
        "lock_records": lock_rows,
        "settled_records": settled_rows,
    }


def _log_summary(prefix: str = "FINAL FORWARD") -> None:
    with LOCK:
        s = summarize_live_snapshot(STATE)
    def fmt(v: Any, d: int = 3) -> str:
        return "NA" if v is None else f"{float(v):.{d}f}"
    print(
        f"{prefix} | status={s['status']} | cutoff={s['live_cutoff_utc']} | "
        f"observed={s['observed_contracts']} | locks={s['lock_calls']} | settled={s['settled_lock_calls']} | "
        f"accuracy={fmt(s['qualified_accuracy'])} | coverage={fmt(s['final_only_coverage'])} | "
        f"avg_left={fmt(s['avg_minutes_left'],2)}m | med_left={fmt(s['median_minutes_left'],2)}m | "
        f"avg_ask={fmt(s['avg_preferred_ask'])} | med_ask={fmt(s['median_preferred_ask'])} | "
        f"ask<=50c={s['ask_le_50c_n']} ({fmt(s['ask_le_50c_rate'])}) | "
        f"ready={s['sample_ready']} | READ ONLY | NO ORDERS",
        flush=True,
    )


def _maybe_settle(now: datetime) -> None:
    with LOCK:
        pending = dict(STATE.get("pending_settlement") or {})
    for contract, next_raw in pending.items():
        if contract in STATE.get("settlements", {}):
            continue
        if now < _dt(next_raw):
            continue
        official = fetch_official_settlement(contract)
        with LOCK:
            if official:
                STATE["settlements"][contract] = official
                STATE["pending_settlement"].pop(contract, None)
                rec = STATE["lock_records"].get(contract)
                if rec:
                    print(
                        "FINAL SETTLED | "
                        f"{contract} | call={rec.get('side')} | official={official} | "
                        f"correct={rec.get('side') == official} | left={rec.get('minutes_left')}m | "
                        f"ask={rec.get('preferred_ask')} | NO ORDERS",
                        flush=True,
                    )
            else:
                STATE["pending_settlement"][contract] = _iso(now + __import__("datetime").timedelta(seconds=SETTLEMENT_RETRY_SEC))


def observer_cycle(main_state: Mapping[str, Any], observed_at: datetime | None = None) -> None:
    now = observed_at or _now()
    cutoff = _dt(LIVE_CUTOFF_RAW)
    contract = str(main_state.get("contract") or "").strip()
    if not contract:
        raise ValueError("production dashboard state missing contract")

    with LOCK:
        STATE["last_poll_utc"] = _iso(now)
        prior = STATE.get("current_contract")
        STATE["current_contract"] = contract

        if prior and prior != contract and prior in STATE.get("lock_records", {}):
            STATE["pending_settlement"].setdefault(
                prior,
                _iso(now + __import__("datetime").timedelta(seconds=30)),
            )

        if now >= cutoff and contract not in STATE["observed_contracts"]:
            STATE["observed_contracts"].append(contract)
            print(f"FINAL OBSERVED CONTRACT | {contract} | {_iso(now)} | NO ORDERS", flush=True)

    if now < cutoff:
        return

    rec = extract_first_lock(main_state, observed_at=now)
    if rec is not None:
        with LOCK:
            if contract not in STATE["lock_records"]:
                STATE["lock_records"][contract] = rec
                print(
                    "FINAL FIRST LOCK | "
                    f"{contract} | {rec['side']} | fair={rec['fair']:.3f} | "
                    f"left={rec['minutes_left']:.2f}m | ask={rec['preferred_ask']} | "
                    f"band={rec['price_band']} | <=50c={rec['ask_at_or_below_50c']} | NO ORDERS",
                    flush=True,
                )
                _log_summary()


def observer_loop() -> None:
    print(
        f"{VERSION} START | cutoff={LIVE_CUTOFF_RAW} | first protected LOCK per contract | "
        "official Kalshi settlement truth | PRICE/TIMING SEPARATE FROM ACCURACY | "
        "READ ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS",
        flush=True,
    )
    while True:
        now = _now()
        try:
            main = _fetch_json(MAIN_STATE_URL)
            observer_cycle(main, observed_at=now)
            _maybe_settle(now)
            with LOCK:
                STATE["last_error"] = None
        except Exception as exc:
            with LOCK:
                STATE["last_error"] = f"{type(exc).__name__}:{exc}"
            print(
                f"FINAL FORWARD WARNING | {type(exc).__name__}: {exc} | "
                "FAIL CLOSED | RETRYING | NO ORDERS",
                flush=True,
            )
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15FinalScorecardV1/1.0"

    def log_message(self, fmt, *args):
        print("FINAL_SCORECARD_HTTP | " + (fmt % args), flush=True)

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
        if path == "/state":
            with LOCK:
                live = summarize_live_snapshot(STATE)
                hist = STATE.get("historical")
                err = STATE.get("last_error")
                last_poll = STATE.get("last_poll_utc")
            return self._json(200, {
                "ok": True,
                "version": VERSION,
                "historical": hist,
                "live": live,
                "last_poll_utc": last_poll,
                "last_error": err,
                "orders": False,
                "manual_execution_only": True,
            })
        if path == "/health":
            with LOCK:
                err = STATE.get("last_error")
                last_poll = STATE.get("last_poll_utc")
            return self._json(200 if last_poll else 503, {
                "ok": bool(last_poll),
                "version": VERSION,
                "last_poll_utc": last_poll,
                "last_error": err,
                "orders": False,
                "manual_execution_only": True,
                "protected_final_thresholds_changed": False,
                "numeric_flip_risk_validated": False,
            })
        return self._json(404, {"ok": False, "orders": False, "error": "not_found"})

    def _reject(self):
        return self._json(405, {"ok": False, "orders": False, "error": "read_only_scorecard"})

    do_POST = _reject
    do_PUT = _reject
    do_PATCH = _reject
    do_DELETE = _reject


def main() -> int:
    hist = summarize_historical()
    with LOCK:
        STATE["started_at_utc"] = _iso()
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

    threading.Thread(target=observer_loop, name="btc15-final-forward-observer", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
