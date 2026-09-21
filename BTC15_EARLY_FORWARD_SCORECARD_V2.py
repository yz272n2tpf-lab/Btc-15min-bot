#!/usr/bin/env python3
"""Frozen protected EARLY 7–10m settlement audit. READ ONLY / NO ORDERS.

Only the production adapter qualifies EARLY. This observer selects a reporting
slice, never recomputes the protected rule, and never loads a previous sample.
Every process creates a distinct run; stdout events and /state are its evidence.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import statistics
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import btc15_main_protected_state_adapter_v1 as adapter

VERSION = "BTC15_EARLY_FORWARD_SCORECARD_V2"
SPEC_COMMIT = "13c8988fed8c97479203910f5620df64826246f3"
MAIN_STATE_URL = "https://btc-15min-bot-production.up.railway.app/dashboard_state.json"
MARKET_BASES = (
    "https://external-api.kalshi.com/trade-api/v2/markets/",
    "https://external-api.kalshi.com/trade-api/v2/historical/markets/",
)
SLICE_MIN_SECONDS = 420.0
SLICE_MAX_SECONDS = 600.0
POLL_SEC = 5.0
TIMEOUT_SEC = 5.0
# Collection-quality limits only; these are not production signal thresholds.
MAX_OBSERVATION_GAP_SEC = 30.0
MAX_SOURCE_AGE_SEC = 30.0
ROLLOVER_GRACE_SEC = 30.0
SAFETY = {"orders": False, "signal_only": True, "manual_execution_only": True,
          "protected_early_thresholds_changed": False, "production_behavior_changed": False}


def utcnow():
    return datetime.now(timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def dt(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def number(value):
    if value is None or isinstance(value, bool):
        raise ValueError("missing numeric field")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("non-finite numeric field")
    return value


def ticker_for_close(close):
    local = close.astimezone(ZoneInfo("America/New_York"))
    return "KXBTC15M-" + local.strftime("%y%b%d%H%M").upper() + local.strftime("-%M")


def allowed_url(url):
    return url == MAIN_STATE_URL or any(
        url.startswith(base) and re.fullmatch(r"KXBTC15M-[A-Z0-9]+-\d{2}", url[len(base):])
        for base in MARKET_BASES)


def fetch_json(url):
    if not allowed_url(url):
        raise ValueError("read-only URL allowlist rejected request")
    req = Request(url, method="GET", headers={"Cache-Control": "no-cache", "User-Agent": VERSION})
    with urlopen(req, timeout=TIMEOUT_SEC) as response:
        if response.geturl() != url:
            raise ValueError("unexpected redirect")
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("JSON must be an object")
    return payload


def official_evidence(payload, ticker, url, now):
    """No price/FINAL/model fallback. Exact official ticker and final yes/no only."""
    if url not in [base + ticker for base in MARKET_BASES]:
        return None
    market = payload.get("market")
    if not isinstance(market, dict) or market.get("ticker") != ticker:
        return None
    result = market.get("result")
    if (market.get("status") not in {"finalized", "settled"}
            or result not in {"yes", "no"} or market.get("is_provisional") is True):
        return None
    return {"contract": ticker, "official_side": "UP" if result == "yes" else "DOWN",
            "result": result, "status": market["status"], "source_url": url,
            "retrieved_at_utc": iso(now), "settlement_ts": market.get("settlement_ts"),
            "payload_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()}


def fetch_official_settlement(ticker, now=None):
    errors = []
    for base in MARKET_BASES:
        url = base + ticker
        try:
            evidence = official_evidence(fetch_json(url), ticker, url, now or utcnow())
            if evidence:
                return evidence, None
        except Exception as exc:
            errors.append(type(exc).__name__ + ":" + str(exc))
    return None, "; ".join(errors) or "official final result pending"


def read_frame(raw, now):
    """Map the current nested schema through the unchanged protected adapter."""
    early = raw.get("early")
    if not isinstance(early, dict) or not isinstance(early.get("ready"), bool):
        raise ValueError("missing production early.ready boolean")
    if early.get("source") != "FROZEN_TIER1":
        raise ValueError("unexpected EARLY producer")
    source = dt(raw["source_timestamp_utc"])
    if not -2 <= (now - source).total_seconds() <= MAX_SOURCE_AGE_SEC:
        raise ValueError("stale/future production source")
    if raw.get("health", {}).get("source_fresh") is not True:
        raise ValueError("production source not fresh")
    left = number(adapter.canonical_seconds_left(raw))
    if not 0 <= left <= 900:
        raise ValueError("invalid 15-minute timer")
    close_raw = dt(raw["timer"]["close_utc"])
    close = datetime.fromtimestamp(round(close_raw.timestamp() / 900) * 900, timezone.utc)
    if abs((close_raw - close).total_seconds()) > 2:
        raise ValueError("unaligned close timestamp")
    if abs((source + timedelta(seconds=left) - close).total_seconds()) > 2:
        raise ValueError("source timestamp/timer mismatch")
    ticker = raw.get("contract")
    if ticker != ticker_for_close(close):
        raise ValueError("contract/close timestamp mismatch")
    signal = adapter.early_state_from_main(raw)
    if signal.state == "QUALIFIED":
        for value in (signal.ask, signal.fair, signal.edge):
            number(value)
    return {"contract": ticker, "source": source, "close": close,
            "start": close - timedelta(minutes=15), "seconds_left": left,
            "signal": signal, "raw_early": copy.deepcopy(early)}


class Observer:
    def __init__(self, now=None, emit=None):
        self.lock = threading.RLock()
        self.started = now or utcnow()
        self.run_id = str(uuid.uuid4())
        self.emit = emit or (lambda event: print(json.dumps(event, sort_keys=True), flush=True))
        self.contracts = {}
        self.calls = {}
        self.first_calls = {}
        self.settlements = {}
        self.pending = {}
        self.current = None
        self.startup = None
        self.last_source = None
        self.last_observed = None
        self.first_eligible = None
        self.forward_start = None
        self.armed_at = None
        self.last_error = None
        self.last_settlement_error = None
        self.poll_successes = 0
        self.settlement_probe = None
        self.probe_done = False
        self.checkpoints = {}
        self.log("CLEAN_PROCESS_START", started_at_utc=iso(self.started), spec_commit=SPEC_COMMIT,
                 source_url=MAIN_STATE_URL, previous_sample_loaded=False)

    def log(self, event, **fields):
        self.emit({"event": event, "run_id": self.run_id, "version": VERSION, **fields, **SAFETY})

    def exclude(self, ticker, reason):
        row = self.contracts.get(ticker)
        # Once a call is frozen, later collection trouble cannot erase its outcome.
        if (row and ticker not in self.first_calls and row["eligible"]
                and not row["slice_observation_complete"]):
            row.update(eligible=False, exclusion_reason=reason)
            self.log("CONTRACT_EXCLUDED", contract=ticker, reason=reason)

    def observe(self, raw, now=None):
        now = now or utcnow()
        with self.lock:
            try:
                frame = read_frame(raw, now)
            except Exception as exc:
                self.last_error = str(exc)
                self.exclude(self.current, "invalid_source_before_first_call")
                raise
            source, ticker = frame["source"], frame["contract"]
            if self.last_source is not None and source <= self.last_source:
                # Duplicated/reordered snapshots cannot create a rollover or call.
                return
            previous_observed, previous_source = self.last_observed, self.last_source
            gap = previous_source is not None and (
                (source - previous_source).total_seconds() > MAX_OBSERVATION_GAP_SEC
                or (now - previous_observed).total_seconds() > MAX_OBSERVATION_GAP_SEC)
            if gap and self.current and self.contracts[self.current]["slice_observation_complete"] is False:
                self.exclude(self.current, "observation_gap_before_first_call")
            self.last_source, self.last_observed = source, now
            self.last_error = None
            self.poll_successes += 1
            if self.current != ticker:
                if ticker in self.contracts:
                    raise ValueError("contract rollback rejected")
                initial = self.current is None
                previous = self.contracts.get(self.current)
                full_rollover = (not initial and not gap
                    and frame["start"] == dt(previous["close_utc"])
                    and self.started < frame["start"]
                    and 0 <= (source - frame["start"]).total_seconds() <= ROLLOVER_GRACE_SEC)
                row = {"contract": ticker, "start_utc": iso(frame["start"]),
                       "close_utc": iso(frame["close"]), "first_seen_at_utc": iso(now),
                       "first_source_timestamp_utc": iso(source),
                       "first_seen_seconds_left": frame["seconds_left"],
                       "eligible": bool(full_rollover), "slice_observation_complete": False,
                       "exclusion_reason": None if full_rollover else (
                           "startup_contract" if initial else "rollover_not_fully_observed")}
                self.contracts[ticker] = row
                self.current = ticker
                if initial:
                    self.startup = ticker
                    self.settlement_probe = {"contract": ticker,
                        "next_attempt_utc": iso(frame["close"] + timedelta(seconds=30)),
                        "purpose": "excluded_startup_contract_plumbing_only"}
                if full_rollover and self.first_eligible is None:
                    self.first_eligible, self.forward_start, self.armed_at = ticker, row["start_utc"], iso(now)
                    self.log("FORWARD_ARMED", contract=ticker, forward_start_utc=self.forward_start,
                             observed_at_utc=self.armed_at, source_timestamp_utc=iso(source))
                self.log("CONTRACT_OBSERVED", **row)
            row = self.contracts[ticker]
            if not row["eligible"]:
                return
            signal = frame["signal"]
            if signal.state == "QUALIFIED" and ticker not in self.first_calls:
                left = frame["seconds_left"]
                in_slice = SLICE_MIN_SECONDS <= left <= SLICE_MAX_SECONDS
                rec = {"contract": ticker, "observed_at_utc": iso(now),
                       "source_timestamp_utc": iso(source), "close_utc": row["close_utc"],
                       "side": signal.side, "ask": signal.ask, "fair": signal.fair,
                       "edge": signal.edge, "seconds_left": left, "minutes_left": left / 60,
                       "in_7to10m_slice": in_slice, "production_early": frame["raw_early"],
                       **SAFETY}
                self.first_calls[ticker] = rec
                row["slice_observation_complete"] = True
                if in_slice:
                    self.calls[ticker] = copy.deepcopy(rec)
                    self.pending[ticker] = iso(frame["close"] + timedelta(seconds=30))
                self.log("FIRST_PROTECTED_EARLY", record=rec)
            if frame["seconds_left"] < SLICE_MIN_SECONDS:
                row["slice_observation_complete"] = True

    def accept_settlement(self, ticker, evidence):
        with self.lock:
            if ticker not in self.calls or ticker in self.settlements:
                return False
            if (evidence.get("contract") != ticker
                    or evidence.get("official_side") not in {"UP", "DOWN"}
                    or evidence.get("source_url") not in [b + ticker for b in MARKET_BASES]
                    or evidence.get("status") not in {"finalized", "settled"}
                    or evidence.get("result") != ("yes" if evidence["official_side"] == "UP" else "no")):
                raise ValueError("invalid official settlement evidence")
            self.settlements[ticker] = copy.deepcopy(evidence)
            self.pending.pop(ticker, None)
            self.log("OFFICIAL_SETTLEMENT", evidence=evidence)
            self.update_checkpoints()
            return True

    def update_checkpoints(self):
        # Checkpoints use the first 10/15 calls in call order, never response order.
        calls = list(self.calls.values())
        for n in (10, 15):
            cohort = calls[:n]
            if str(n) in self.checkpoints or len(cohort) < n:
                continue
            if not all(c["contract"] in self.settlements for c in cohort):
                continue
            correct = sum(c["side"] == self.settlements[c["contract"]]["official_side"] for c in cohort)
            decision = ("FAIL_7TO10M_CLAIM" if correct <= 8 else "CONTINUE_UNCHANGED_TO_15") if n == 10 else (
                "PROVISIONAL_SUPPORT_93_TO_95_TARGET" if correct >= 14 else "FAIL_TARGET")
            self.checkpoints[str(n)] = {"settled_calls": n, "correct": correct,
                                       "same_side_rate": correct / n, "decision": decision}
            self.log("FROZEN_CHECKPOINT", **self.checkpoints[str(n)])

    def settle_due(self, now=None, fetcher=fetch_official_settlement):
        now = now or utcnow()
        with self.lock:
            due = [(t, when) for t, when in self.pending.items() if now >= dt(when)]
            probe = copy.deepcopy(self.settlement_probe) if not self.probe_done else None
        if probe and now >= dt(probe["next_attempt_utc"]):
            evidence, error = fetcher(probe["contract"], now)
            with self.lock:
                self.last_settlement_error = error
                if evidence:
                    # The startup contract never enters calls, settlements or gates.
                    self.probe_done = True
                    self.settlement_probe.update(verified=True, verified_at_utc=iso(now),
                                                 source_url=evidence["source_url"])
                    self.log("SETTLEMENT_PLUMBING_VERIFIED", **self.settlement_probe)
                else:
                    self.settlement_probe["next_attempt_utc"] = iso(now + timedelta(seconds=60))
        for ticker, _ in due:
            evidence, error = fetcher(ticker, now)
            with self.lock:
                self.last_settlement_error = error
                if evidence:
                    self.accept_settlement(ticker, evidence)
                else:
                    self.pending[ticker] = iso(now + timedelta(seconds=60))

    def plumbing(self, now=None):
        now = now or utcnow()
        with self.lock:
            age = None if self.last_observed is None else (now - self.last_observed).total_seconds()
            return {"version": VERSION, "run_id": self.run_id, "spec_commit": SPEC_COMMIT,
                    "source_url": MAIN_STATE_URL, "started_at_utc": iso(self.started),
                    "startup_contract_excluded": self.startup, "current_contract": self.current,
                    "live_scoring_armed": self.first_eligible is not None,
                    "first_eligible_contract": self.first_eligible,
                    "forward_start_utc": self.forward_start, "armed_observed_at_utc": self.armed_at,
                    "last_source_timestamp_utc": iso(self.last_source) if self.last_source else None,
                    "last_poll_utc": iso(self.last_observed) if self.last_observed else None,
                    "poll_successes": self.poll_successes, "source_age_sec": age,
                    "healthy": age is not None and age <= MAX_SOURCE_AGE_SEC and self.last_error is None,
                    "last_error": self.last_error, "last_settlement_error": self.last_settlement_error,
                    "settlement_probe": copy.deepcopy(self.settlement_probe),
                    "previous_sample_loaded": False, "restart_policy": "NEW_RUN_NO_RESTORE_NO_BACKFILL",
                    "commit": os.environ.get("RAILWAY_GIT_COMMIT_SHA"),
                    "deployment_id": os.environ.get("RAILWAY_DEPLOYMENT_ID"), **SAFETY}

    def summary(self):
        with self.lock:
            calls = copy.deepcopy(list(self.calls.values()))
            settled = [{**c, "official_evidence": copy.deepcopy(self.settlements[c["contract"]]),
                        "same_side_as_settlement": c["side"] == self.settlements[c["contract"]]["official_side"]}
                       for c in calls if c["contract"] in self.settlements]
            eligible = sum(r["eligible"] for r in self.contracts.values())
            complete = sum(r["eligible"] and r["slice_observation_complete"] for r in self.contracts.values())
            rate = lambda n, d: n / d if d else None
            mean = lambda values: statistics.fmean(values) if values else None
            correct = sum(c["same_side_as_settlement"] for c in settled)
            gate10, gate15 = self.checkpoints.get("10"), self.checkpoints.get("15")
            status = "COLLECTING_TO_10"
            if gate10:
                status = gate10["decision"]
            if gate15 and status != "FAIL_7TO10M_CLAIM":
                status = gate15["decision"]
            return {**self.plumbing(), "status": status,
                    "primary_success_definition": "EARLY_SIDE_EQUALS_OFFICIAL_FINAL_SETTLEMENT_SIDE",
                    "slice_seconds_inclusive": [SLICE_MIN_SECONDS, SLICE_MAX_SECONDS],
                    "coverage_universe_semantics": "CONTINUOUS_POST_RESTART_ROLLOVERS",
                    "eligible_contracts": eligible, "slice_observation_complete_contracts": complete,
                    "qualifying_calls": len(calls), "eligible_contract_coverage": rate(len(calls), eligible),
                    "completed_slice_coverage": rate(len(calls), complete),
                    "settled_qualifying_calls": len(settled), "settlement_same_side_n": correct,
                    "settlement_same_side_rate": rate(correct, len(settled)),
                    "avg_ask": mean([c["ask"] for c in calls]),
                    "median_ask": statistics.median([c["ask"] for c in calls]) if calls else None,
                    "ask_25_35c_rate": rate(sum(.25 <= c["ask"] <= .35 for c in calls), len(calls)),
                    "ask_le_50c_rate": rate(sum(c["ask"] <= .50 for c in calls), len(calls)),
                    "avg_minutes_left": mean([c["minutes_left"] for c in calls]),
                    "up_calls": sum(c["side"] == "UP" for c in calls),
                    "down_calls": sum(c["side"] == "DOWN" for c in calls),
                    "checkpoints": copy.deepcopy(self.checkpoints), "call_records": calls,
                    "settled_records": settled, "first_protected_calls": copy.deepcopy(list(self.first_calls.values())),
                    "contract_audit": copy.deepcopy(list(self.contracts.values())),
                    "pending_settlement": copy.deepcopy(self.pending), "price_filter_added": False}


OBSERVER = None


def poll_loop(observer):
    while True:
        try:
            observer.observe(fetch_json(MAIN_STATE_URL), utcnow())
        except Exception as exc:
            with observer.lock:
                observer.last_error = type(exc).__name__ + ":" + str(exc)
            observer.log("POLL_WARNING", error=observer.last_error)
        time.sleep(POLL_SEC)


def settlement_loop(observer):
    while True:
        try:
            observer.settle_due()
        except Exception as exc:
            with observer.lock:
                observer.last_settlement_error = type(exc).__name__ + ":" + str(exc)
            observer.log("SETTLEMENT_WARNING", error=observer.last_settlement_error)
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def send_json(self, code, payload):
        body = json.dumps(payload, sort_keys=True).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in {"/health", "/plumbing"}:
            info = OBSERVER.plumbing()
            self.send_json(200 if path == "/plumbing" or info["healthy"] else 503, info)
        elif path == "/state":
            self.send_json(200, {"ok": True, "version": VERSION, "live": OBSERVER.summary(), **SAFETY})
        else:
            self.send_json(404, {"error": "not_found", **SAFETY})

    def reject(self):
        self.send_json(405, {"error": "read_only_observer", **SAFETY})

    do_POST = do_PUT = do_PATCH = do_DELETE = reject


def main():
    global OBSERVER
    # No bootstrap env, file, API, or previous module state is read here.
    OBSERVER = Observer()
    threading.Thread(target=poll_loop, args=(OBSERVER,), daemon=True).start()
    threading.Thread(target=settlement_loop, args=(OBSERVER,), daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()


if __name__ == "__main__":
    main()
