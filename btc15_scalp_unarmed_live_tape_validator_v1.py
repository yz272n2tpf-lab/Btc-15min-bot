#!/usr/bin/env python3
"""
BTC15 live-tape validator for the ENDED_UNARMED scalp lifecycle projection.

RESEARCH / SHADOW ONLY | SIGNAL ONLY | NO ORDERS

This service reads the existing generalized scalp event export and compares:
1) the current protected serial ladder, which can stop after a completed scalp
   that never armed +5c; versus
2) a research-only lifecycle projection that treats collector RESULT + never
   armed as ENDED_UNARMED (informational terminal only), then resumes scanning
   for the next frozen-qualified scalp.

It also decomposes observed 10c+ moves into selected, overlap, blocked-by-unarmed,
and true post-exit miss classes so coverage and signal precision are not confused.

It does NOT create a stop-loss or sell rule. The existing +5c arm / 4c giveback
profit-protection thresholds are untouched. Kalshi entry price remains telemetry
only and is never used as an entry/suppression filter.
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

import BTC15_SCALP_MEANINGFUL_MOVE_COVERAGE_V1 as meaningful
import BTC15_SCALP_UNARMED_TERMINAL_HANDOFF_AUDIT_V1 as handoff
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_UNARMED_LIVE_TAPE_VALIDATOR_V1"
PORT = int(os.environ.get("PORT", "8080"))
POLL_SEC = max(20, int(os.environ.get("SCALP_UNARMED_LIVE_POLL_SEC", "45")))

LOCK = threading.Lock()
STATE: dict[str, Any] = {
    "ok": False,
    "version": VERSION,
    "status": "STARTING",
    "research_only": True,
    "orders": False,
    "manual_execution_only": True,
}


def summarize(rows: list[dict[str, Any]], source_sha256: str = "") -> dict[str, Any]:
    baseline = forward.build_serial_opportunities(rows)
    projected = handoff.audit(rows)
    moves = meaningful.audit(rows)

    baseline_n = len(baseline)
    projected_n = int(projected.get("projected_completed_serial_opportunities") or 0)
    delta = projected_n - baseline_n
    completed_handoffs = int(projected.get("post_unarmed_later_completed_n") or 0)
    plus10_handoffs = int(projected.get("post_unarmed_later_plus10_n") or 0)
    plus20_handoffs = int(projected.get("post_unarmed_later_plus20_n") or 0)

    return {
        "ok": True,
        "version": VERSION,
        "status": "OBSERVING_LIVE_TAPE",
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": source_sha256,
        "source_rows": len(rows),
        "cutoff_utc": forward.CUTOFF_RAW,
        "baseline_completed_serial_opportunities": baseline_n,
        "projected_completed_serial_opportunities": projected_n,
        "projected_additional_serial_opportunities": delta,
        "ended_unarmed_n": int(projected.get("ended_unarmed_n") or 0),
        "post_unarmed_later_qualified_n": int(projected.get("post_unarmed_later_qualified_n") or 0),
        "post_unarmed_later_completed_n": completed_handoffs,
        "post_unarmed_later_plus10_n": plus10_handoffs,
        "post_unarmed_later_plus20_n": plus20_handoffs,
        "post_unarmed_later_plus10_rate": None if not completed_handoffs else plus10_handoffs / completed_handoffs,
        "post_unarmed_later_plus20_rate": None if not completed_handoffs else plus20_handoffs / completed_handoffs,
        "recovered_handoffs": projected.get("recovered_handoffs") or [],
        "ended_unarmed_records": projected.get("ended_unarmed_records") or [],
        "completed_meaningful_10c_candidates": moves.get("completed_meaningful_10c_candidates"),
        "selected_meaningful_10c": moves.get("selected_meaningful_10c"),
        "selected_sub10": moves.get("selected_sub10"),
        "selected_10c_precision": moves.get("selected_10c_precision"),
        "overlap_meaningful_10c": moves.get("overlap_meaningful_10c"),
        "blocked_prearm_meaningful_10c": moves.get("blocked_prearm_meaningful_10c"),
        "true_post_exit_missed_meaningful_10c": moves.get("true_post_exit_missed_meaningful_10c"),
        "serial_addressable_meaningful_10c": moves.get("serial_addressable_meaningful_10c"),
        "baseline_serial_captured_meaningful_10c": moves.get("baseline_serial_captured_meaningful_10c"),
        "baseline_serial_10c_capture_rate": moves.get("baseline_serial_10c_capture_rate"),
        "projected_unarmed_lifecycle_captured_meaningful_10c": moves.get("projected_unarmed_lifecycle_captured_meaningful_10c"),
        "projected_unarmed_lifecycle_10c_capture_rate": moves.get("projected_unarmed_lifecycle_10c_capture_rate"),
        "projected_additional_10c_captured": moves.get("projected_additional_10c_captured"),
        "meaningful_10c_by_classification": moves.get("meaningful_10c_by_classification") or {},
        "protected_thresholds_changed": False,
        "stop_loss_rule_selected": False,
        "ended_unarmed_is_actionable_exit": False,
        "entry_price_filter_applied": False,
        "price_is_telemetry_only": True,
        "auto_promote_allowed": False,
        "research_only": True,
        "manual_execution_only": True,
        "orders": False,
        "note": (
            "ENDED_UNARMED is a lifecycle/reset projection after collector RESULT, "
            "not a trade exit. 10c coverage is descriptive only. Live strategy remains unchanged."
        ),
    }


def cycle() -> dict[str, Any]:
    rows, sha = forward.fetch_csv_rows()
    summary = summarize(rows, sha)
    with LOCK:
        STATE.clear()
        STATE.update(summary)
    print(
        "SCALP UNARMED LIVE TAPE | "
        f"baseline={summary['baseline_completed_serial_opportunities']} | "
        f"projected={summary['projected_completed_serial_opportunities']} | "
        f"additional={summary['projected_additional_serial_opportunities']} | "
        f"ended_unarmed={summary['ended_unarmed_n']} | "
        f"handoff_completed={summary['post_unarmed_later_completed_n']} | "
        f"handoff_+10={summary['post_unarmed_later_plus10_n']} | "
        f"all_+10={summary['completed_meaningful_10c_candidates']} | "
        f"selected_+10={summary['selected_meaningful_10c']} | "
        f"blocked_+10={summary['blocked_prearm_meaningful_10c']} | "
        f"true_missed_+10={summary['true_post_exit_missed_meaningful_10c']} | "
        "RESEARCH ONLY | NO ORDERS",
        flush=True,
    )
    return summary


def worker() -> None:
    while True:
        try:
            cycle()
        except Exception as exc:
            with LOCK:
                STATE.update({
                    "ok": False,
                    "status": "ERROR_RETRYING",
                    "last_error": f"{type(exc).__name__}: {exc}",
                    "research_only": True,
                    "orders": False,
                    "manual_execution_only": True,
                })
            print(
                f"SCALP UNARMED LIVE TAPE ERROR | {type(exc).__name__}: {exc} | "
                "RETRYING | NO ORDERS",
                flush=True,
            )
        time.sleep(POLL_SEC)


class Handler(BaseHTTPRequestHandler):
    server_version = "BTC15ScalpUnarmedLiveTape/1.0"

    def log_message(self, fmt, *args):
        return

    def _json(self, code: int, obj: Any) -> None:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in {"/", "/health", "/summary.json"}:
            with LOCK:
                data = dict(STATE)
            return self._json(200 if data.get("ok") else 503, data)
        return self._json(404, {"ok": False, "orders": False, "error": "not_found"})

    def _reject(self):
        return self._json(405, {"ok": False, "orders": False, "error": "read_only_shadow"})

    do_POST = _reject
    do_PUT = _reject
    do_PATCH = _reject
    do_DELETE = _reject


def main() -> int:
    print(
        f"{VERSION} START | cutoff={forward.CUTOFF_RAW} | poll={POLL_SEC}s | "
        "READ ONLY | SIGNAL ONLY | NO ORDERS",
        flush=True,
    )
    cycle()
    threading.Thread(target=worker, name="scalp-unarmed-live-tape", daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
