#!/usr/bin/env python3
"""
BTC15 combined-system fresh-forward scorecard V1.

READ ONLY | SIGNAL ONLY | MANUAL EXECUTION ONLY | NO ORDERS

Observes the existing V6 combined display bridge plus frozen V5 serial scalp
state. It records already-evaluated protected EARLY, serial SCALP, and protected
FINAL evidence on one common contract timeline. It never re-qualifies or changes
any module threshold.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import quote, urlparse

import requests

from btc15_combined_empirical_scorecard_v2 import score_records

VERSION = "BTC15_COMBINED_FORWARD_SCORECARD_V1"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(1.0, float(os.environ.get("COMBINED_SCORECARD_POLL_SEC", "2")))
TIMEOUT_SEC = 3.0
SETTLEMENT_RETRY_SEC = 60.0
SETTLEMENT_INITIAL_DELAY_SEC = 45.0

COMBINED_URL = os.environ.get(
    "BTC15_COMBINED_V6_URL",
    "https://scalp-display-bridge-v6-production.up.railway.app/combined-state",
)
SCALP_URL = os.environ.get(
    "BTC15_SCALP_V5_URL",
    "https://scalp-move-shadow-v1-production.up.railway.app/state",
)

LIVE_CUTOFF_RAW = "2026-09-15T18:00:00Z"
MIN_FULL_CONTRACTS = 30
MIN_SETTLED_CONTRACTS = 25

LIVE_MARKET_BASE = "https://external-api.kalshi.com/trade-api/v2/markets/"
HIST_MARKET_BASE = "https://external-api.kalshi.com/trade-api/v2/historical/markets/"

LOCK = threading.RLock()
STATE: dict[str, Any] = {
    "started_at_utc": None,
    "last_poll_utc": None,
    "last_error": None,
    "current_contract": None,
    "startup_contract": None,
    "live_scoring_armed": False,
    "live_scoring_armed_at_utc": None,
    "first_full_contract": None,
    "records": {},
    "pending_settlement": {},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime | None = None) -> str:
    return (d or _now()).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _dt(v: Any) -> datetime:
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
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
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _side(v: Any) -> str | None:
    x = str(v or "").strip().upper()
    if x in {"UP", "YES", "Y", "TRUE", "1"}:
        return "UP"
    if x in {"DOWN", "NO", "N", "FALSE", "0"}:
        return "DOWN"
    return None


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
                s = _side(market.get("result"))
                if s:
                    return s
        except Exception:
            continue
    return None


def validate_payloads(combined: Mapping[str, Any], scalp: Mapping[str, Any]) -> str:
    if combined.get("version") != "BTC15_COMBINED_STATE_BRIDGE_V6":
        raise ValueError("expected V6 combined-state bridge")
    if combined.get("orders") is not False or combined.get("manual_execution_only") is not True:
        raise ValueError("combined safety envelope invalid")
    if combined.get("order_action") is not None:
        raise ValueError("combined order_action must remain null")
    if combined.get("numeric_flip_risk_validated") is not False:
        raise ValueError("numeric flip risk must remain unvalidated")
    if combined.get("scalp_entry_price_filter_applied") is not False:
        raise ValueError("scalp price must remain telemetry-only")

    if scalp.get("version") != "GENERALIZED_SCALP_INTEGRATION_V5":
        raise ValueError("expected frozen V5 scalp-state")
    if scalp.get("orders") is not False or scalp.get("manual_execution_only") is not True:
        raise ValueError("scalp safety envelope invalid")
    if scalp.get("order_action") is not None:
        raise ValueError("scalp order_action must remain null")
    if scalp.get("lifecycle_ended_unarmed_is_actionable_exit") is not False:
        raise ValueError("ENDED_UNARMED cannot become actionable EXIT")
    if scalp.get("armed_no_exit_reset_allowed") is not False:
        raise ValueError("armed/no-exit reset loophole detected")

    cc = str(combined.get("contract") or "").strip()
    sc = str(scalp.get("contract") or "").strip()
    if not cc or cc != sc:
        raise ValueError("combined/scalp contract mismatch")
    return cc


def _new_record(contract: str) -> dict[str, Any]:
    return {
        "contract": contract,
        "official_side": None,
        "early": {},
        "final": {},
        "scalps": [],
    }


def _opp_key(row: Mapping[str, Any]) -> str:
    cid = str(row.get("candidate_id") or "").strip()
    if cid:
        return "cid:" + cid
    idx = row.get("opportunity_index")
    return "opp:" + str(idx) if idx is not None else ""


def _merge_scalp(record: dict[str, Any], incoming: Mapping[str, Any]) -> bool:
    row = dict(incoming)
    key = _opp_key(row)
    if not key:
        return False
    rows = record.setdefault("scalps", [])
    for i, old in enumerate(rows):
        if _opp_key(old) != key:
            continue
        merged = dict(old)
        for k, v in row.items():
            if v is not None and v != "":
                if k == "peak_exec_gain":
                    old_peak = _f(merged.get(k))
                    new_peak = _f(v)
                    if new_peak is not None and (old_peak is None or new_peak > old_peak):
                        merged[k] = new_peak
                elif k == "entry_seconds_left" and merged.get(k) is not None:
                    pass
                else:
                    merged[k] = v
        rows[i] = merged
        return False
    rows.append(row)
    return True


def _capture_modules(record: dict[str, Any], combined: Mapping[str, Any]) -> tuple[bool, bool]:
    early_new = False
    final_new = False

    early = dict(combined.get("early") or {})
    if not record.get("early") and str(early.get("state") or "").upper() == "QUALIFIED":
        side = _side(early.get("side"))
        if side:
            record["early"] = {
                "state": "QUALIFIED",
                "side": side,
                "ask": _f(early.get("ask")),
                "fair": _f(early.get("fair")),
                "edge": _f(early.get("edge")),
                "seconds_left": _f(early.get("seconds_left", combined.get("canonical_seconds_left"))),
            }
            early_new = True

    final = dict(combined.get("final") or {})
    fstate = str(final.get("state") or "WATCH").upper()
    if not record.get("final") and fstate in {"QUALIFIED", "LOCK"}:
        side = _side(final.get("side"))
        if side:
            ask_key = "up_ask" if side == "UP" else "down_ask"
            record["final"] = {
                "state": fstate,
                "side": side,
                "ask": _f(combined.get(ask_key)),
                "fair": _f(final.get("fair")),
                "seconds_left": _f(final.get("seconds_left", combined.get("canonical_seconds_left"))),
            }
            final_new = True

    return early_new, final_new


def _capture_scalps(record: dict[str, Any], scalp: Mapping[str, Any]) -> int:
    added = 0
    for t_any in scalp.get("terminal_history") or ():
        if not isinstance(t_any, Mapping):
            continue
        t = dict(t_any)
        terminal = str(t.get("terminal_state") or "").upper()
        if terminal == "ENDED_UNARMED" and t.get("actionable_exit") is True:
            raise ValueError("ENDED_UNARMED actionable-exit invariant violated")
        row = {
            "candidate_id": t.get("candidate_id"),
            "opportunity_index": t.get("opportunity_index"),
            "state": terminal,
            "terminal_state": terminal,
            "completed": True,
            "side": _side(t.get("side")),
            "entry_price": _f(t.get("entry_price")),
            "exit_gain": _f(t.get("exit_gain")),
            "peak_exec_gain": _f(t.get("peak_exec_gain")),
            "adverse_exec_gain": _f(t.get("adverse_exec_gain")),
            "actionable_exit": bool(t.get("actionable_exit") is True),
            "terminal_time_utc": t.get("terminal_time_utc"),
        }
        added += int(_merge_scalp(record, row))

    state = str(scalp.get("state") or "PASS").upper()
    cid = str(scalp.get("candidate_id") or "").strip()
    if cid and state in {"ACTIVE", "PROTECT", "EXIT"}:
        row = {
            "candidate_id": cid,
            "opportunity_index": scalp.get("opportunity_index"),
            "state": state,
            "completed": False,
            "side": _side(scalp.get("side")),
            "entry_price": _f(scalp.get("entry_price")),
            "current_bid": _f(scalp.get("current_bid")),
            "exec_gain": _f(scalp.get("exec_gain")),
            "peak_exec_gain": _f(scalp.get("peak_exec_gain")),
            "entry_seconds_left": _f(scalp.get("entry_seconds_left")),
        }
        added += int(_merge_scalp(record, row))
    return added


def reset_state_for_tests() -> None:
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
            "records": {},
            "pending_settlement": {},
        })


def observer_cycle(combined: Mapping[str, Any], scalp: Mapping[str, Any], *, observed_at: datetime | None = None) -> None:
    now = observed_at or _now()
    contract = validate_payloads(combined, scalp)
    cutoff = _dt(LIVE_CUTOFF_RAW)

    with LOCK:
        STATE["last_poll_utc"] = _iso(now)
        prior = STATE.get("current_contract")

        if not prior:
            STATE["current_contract"] = contract
            STATE["startup_contract"] = contract
            return

        if prior != contract:
            if prior in STATE["records"]:
                STATE["pending_settlement"].setdefault(
                    prior,
                    _iso(now + timedelta(seconds=SETTLEMENT_INITIAL_DELAY_SEC)),
                )
            STATE["current_contract"] = contract

            if now >= cutoff and STATE.get("live_scoring_armed") is not True:
                STATE["live_scoring_armed"] = True
                STATE["live_scoring_armed_at_utc"] = _iso(now)
                STATE["first_full_contract"] = contract
                print(
                    f"COMBINED FORWARD ARMED | rollover={prior}->{contract} | at={_iso(now)} | "
                    "FIRST FULL CONTRACT | NO ORDERS",
                    flush=True,
                )

        if STATE.get("live_scoring_armed") is not True:
            return

        if contract not in STATE["records"]:
            STATE["records"][contract] = _new_record(contract)
            print(f"COMBINED OBSERVED CONTRACT | {contract} | {_iso(now)} | NO ORDERS", flush=True)

        record = STATE["records"][contract]
        early_new, final_new = _capture_modules(record, combined)
        scalp_new = _capture_scalps(record, scalp)

        if early_new:
            e = record["early"]
            print(
                f"COMBINED EARLY | {contract} | {e['side']} | ask={e['ask']} | "
                f"left={e['seconds_left']}s | NO ORDERS",
                flush=True,
            )
        if final_new:
            f = record["final"]
            print(
                f"COMBINED FINAL | {contract} | {f['side']} | ask={f['ask']} | "
                f"left={f['seconds_left']}s | NO ORDERS",
                flush=True,
            )
        if scalp_new:
            print(
                f"COMBINED SCALP | {contract} | serial_opportunities={len(record['scalps'])} | NO ORDERS",
                flush=True,
            )


def _maybe_settle(now: datetime | None = None) -> None:
    now = now or _now()
    with LOCK:
        due = [
            c for c, raw in STATE["pending_settlement"].items()
            if now >= _dt(raw)
        ]
    for contract in due:
        side = fetch_official_settlement(contract)
        with LOCK:
            if side:
                if contract in STATE["records"]:
                    STATE["records"][contract]["official_side"] = side
                STATE["pending_settlement"].pop(contract, None)
                print(f"COMBINED SETTLED | {contract} | {side} | NO ORDERS", flush=True)
            else:
                STATE["pending_settlement"][contract] = _iso(
                    now + timedelta(seconds=SETTLEMENT_RETRY_SEC)
                )


def summarize_state() -> dict[str, Any]:
    with LOCK:
        rows = [dict(r) for r in STATE["records"].values()]
        armed = STATE.get("live_scoring_armed") is True
        first_full = STATE.get("first_full_contract")
        startup = STATE.get("startup_contract")
    score = score_records(rows)
    settled = sum(_side(r.get("official_side")) is not None for r in rows)
    ready = bool(len(rows) >= MIN_FULL_CONTRACTS and settled >= MIN_SETTLED_CONTRACTS)
    score.update({
        "observer_version": VERSION,
        "status": "COMBINED_SMOKE_SAMPLE_READY" if ready else "COLLECTING_COMBINED_FORWARD",
        "live_cutoff_utc": LIVE_CUTOFF_RAW,
        "live_scoring_armed": armed,
        "first_full_contract": first_full,
        "startup_contract_excluded": startup,
        "partial_start_contract_counted": False,
        "settled_contracts": settled,
        "min_full_contracts": MIN_FULL_CONTRACTS,
        "min_settled_contracts": MIN_SETTLED_CONTRACTS,
        "sample_ready": ready,
    })
    return score


def log_summary() -> None:
    s = summarize_state()
    def fmt(v: Any, d: int = 3) -> str:
        return "NA" if v is None else f"{float(v):.{d}f}"
    print(
        f"COMBINED FORWARD | status={s['status']} | observed={s['contracts']} | settled={s['settled_contracts']} | "
        f"EARLY={s['early_contracts']} acc={fmt(s['early']['accuracy'])} | "
        f"SCALP contracts={s['scalp_contracts']} opps={s['scalp']['opportunities']} +10={fmt(s['scalp']['plus_10c_rate'])} | "
        f"FINAL={s['final_contracts']} acc={fmt(s['final']['accuracy'])} | "
        f"UNION={s['union_actionable_contracts']}/{s['contracts']} ({fmt(s['union_actionable_coverage'])}) | "
        f"ready={s['sample_ready']} | NO ORDERS",
        flush=True,
    )


def observer_loop() -> None:
    print(
        f"{VERSION} START | cutoff={LIVE_CUTOFF_RAW} | common contract universe | "
        "protected EARLY + serial V5 SCALP + protected FINAL | UNION COUNTS CONTRACT ONCE | "
        "READ ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS",
        flush=True,
    )
    last_contract = None
    while True:
        now = _now()
        try:
            combined = _fetch_json(COMBINED_URL)
            scalp = _fetch_json(SCALP_URL)
            before = str(STATE.get("current_contract") or "")
            observer_cycle(combined, scalp, observed_at=now)
            _maybe_settle(now)
            after = str(STATE.get("current_contract") or "")
            if after and after != last_contract:
                log_summary()
                last_contract = after
            with LOCK:
                STATE["last_error"] = None
        except Exception as exc:
            with LOCK:
                STATE["last_error"] = f"{type(exc).__name__}:{exc}"
            print(
                f"COMBINED FORWARD WARNING | {type(exc).__name__}: {exc} | FAIL CLOSED | NO ORDERS",
                flush=True,
            )
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15CombinedForwardScorecardV1/1.0"

    def log_message(self, fmt, *args):
        print("COMBINED_SCORECARD_HTTP | " + (fmt % args), flush=True)

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
                err = STATE.get("last_error")
                last_poll = STATE.get("last_poll_utc")
            return self._json(200, {
                "ok": True,
                "scorecard": summarize_state(),
                "last_poll_utc": last_poll,
                "last_error": err,
                "orders": False,
                "manual_execution_only": True,
            })
        if path == "/health":
            with LOCK:
                last_poll = STATE.get("last_poll_utc")
                err = STATE.get("last_error")
            return self._json(200 if last_poll else 503, {
                "ok": bool(last_poll),
                "version": VERSION,
                "last_poll_utc": last_poll,
                "last_error": err,
                "orders": False,
                "manual_execution_only": True,
                "module_thresholds_changed": False,
                "production_behavior_changed": False,
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
    with LOCK:
        STATE["started_at_utc"] = _iso()
    threading.Thread(target=observer_loop, name="btc15-combined-forward-observer", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
