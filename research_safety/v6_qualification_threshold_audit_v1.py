#!/usr/bin/env python3
"""Read-only audit of the frozen V6 qualification constants.

The utility parses a supplied V6 collector with Python's AST, compares exactly
the qualification constants named in a lock manifest, and also verifies the
collector's Git blob SHA. It never imports or executes the collector.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any


class ThresholdAuditError(RuntimeError):
    pass


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def _top_level_assignments(source: str, watched: set[str]) -> dict[str, list[ast.AST]]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ThresholdAuditError(f"collector syntax error: {exc}") from exc

    found: dict[str, list[ast.AST]] = {name: [] for name in watched}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in watched:
                    found[target.id].append(node.value)
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id in watched and node.value is not None:
                found[target.id].append(node.value)
    return found


def _same_value(observed: Any, expected: Any) -> bool:
    if isinstance(observed, bool) or isinstance(expected, bool):
        return type(observed) is type(expected) and observed == expected
    if isinstance(observed, (int, float)) and isinstance(expected, (int, float)):
        return float(observed) == float(expected)
    return type(observed) is type(expected) and observed == expected


def audit_thresholds(collector_bytes: bytes, lock: dict) -> dict:
    expected_blob = str(lock.get("collector_git_blob_sha", "")).strip()
    expected = lock.get("qualification_constants")
    if not expected_blob:
        raise ThresholdAuditError("lock is missing collector_git_blob_sha")
    if not isinstance(expected, dict) or not expected:
        raise ThresholdAuditError("lock is missing qualification_constants")
    if len(expected) != 11:
        raise ThresholdAuditError(
            f"lock must contain exactly 11 frozen qualification constants; found {len(expected)}"
        )

    try:
        source = collector_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ThresholdAuditError("collector is not valid UTF-8") from exc

    observed_blob = git_blob_sha(collector_bytes)
    assignments = _top_level_assignments(source, set(expected))
    missing: list[str] = []
    duplicate: list[str] = []
    nonliteral: list[str] = []
    changed: list[dict[str, Any]] = []
    observed_values: dict[str, Any] = {}

    for name, expected_value in expected.items():
        values = assignments.get(name, [])
        if not values:
            missing.append(name)
            continue
        if len(values) != 1:
            duplicate.append(name)
            continue
        try:
            observed_value = ast.literal_eval(values[0])
        except (ValueError, TypeError):
            nonliteral.append(name)
            continue
        observed_values[name] = observed_value
        if not _same_value(observed_value, expected_value):
            changed.append(
                {"name": name, "expected": expected_value, "observed": observed_value}
            )

    blob_matches = observed_blob == expected_blob
    ok = blob_matches and not (missing or duplicate or nonliteral or changed)
    return {
        "ok": ok,
        "collector_blob_sha": observed_blob,
        "expected_collector_blob_sha": expected_blob,
        "collector_blob_matches": blob_matches,
        "locked_constant_count": len(expected),
        "observed_constant_count": len(observed_values),
        "missing": sorted(missing),
        "duplicate": sorted(duplicate),
        "nonliteral": sorted(nonliteral),
        "changed": sorted(changed, key=lambda item: item["name"]),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--collector", required=True)
    p.add_argument("--lock", required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    try:
        collector_bytes = Path(args.collector).read_bytes()
        lock = json.loads(Path(args.lock).read_text(encoding="utf-8"))
        result = audit_thresholds(collector_bytes, lock)
    except (OSError, json.JSONDecodeError, ThresholdAuditError) as exc:
        result = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            print(f"BLOCKED: {exc}")
        return 2

    if args.json:
        print(json.dumps(result, sort_keys=True))
    elif result["ok"]:
        print("SAFE: collector blob and all 11 frozen V6 qualification constants match the lock.")
    else:
        print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
