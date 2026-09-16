#!/usr/bin/env python3
"""BTC15 Candidate -> Verify Forward V1.

SHADOW ONLY | PROSPECTIVE COMPARISON | NO ORDERS | NO AUTO-PROMOTION

Compare the unchanged immediate serial scalp candidate with fixed confirmation
waits of 5s / 10s / 15s / 30s.  A delayed policy enters at the first then-current
executable ASK observed at/after its requested delay and scores only subsequent
executable BID.  Its +5c arm / 4c giveback protection lifecycle is rebased from
that delayed entry; pre-entry path gains cannot leak into delayed performance.

This first fresh window is a development/comparison sample only.  It may expose
tradeoffs but cannot select and promote a production delay on the same sample.
Any chosen policy requires a later separately frozen prospective certification.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

import scalp_economics_exit_cert_v1 as econ
import scalp_event_schema_adapter_v1 as adapter
import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_frontier_v1 as union
import scalp_specialist_union_live_review_v1 as source

VERSION = "BTC15_SCALP_CANDIDATE_VERIFY_FORWARD_V1_FROZEN_POLICIES"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(120, int(os.environ.get("SCALP_CANDIDATE_VERIFY_POLL_SEC", "300")))
CUTOFF_TEXT = os.environ.get("SCALP_CANDIDATE_VERIFY_CUTOFF_UTC", "").strip()
VERIFY_DELAYS_SEC = (0.0, 5.0, 10.0, 15.0, 30.0)
MIN_FUTURE_FULL_CONTRACTS = 100
MIN_IMMEDIATE_SIGNALS = 100
MIN_30S_VERIFIED_SIGNALS = 50

LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "status": "STARTING",
    "cutoff_utc": CUTOFF_TEXT or None,
    "orders": False,
    "shadow_only": True,
    "automatic_promotion": False,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_cutoff(text: str) -> datetime | None:
    if not text:
        return None
    try:
        x = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if x.tzinfo is None:
            x = x.replace(tzinfo=timezone.utc)
        return x.astimezone(timezone.utc)
    except Exception:
        return None


def future_universe(rows: list[Mapping[str, Any]], cutoff: datetime) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    adapted = adapter.adapt_rows(rows)
    full = union.full_contract_universe(adapted)
    future: dict[str, dict[str, Any]] = {}
    for contract, meta in full.items():
        first = meta.get("first_seen")
        if isinstance(first, datetime) and first >= cutoff:
            future[contract] = dict(meta)
    return future, adapted


def _finite(v: Any) -> float | None:
    x = q.f(v)
    return x if x is not None and math.isfinite(x) else None


def _fee_scenarios(entry: float, exit_bid: float) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for lot in econ.LOT_SIZES:
        tt = econ.fee_adjusted_per_contract(entry, exit_bid, lot)
        mt = econ.fee_adjusted_per_contract(entry, exit_bid, lot, entry_maker=True)
        out[str(lot)] = {
            "TAKER_TAKER": {
                "round_trip_fee_c_per_contract": 100.0 * tt["round_trip_fee_dollars_per_contract"],
                "net_gain_c_per_contract": 100.0 * tt["net_gain_dollars_per_contract"],
            },
            "MAKER_ENTRY_TAKER_EXIT": {
                "round_trip_fee_c_per_contract": 100.0 * mt["round_trip_fee_dollars_per_contract"],
                "net_gain_c_per_contract": 100.0 * mt["net_gain_dollars_per_contract"],
            },
        }
    return out


def immediate_record(op: Mapping[str, Any]) -> dict[str, Any]:
    rec = econ._op_record(op)
    rec.update({
        "requested_delay_sec": 0.0,
        "actual_delay_sec": 0.0,
        "entry_slippage_c_vs_candidate": 0.0,
        "verified_entry_available": True,
        "delayed_lifecycle_rebased": True,
    })
    return rec


def delayed_record(op: Mapping[str, Any], requested_delay: float) -> dict[str, Any] | None:
    """Enter at delayed ASK; calculate all movement/protection from that moment."""
    candidate = op.get("_candidate")
    paths = op.get("_paths")
    if not isinstance(candidate, Mapping) or not isinstance(paths, list):
        return None
    t0 = q.dt(candidate.get("timestamp_utc"))
    timeline: list[tuple[float, Mapping[str, Any]]] = []
    for row in paths:
        if not isinstance(row, Mapping):
            continue
        e = q.elapsed(row, t0)
        if e is not None:
            timeline.append((float(e), row))
    timeline.sort(key=lambda x: x[0])

    entry_row = next(
        ((e, row) for e, row in timeline
         if e >= float(requested_delay) and _finite(row.get("current_ask")) is not None),
        None,
    )
    if entry_row is None:
        return None
    entry_elapsed, row0 = entry_row
    entry_ask = _finite(row0.get("current_ask"))
    if entry_ask is None:
        return None

    future: list[tuple[float, float]] = []
    for e, row in timeline:
        if e < entry_elapsed:
            continue
        bid = _finite(row.get("current_bid"))
        if bid is not None:
            future.append((e, bid - entry_ask))
    if not future:
        return None

    gains = [g for _, g in future]
    peak_gain = max(gains)
    adverse_gain = min(gains)
    t5 = next((e - entry_elapsed for e, g in future if g >= q.ARM_GAIN), None)
    t10 = next((e - entry_elapsed for e, g in future if g >= .10), None)
    t20 = next((e - entry_elapsed for e, g in future if g >= .20), None)

    peak_so_far = -float("inf")
    armed = False
    exit_gain: float | None = None
    for _, gain in future:
        peak_so_far = max(peak_so_far, gain)
        armed = armed or peak_so_far >= q.ARM_GAIN
        if armed and peak_so_far - gain >= q.GIVEBACK - 1e-12:
            exit_gain = gain
            break

    original_ask = _finite(op.get("entry_ask"))
    original_left = _finite(op.get("seconds_left"))
    seconds_left = None if original_left is None else max(0.0, original_left - entry_elapsed)
    rec: dict[str, Any] = {
        "contract": str(op.get("contract") or ""),
        "candidate_id": str(op.get("candidate_id") or ""),
        "opportunity_index": int(op.get("opportunity_index") or 0),
        "side": str(op.get("side") or ""),
        "entry_ask": entry_ask,
        "seconds_left": seconds_left,
        "plus5": int(peak_gain >= .05),
        "plus10": int(peak_gain >= .10),
        "plus20": int(peak_gain >= .20),
        "peak_gain": peak_gain,
        "adverse_gain": adverse_gain,
        "protected_exit_gain": exit_gain,
        "protected_exit_observed": exit_gain is not None,
        "requested_delay_sec": float(requested_delay),
        "actual_delay_sec": entry_elapsed,
        "entry_slippage_c_vs_candidate": None if original_ask is None else 100.0 * (entry_ask - original_ask),
        "verified_entry_available": True,
        "delayed_lifecycle_rebased": True,
        "t5_sec_from_verified_entry": t5,
        "t10_sec_from_verified_entry": t10,
        "t20_sec_from_verified_entry": t20,
    }
    if exit_gain is not None:
        exit_bid = entry_ask + exit_gain
        rec["protected_exit_bid"] = exit_bid
        rec["gross_protected_gain_c"] = 100.0 * exit_gain
        rec["giveback_from_peak_c"] = 100.0 * (peak_gain - exit_gain)
        rec["capture_efficiency"] = None if peak_gain <= 0 else exit_gain / peak_gain
        rec["fee_scenarios"] = _fee_scenarios(entry_ask, exit_bid)
    else:
        rec["protected_exit_bid"] = None
        rec["gross_protected_gain_c"] = None
        rec["giveback_from_peak_c"] = None
        rec["capture_efficiency"] = None
        rec["fee_scenarios"] = {}
    return rec


def build_policy_records(opps: list[dict[str, Any]], delay: float) -> tuple[list[dict[str, Any]], int]:
    if delay == 0.0:
        return [immediate_record(op) for op in opps], 0
    records: list[dict[str, Any]] = []
    unavailable = 0
    for op in opps:
        rec = delayed_record(op, delay)
        if rec is None:
            unavailable += 1
        else:
            records.append(rec)
    return records, unavailable


def _mean(values: list[float]) -> float | None:
    z = [float(x) for x in values if x is not None and math.isfinite(float(x))]
    return None if not z else statistics.fmean(z)


def _median(values: list[float]) -> float | None:
    z = [float(x) for x in values if x is not None and math.isfinite(float(x))]
    return None if not z else statistics.median(z)


def compact_econ(summary: Mapping[str, Any]) -> dict[str, Any]:
    one = (((summary.get("fee_adjusted_protected_exits") or {}).get("1") or {}).get("TAKER_TAKER") or {})
    ten = (((summary.get("fee_adjusted_protected_exits") or {}).get("10") or {}).get("TAKER_TAKER") or {})
    return {
        "signals": summary.get("signals"),
        "contracts": summary.get("contracts"),
        "plus5_rate": summary.get("plus5_rate"),
        "plus10_rate": summary.get("plus10_rate"),
        "plus20_rate": summary.get("plus20_rate"),
        "protected_exit_signals": summary.get("protected_exit_signals"),
        "protected_exit_rate": summary.get("protected_exit_rate"),
        "avg_entry_ask_c": summary.get("avg_entry_ask_c"),
        "median_entry_ask_c": summary.get("median_entry_ask_c"),
        "entry_le50_rate": summary.get("entry_le50_rate"),
        "entry_ideal_25_35_rate": summary.get("entry_ideal_25_35_rate"),
        "avg_minutes_left": summary.get("avg_minutes_left"),
        "avg_gross_protected_gain_c": summary.get("avg_gross_protected_gain_c"),
        "one_lot_taker_taker_avg_net_c": one.get("avg_net_gain_c_per_contract"),
        "one_lot_taker_taker_median_net_c": one.get("median_net_gain_c_per_contract"),
        "one_lot_taker_taker_positive_net_rate": one.get("positive_net_rate"),
        "ten_lot_taker_taker_avg_net_c": ten.get("avg_net_gain_c_per_contract"),
        "ten_lot_taker_taker_median_net_c": ten.get("median_net_gain_c_per_contract"),
        "ten_lot_taker_taker_positive_net_rate": ten.get("positive_net_rate"),
        "max_opportunity_index": summary.get("max_opportunity_index"),
    }


def summarize_policy(records: list[dict[str, Any]], unavailable: int,
                     immediate_signal_n: int, immediate_contract_n: int,
                     future_contract_n: int) -> dict[str, Any]:
    full = econ.summarize(records)
    compact = compact_econ(full)
    contracts = {str(r.get("contract") or "") for r in records if r.get("contract")}
    slips = [r.get("entry_slippage_c_vs_candidate") for r in records
             if r.get("entry_slippage_c_vs_candidate") is not None]
    actual_delays = [r.get("actual_delay_sec") for r in records if r.get("actual_delay_sec") is not None]
    compact.update({
        "unavailable_verified_entries": unavailable,
        "signal_retention_vs_immediate": None if not immediate_signal_n else len(records) / immediate_signal_n,
        "contract_retention_vs_immediate": None if not immediate_contract_n else len(contracts) / immediate_contract_n,
        "true_future_contract_coverage": None if not future_contract_n else len(contracts) / future_contract_n,
        "avg_entry_slippage_c_vs_candidate": _mean(slips),
        "median_entry_slippage_c_vs_candidate": _median(slips),
        "avg_actual_delay_sec": _mean(actual_delays),
        "median_actual_delay_sec": _median(actual_delays),
    })
    by_index: dict[str, Any] = {}
    for idx in sorted({int(r.get("opportunity_index") or 0) for r in records}):
        by_index[str(idx)] = compact_econ(econ.summarize([
            r for r in records if int(r.get("opportunity_index") or 0) == idx
        ]))
    compact["by_opportunity_index"] = by_index
    return compact


def compact_state(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": result.get("status"),
        "cutoff_utc": result.get("cutoff_utc"),
        "future_full_contracts": result.get("future_full_contracts"),
        "immediate_serial_signals": result.get("immediate_serial_signals"),
        "policies": result.get("policies"),
        "evidence_readiness": result.get("evidence_readiness"),
        "policy_selection": False,
        "same_sample_promotion": False,
        "automatic_promotion": False,
        "orders": False,
    }


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0,
                 cutoff_text: str | None = None) -> dict[str, Any]:
    text = CUTOFF_TEXT if cutoff_text is None else cutoff_text
    cutoff = parse_cutoff(text)
    if cutoff is None:
        return {
            "ok": False, "version": VERSION,
            "status": "FAIL_CLOSED_MISSING_OR_INVALID_CUTOFF",
            "cutoff_utc": text or None, "source_sha256": sha,
            "source_rows": len(rows), "policy_selection": False,
            "automatic_promotion": False, "orders": False,
        }

    future, adapted = future_universe(rows, cutoff)
    contracts = set(future)
    opps = [op for op in q.build_serial_opportunities(adapted)
            if str(op.get("contract") or "") in contracts]
    immediate_signal_n = len(opps)
    immediate_contracts = {str(op.get("contract") or "") for op in opps if op.get("contract")}
    policies: dict[str, Any] = {}
    records_by_delay: dict[float, list[dict[str, Any]]] = {}
    for delay in VERIFY_DELAYS_SEC:
        records, unavailable = build_policy_records(opps, delay)
        records_by_delay[delay] = records
        policies[f"{int(delay)}s" if delay else "IMMEDIATE"] = summarize_policy(
            records, unavailable, immediate_signal_n, len(immediate_contracts), len(contracts)
        )

    verified30 = len(records_by_delay.get(30.0, []))
    ready = (
        len(contracts) >= MIN_FUTURE_FULL_CONTRACTS
        and immediate_signal_n >= MIN_IMMEDIATE_SIGNALS
        and verified30 >= MIN_30S_VERIFIED_SIGNALS
    )
    status = "READY_FOR_MANUAL_DEVELOPMENT_COMPARISON" if ready else "COLLECTING_FUTURE_CANDIDATE_VERIFY_V1"
    result = {
        "ok": True,
        "version": VERSION,
        "status": status,
        "updated_utc": utcnow(),
        "cutoff_utc": cutoff.isoformat(),
        "source_sha256": sha,
        "source_bytes": source_bytes,
        "source_rows": len(rows),
        "future_full_contracts": len(contracts),
        "future_contract_ids": sorted(contracts),
        "immediate_serial_signals": immediate_signal_n,
        "immediate_serial_contracts": len(immediate_contracts),
        "policies": policies,
        "evidence_readiness": {
            "sample_ready": ready,
            "required_future_full_contracts": MIN_FUTURE_FULL_CONTRACTS,
            "required_immediate_signals": MIN_IMMEDIATE_SIGNALS,
            "required_30s_verified_signals": MIN_30S_VERIFIED_SIGNALS,
            "observed_future_full_contracts": len(contracts),
            "observed_immediate_signals": immediate_signal_n,
            "observed_30s_verified_signals": verified30,
            "readiness_is_development_comparison_only": True,
            "a_selected_policy_requires_a_later_fresh_certification_window": True,
        },
        "frozen_policies": {
            "delays_sec": list(VERIFY_DELAYS_SEC),
            "delayed_entry": "first executable current_ask at_or_after requested delay",
            "delayed_score": "only subsequent executable current_bid",
            "protection": "+5c arm / 4c giveback rebased from verified entry",
            "fees": "same Kalshi general event-contract fee scenarios as Economics V1",
        },
        "movement_vs_realized_warning": "+10 touch is not treated as realized +10",
        "policy_selection": False,
        "same_sample_promotion": False,
        "manual_execution_only": True,
        "production_logic_changed": False,
        "automatic_promotion": False,
        "shadow_only": True,
        "orders": False,
    }
    print("SCALP_CANDIDATE_VERIFY_FORWARD | " + json.dumps(compact_state(result), separators=(",", ":"), sort_keys=True, default=str), flush=True)
    return result


def refresh_once() -> dict[str, Any]:
    rows, sha, source_bytes = source.fetch_rows()
    with LOCK:
        old_sha = STATE.get("source_sha256")
    if old_sha == sha and STATE.get("status") != "STARTING":
        with LOCK:
            STATE["last_poll_utc"] = utcnow()
            return dict(STATE)
    result = analyze_rows(rows, sha=sha, source_bytes=source_bytes)
    result["last_poll_utc"] = utcnow()
    with LOCK:
        STATE.clear(); STATE.update(result)
        return dict(STATE)


def loop() -> None:
    while True:
        try:
            refresh_once()
        except Exception as exc:
            with LOCK:
                STATE.update({
                    "ok": False, "version": VERSION,
                    "status": "FAIL_CLOSED_SOURCE_OR_ANALYSIS_ERROR",
                    "last_poll_utc": utcnow(),
                    "error": f"{type(exc).__name__}:{exc}",
                    "policy_selection": False,
                    "automatic_promotion": False,
                    "orders": False, "shadow_only": True,
                })
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15CandidateVerifyForwardV1/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_CANDIDATE_VERIFY_HTTP | request", flush=True)

    def send_json(self, code: int, obj: Mapping[str, Any]) -> None:
        raw = json.dumps(obj, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(raw)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        with LOCK:
            state = dict(STATE)
        if path == "/health":
            return self.send_json(200, {
                "ok": True, "analysis_ok": state.get("ok") is True,
                "status": state.get("status"), "version": VERSION,
                "cutoff_utc": state.get("cutoff_utc"),
                "policy_selection": False, "orders": False,
            })
        if path == "/summary":
            return self.send_json(200, compact_state(state))
        if path == "/state":
            return self.send_json(200, state)
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def assert_integrity() -> None:
    if VERIFY_DELAYS_SEC != (0.0, 5.0, 10.0, 15.0, 30.0):
        raise RuntimeError("candidate verify policy grid drifted")
    if q.ARM_GAIN != 0.05 or q.GIVEBACK != 0.04:
        raise RuntimeError("protection lifecycle drifted")
    if (MIN_FUTURE_FULL_CONTRACTS, MIN_IMMEDIATE_SIGNALS, MIN_30S_VERIFIED_SIGNALS) != (100, 100, 50):
        raise RuntimeError("development evidence-readiness gate drifted")


assert_integrity()


def main() -> int:
    print(
        f"{VERSION} START | cutoff={CUTOFF_TEXT or 'MISSING'} | FIXED 0/5/10/15/30s POLICIES | "
        "DEVELOPMENT COMPARISON ONLY | NO SAME-SAMPLE PROMOTION | NO ORDERS",
        flush=True,
    )
    threading.Thread(target=loop, name="candidate-verify-forward-v1-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
