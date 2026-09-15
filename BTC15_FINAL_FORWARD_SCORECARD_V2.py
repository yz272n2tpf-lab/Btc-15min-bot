#!/usr/bin/env python3
"""
BTC15 protected FINAL forward scorecard V2.

READ ONLY | SIGNAL ONLY | MANUAL EXECUTION ONLY | NO ORDERS

V2 preserves the frozen V1 scorecard and adds one live-sample integrity rule:
a newly started observer never counts the contract already in progress. Live
scoring arms only after the first observed contract rollover at/after the frozen
cutoff, guaranteeing the first counted contract is observed from its beginning.

Protected FINAL qualification is not recalculated or changed.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

import BTC15_FINAL_FORWARD_SCORECARD_V1 as v1

VERSION = "BTC15_FINAL_FORWARD_SCORECARD_V2"
LIVE_CUTOFF_RAW = v1.LIVE_CUTOFF_RAW
PORT = v1.PORT
POLL_SEC = v1.POLL_SEC
MAIN_STATE_URL = v1.MAIN_STATE_URL

# Reuse the V1 state object so V1 settlement helpers and historical summaries
# operate on exactly the same records. These keys are V2 sample-integrity only.
STATE = v1.STATE
STATE.setdefault("startup_contract", None)
STATE.setdefault("live_scoring_armed", False)
STATE.setdefault("live_scoring_armed_at_utc", None)
STATE.setdefault("first_full_contract", None)

LOCK = v1.LOCK


def reset_live_state_for_tests() -> None:
    """Test helper only; never called by runtime main()."""
    with LOCK:
        STATE.update({
            "started_at_utc": None,
            "last_poll_utc": None,
            "last_error": None,
            "current_contract": None,
            "startup_contract": None,
            "live_scoring_armed": False,
            "live_scoring_armed_at_utc": None,
            "first_full_contract": None,
            "observed_contracts": [],
            "lock_records": {},
            "settlements": {},
            "pending_settlement": {},
            "historical": None,
        })


def summarize_live_snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    out = v1.summarize_live_snapshot(state)
    out["version"] = VERSION
    out["live_scoring_armed"] = bool(state.get("live_scoring_armed") is True)
    out["live_scoring_armed_at_utc"] = state.get("live_scoring_armed_at_utc")
    out["first_full_contract"] = state.get("first_full_contract")
    out["startup_contract_excluded"] = state.get("startup_contract")
    out["partial_start_contract_counted"] = False
    return out


def observer_cycle(main_state: Mapping[str, Any], observed_at: datetime | None = None) -> None:
    now = observed_at or datetime.now(timezone.utc)
    cutoff = v1._dt(LIVE_CUTOFF_RAW)
    contract = str(main_state.get("contract") or "").strip()
    if not contract:
        raise ValueError("production dashboard state missing contract")

    with LOCK:
        STATE["last_poll_utc"] = v1._iso(now)
        prior = STATE.get("current_contract")

        # First poll establishes the in-progress contract only. It is never
        # eligible for the forward universe because we did not witness its start.
        if not prior:
            STATE["current_contract"] = contract
            STATE["startup_contract"] = contract
            return

        changed = prior != contract
        if changed:
            if prior in STATE.get("lock_records", {}):
                STATE["pending_settlement"].setdefault(
                    prior,
                    v1._iso(now + __import__("datetime").timedelta(seconds=30)),
                )
            STATE["current_contract"] = contract

            # Arm only on a rollover at/after the frozen cutoff. This works both
            # when the process starts before cutoff and when it starts mid-contract
            # after cutoff: the new contract is the first one fully observed.
            if now >= cutoff and STATE.get("live_scoring_armed") is not True:
                STATE["live_scoring_armed"] = True
                STATE["live_scoring_armed_at_utc"] = v1._iso(now)
                STATE["first_full_contract"] = contract
                print(
                    "FINAL FORWARD ARMED | "
                    f"rollover={prior}->{contract} | at={v1._iso(now)} | "
                    "FIRST FULL CONTRACT | NO ORDERS",
                    flush=True,
                )

        if STATE.get("live_scoring_armed") is True and contract not in STATE["observed_contracts"]:
            STATE["observed_contracts"].append(contract)
            print(f"FINAL OBSERVED CONTRACT | {contract} | {v1._iso(now)} | NO ORDERS", flush=True)

        armed = STATE.get("live_scoring_armed") is True

    if not armed:
        return

    rec = v1.extract_first_lock(main_state, observed_at=now)
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
                log_summary()


def log_summary(prefix: str = "FINAL FORWARD V2") -> None:
    with LOCK:
        s = summarize_live_snapshot(STATE)

    def fmt(v: Any, d: int = 3) -> str:
        return "NA" if v is None else f"{float(v):.{d}f}"

    print(
        f"{prefix} | status={s['status']} | cutoff={s['live_cutoff_utc']} | "
        f"armed={s['live_scoring_armed']} | first_full={s['first_full_contract']} | "
        f"observed={s['observed_contracts']} | locks={s['lock_calls']} | settled={s['settled_lock_calls']} | "
        f"accuracy={fmt(s['qualified_accuracy'])} | coverage={fmt(s['final_only_coverage'])} | "
        f"avg_left={fmt(s['avg_minutes_left'],2)}m | med_left={fmt(s['median_minutes_left'],2)}m | "
        f"avg_ask={fmt(s['avg_preferred_ask'])} | med_ask={fmt(s['median_preferred_ask'])} | "
        f"ask<=50c={s['ask_le_50c_n']} ({fmt(s['ask_le_50c_rate'])}) | "
        f"ready={s['sample_ready']} | READ ONLY | NO ORDERS",
        flush=True,
    )


def observer_loop() -> None:
    print(
        f"{VERSION} START | frozen_cutoff={LIVE_CUTOFF_RAW} | ARM ON FIRST POST-CUTOFF ROLLOVER | "
        "first protected LOCK per full contract | official Kalshi settlement truth | "
        "PRICE/TIMING SEPARATE FROM ACCURACY | READ ONLY | SIGNAL ONLY | NO ORDERS",
        flush=True,
    )
    while True:
        now = datetime.now(timezone.utc)
        try:
            main = v1._fetch_json(MAIN_STATE_URL)
            observer_cycle(main, observed_at=now)
            v1._maybe_settle(now)
            with LOCK:
                STATE["last_error"] = None
        except Exception as exc:
            with LOCK:
                STATE["last_error"] = f"{type(exc).__name__}:{exc}"
            print(
                f"FINAL FORWARD V2 WARNING | {type(exc).__name__}: {exc} | "
                "FAIL CLOSED | RETRYING | NO ORDERS",
                flush=True,
            )
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15FinalScorecardV2/1.0"

    def log_message(self, fmt, *args):
        print("FINAL_SCORECARD_V2_HTTP | " + (fmt % args), flush=True)

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
                "partial_start_contract_counted": False,
            })
        return self._json(404, {"ok": False, "orders": False, "error": "not_found"})

    def _reject(self):
        return self._json(405, {"ok": False, "orders": False, "error": "read_only_scorecard"})

    do_POST = _reject
    do_PUT = _reject
    do_PATCH = _reject
    do_DELETE = _reject


def main() -> int:
    hist = v1.summarize_historical()
    with LOCK:
        STATE["started_at_utc"] = v1._iso()
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
    threading.Thread(target=observer_loop, name="btc15-final-forward-v2-observer", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
