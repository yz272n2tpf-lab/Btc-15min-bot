#!/usr/bin/env python3
"""Read-only V6 runtime provenance auditor.

Compares a frozen forward-test lock with a captured Railway runtime snapshot and
an on-disk collector source file. It never imports/executes the collector and
never mutates Railway/GitHub. Branch-tip commit drift is informational when the
locked collector blob and frozen constants are unchanged.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shlex
from pathlib import Path
from typing import Any

EXPECTED_SERVICE = "scalp-lead-v6"
EXPECTED_COLLECTOR = "scalp_lead_shadow_v6.py"


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def extract_top_level_constants(source: str, names: set[str]) -> dict[str, Any]:
    tree = ast.parse(source)
    found: dict[str, Any] = {}
    for node in tree.body:
        targets: list[ast.expr] = []
        value_node: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets = node.targets
            value_node = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value_node = node.value
        if value_node is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id in names:
                try:
                    found[target.id] = ast.literal_eval(value_node)
                except (ValueError, TypeError):
                    found[target.id] = "<nonliteral>"
    return found


def normalize_start_command(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return [command]


def audit(lock: dict[str, Any], snapshot: dict[str, Any], collector_bytes: bytes) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    if snapshot.get("service_name") != EXPECTED_SERVICE:
        failures.append(f"service_name expected {EXPECTED_SERVICE!r}, got {snapshot.get('service_name')!r}")

    expected_branch = lock.get("deployment_source_branch")
    if snapshot.get("source_branch") != expected_branch:
        failures.append(f"source_branch expected {expected_branch!r}, got {snapshot.get('source_branch')!r}")

    expected_repo = snapshot.get("expected_repo")
    if expected_repo and snapshot.get("source_repo") != expected_repo:
        failures.append(f"source_repo expected {expected_repo!r}, got {snapshot.get('source_repo')!r}")

    start_tokens = normalize_start_command(str(snapshot.get("start_command", "")))
    if start_tokens != ["python", EXPECTED_COLLECTOR]:
        failures.append(f"start_command expected 'python {EXPECTED_COLLECTOR}', got {snapshot.get('start_command')!r}")

    collectors = {item.get("path"): item for item in lock.get("collectors", [])}
    locked_collector = collectors.get(EXPECTED_COLLECTOR)
    if not locked_collector:
        failures.append(f"lock missing collector record for {EXPECTED_COLLECTOR}")
        locked_blob = None
    else:
        locked_blob = locked_collector.get("github_blob_sha")

    actual_blob = git_blob_sha(collector_bytes)
    if locked_blob and actual_blob != locked_blob:
        failures.append(f"collector blob drift: locked {locked_blob}, actual {actual_blob}")

    frozen = lock.get("v6_frozen_constants", {})
    source_text = collector_bytes.decode("utf-8")
    observed = extract_top_level_constants(source_text, set(frozen))
    missing = sorted(set(frozen) - set(observed))
    if missing:
        failures.append("frozen constants missing from source: " + ", ".join(missing))
    for name, expected in frozen.items():
        if name in observed and observed[name] != expected:
            failures.append(f"constant drift {name}: locked {expected!r}, actual {observed[name]!r}")

    locked_commit = lock.get("deployment_source_commit")
    runtime_commit = snapshot.get("deployment_commit")
    if runtime_commit and locked_commit and runtime_commit != locked_commit:
        if locked_blob and actual_blob == locked_blob and not any(msg.startswith("constant drift") for msg in failures):
            info.append(
                "deployment branch tip advanced after lock, but the V6 collector blob and frozen constants are unchanged"
            )
        else:
            warnings.append("deployment commit differs from lock and collector integrity is not proven unchanged")

    return {
        "status": "PASS" if not failures else "FAIL",
        "service_name": snapshot.get("service_name"),
        "source_branch": snapshot.get("source_branch"),
        "locked_commit": locked_commit,
        "deployment_commit": runtime_commit,
        "collector_blob_locked": locked_blob,
        "collector_blob_actual": actual_blob,
        "frozen_constants_checked": len(frozen),
        "failures": failures,
        "warnings": warnings,
        "info": info,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--collector-source", required=True, type=Path)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    collector_bytes = args.collector_source.read_bytes()
    result = audit(lock, snapshot, collector_bytes)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"V6_RUNTIME_PROVENANCE: {result['status']}")
        print(f"service={result['service_name']} branch={result['source_branch']}")
        print(f"locked_commit={result['locked_commit']}")
        print(f"deployment_commit={result['deployment_commit']}")
        print(f"collector_blob={result['collector_blob_actual']}")
        print(f"frozen_constants_checked={result['frozen_constants_checked']}")
        for key in ("failures", "warnings", "info"):
            for item in result[key]:
                print(f"{key[:-1].upper()}: {item}")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
