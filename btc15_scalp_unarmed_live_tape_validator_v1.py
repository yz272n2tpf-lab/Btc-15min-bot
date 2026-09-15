#!/usr/bin/env python3
"""
BTC15 live-tape validator for the ENDED_UNARMED scalp lifecycle projection.

RESEARCH / SHADOW ONLY | SIGNAL ONLY | NO ORDERS

Reads the existing generalized scalp event export and compares the current
protected serial ladder with a research-only ENDED_UNARMED lifecycle projection.
It also runs meaningful-move coverage, the btc30 tightening tournament, and the
fixed failed-prearm reset tournament.

This service does NOT create a stop-loss or sell rule. Existing +5c arm / 4c
giveback protection is untouched. Kalshi entry price and seconds-left remain
telemetry only. No strategy rule is auto-promoted.
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

import BTC15_SCALP_FAILED_PREARM_RESET_TOURNAMENT_V1 as reset_tournament
import BTC15_SCALP_MEANINGFUL_MOVE_COVERAGE_V1 as meaningful
import BTC15_SCALP_TRIGGER_TIGHTENING_RESEARCH_V1 as tightening
import BTC15_SCALP_UNARMED_TERMINAL_HANDOFF_AUDIT_V1 as handoff
import btc15_scalp_blueprint_forward_v1 as forward

VERSION = "BTC15_SCALP_UNARMED_LIVE_TAPE_VALIDATOR_V1_3"
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


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "NA"
    if isinstance(value, bool):
        return str(value)
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)


def _tightening_decision(tight: dict[str, Any]) -> str:
    if tight.get("development_nominee_btc30_min") is None:
        return "NO_DEVELOPMENT_NOMINEE"
    if not bool(tight.get("holdout_review_ready")):
        return "WAITING_FOR_HOLDOUT"
    if bool(tight.get("holdout_supports_nominee")):
        return "HOLDOUT_SUPPORTS_NOMINEE"
    return "HOLDOUT_REJECTS_NOMINEE"


def _compact_reset_grid(reset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    compact: dict[str, dict[str, Any]] = {}
    for rule, raw in (reset.get("grid") or {}).items():
        cell = dict(raw or {})
        compact[str(rule)] = {
            "triggered": int(cell.get("triggered_before_arm_n") or 0),
            "false_abort_n": int(cell.get("original_later_recovers_plus5_n") or 0),
            "false_abort_rate": cell.get("false_abort_recovery_rate"),
            "later_available": int(cell.get("later_candidate_available_n") or 0),
            "later_completed": int(cell.get("later_candidate_completed_n") or 0),
            "later_plus10": int(cell.get("later_candidate_plus10_n") or 0),
            "later_plus10_rate": cell.get("later_candidate_plus10_rate"),
            "avg_release_gain": cell.get("avg_release_gain"),
        }
    return compact


def summarize(rows: list[dict[str, Any]], source_sha256: str = "") -> dict[str, Any]:
    baseline = forward.build_serial_opportunities(rows)
    projected = handoff.audit(rows)
    moves = meaningful.audit(rows)
    tight = tightening.audit(rows)
    reset = reset_tournament.audit(rows)

    baseline_n = len(baseline)
    projected_n = int(projected.get("projected_completed_serial_opportunities") or 0)
    delta = projected_n - baseline_n
    completed_handoffs = int(projected.get("post_unarmed_later_completed_n") or 0)
    plus10_handoffs = int(projected.get("post_unarmed_later_plus10_n") or 0)
    plus20_handoffs = int(projected.get("post_unarmed_later_plus20_n") or 0)
    ended_unarmed_n = int(projected.get("ended_unarmed_n") or 0)
    armed_unresolved_n = int(projected.get("armed_no_validated_exit_n") or 0)

    dev_base = dict(tight.get("development_baseline") or {})
    dev_nom = dict(tight.get("development_nominee") or {})
    hold_base = dict(tight.get("holdout_baseline") or {})
    hold_nom = dict(tight.get("holdout_nominee") or {})
    true_missed = moves.get("true_post_exit_missed_meaningful_10c")
    lifecycle_review_ready = bool(
        ended_unarmed_n > 0
        and armed_unresolved_n == 0
        and true_missed is not None
        and int(true_missed) == 0
        and projected_n >= baseline_n
    )

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
        "ended_unarmed_n": ended_unarmed_n,
        "ended_unarmed_records": projected.get("ended_unarmed_records") or [],
        "armed_no_validated_exit_n": armed_unresolved_n,
        "armed_no_validated_exit_records": projected.get("armed_no_validated_exit_records") or [],
        "post_unarmed_later_qualified_n": int(projected.get("post_unarmed_later_qualified_n") or 0),
        "post_unarmed_later_completed_n": completed_handoffs,
        "post_unarmed_later_plus10_n": plus10_handoffs,
        "post_unarmed_later_plus20_n": plus20_handoffs,
        "post_unarmed_later_plus10_rate": None if not completed_handoffs else plus10_handoffs / completed_handoffs,
        "post_unarmed_later_plus20_rate": None if not completed_handoffs else plus20_handoffs / completed_handoffs,
        "recovered_handoffs": projected.get("recovered_handoffs") or [],
        "lifecycle_reset_review_ready": lifecycle_review_ready,
        "completed_meaningful_10c_candidates": moves.get("completed_meaningful_10c_candidates"),
        "selected_meaningful_10c": moves.get("selected_meaningful_10c"),
        "selected_sub10": moves.get("selected_sub10"),
        "selected_10c_precision": moves.get("selected_10c_precision"),
        "overlap_meaningful_10c": moves.get("overlap_meaningful_10c"),
        "blocked_prearm_meaningful_10c": moves.get("blocked_prearm_meaningful_10c"),
        "true_post_exit_missed_meaningful_10c": true_missed,
        "serial_addressable_meaningful_10c": moves.get("serial_addressable_meaningful_10c"),
        "baseline_serial_captured_meaningful_10c": moves.get("baseline_serial_captured_meaningful_10c"),
        "baseline_serial_10c_capture_rate": moves.get("baseline_serial_10c_capture_rate"),
        "projected_unarmed_lifecycle_captured_meaningful_10c": moves.get("projected_unarmed_lifecycle_captured_meaningful_10c"),
        "projected_unarmed_lifecycle_10c_capture_rate": moves.get("projected_unarmed_lifecycle_10c_capture_rate"),
        "projected_additional_10c_captured": moves.get("projected_additional_10c_captured"),
        "meaningful_10c_by_classification": moves.get("meaningful_10c_by_classification") or {},
        "tightening_records_n": tight.get("records_n"),
        "tightening_development_n": tight.get("development_n"),
        "tightening_holdout_n": tight.get("holdout_n"),
        "tightening_development_baseline": dev_base,
        "tightening_development_nominee_btc30_min": tight.get("development_nominee_btc30_min"),
        "tightening_development_nominee": dev_nom or None,
        "tightening_holdout_baseline": hold_base,
        "tightening_holdout_nominee": hold_nom or None,
        "tightening_holdout_review_ready": bool(tight.get("holdout_review_ready")),
        "tightening_holdout_supports_nominee": bool(tight.get("holdout_supports_nominee")),
        "tightening_decision": _tightening_decision(tight),
        "tightening_auto_promote_allowed": False,
        "prearm_reset_completed_primary_n": int(reset.get("completed_primary_n") or 0),
        "prearm_reset_failed_primary_n": int(reset.get("failed_prearm_primary_n") or 0),
        "prearm_reset_failed_primary_candidate_ids": reset.get("failed_primary_candidate_ids") or [],
        "prearm_reset_grid": _compact_reset_grid(reset),
        "prearm_reset_rule_selected": False,
        "prearm_reset_auto_promote_allowed": False,
        "protected_thresholds_changed": False,
        "stop_loss_rule_selected": False,
        "ended_unarmed_is_actionable_exit": False,
        "entry_price_filter_applied": False,
        "price_is_telemetry_only": True,
        "fixed_time_window_applied": False,
        "seconds_left_is_telemetry_only": True,
        "auto_promote_allowed": False,
        "research_only": True,
        "manual_execution_only": True,
        "orders": False,
        "note": (
            "ENDED_UNARMED is a lifecycle/reset projection after collector RESULT, not a trade exit. "
            "btc30 tightening and failed-prearm reset rules are descriptive research only; no rule is auto-promoted."
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
        f"armed_no_exit={summary['armed_no_validated_exit_n']} | "
        f"handoff_completed={summary['post_unarmed_later_completed_n']} | "
        f"handoff_+10={summary['post_unarmed_later_plus10_n']} | "
        f"all_+10={summary['completed_meaningful_10c_candidates']} | "
        f"selected_+10={summary['selected_meaningful_10c']} | "
        f"blocked_+10={summary['blocked_prearm_meaningful_10c']} | "
        f"true_missed_+10={summary['true_post_exit_missed_meaningful_10c']} | "
        f"lifecycle_review_ready={summary['lifecycle_reset_review_ready']} | "
        f"tighten_nominee={summary['tightening_development_nominee_btc30_min']} | "
        f"tighten_holdout_ready={summary['tightening_holdout_review_ready']} | "
        f"tighten_support={summary['tightening_holdout_supports_nominee']} | "
        "RESEARCH ONLY | NO ORDERS",
        flush=True,
    )

    dev_base = summary.get("tightening_development_baseline") or {}
    dev_nom = summary.get("tightening_development_nominee") or {}
    hold_base = summary.get("tightening_holdout_baseline") or {}
    hold_nom = summary.get("tightening_holdout_nominee") or {}
    print(
        "SCALP TIGHTENING HOLDOUT | "
        f"decision={summary['tightening_decision']} | "
        f"nominee={_fmt(summary.get('tightening_development_nominee_btc30_min'),1)} | "
        f"dev_base_n={dev_base.get('n','NA')} | dev_base_+10={_fmt(dev_base.get('plus10_rate'))} | "
        f"dev_nom_n={dev_nom.get('n','NA')} | dev_nom_+10={_fmt(dev_nom.get('plus10_rate'))} | "
        f"dev_winner_retention={_fmt(dev_nom.get('plus10_winner_retention'))} | "
        f"hold_base_n={hold_base.get('n','NA')} | hold_base_+10={_fmt(hold_base.get('plus10_rate'))} | "
        f"hold_nom_n={hold_nom.get('n','NA')} | hold_nom_+10={_fmt(hold_nom.get('plus10_rate'))} | "
        f"hold_winner_retention={_fmt(hold_nom.get('plus10_winner_retention'))} | "
        f"hold_selected_retained={_fmt(hold_nom.get('selected_share_retained'))} | "
        f"support={summary['tightening_holdout_supports_nominee']} | "
        "RESEARCH ONLY | NO AUTO-PROMOTE | NO ORDERS",
        flush=True,
    )

    print(
        "SCALP PREARM RESET GRID | "
        f"completed_primaries={summary['prearm_reset_completed_primary_n']} | "
        f"failed_primaries={summary['prearm_reset_failed_primary_n']} | "
        f"grid={json.dumps(summary['prearm_reset_grid'], separators=(',', ':'))} | "
        "DESCRIPTIVE ONLY | NO RULE SELECTED | NO ORDERS",
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
    server_version = "BTC15ScalpUnarmedLiveTape/1.3"

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
