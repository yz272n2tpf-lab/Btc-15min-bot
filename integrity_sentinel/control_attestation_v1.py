#!/usr/bin/env python3
"""Fail-closed control-plane attestation model for the BTC15 Integrity Sentinel.

This module does not contact Railway. It compares a frozen expected control
manifest with a separately captured read-only control-plane snapshot. Missing
facts remain UNKNOWN; a mismatch is FAIL.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

REQUIRED_IDENTITY_FIELDS = (
    "service_id", "deployment_id", "branch", "commit_sha", "start_command",
    "role", "cutoff_utc",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def manifest_sha256(manifest: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(manifest).encode()).hexdigest()


def identity_value_present(value: Any) -> bool:
    # Explicit non-applicability is separate from missing/null. It must carry a
    # reason and must match the independently captured actual representation.
    return (isinstance(value, str) and bool(value.strip())) or (
        isinstance(value, dict) and set(value) == {"not_applicable", "reason"}
        and value["not_applicable"] is True
        and isinstance(value["reason"], str) and bool(value["reason"].strip()))


def validate_manifest(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError("control manifest must be an object")
    sources = obj.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("control manifest requires non-empty sources")
    for name, row in sources.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(row, dict):
            raise ValueError("invalid source expectation")
        for field in REQUIRED_IDENTITY_FIELDS:
            value = row.get(field)
            if not identity_value_present(value):
                raise ValueError(f"source {name} missing expected field: {field}")
            if isinstance(value, dict) and field != "cutoff_utc":
                raise ValueError(f"source {name}: {field} cannot be non-applicable")
    return obj


def load_manifest(path: str | Path) -> dict[str, Any]:
    return validate_manifest(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass(frozen=True)
class SourceAttestation:
    source: str
    passed: bool | None
    mismatches: tuple[str, ...]
    unknown: tuple[str, ...]


def compare_source(name: str, expected: Mapping[str, Any], actual: Mapping[str, Any] | None) -> SourceAttestation:
    if not isinstance(actual, Mapping):
        return SourceAttestation(name, None, (), tuple(REQUIRED_IDENTITY_FIELDS))
    mismatch: list[str] = []
    unknown: list[str] = []
    for field in REQUIRED_IDENTITY_FIELDS:
        expected_value = expected.get(field)
        actual_value = actual.get(field)
        if not identity_value_present(expected_value):
            unknown.append("expected:" + field)
        elif not identity_value_present(actual_value):
            unknown.append(field)
        elif actual_value != expected_value:
            mismatch.append(field)
    if mismatch:
        passed: bool | None = False
    elif unknown:
        passed = None
    else:
        passed = True
    return SourceAttestation(name, passed, tuple(mismatch), tuple(unknown))


def compare_manifest(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> dict[str, Any]:
    try:
        validate_manifest(expected)
    except ValueError as exc:
        return {"control_plane_pass": None, "error": str(exc), "sources": [],
                "orders": False, "production_mutation": False}
    actual = actual if isinstance(actual, Mapping) else {}
    expected_sources = expected.get("sources") if isinstance(expected.get("sources"), Mapping) else {}
    actual_sources = actual.get("sources") if isinstance(actual.get("sources"), Mapping) else {}
    rows = [compare_source(name, row, actual_sources.get(name)) for name, row in expected_sources.items()]
    states = [r.passed for r in rows]
    if any(x is False for x in states):
        passed: bool | None = False
    elif any(x is None for x in states):
        passed = None
    else:
        passed = True
    return {
        "control_plane_pass": passed,
        "expected_manifest_sha256": manifest_sha256(expected),
        "sources": [asdict(r) for r in rows],
        "orders": False,
        "production_mutation": False,
    }
