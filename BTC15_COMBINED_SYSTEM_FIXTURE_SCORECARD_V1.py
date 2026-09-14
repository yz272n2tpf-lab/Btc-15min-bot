#!/usr/bin/env python3
"""
BTC15 combined-system fixture scorecard V1.

PURE OFFLINE INTEGRATION VALIDATION | SIGNAL ONLY | NO ORDERS

Purpose
-------
Validate the frozen EARLY / FINAL / SCALP integration contract with deterministic
fixtures before any live wiring. This script does NOT qualify signals, change
thresholds, read secrets, call networks, or place orders.
"""
from __future__ import annotations

from dataclasses import asdict

from btc15_signal_integration_v1 import (
    EarlyState,
    FinalState,
    ScalpState,
    compose_contract_state,
)


def fixture(name, early=None, final=None, scalp=None, *, headline, paths, labels=(), union=True):
    return {
        "name": name,
        "early": early or EarlyState(),
        "final": final or FinalState(),
        "scalp": scalp or ScalpState(),
        "headline": headline,
        "paths": tuple(paths),
        "labels": tuple(labels),
        "union": bool(union),
    }


FIXTURES = [
    fixture(
        "all_non_actionable",
        final=FinalState("WATCH", side="UP", fair=.61, seconds_left=710),
        headline="FINAL_WATCH", paths=(), labels=(), union=False,
    ),
    fixture(
        "early_only",
        early=EarlyState("QUALIFIED", "UP", ask=.34, fair=.78, edge=.10, seconds_left=390),
        final=FinalState("WATCH", "UP", fair=.72, seconds_left=390),
        headline="EARLY_QUALIFIED", paths=("EARLY",),
    ),
    fixture(
        "final_qualified_only",
        final=FinalState("QUALIFIED", "DOWN", fair=.91, seconds_left=310),
        headline="FINAL_QUALIFIED", paths=("FINAL",),
    ),
    fixture(
        "final_lock_only",
        final=FinalState("LOCK", "UP", fair=.95, seconds_left=255),
        headline="FINAL_LOCK", paths=("FINAL",),
    ),
    fixture(
        "scalp_only_low_price",
        scalp=ScalpState("ACTIVE", "UP", entry_ask=.08, current_bid=.10, peak_exec_gain=.02, exec_gain=.02, seconds_left=620),
        headline="SCALP_ACTIVE", paths=("SCALP",),
    ),
    fixture(
        "scalp_only_high_price",
        scalp=ScalpState("ACTIVE", "DOWN", entry_ask=.91, current_bid=.93, peak_exec_gain=.02, exec_gain=.02, seconds_left=605),
        headline="SCALP_ACTIVE", paths=("SCALP",),
    ),
    fixture(
        "early_final_aligned",
        early=EarlyState("QUALIFIED", "UP", ask=.31, fair=.80, edge=.12, seconds_left=420),
        final=FinalState("QUALIFIED", "UP", fair=.92, seconds_left=295),
        headline="FINAL_QUALIFIED", paths=("EARLY", "FINAL"), labels=("ALIGNED",),
    ),
    fixture(
        "early_final_divergence",
        early=EarlyState("QUALIFIED", "DOWN", ask=.29, fair=.77, edge=.09, seconds_left=430),
        final=FinalState("QUALIFIED", "UP", fair=.91, seconds_left=300),
        headline="FINAL_QUALIFIED", paths=("EARLY", "FINAL"),
        labels=("EARLY_FINAL_DIVERGENCE", "MIXED_HORIZONS"),
    ),
    fixture(
        "final_lock_scalp_aligned",
        final=FinalState("LOCK", "UP", fair=.94, seconds_left=250),
        scalp=ScalpState("ACTIVE", "UP", entry_ask=.67, current_bid=.74, peak_exec_gain=.07, exec_gain=.07, seconds_left=250),
        headline="FINAL_LOCK", paths=("FINAL", "SCALP"), labels=("ALIGNED",),
    ),
    fixture(
        "final_lock_countertrend_scalp",
        final=FinalState("LOCK", "UP", fair=.94, seconds_left=245),
        scalp=ScalpState("ACTIVE", "DOWN", entry_ask=.36, current_bid=.43, peak_exec_gain=.07, exec_gain=.07, seconds_left=245),
        headline="FINAL_LOCK", paths=("FINAL", "SCALP"),
        labels=("COUNTERTREND_SCALP", "MIXED_HORIZONS"),
    ),
    fixture(
        "protect_priority",
        final=FinalState("LOCK", "UP", fair=.94, seconds_left=225),
        scalp=ScalpState("PROTECT", "DOWN", entry_ask=.39, current_bid=.52, peak_exec_gain=.17, exec_gain=.13, seconds_left=225),
        headline="SCALP_PROTECT", paths=("FINAL", "SCALP"),
        labels=("COUNTERTREND_SCALP", "MIXED_HORIZONS"),
    ),
    fixture(
        "exit_priority",
        final=FinalState("LOCK", "UP", fair=.94, seconds_left=210),
        scalp=ScalpState("EXIT", "DOWN", entry_ask=.39, current_bid=.51, peak_exec_gain=.17, exec_gain=.12, seconds_left=210),
        headline="SCALP_EXIT", paths=("FINAL", "SCALP"),
        labels=("COUNTERTREND_SCALP", "MIXED_HORIZONS"),
    ),
    fixture(
        "all_three_aligned",
        early=EarlyState("QUALIFIED", "DOWN", ask=.33, fair=.79, edge=.11, seconds_left=410),
        final=FinalState("LOCK", "DOWN", fair=.96, seconds_left=235),
        scalp=ScalpState("ACTIVE", "DOWN", entry_ask=.58, current_bid=.66, peak_exec_gain=.08, exec_gain=.08, seconds_left=235),
        headline="FINAL_LOCK", paths=("EARLY", "FINAL", "SCALP"), labels=("ALIGNED",),
    ),
    fixture(
        "early_final_aligned_scalp_countertrend",
        early=EarlyState("QUALIFIED", "UP", ask=.35, fair=.76, edge=.09, seconds_left=445),
        final=FinalState("QUALIFIED", "UP", fair=.91, seconds_left=280),
        scalp=ScalpState("ACTIVE", "DOWN", entry_ask=.42, current_bid=.47, peak_exec_gain=.05, exec_gain=.05, seconds_left=280),
        headline="FINAL_QUALIFIED", paths=("EARLY", "FINAL", "SCALP"),
        labels=("COUNTERTREND_SCALP", "MIXED_HORIZONS"),
    ),
    fixture(
        "watch_plus_scalp",
        final=FinalState("WATCH", "DOWN", fair=.68, seconds_left=690),
        scalp=ScalpState("ACTIVE", "UP", entry_ask=.47, current_bid=.52, peak_exec_gain=.05, exec_gain=.05, seconds_left=690),
        headline="SCALP_ACTIVE", paths=("SCALP",),
    ),
]


