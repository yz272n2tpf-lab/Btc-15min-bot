#!/usr/bin/env python3
"""One-command, read-only safety suite for isolated BTC15 V6 research work.

Combines branch/collector/start-command preflight, research diff-scope auditing,
and the frozen 11-constant V6 qualification audit. The suite is fail-closed and
never imports or executes the V6 collector.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research_diff_scope_guard_v1 import ScopeError, audit_changed_paths
from research_safety_preflight_v1 import PreflightError, check_preflight
from v6_qualification_threshold_audit_v1 import ThresholdAuditError, audit_thresholds


class SafetySuiteError(RuntimeError):
    pass


def run_suite(
    *,
    active_branch: str,
    work_branch: str,
    collector_path: str,
    active_start_command: str,
    provenance_lock: dict,
    threshold_lock: dict,
    changed_paths: list[str],
) -> dict:
    railway = provenance_lock.get("railway")
    frozen = provenance_lock.get("frozen_collector")
    if not isinstance(railway, dict) or not isinstance(frozen, dict):
        raise SafetySuiteError("provenance lock is missing railway/frozen_collector sections")

    locked_active_branch = str(railway.get("source_branch", "")).strip()
    locked_start = str(railway.get("start_command", "")).strip()
    locked_blob = str(frozen.get("git_blob_sha", "")).strip()
    locked_path = str(frozen.get("path", "")).strip()
    if not all((locked_active_branch, locked_start, locked_blob, locked_path)):
        raise SafetySuiteError("provenance lock is incomplete")

    if active_branch.strip() != locked_active_branch:
        raise SafetySuiteError(
            f"active branch does not match provenance lock: {active_branch!r} != {locked_active_branch!r}"
        )

    threshold_blob = str(threshold_lock.get("collector_git_blob_sha", "")).strip()
    threshold_path = str(threshold_lock.get("collector_path", "")).strip()
    if threshold_blob != locked_blob:
        raise SafetySuiteError("cross-lock collector blob mismatch")
    if threshold_path and threshold_path != locked_path:
        raise SafetySuiteError("cross-lock collector path mismatch")

    preflight = check_preflight(
        active_branch=active_branch,
        work_branch=work_branch,
        collector_path=collector_path,
        expected_collector_blob=locked_blob,
        active_start_command=active_start_command,
        expected_start_command=locked_start,
    )
    collector_bytes = Path(collector_path).read_bytes()
    thresholds = audit_thresholds(collector_bytes, threshold_lock)
    scope = audit_changed_paths(changed_paths)

    ok = bool(preflight.get("ok") and thresholds.get("ok") and scope.get("ok"))
    return {
        "ok": ok,
        "preflight": preflight,
        "thresholds": thresholds,
        "scope": scope,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--active-branch", required=True)
    p.add_argument("--work-branch", required=True)
    p.add_argument("--collector", required=True)
    p.add_argument("--active-start-command", required=True)
    p.add_argument("--provenance-lock", required=True)
    p.add_argument("--threshold-lock", required=True)
    p.add_argument("--path", action="append", default=[])
    p.add_argument("--paths-file")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    paths = list(args.path)
    try:
        if args.paths_file:
            with open(args.paths_file, "r", encoding="utf-8") as fh:
                paths.extend(line.rstrip("\n") for line in fh if line.strip())
        provenance_lock = json.loads(Path(args.provenance_lock).read_text(encoding="utf-8"))
        threshold_lock = json.loads(Path(args.threshold_lock).read_text(encoding="utf-8"))
        result = run_suite(
            active_branch=args.active_branch,
            work_branch=args.work_branch,
            collector_path=args.collector,
            active_start_command=args.active_start_command,
            provenance_lock=provenance_lock,
            threshold_lock=threshold_lock,
            changed_paths=paths,
        )
    except (
        OSError,
        json.JSONDecodeError,
        SafetySuiteError,
        PreflightError,
        ThresholdAuditError,
        ScopeError,
    ) as exc:
        result = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            print(f"BLOCKED: {exc}")
        return 2

    if args.json:
        print(json.dumps(result, sort_keys=True))
    elif result["ok"]:
        print("SAFE: provenance, frozen V6 thresholds, and research-only diff scope all pass.")
    else:
        print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
