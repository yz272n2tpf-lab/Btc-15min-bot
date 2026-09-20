"""Offline recovery of archived aggregates; never claims raw-tape reproduction.

No network, service, source-tape mutation, model fitting, or order execution.
Run: python research_review/ladder_20260920/review.py
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SOURCE_SHA = "8dbd61e1e04057b8d123760209c108ccf14d58fd342fbcbe6a82907eda35927a"
CODE_SHA = "7f901c87774dd418db79a29f513b05245488a6ba0cedd6e7a8572ac9865ce55f"
CONTROL = "V1_IMMEDIATE_CONTROL"
CANDIDATE = "V1_LE50_30S"


def code_fingerprint():
    digest = hashlib.sha256()
    paths = sorted(ROOT.glob("shadow_diagnostics/*.py"))
    paths += [ROOT / "requirements.txt", ROOT / "railway.json"]
    for path in paths:
        digest.update(str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def parse_comparison(run):
    states, lanes = [], {}
    for line in run["lines"]:
        if "Z VALUE_STATE " in line:
            states.append(json.loads(line.split("Z VALUE_STATE ", 1)[1]))
        elif "Z VALUE_SET " in line:
            row = json.loads(line.split("Z VALUE_SET ", 1)[1])
            if row["name"] in lanes:
                raise ValueError("duplicate aggregate lane")
            lanes[row["name"]] = row
    if len(states) != 1:
        raise ValueError("exactly one source state required")
    state = states[0]
    if state["source_sha256"] != SOURCE_SHA or state["code_sha256"] != CODE_SHA:
        raise ValueError("source/code hash mismatch: growing export is not a replacement")
    if (state["future_full_contracts"], state["serial_signals"]) != (352, 563):
        raise ValueError("different cohort")
    return state, lanes


def count_from_rate(rate, n):
    count = round(rate * n)
    if not 0 <= count <= n or not math.isclose(rate, count / n, abs_tol=1e-12):
        raise ValueError("reported rate does not recover an integer count")
    return count


def scorecard(evidence):
    parsed = [parse_comparison(run) for run in evidence["comparisons"]]
    if not parsed or any(p != parsed[0] for p in parsed):
        raise ValueError("archived matching-hash runs disagree")
    if code_fingerprint() != CODE_SHA:
        raise ValueError("local frozen replay dependencies changed")
    _, lanes = parsed[0]
    out = {
        "status": "BLOCKED_MISSING_EXACT_RAW_EVIDENCE",
        "raw_tape_reproduced": False,
        "aggregate_log_recovery": True,
        "source_sha256_reported_by_archived_state": SOURCE_SHA,
        "code_sha256_verified_locally": CODE_SHA,
        "cohort_full_contracts_reported": 352,
        "cohort_serial_opportunities_reported": 563,
        "state_and_audit_hash_coherence_verified": False,
        "lanes": {},
    }
    for name in (CONTROL, CANDIDATE):
        row = lanes[name]
        n = row["n"]
        counts = {k: count_from_rate(row[k + "_rate"], n)
                  for k in ("plus5", "plus10", "plus20", "protected_exit")}
        out["lanes"][name] = {
            **row, "reported_count_numerators": counts,
            "full_contract_denominator": 352,
            "contract_coverage": row["contracts"] / 352,
            "opportunity_retention": n / 563,
            "no_actionable_entry": 563 - n,
            "without_observed_protected_exit": n - counts["protected_exit"],
            "no_reported_plus5_including_unknown": n - counts["plus5"],
            "reported_plus5_without_exit": counts["plus5"] - counts["protected_exit"],
            "confirmed_never_armed": None,
            "missing_path_count": None,
            "plus15": None,
            "adverse_movement": None,
            "pre_exit_movement_hits": None,
            "total_pnl": None,
        }
    # Entry-ID retention of control winners, NOT candidate successes/control successes.
    winners = out["lanes"][CONTROL]["reported_count_numerators"]["plus10"]
    entries = lanes[CANDIDATE]["n"]
    out["winner_id_retention"] = {
        "observed": None, "control_plus10_winners": winners,
        "numerator_lower_bound": max(0, entries - (563 - winners)),
        "numerator_upper_bound": min(entries, winners),
        "bounds_are_set_arithmetic_not_measurements": True,
    }
    out["holdout"] = {
        "recorded_collection_boundary_utc": "2026-09-20T19:05:17.147189Z",
        "eligible_boundary_certified": False,
        "provisional_conservative_contract_start_floor_utc": "2026-09-20T20:15:00Z",
        "rule": "Use existing collected tape only; require full contract at/after floor and ID absent from every development cohort, including the separate 609-entry study. Until IDs are recovered, no validation cohort is certified.",
        "clean_performance_inspected": False,
    }
    return out


if __name__ == "__main__":
    result = scorecard(json.loads((HERE / "archived_workflow_evidence.json").read_text()))
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