def check(cond, msg, failures):
    if not cond:
        failures.append(msg)


def main():
    failures = []
    rows = []

    for f in FIXTURES:
        out = compose_contract_state(
            f["name"], early=f["early"], final=f["final"], scalp=f["scalp"]
        )

        # Module preservation: composer may normalize, but it must not rewrite
        # any already-valid fixture value.
        check(asdict(out.early) == asdict(f["early"].normalized()), f"{f['name']}: EARLY rewritten", failures)
        check(asdict(out.final) == asdict(f["final"].normalized()), f"{f['name']}: FINAL rewritten", failures)
        check(asdict(out.scalp) == asdict(f["scalp"].normalized()), f"{f['name']}: SCALP rewritten", failures)

        # Frozen integration semantics.
        check(out.headline == f["headline"], f"{f['name']}: headline {out.headline} != {f['headline']}", failures)
        check(out.actionable_paths == f["paths"], f"{f['name']}: paths {out.actionable_paths} != {f['paths']}", failures)
        check(out.context_labels == f["labels"], f"{f['name']}: labels {out.context_labels} != {f['labels']}", failures)
        check(out.union_actionable == f["union"], f"{f['name']}: union mismatch", failures)
        check(out.union_actionable == bool(out.actionable_paths), f"{f['name']}: union/path disagreement", failures)
        check(len(out.actionable_paths) == len(set(out.actionable_paths)), f"{f['name']}: double-counted path", failures)

        payload = out.to_dict()
        check(payload.get("manual_execution_only") is True, f"{f['name']}: manual-only flag missing", failures)
        check(payload.get("numeric_flip_risk_validated") is False, f"{f['name']}: numeric flip-risk unexpectedly enabled", failures)
        check("order" not in payload, f"{f['name']}: order field present", failures)
        check("flip_risk_percent" not in payload, f"{f['name']}: numeric flip-risk field present", failures)

        rows.append(out)

    union_contracts = sum(1 for r in rows if r.union_actionable)
    expected_union = sum(1 for f in FIXTURES if f["union"])
    check(union_contracts == expected_union, f"union count {union_contracts} != {expected_union}", failures)

    # WATCH never counts as an actionable path.
    for r in rows:
        if r.final.state == "WATCH" and r.early.state == "PASS" and r.scalp.state == "PASS":
            check(not r.union_actionable, f"{r.contract}: WATCH counted actionable", failures)

    # Scalp price must remain telemetry only inside the composer.
    low = next(r for r in rows if r.contract == "scalp_only_low_price")
    high = next(r for r in rows if r.contract == "scalp_only_high_price")
    check(low.union_actionable and high.union_actionable, "scalp price became eligibility gate", failures)

    print("=" * 96)
    print("BTC15 COMBINED SYSTEM FIXTURE SCORECARD V1 | PURE OFFLINE | SIGNAL ONLY | NO ORDERS")
    print("=" * 96)
    print(f"fixtures={len(rows)}")
    print(f"union_actionable={union_contracts}/{len(rows)}")
    print(f"non_actionable={len(rows)-union_contracts}/{len(rows)}")
    print(f"module_preservation_checks={len(rows)*3}")
    print("display/conflict/union/safety checks=ENABLED")
    print("")

    for r in rows:
        labels = ",".join(r.context_labels) if r.context_labels else "-"
        paths = ",".join(r.actionable_paths) if r.actionable_paths else "-"
        print(f"{r.contract:38s} headline={r.headline:16s} paths={paths:18s} labels={labels}")

    print("")
    print("GUARDRAILS")
    print("- Composer does not qualify EARLY, FINAL, or SCALP rules.")
    print("- Protected module payload values must survive composition unchanged.")
    print("- Union coverage counts a contract once, regardless of active-path count.")
    print("- WATCH is non-actionable.")
    print("- SCALP price remains telemetry, not eligibility.")
    print("- No unvalidated numeric flip/reversal-risk percentage is emitted.")
    print("- No order-placement code exists.")
    print("")

    if failures:
        print(f"RESULT: FAIL ({len(failures)} issues)")
        for x in failures:
            print("FAIL | " + x)
        raise SystemExit(1)

    print("RESULT: PASS")
    print("Frozen integration semantics held across all deterministic fixtures.")


if __name__ == "__main__":
    main()
