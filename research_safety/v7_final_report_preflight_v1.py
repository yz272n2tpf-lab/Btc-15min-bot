#!/usr/bin/env python3
"""Fail-closed completeness/safety preflight for V7 research final reports.

This module validates report structure and cross-section consistency only.
It embeds no qualification thresholds, changes no collector behavior, and
never promotes anything to production.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ALLOWED_DECISIONS = {"KEEP", "TIGHTEN", "REJECT", "MORE_DATA"}
ALLOWED_ARCHITECTURE_STATUS = {
    "MORE_DATA",
    "REJECT_ALL_LANES",
    "READY_FOR_MANUAL_FINALIZATION",
}
REQUIRED_DICT_SECTIONS = (
    "result_source_authority",
    "scorecard",
    "evidence_decomposition",
    "contract_independence",
    "brti_reliability",
    "data_quality_incidents",
    "summary_staleness",
    "freeze_gate",
    "architecture_decision",
)


def validate_report(report):
    failures = []

    if not isinstance(report, dict):
        return {
            "schema_version": 1,
            "status": "FAIL",
            "checks_total": 1,
            "checks_passed": 0,
            "failure_codes": ["REPORT_NOT_OBJECT"],
            "production_promotion": "NOT_PERFORMED",
        }

    checks_total = 0
    checks_passed = 0

    def check(condition, code):
        nonlocal checks_total, checks_passed
        checks_total += 1
        if condition:
            checks_passed += 1
        else:
            failures.append(code)

    check(isinstance(report.get("schema_version"), int) and report["schema_version"] >= 6, "SCHEMA_VERSION_UNSUPPORTED")
    check(report.get("collector_identity") == "LEAD_V7", "COLLECTOR_IDENTITY_MISMATCH")
    check(report.get("production_promotion") == "NOT_PERFORMED", "PRODUCTION_PROMOTION_NOT_LOCKED")

    for section in REQUIRED_DICT_SECTIONS:
        check(isinstance(report.get(section), dict), f"MISSING_OR_INVALID_SECTION:{section}")

    authority = report.get("result_source_authority", {})
    if isinstance(authority, dict):
        check(authority.get("scoring_source") == "RESULT_STREAM", "SCORING_SOURCE_NOT_RESULT_STREAM")
        check(authority.get("contract_summary_role") == "ADVISORY_ONLY", "CONTRACT_SUMMARY_NOT_ADVISORY")

    gate = report.get("freeze_gate", {})
    gate_lanes = gate.get("lanes", {}) if isinstance(gate, dict) else {}
    check(isinstance(gate_lanes, dict) and bool(gate_lanes), "FREEZE_GATE_LANES_EMPTY")

    normalized_gate = {}
    if isinstance(gate_lanes, dict):
        for lane, payload in sorted(gate_lanes.items()):
            valid_payload = isinstance(payload, dict)
            check(valid_payload, f"FREEZE_GATE_LANE_INVALID:{lane}")
            if not valid_payload:
                continue
            decision = payload.get("decision")
            check(decision in ALLOWED_DECISIONS, f"FREEZE_GATE_DECISION_INVALID:{lane}")
            if decision in ALLOWED_DECISIONS:
                normalized_gate[lane] = decision

    architecture = report.get("architecture_decision", {})
    arch_lanes = architecture.get("lanes", {}) if isinstance(architecture, dict) else {}
    if isinstance(architecture, dict):
        check(architecture.get("collector_identity") == "LEAD_V7", "ARCHITECTURE_COLLECTOR_IDENTITY_MISMATCH")
        check(architecture.get("production_promotion") == "NOT_PERFORMED", "ARCHITECTURE_PRODUCTION_PROMOTION_NOT_LOCKED")
        check(
            architecture.get("overall_architecture_status") in ALLOWED_ARCHITECTURE_STATUS,
            "ARCHITECTURE_STATUS_INVALID",
        )
    check(isinstance(arch_lanes, dict), "ARCHITECTURE_LANES_INVALID")

    if isinstance(arch_lanes, dict):
        check(set(arch_lanes) == set(normalized_gate), "ARCHITECTURE_LANE_SET_MISMATCH")
        for lane, decision in normalized_gate.items():
            payload = arch_lanes.get(lane)
            valid_payload = isinstance(payload, dict)
            check(valid_payload, f"ARCHITECTURE_LANE_INVALID:{lane}")
            if valid_payload:
                check(
                    payload.get("freeze_decision") == decision,
                    f"ARCHITECTURE_FREEZE_DECISION_MISMATCH:{lane}",
                )

    return {
        "schema_version": 1,
        "status": "PASS" if not failures else "FAIL",
        "checks_total": checks_total,
        "checks_passed": checks_passed,
        "failure_codes": failures,
        "production_promotion": "NOT_PERFORMED",
    }


def assert_report_safe(report):
    result = validate_report(report)
    if result["status"] != "PASS":
        raise ValueError("V7 final-report preflight failed: " + ", ".join(result["failure_codes"]))
    return result


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("final_report")
    p.add_argument("--out")
    args = p.parse_args(argv)
    report = json.loads(Path(args.final_report).read_text(encoding="utf-8"))
    result = validate_report(report)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
