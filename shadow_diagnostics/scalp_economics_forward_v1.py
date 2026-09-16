#!/usr/bin/env python3
"""BTC15 scalp economics prospective forward ledger V1.

SHADOW ONLY | SIGNAL ONLY | NO ORDERS | NO AUTO-PROMOTION

This scorer freezes accounting semantics before a new prospective cutoff. It
uses only fully observed contracts whose first passive observation is at/after
the cutoff. It does not change the scalp detector or protection lifecycle.

The evidence gates are intentionally break-even style, not tuned return targets:
for a lane that has enough protected exits, conservative TAKER_TAKER economics
at both 1- and 10-contract lot sizes must have positive average net, positive
median net, and >50% positive-net exits. These flags support manual review only.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

import scalp_economics_exit_cert_v1 as econ
import scalp_event_schema_adapter_v1 as adapter
import scalp_specialist_union_frontier_v1 as union
import scalp_specialist_union_live_review_v1 as source

VERSION = "BTC15_SCALP_ECONOMICS_FORWARD_V1_FROZEN"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(60, int(os.environ.get("SCALP_ECONOMICS_FORWARD_POLL_SEC", "180")))
CUTOFF_TEXT = os.environ.get("SCALP_ECONOMICS_FORWARD_CUTOFF_UTC", "").strip()

MIN_FULL_CONTRACTS = 100
MIN_OVERALL_PROTECTED_EXITS = 50
LANE_MIN_PROTECTED_EXITS = {"SCALP_1": 40, "SCALP_2": 20, "SCALP_3_PLUS": 20}
GATE_LOTS = (1, 10)

LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "status": "STARTING",
    "cutoff_utc": CUTOFF_TEXT or None,
    "automatic_promotion": False,
    "orders": False,
    "shadow_only": True,
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


def future_universe(rows: list[Mapping[str, Any]], cutoff: datetime) -> tuple[set[str], list[dict[str, Any]]]:
    adapted = adapter.adapt_rows(rows)
    full = union.full_contract_universe(adapted)
    contracts: set[str] = set()
    for c, meta in full.items():
        first = meta.get("first_seen")
        if isinstance(first, datetime) and first >= cutoff:
            contracts.add(c)
    return contracts, adapted


def future_economics_records(adapted: list[Mapping[str, Any]], contracts: set[str]) -> list[dict[str, Any]]:
    # Build the unchanged serial lifecycle, then restrict its outputs to the
    # prospective fully-observed contract universe. PATH rows need not carry a
    # contract field because build_serial_opportunities joins by candidate_id.
    return [r for r in econ.build_records(adapted) if str(r.get("contract") or "") in contracts]


def lane_records(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "OVERALL": list(records),
        "SCALP_1": [r for r in records if int(r.get("opportunity_index") or 0) == 1],
        "SCALP_2": [r for r in records if int(r.get("opportunity_index") or 0) == 2],
        "SCALP_3_PLUS": [r for r in records if int(r.get("opportunity_index") or 0) >= 3],
    }


def _positive_number(v: Any) -> bool:
    try:
        return math.isfinite(float(v)) and float(v) > 0.0
    except Exception:
        return False


def _over_half(v: Any) -> bool:
    try:
        return math.isfinite(float(v)) and float(v) > 0.50
    except Exception:
        return False


def economic_conditions(summary: Mapping[str, Any]) -> dict[str, Any]:
    fees = summary.get("fee_adjusted_protected_exits") or {}
    by_lot: dict[str, Any] = {}
    all_pass = True
    for lot in GATE_LOTS:
        row = ((fees.get(str(lot)) or {}).get("TAKER_TAKER") or {})
        conditions = {
            "avg_net_gt_zero": _positive_number(row.get("avg_net_gain_c_per_contract")),
            "median_net_gt_zero": _positive_number(row.get("median_net_gain_c_per_contract")),
            "positive_net_rate_gt_50pct": _over_half(row.get("positive_net_rate")),
        }
        lot_pass = all(conditions.values())
        by_lot[str(lot)] = {"conditions": conditions, "break_even_evidence_pass": lot_pass}
        all_pass = all_pass and lot_pass
    return {"gate_lots": list(GATE_LOTS), "by_lot": by_lot, "break_even_evidence_pass": all_pass}


def lane_gate(name: str, summary: Mapping[str, Any], future_full_contracts: int) -> dict[str, Any]:
    protected = int(summary.get("protected_exit_signals") or 0)
    if name == "OVERALL":
        sample_ready = future_full_contracts >= MIN_FULL_CONTRACTS and protected >= MIN_OVERALL_PROTECTED_EXITS
        min_protected = MIN_OVERALL_PROTECTED_EXITS
    else:
        min_protected = LANE_MIN_PROTECTED_EXITS[name]
        sample_ready = future_full_contracts >= MIN_FULL_CONTRACTS and protected >= min_protected
    econ_flags = economic_conditions(summary)
    return {
        "sample_ready": sample_ready,
        "future_full_contracts": future_full_contracts,
        "required_future_full_contracts": MIN_FULL_CONTRACTS,
        "protected_exit_signals": protected,
        "required_protected_exits": min_protected,
        "economic_conditions": econ_flags,
        "manual_review_break_even_evidence_pass": bool(sample_ready and econ_flags["break_even_evidence_pass"]),
        "automatic_promotion": False,
    }


def frozen_gate() -> dict[str, Any]:
    return {
        "minimum_future_full_contracts": MIN_FULL_CONTRACTS,
        "minimum_overall_protected_exits": MIN_OVERALL_PROTECTED_EXITS,
        "lane_minimum_protected_exits": dict(LANE_MIN_PROTECTED_EXITS),
        "gate_lot_sizes": list(GATE_LOTS),
        "taker_taker_break_even_conditions": {
            "avg_net_gain_c_per_contract": ">0",
            "median_net_gain_c_per_contract": ">0",
            "positive_net_rate": ">0.50",
        },
        "maker_view_is_secondary": True,
        "unprotected_paths_never_count_as_realized": True,
        "legacy_protection_lifecycle_unchanged": True,
        "automatic_promotion": False,
        "orders": False,
    }


def compact(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": state.get("status"),
        "cutoff_utc": state.get("cutoff_utc"),
        "future_full_contracts": state.get("future_full_contracts"),
        "overall": state.get("overall"),
        "scalp_1": state.get("scalp_1"),
        "scalp_2": state.get("scalp_2"),
        "scalp_3_plus": state.get("scalp_3_plus"),
        "gates": state.get("gates"),
        "frozen_gate": frozen_gate(),
        "automatic_promotion": False,
        "orders": False,
    }


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0,
                 cutoff_text: str | None = None) -> dict[str, Any]:
    text = CUTOFF_TEXT if cutoff_text is None else cutoff_text
    cutoff = parse_cutoff(text)
    if cutoff is None:
        return {
            "ok": False,
            "version": VERSION,
            "status": "FAIL_CLOSED_MISSING_OR_INVALID_CUTOFF",
            "cutoff_utc": text or None,
            "source_sha256": sha,
            "source_rows": len(rows),
            "automatic_promotion": False,
            "orders": False,
        }

    contracts, adapted = future_universe(rows, cutoff)
    records = future_economics_records(adapted, contracts)
    lanes = lane_records(records)
    summaries = {name: econ.summarize(z) for name, z in lanes.items()}
    gates = {name: lane_gate(name, summaries[name], len(contracts)) for name in lanes}

    overall_ready = gates["OVERALL"]["sample_ready"]
    status = "COLLECTING_FUTURE_ECONOMICS_V1" if not overall_ready else "READY_FOR_MANUAL_ECONOMICS_REVIEW"

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
        "overall": summaries["OVERALL"],
        "scalp_1": summaries["SCALP_1"],
        "scalp_2": summaries["SCALP_2"],
        "scalp_3_plus": summaries["SCALP_3_PLUS"],
        "gates": gates,
        "frozen_gate": frozen_gate(),
        "manual_execution_only": True,
        "shadow_only": True,
        "production_logic_changed": False,
        "automatic_promotion": False,
        "orders": False,
    }
    print("SCALP_ECONOMICS_FORWARD | " + json.dumps(compact(result), separators=(",", ":"), sort_keys=True, default=str), flush=True)
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
                    "ok": False,
                    "version": VERSION,
                    "status": "FAIL_CLOSED_ECONOMICS_FORWARD_ERROR",
                    "last_poll_utc": utcnow(),
                    "error": f"{type(exc).__name__}:{exc}",
                    "automatic_promotion": False,
                    "orders": False,
                    "shadow_only": True,
                })
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15EconomicsForwardV1/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_ECONOMICS_FORWARD_HTTP | request", flush=True)

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
            return self.send_json(200, {"ok": True, "analysis_ok": state.get("ok") is True,
                                        "status": state.get("status"), "cutoff_utc": state.get("cutoff_utc"),
                                        "orders": False, "version": VERSION})
        if path == "/summary":
            return self.send_json(200, compact(state))
        if path == "/state":
            return self.send_json(200, state)
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def main() -> int:
    print(f"{VERSION} START | cutoff={CUTOFF_TEXT or 'MISSING'} | SHADOW ONLY | NO AUTO-PROMOTION | NO ORDERS", flush=True)
    threading.Thread(target=loop, name="scalp-economics-forward-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
