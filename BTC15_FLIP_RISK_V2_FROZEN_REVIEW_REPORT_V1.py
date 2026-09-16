#!/usr/bin/env python3
"""BTC15 Direct-BRTI Flip Risk V2 frozen review report.

PURE / OFFLINE / READ ONLY | SHADOW ONLY | MANUAL EXECUTION | NO ORDERS

This report mirrors the predeclared future-only V2 calibration decision tree.
It does not fit/calibrate a model, recompute predictions, change any signal, or
approve a user-facing numeric Flip Risk. A V2 PASS earns manual review only.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

VERSION = "BTC15_FLIP_RISK_V2_FROZEN_REVIEW_REPORT_V1"
EXPECTED_COLLECTOR_VERSION = "BTC15_DIRECT_BRTI_FLIP_RISK_FORWARD_V2"
EXPECTED_TRAIN_SNAPSHOTS = 593
EXPECTED_CAL_SNAPSHOTS = 214
MIN_COMPLETE_CONTRACTS = 30
MAX_WAIT_COMPLETE_CONTRACTS = 50
MIN_SETTLED_PREDICTIONS = 240
MIN_HIGH_STAY_SNAPSHOTS = 30
MIN_HIGH_STAY_CONTRACTS = 8
MIN_BRIER_SKILL = 0.05
MAX_WEIGHTED_CAL_ERROR = 0.05
MAX_BIN_ERROR_N30 = 0.10
MIN_RELIABILITY_BINS = 3
MIN_RELIABILITY_SPEARMAN = 0.80
MIN_HIGH_STAY_ACTUAL = 0.90
MAX_TIME_BUCKET_ERROR = 0.15
EPS = 1e-9


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _i(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _f(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _close(a: Any, b: Any, eps: float = 1e-8) -> bool:
    x, y = _f(a), _f(b)
    if x is None or y is None:
        return x is None and y is None
    return abs(x - y) <= eps


def _live(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    q = payload.get("live")
    return q if isinstance(q, Mapping) else payload


def build_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise TypeError("Flip V2 review payload must be a mapping")
    s = _live(payload)
    errors: list[str] = []

    version = str(payload.get("version") or s.get("version") or "")
    if version != EXPECTED_COLLECTOR_VERSION:
        errors.append(f"collector_version:{version or 'MISSING'}")
    if s.get("model_ready") is not True:
        errors.append("model_not_ready")
    if _i(s.get("historical_train_snapshots")) != EXPECTED_TRAIN_SNAPSHOTS:
        errors.append("historical_train_snapshot_drift")
    if _i(s.get("historical_cal_snapshots")) != EXPECTED_CAL_SNAPSHOTS:
        errors.append("historical_cal_snapshot_drift")
    if s.get("production_changed") is not False:
        errors.append("production_changed")
    if s.get("orders") is not False or payload.get("orders") is True:
        errors.append("orders_not_false")
    if s.get("manual_execution_only") is not True:
        errors.append("manual_execution_only_not_true")
    if s.get("numeric_flip_risk_user_facing_allowed") is not False:
        errors.append("numeric_flip_risk_exposed_early")

    eligible = _i(s.get("eligible_contracts"))
    complete = _i(s.get("prediction_complete_contracts"))
    settled_complete = _i(s.get("settled_prediction_complete_contracts"))
    settled_preds = _i(s.get("settled_review_predictions"))
    captured = _i(s.get("all_captured_predictions"))
    stay_n = _i(s.get("stay90_snapshots"))
    stay_contracts = _i(s.get("stay90_contracts"))
    if any(x < 0 for x in (eligible, complete, settled_complete, settled_preds, captured, stay_n, stay_contracts)):
        errors.append("negative_counts")
    if complete > eligible:
        errors.append("complete_gt_eligible")
    if settled_complete > complete:
        errors.append("settled_complete_gt_complete")
    if settled_preds > captured:
        errors.append("settled_preds_gt_captured")
    if stay_contracts > settled_complete:
        errors.append("stay_contracts_gt_settled_complete")
    if stay_n > settled_preds:
        errors.append("stay_snapshots_gt_settled_preds")

    base_ready_expected = bool(
        settled_complete >= MIN_COMPLETE_CONTRACTS
        and settled_preds >= MIN_SETTLED_PREDICTIONS
    )
    if bool(s.get("sample_ready")) != base_ready_expected:
        errors.append("sample_ready_math")

    high_ready_expected = bool(stay_n >= MIN_HIGH_STAY_SNAPSHOTS)
    if bool(s.get("high_stay_ready")) != high_ready_expected:
        errors.append("high_stay_ready_math")

    forced_high_fail_expected = bool(
        settled_complete >= MAX_WAIT_COMPLETE_CONTRACTS and not high_ready_expected
    )
    if bool(s.get("forced_high_stay_fail")) != forced_high_fail_expected:
        errors.append("forced_high_stay_fail_math")

    decision_ready_expected = bool(
        base_ready_expected and (high_ready_expected or forced_high_fail_expected)
    )
    if bool(s.get("decision_ready")) != decision_ready_expected:
        errors.append("decision_ready_math")

    reliability = s.get("reliability") if isinstance(s.get("reliability"), list) else []
    populated_rel = [x for x in reliability if isinstance(x, Mapping) and _i(x.get("n")) >= 20]
    for row in populated_rel:
        stated, actual, err = _f(row.get("stated")), _f(row.get("actual")), _f(row.get("error"))
        if None in (stated, actual, err) or not _close(err, abs(stated - actual)):
            errors.append("reliability_row_math")
            break
    if populated_rel:
        total_n = sum(_i(x.get("n")) for x in populated_rel)
        calc_ece = sum(_i(x.get("n")) * float(_f(x.get("error")) or 0.0) for x in populated_rel) / total_n
        if not _close(s.get("weighted_abs_calibration_error"), calc_ece):
            errors.append("ece_math")
        errs_n30 = [float(_f(x.get("error")) or 0.0) for x in populated_rel if _i(x.get("n")) >= 30]
        calc_max30 = max(errs_n30) if errs_n30 else None
        if not _close(s.get("max_bin_error_n30"), calc_max30):
            errors.append("max_bin_error_math")

    raw_brier = _f(s.get("raw_brier"))
    v2_brier = _f(s.get("v2_brier"))
    null_brier = _f(s.get("null_brier"))
    skill = _f(s.get("brier_skill"))
    if null_brier is not None and null_brier > 0 and v2_brier is not None:
        if not _close(skill, 1.0 - v2_brier / null_brier):
            errors.append("brier_skill_math")

    brier_expected = bool(
        v2_brier is not None and raw_brier is not None
        and v2_brier <= raw_brier + EPS
        and skill is not None and skill >= MIN_BRIER_SKILL - EPS
    )
    rel_spearman = _f(s.get("reliability_spearman"))
    ece = _f(s.get("weighted_abs_calibration_error"))
    max30 = _f(s.get("max_bin_error_n30"))
    reliability_expected = bool(
        len(populated_rel) >= MIN_RELIABILITY_BINS
        and ece is not None and ece <= MAX_WEIGHTED_CAL_ERROR + EPS
        and max30 is not None and max30 <= MAX_BIN_ERROR_N30 + EPS
        and rel_spearman is not None and rel_spearman >= MIN_RELIABILITY_SPEARMAN - EPS
    )
    stay_actual = _f(s.get("stay90_actual_stay"))
    high_expected = bool(
        high_ready_expected
        and stay_contracts >= MIN_HIGH_STAY_CONTRACTS
        and stay_actual is not None and stay_actual >= MIN_HIGH_STAY_ACTUAL - EPS
    )

    time_rows = s.get("time_buckets") if isinstance(s.get("time_buckets"), list) else []
    time_expected = True
    for row in time_rows:
        if not isinstance(row, Mapping) or _i(row.get("n")) < 20:
            continue
        stated, actual, err = _f(row.get("stated")), _f(row.get("actual")), _f(row.get("error"))
        if None in (stated, actual, err) or not _close(err, abs(stated - actual)):
            errors.append("time_bucket_math")
            time_expected = False
            continue
        if err > MAX_TIME_BUCKET_ERROR + EPS:
            time_expected = False
    if bool(s.get("time_ok")) != bool(time_expected):
        errors.append("time_gate_math")

    # Gate booleans matter only after metrics exist; when the review frame is not
    # populated the collector can legitimately omit them.
    if v2_brier is not None and bool(s.get("brier_gate_ok")) != brier_expected:
        errors.append("brier_gate_math")
    if reliability and bool(s.get("reliability_gate_ok")) != reliability_expected:
        errors.append("reliability_gate_math")
    if stay_actual is not None and bool(s.get("high_stay_gate_ok")) != high_expected:
        errors.append("high_stay_gate_math")

    pass_expected = bool(
        decision_ready_expected
        and not forced_high_fail_expected
        and brier_expected
        and reliability_expected
        and high_expected
        and time_expected
    )
    if bool(s.get("gate_pass")) != pass_expected:
        errors.append("gate_pass_math")

    status = str(s.get("status") or "")
    if pass_expected and status != "READY_FOR_NUMERIC_FLIP_RISK_MANUAL_REVIEW":
        errors.append("pass_status_mismatch")
    if decision_ready_expected and not pass_expected and status != "FUTURE_V2_REVIEW_SAMPLE_FAILED":
        errors.append("fail_status_mismatch")
    if base_ready_expected and not decision_ready_expected and not high_ready_expected and status != "COLLECTING_HIGH_STAY_COHORT":
        errors.append("high_stay_wait_status_mismatch")

    integrity = not errors
    if not integrity:
        review_status = "INVALID_SNAPSHOT_FAIL_CLOSED"
    elif pass_expected:
        review_status = "READY_FOR_NUMERIC_FLIP_RISK_MANUAL_REVIEW"
    elif decision_ready_expected:
        review_status = "FUTURE_V2_REVIEW_SAMPLE_FAILED"
    elif base_ready_expected:
        review_status = "COLLECTING_HIGH_STAY_COHORT"
    else:
        review_status = "COLLECTING_FUTURE_V2"

    return {
        "version": VERSION,
        "status": review_status,
        "integrity": {"pass": integrity, "errors": errors},
        "sample_progress": {
            "eligible_contracts": eligible,
            "prediction_complete_contracts": complete,
            "settled_prediction_complete_contracts": settled_complete,
            "settled_predictions": settled_preds,
            "minimum_complete_contracts": MIN_COMPLETE_CONTRACTS,
            "minimum_settled_predictions": MIN_SETTLED_PREDICTIONS,
            "remaining_complete_contracts": max(0, MIN_COMPLETE_CONTRACTS - settled_complete),
            "remaining_settled_predictions": max(0, MIN_SETTLED_PREDICTIONS - settled_preds),
            "base_sample_ready": base_ready_expected,
        },
        "high_stay_progress": {
            "stay90_snapshots": stay_n,
            "stay90_contracts": stay_contracts,
            "minimum_snapshots": MIN_HIGH_STAY_SNAPSHOTS,
            "minimum_contracts_when_ready": MIN_HIGH_STAY_CONTRACTS,
            "remaining_snapshots": max(0, MIN_HIGH_STAY_SNAPSHOTS - stay_n),
            "high_stay_ready": high_ready_expected,
            "forced_fail_at_50_complete": forced_high_fail_expected,
        },
        "calibration": {
            "raw_brier": raw_brier,
            "v2_brier": v2_brier,
            "null_brier": null_brier,
            "brier_skill": skill,
            "brier_gate_ok": brier_expected,
            "weighted_abs_calibration_error": ece,
            "max_bin_error_n30": max30,
            "reliability_bins_n20": len(populated_rel),
            "reliability_spearman": rel_spearman,
            "reliability_gate_ok": reliability_expected,
            "stay90_actual_stay": stay_actual,
            "high_stay_gate_ok": high_expected,
            "time_gate_ok": time_expected,
        },
        "decision": {
            "decision_ready": decision_ready_expected,
            "gate_pass": pass_expected,
            "manual_review_only_if_pass": True,
            "numeric_user_facing_allowed": False,
            "same_sample_retune_allowed": False,
            "auto_promote_allowed": False,
            "production_change_allowed": False,
            "orders": False,
        },
    }


def _pct(v: Any) -> str:
    x = _f(v)
    return "—" if x is None else f"{100*x:.2f}%"


def render_text(report: Mapping[str, Any]) -> str:
    p = _m(report.get("sample_progress")); h = _m(report.get("high_stay_progress")); c = _m(report.get("calibration")); d = _m(report.get("decision")); i = _m(report.get("integrity"))
    lines = [
        "=== BTC15 FLIP RISK V2 FROZEN REVIEW ===",
        f"Status: {report.get('status')}",
        f"Integrity: {'PASS' if i.get('pass') else 'FAIL'}",
        f"Base sample: complete {p.get('settled_prediction_complete_contracts',0)}/30 · settled predictions {p.get('settled_predictions',0)}/240",
        f"High-stay cohort: {h.get('stay90_snapshots',0)}/30 snapshots · {h.get('stay90_contracts',0)} contracts",
        f"Brier skill: {_pct(c.get('brier_skill'))} · gate={c.get('brier_gate_ok')}",
        f"Calibration error: {_pct(c.get('weighted_abs_calibration_error'))} · max n>=30 bin {_pct(c.get('max_bin_error_n30'))} · reliability gate={c.get('reliability_gate_ok')}",
        f"Stay>=90 actual: {_pct(c.get('stay90_actual_stay'))} · gate={c.get('high_stay_gate_ok')}",
        f"Time conditioning gate: {c.get('time_gate_ok')}",
        f"Decision ready={d.get('decision_ready')} · gate pass={d.get('gate_pass')}",
        "Numeric Flip Risk remains HIDDEN · PASS is manual review only · no same-sample retune · no auto-promotion · no orders",
    ]
    if i.get("errors"):
        lines.append("Integrity errors: " + ", ".join(map(str, i.get("errors") or [])))
    return "\n".join(lines) + "\n"


__all__ = ["VERSION", "build_report", "render_text"]
