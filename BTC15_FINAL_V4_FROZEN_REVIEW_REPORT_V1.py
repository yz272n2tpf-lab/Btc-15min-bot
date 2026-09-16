#!/usr/bin/env python3
"""
BTC15 FINAL V4 frozen review report V1.

PURE / OFFLINE / READ ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

Consumes the authoritative FINAL V4 /state payload and produces a deterministic
review packet. It never recomputes FINAL qualification, changes thresholds, or
auto-promotes anything.

Frozen review gate
------------------
- >=30 eligibility-complete contracts
- >=12 officially settled protected FINAL locks
- collector itself must report sample_ready=True

The report separates directional accuracy, FINAL-only coverage, timing, and
Kalshi entry economics. The project's 93% accuracy floor and 95% stretch marker
are descriptive checks only; neither authorizes promotion.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

VERSION = "BTC15_FINAL_V4_FROZEN_REVIEW_REPORT_V1"
EXPECTED_COLLECTOR_VERSION = "BTC15_FINAL_FORWARD_SCORECARD_V4"
EXPECTED_COVERAGE_SEMANTICS = "FIRST_SEEN_BEFORE_FINAL_ELIGIBILITY_WINDOW"
EXPECTED_FINAL_WINDOW_SECONDS = 480.0
MIN_ELIGIBLE = 30
MIN_SETTLED = 12
ACCURACY_FLOOR = 0.93
ACCURACY_STRETCH = 0.95
EPS = 1e-9


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _f(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _i(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _close(a: Any, b: Any, eps: float = EPS) -> bool:
    x, y = _f(a), _f(b)
    if x is None or y is None:
        return x is None and y is None
    return abs(x - y) <= eps


def _rate(n: int, d: int) -> float | None:
    return None if d <= 0 else n / d


def _live(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    q = payload.get("live")
    return q if isinstance(q, Mapping) else payload


def _integrity(payload: Mapping[str, Any], live: Mapping[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    version = str(payload.get("version") or live.get("version") or "")
    if version != EXPECTED_COLLECTOR_VERSION:
        errors.append(f"collector_version:{version or 'MISSING'}")
    if str(live.get("coverage_universe_semantics") or "") != EXPECTED_COVERAGE_SEMANTICS:
        errors.append("coverage_semantics")
    if not _close(live.get("final_eligibility_open_seconds_left"), EXPECTED_FINAL_WINDOW_SECONDS):
        errors.append("eligibility_window")
    if live.get("full_contract_from_second_zero_required") is not False:
        errors.append("second_zero_required")
    if live.get("full_contract_from_second_zero_claimed") is not False:
        errors.append("second_zero_claimed")
    if live.get("protected_final_thresholds_changed") is not False:
        errors.append("protected_thresholds_changed")
    if live.get("production_behavior_changed") is not False:
        errors.append("production_behavior_changed")
    if live.get("orders") is not False or payload.get("orders") is True:
        errors.append("orders_not_false")
    if live.get("manual_execution_only") is not True:
        errors.append("manual_execution_only_not_true")
    if live.get("numeric_flip_risk_validated") is not False:
        errors.append("numeric_flip_risk_unexpected")

    eligible = _i(live.get("eligibility_complete_contracts"))
    locks = _i(live.get("lock_calls"))
    settled = _i(live.get("settled_lock_calls"))
    correct = _i(live.get("settled_correct_n"))
    le50 = _i(live.get("ask_le_50c_n"))
    settled_le50 = _i(live.get("settled_ask_le_50c_n"))

    if eligible < 0 or locks < 0 or settled < 0 or correct < 0:
        errors.append("negative_counts")
    if locks > eligible:
        errors.append("locks_gt_eligible")
    if settled > locks:
        errors.append("settled_gt_locks")
    if correct > settled:
        errors.append("correct_gt_settled")
    if le50 > locks:
        errors.append("le50_gt_locks")
    if settled_le50 > min(settled, le50):
        errors.append("settled_le50_invalid")

    expected_accuracy = _rate(correct, settled)
    if not _close(live.get("qualified_accuracy"), expected_accuracy):
        errors.append("accuracy_math")
    expected_coverage = _rate(locks, eligible)
    if not _close(live.get("final_only_coverage"), expected_coverage):
        errors.append("coverage_math")
    expected_le50_rate = _rate(le50, locks)
    if not _close(live.get("ask_le_50c_rate"), expected_le50_rate):
        errors.append("le50_rate_math")

    settled_le50_acc = live.get("settled_ask_le_50c_accuracy")
    if settled_le50 == 0 and settled_le50_acc is not None:
        errors.append("le50_accuracy_should_be_null")

    return (not errors), errors


def build_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise TypeError("FINAL V4 review payload must be a mapping")
    live = _live(payload)
    ok, errors = _integrity(payload, live)

    eligible = _i(live.get("eligibility_complete_contracts"))
    excluded_late = _i(live.get("coverage_excluded_late_n"))
    locks = _i(live.get("lock_calls"))
    settled = _i(live.get("settled_lock_calls"))
    correct = _i(live.get("settled_correct_n"))
    accuracy = _f(live.get("qualified_accuracy"))
    coverage = _f(live.get("final_only_coverage"))
    collector_ready = bool(live.get("sample_ready"))
    counts_ready = bool(eligible >= MIN_ELIGIBLE and settled >= MIN_SETTLED)
    review_ready = bool(ok and counts_ready and collector_ready)

    if not ok:
        status = "INVALID_SNAPSHOT_FAIL_CLOSED"
    elif review_ready:
        status = "FINAL_V4_MANUAL_REVIEW_READY"
    else:
        status = "WAITING_FOR_FROZEN_GATE"

    return {
        "version": VERSION,
        "status": status,
        "collector": {
            "version": payload.get("version") or live.get("version"),
            "live_cutoff_utc": live.get("live_cutoff_utc"),
            "coverage_universe_semantics": live.get("coverage_universe_semantics"),
            "final_eligibility_open_seconds_left": _f(live.get("final_eligibility_open_seconds_left")),
        },
        "integrity": {
            "pass": ok,
            "errors": errors,
            "protected_final_thresholds_changed": live.get("protected_final_thresholds_changed"),
            "production_behavior_changed": live.get("production_behavior_changed"),
            "orders": live.get("orders"),
            "manual_execution_only": live.get("manual_execution_only"),
        },
        "frozen_gate": {
            "minimum_eligible_contracts": MIN_ELIGIBLE,
            "minimum_settled_locks": MIN_SETTLED,
            "eligible_contracts": eligible,
            "settled_locks": settled,
            "remaining_eligible": max(0, MIN_ELIGIBLE - eligible),
            "remaining_settled": max(0, MIN_SETTLED - settled),
            "counts_ready": counts_ready,
            "collector_sample_ready": collector_ready,
            "manual_review_ready": review_ready,
        },
        "direction": {
            "lock_calls": locks,
            "settled_correct_n": correct,
            "settled_lock_calls": settled,
            "accuracy": accuracy,
            "project_93pct_floor_met": bool(accuracy is not None and accuracy + EPS >= ACCURACY_FLOOR),
            "project_95pct_stretch_met": bool(accuracy is not None and accuracy + EPS >= ACCURACY_STRETCH),
            "accuracy_is_final_only": True,
        },
        "coverage": {
            "eligible_contracts": eligible,
            "excluded_late_contracts": excluded_late,
            "final_only_coverage": coverage,
            "union_coverage_claimed": False,
        },
        "timing": {
            "avg_minutes_left": _f(live.get("avg_minutes_left")),
            "median_minutes_left": _f(live.get("median_minutes_left")),
            "calls_ge_5m_n": _i(live.get("calls_ge_5m_n")),
        },
        "entry_economics": {
            "avg_locked_side_ask": _f(live.get("avg_preferred_ask")),
            "median_locked_side_ask": _f(live.get("median_preferred_ask")),
            "ask_le_50c_n": _i(live.get("ask_le_50c_n")),
            "ask_le_50c_rate": _f(live.get("ask_le_50c_rate")),
            "settled_ask_le_50c_n": _i(live.get("settled_ask_le_50c_n")),
            "settled_ask_le_50c_accuracy": _f(live.get("settled_ask_le_50c_accuracy")),
            "price_filter_applied": live.get("price_filter_applied"),
            "economics_do_not_change_final_accuracy": True,
        },
        "decision_controls": {
            "auto_promote_allowed": False,
            "threshold_retune_allowed_from_confirmation_sample": False,
            "numeric_flip_risk_validated": False,
            "manual_review_required": True,
        },
    }


def _pct(v: Any) -> str:
    x = _f(v)
    return "—" if x is None else f"{100*x:.2f}%"


def _cents(v: Any) -> str:
    x = _f(v)
    return "—" if x is None else f"{100*x:.1f}¢"


def _mins(v: Any) -> str:
    x = _f(v)
    return "—" if x is None else f"{x:.2f}m"


def render_text(report: Mapping[str, Any]) -> str:
    g = _m(report.get("frozen_gate"))
    d = _m(report.get("direction"))
    c = _m(report.get("coverage"))
    t = _m(report.get("timing"))
    e = _m(report.get("entry_economics"))
    integ = _m(report.get("integrity"))
    lines = [
        "=== BTC15 FINAL V4 FROZEN REVIEW ===",
        f"Status: {report.get('status')}",
        f"Integrity: {'PASS' if integ.get('pass') else 'FAIL'}",
        f"Gate: eligible {g.get('eligible_contracts',0)}/{g.get('minimum_eligible_contracts',30)} · settled {g.get('settled_locks',0)}/{g.get('minimum_settled_locks',12)}",
        f"Remaining: eligible {g.get('remaining_eligible',0)} · settled {g.get('remaining_settled',0)}",
        f"FINAL accuracy: {_pct(d.get('accuracy'))} ({d.get('settled_correct_n',0)}/{d.get('settled_lock_calls',0)})",
        f"Project markers: >=93%={d.get('project_93pct_floor_met')} · >=95%={d.get('project_95pct_stretch_met')}",
        f"FINAL-only coverage: {_pct(c.get('final_only_coverage'))} · excluded late={c.get('excluded_late_contracts',0)}",
        f"Timing: avg {_mins(t.get('avg_minutes_left'))} · median {_mins(t.get('median_minutes_left'))}",
        f"Locked-side ask: avg {_cents(e.get('avg_locked_side_ask'))} · median {_cents(e.get('median_locked_side_ask'))}",
        f"<=50¢ locks: {e.get('ask_le_50c_n',0)} ({_pct(e.get('ask_le_50c_rate'))})",
        "Controls: manual review only · no threshold retune · no auto-promotion · no orders",
    ]
    if integ.get("errors"):
        lines.append("Integrity errors: " + ", ".join(str(x) for x in integ.get("errors") or []))
    return "\n".join(lines) + "\n"


__all__ = [
    "VERSION", "EXPECTED_COLLECTOR_VERSION", "MIN_ELIGIBLE", "MIN_SETTLED",
    "ACCURACY_FLOOR", "ACCURACY_STRETCH", "build_report", "render_text",
]
