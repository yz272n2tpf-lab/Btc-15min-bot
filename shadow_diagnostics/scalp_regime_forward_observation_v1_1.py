#!/usr/bin/env python3
"""BTC15 prospective Regime Observation Ledger V1.1.

SHADOW ONLY | DESCRIPTIVE ONLY | NO SIGNAL SUPPRESSION | NO ORDERS

This observer applies the already-frozen Regime V1.1 semantic repair to a fresh
future contract universe.  It does not select a tag, change a threshold, rescue
or suppress a signal, or promote production logic.

A contract enters the denominator only when:
- its first passive observation is at/after the mandatory cutoff; and
- it is later proven fully observed (>=840s left through <=60s left).

The observer reports tag incidence against that true future-contract universe,
then movement/captured economics for serial scalp opportunities inside it.
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

import scalp_economics_exit_cert_v1 as econ
import scalp_event_schema_adapter_v1 as adapter
import scalp_market_regime_ledger_v1 as regime_v1
import scalp_market_regime_ledger_v1_1 as regime_v11
import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_frontier_v1 as union
import scalp_specialist_union_live_review_v1 as source

VERSION = "BTC15_SCALP_REGIME_FORWARD_OBSERVATION_V1_1_FROZEN"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(120, int(os.environ.get("SCALP_REGIME_FORWARD_POLL_SEC", "300")))
CUTOFF_TEXT = os.environ.get("SCALP_REGIME_FORWARD_CUTOFF_UTC", "").strip()
MIN_FUTURE_FULL_CONTRACTS = 100
MIN_PROTECTED_EXITS = 50

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


def build_future_records(adapted: list[Mapping[str, Any]], contracts: set[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for op in q.build_serial_opportunities(list(adapted)):
        contract = str(op.get("contract") or "")
        if contract not in contracts:
            continue
        tags = regime_v11.regime_tags(op)
        rec = econ._op_record(op)
        rec["tags"] = tags
        rec["primary_regime"] = regime_v11.primary_regime(tags)
        records.append(rec)
    return records


def compact_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    return regime_v1.compact_metrics(records)


def grouped_metrics(records: list[dict[str, Any]], *, primary: bool) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if primary:
        for r in records:
            groups[str(r.get("primary_regime") or "OTHER")].append(r)
    else:
        for r in records:
            for tag in r.get("tags") or ["OTHER"]:
                groups[str(tag)].append(r)
    return {name: compact_metrics(z) for name, z in sorted(groups.items())}


def tag_incidence(records: list[dict[str, Any]], denominator: int, *, primary: bool) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if primary:
        for r in records:
            groups[str(r.get("primary_regime") or "OTHER")].append(r)
    else:
        for r in records:
            for tag in r.get("tags") or ["OTHER"]:
                groups[str(tag)].append(r)
    out: dict[str, Any] = {}
    for name, z in sorted(groups.items()):
        c = {str(r.get("contract") or "") for r in z if r.get("contract")}
        out[name] = {
            "signals": len(z),
            "contracts": len(c),
            "true_future_contract_incidence": None if denominator <= 0 else len(c) / denominator,
        }
    return out


def by_opportunity_index(records: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for idx in sorted({int(r.get("opportunity_index") or 0) for r in records}):
        z = [r for r in records if int(r.get("opportunity_index") or 0) == idx]
        out[str(idx)] = {
            "overall": compact_metrics(z),
            "primary_regimes": grouped_metrics(z, primary=True),
        }
    return out


def compact(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": result.get("status"),
        "cutoff_utc": result.get("cutoff_utc"),
        "future_full_contracts": result.get("future_full_contracts"),
        "serial_covered_contracts": result.get("serial_covered_contracts"),
        "serial_true_contract_coverage": result.get("serial_true_contract_coverage"),
        "overall": result.get("overall"),
        "primary_tag_incidence": result.get("primary_tag_incidence"),
        "overlapping_tag_incidence": result.get("overlapping_tag_incidence"),
        "primary_regimes": result.get("primary_regimes"),
        "by_opportunity_index": result.get("by_opportunity_index"),
        "evidence_readiness": result.get("evidence_readiness"),
        "fixed_tag_definitions": result.get("fixed_tag_definitions"),
        "no_threshold_selection": True,
        "no_signal_suppression_or_rescue": True,
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
            "source_rows": len(rows), "orders": False,
            "automatic_promotion": False,
        }

    future, adapted = future_universe(rows, cutoff)
    contracts = set(future)
    records = build_future_records(adapted, contracts)
    covered = {str(r.get("contract") or "") for r in records if r.get("contract")}
    overall = compact_metrics(records)
    protected = int(overall.get("protected_exit_signals") or 0)
    ready = len(contracts) >= MIN_FUTURE_FULL_CONTRACTS and protected >= MIN_PROTECTED_EXITS
    status = "READY_FOR_MANUAL_DESCRIPTIVE_REVIEW" if ready else "COLLECTING_FUTURE_REGIME_OBSERVATION_V1_1"

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
        "serial_covered_contracts": len(covered),
        "serial_true_contract_coverage": None if not contracts else len(covered) / len(contracts),
        "overall": overall,
        "primary_tag_incidence": tag_incidence(records, len(contracts), primary=True),
        "overlapping_tag_incidence": tag_incidence(records, len(contracts), primary=False),
        "primary_regimes": grouped_metrics(records, primary=True),
        "overlapping_tags": grouped_metrics(records, primary=False),
        "by_opportunity_index": by_opportunity_index(records),
        "evidence_readiness": {
            "sample_ready": ready,
            "required_future_full_contracts": MIN_FUTURE_FULL_CONTRACTS,
            "required_protected_exits": MIN_PROTECTED_EXITS,
            "observed_future_full_contracts": len(contracts),
            "observed_protected_exits": protected,
            "readiness_is_not_a_pass_fail_or_promotion_gate": True,
        },
        "fixed_tag_definitions": {
            "TREND_ALIGNED": {"btc5_norm_min": regime_v1.TREND_BTC5_NORM_MIN,
                              "btc15_norm_min": regime_v1.TREND_BTC15_NORM_MIN},
            "KALSHI_LAG": {"requires_trend_aligned": True,
                           "abs_ask15_max": regime_v1.KALSHI_LAG_ABS_ASK15_MAX},
            "ACCELERATION_BURST": {"btc5_norm_min": regime_v1.ACCEL_BTC5_NORM_MIN,
                                   "acceleration_gt_zero": True},
            "REVERSAL_HAZARD": {"any_against_side_or_dual_reversal": True},
            "CHOP_LOW_CONVICTION": {"btc5_norm_max_exclusive": regime_v1.CHOP_BTC5_NORM_MAX,
                                     "btc15_norm_max_exclusive": regime_v1.CHOP_BTC15_NORM_MAX},
            "boolean_semantics": "V1.1_NUMERIC_NONZERO_TRUE",
            "thresholds_changed_from_v1": False,
        },
        "holdout_or_historical_results_used_to_select_thresholds": False,
        "no_threshold_selection": True,
        "no_signal_suppression_or_rescue": True,
        "manual_execution_only": True,
        "automatic_promotion": False,
        "production_logic_changed": False,
        "shadow_only": True,
        "orders": False,
    }
    print("SCALP_REGIME_FORWARD | " + json.dumps(compact(result), separators=(",", ":"), sort_keys=True, default=str), flush=True)
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
                    "no_threshold_selection": True,
                    "automatic_promotion": False,
                    "orders": False, "shadow_only": True,
                })
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15RegimeForwardObservationV11/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_REGIME_FORWARD_HTTP | request", flush=True)

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
                "descriptive_only": True, "orders": False,
            })
        if path == "/summary":
            return self.send_json(200, compact(state))
        if path == "/state":
            return self.send_json(200, state)
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def assert_integrity() -> None:
    regime_v11.assert_integrity()
    if q.ARM_GAIN != 0.05 or q.GIVEBACK != 0.04:
        raise RuntimeError("serial protection lifecycle drifted")
    if MIN_FUTURE_FULL_CONTRACTS != 100 or MIN_PROTECTED_EXITS != 50:
        raise RuntimeError("prospective descriptive readiness gate drifted")


assert_integrity()


def main() -> int:
    print(
        f"{VERSION} START | cutoff={CUTOFF_TEXT or 'MISSING'} | PROSPECTIVE DESCRIPTIVE ONLY | "
        "NO THRESHOLD SELECTION | NO SIGNAL SUPPRESSION | NO ORDERS",
        flush=True,
    )
    threading.Thread(target=loop, name="regime-forward-v11-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
