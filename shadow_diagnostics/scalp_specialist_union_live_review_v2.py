#!/usr/bin/env python3
"""BTC15 read-only live scalp specialist review V2.

SHADOW RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

V2 keeps V1's read-only source contract and adds the normalized Kalshi-lag
fingerprint to the same review snapshot. It never modifies the source event
tape, production bot, FINAL, EARLY, or collector.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import scalp_contract_zone_map_v1 as zones
import scalp_kalshi_lag_fingerprint_v1 as lag
import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_frontier_v1 as union_v1
import scalp_specialist_union_frontier_v2 as union_v2
import scalp_specialist_union_live_review_v1 as live_v1

VERSION = "BTC15_SCALP_SPECIALIST_UNION_LIVE_REVIEW_V2"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(60, int(os.environ.get("SCALP_SPECIALIST_REVIEW_POLL_SEC", "300")))

LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "status": "STARTING",
    "orders": False,
    "manual_execution_only": True,
    "shadow_only": True,
    "production_logic_changed": False,
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0) -> dict[str, Any]:
    universe = union_v1.full_contract_universe(rows)
    if not universe:
        return {
            "ok": False,
            "version": VERSION,
            "status": "FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE",
            "updated_utc": utcnow(),
            "source_sha256": sha,
            "source_bytes": source_bytes,
            "source_rows": len(rows),
            "orders": False,
            "manual_execution_only": True,
            "shadow_only": True,
            "production_logic_changed": False,
            "promotion": False,
        }

    denominator = set(universe)
    split = union_v1.split_universe(universe)
    opps = [r for r in q.build_serial_opportunities(rows) if r.get("contract") in denominator]
    for r in opps:
        r["split"] = split.get(r.get("contract"), "")

    dev = [r for r in opps if r.get("split") == "DEVELOPMENT"]
    lane_cuts = union_v1.calibrate_lane_cuts(dev)
    union_v1.lane_tags(opps, lane_cuts)
    zones.add_zone_tags(opps)

    baseline = union_v1.score_with_true_coverage(opps, denominator)
    lane_breakdown = union_v1.lane_breakdown(opps, denominator)
    zone_map = zones.score_zone_map(opps, denominator)
    cumulative = zones.cumulative_map(opps, denominator)

    union_frontier, union_winner, union_holdout, union_selected_holdout = union_v2.model_frontier(opps, split)

    lag_scales = lag.build_scales(dev)
    lag_frontier, lag_winner, lag_holdout = lag.score_frontier(opps, split, lag_scales)

    return union_v1.clean({
        "ok": True,
        "version": VERSION,
        "status": "RESEARCH_SNAPSHOT_READY",
        "updated_utc": utcnow(),
        "source_sha256": sha,
        "source_bytes": source_bytes,
        "source_rows": len(rows),
        "full_observed_contracts": len(denominator),
        "serial_opportunities": len(opps),
        "split_contracts": {
            s: sum(v == s for v in split.values())
            for s in ("DEVELOPMENT", "VALIDATION", "HOLDOUT")
        },
        "baseline": baseline,
        "specialist_union": {
            "development_only_lane_cuts": lane_cuts,
            "lane_breakdown": lane_breakdown,
            "validation_selected_candidate": union_winner,
            "untouched_holdout_result": union_holdout,
            "holdout_selected_n": len(union_selected_holdout),
            "validation_frontier_rows": len(union_frontier),
        },
        "normalized_kalshi_lag": {
            "normalization": "DEVELOPMENT_ONLY_EMPIRICAL_PERCENTILES",
            "validation_selected_candidate": lag_winner,
            "untouched_holdout_result": lag_holdout,
            "validation_frontier_rows": len(lag_frontier),
            "unit_safety": "BTC/BRTI price units are never directly subtracted from Kalshi contract-price units",
        },
        "contract_zone_map": zone_map,
        "cumulative_coverage": cumulative,
        "orders": False,
        "manual_execution_only": True,
        "shadow_only": True,
        "production_logic_changed": False,
        "automatic_promotion": False,
        "research_warning": (
            "Discovery/review snapshot only. Repeated snapshots do not certify a production rule. "
            "Any selected rule still requires a newly frozen untouched forward test."
        ),
    })


def refresh_once() -> dict[str, Any]:
    rows, sha, source_bytes = live_v1.fetch_rows()
    with LOCK:
        old_sha = STATE.get("source_sha256")
        old_ok = STATE.get("ok")
    if old_ok and old_sha == sha:
        with LOCK:
            STATE["last_poll_utc"] = utcnow()
            return dict(STATE)

    result = analyze_rows(rows, sha=sha, source_bytes=source_bytes)
    result["last_poll_utc"] = utcnow()
    with LOCK:
        STATE.clear()
        STATE.update(result)
        return dict(STATE)


def loop() -> None:
    while True:
        try:
            refresh_once()
        except Exception as exc:
            with LOCK:
                previous = dict(STATE)
                STATE.update({
                    "ok": False,
                    "version": VERSION,
                    "status": "FAIL_CLOSED_SOURCE_OR_ANALYSIS_ERROR",
                    "last_poll_utc": utcnow(),
                    "error": f"{type(exc).__name__}:{exc}",
                    "orders": False,
                    "manual_execution_only": True,
                    "shadow_only": True,
                    "production_logic_changed": False,
                    "last_good_source_sha256": previous.get("source_sha256"),
                })
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15ScalpSpecialistReviewV2/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_SPECIALIST_REVIEW_V2_HTTP | request", flush=True)

    def send_json(self, code: int, obj: dict[str, Any]) -> None:
        raw = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        with LOCK:
            state = dict(STATE)
        if path == "/health":
            return self.send_json(200, {
                "ok": True,
                "version": VERSION,
                "analysis_ok": state.get("ok") is True,
                "analysis_status": state.get("status"),
                "orders": False,
                "shadow_only": True,
            })
        if path == "/state":
            return self.send_json(200, state)
        return self.send_json(404, {"ok": False, "error": "not_found", "orders": False})


def main() -> int:
    print(
        f"{VERSION} START | READ ONLY | POLL={POLL_SEC}s | SIGNAL ONLY | NO ORDERS",
        flush=True,
    )
    t = threading.Thread(target=loop, name="scalp-specialist-review-v2-loop", daemon=True)
    t.start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
