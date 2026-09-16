#!/usr/bin/env python3
"""BTC15 read-only live scalp specialist review V3.

SHADOW RESEARCH ONLY | SIGNAL ONLY | NO ORDERS

V3 preserves V2 and adds:
- multi-objective Pareto audit of the validation frontier;
- specialist-lane complementarity/overlap audit.

No production writes, no order capability, no automatic promotion.
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

import scalp_lane_complementarity_v1 as complement
import scalp_multiobjective_pareto_v1 as pareto
import scalp_opportunity_quality_frontier_v1 as q
import scalp_specialist_union_frontier_v1 as union_v1
import scalp_specialist_union_frontier_v2 as union_v2
import scalp_specialist_union_live_review_v1 as live_v1
import scalp_specialist_union_live_review_v2 as live_v2

VERSION = "BTC15_SCALP_SPECIALIST_UNION_LIVE_REVIEW_V3"
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


def augment_analysis(rows: list[dict[str, str]], base: dict[str, Any]) -> dict[str, Any]:
    """Add Pareto + complementarity without changing V2 scoring semantics."""
    if base.get("ok") is not True:
        out = dict(base)
        out["version"] = VERSION
        return out

    universe = union_v1.full_contract_universe(rows)
    if not universe:
        out = dict(base)
        out.update({
            "ok": False,
            "version": VERSION,
            "status": "FAIL_CLOSED_NO_FULL_CONTRACT_UNIVERSE",
            "automatic_promotion": False,
        })
        return out

    denominator = set(universe)
    split = union_v1.split_universe(universe)
    opps = [r for r in q.build_serial_opportunities(rows) if r.get("contract") in denominator]
    for r in opps:
        r["split"] = split.get(r.get("contract"), "")
    dev = [r for r in opps if r.get("split") == "DEVELOPMENT"]
    cuts = union_v1.calibrate_lane_cuts(dev)
    union_v1.lane_tags(opps, cuts)

    frontier, _, _, _ = union_v2.model_frontier(opps, split)
    valid_frontier = [r for r in frontier if not r.get("error")]
    min_n = max(8, int(max(1, len([r for r in opps if r.get("split") == "VALIDATION"])) * .15))
    p = pareto.summarize(valid_frontier, min_n=min_n)

    comp = {
        "unique_lane_coverage": complement.unique_lane_coverage(opps, denominator),
        "pairwise_overlap": complement.pairwise_overlap(opps, denominator),
        "subset_frontier": complement.subset_frontier(opps, denominator),
    }

    out = dict(base)
    out.update({
        "version": VERSION,
        "multiobjective_pareto": p,
        "lane_complementarity": comp,
        "automatic_promotion": False,
        "v3_warning": (
            "Pareto and complementarity are validation/research diagnostics only. "
            "They cannot select or certify a production rule."
        ),
    })
    return union_v1.clean(out)


def analyze_rows(rows: list[dict[str, str]], sha: str = "", source_bytes: int = 0) -> dict[str, Any]:
    base = live_v2.analyze_rows(rows, sha=sha, source_bytes=source_bytes)
    return augment_analysis(rows, base)


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
    server_version = "BTC15ScalpSpecialistReviewV3/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("SCALP_SPECIALIST_REVIEW_V3_HTTP | request", flush=True)

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
    print(f"{VERSION} START | READ ONLY | POLL={POLL_SEC}s | SIGNAL ONLY | NO ORDERS", flush=True)
    threading.Thread(target=loop, name="scalp-specialist-review-v3-loop", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
