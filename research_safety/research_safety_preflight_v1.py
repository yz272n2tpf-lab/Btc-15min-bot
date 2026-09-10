#!/usr/bin/env python3
"""Fail-closed preflight for research work during an active Railway V6 test.

This utility is intentionally read-only. It does not call Railway or GitHub,
does not deploy, and does not mutate production. It checks supplied provenance
facts before research work is committed or run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class PreflightError(RuntimeError):
    pass


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("utf-8")
    return hashlib.sha1(header + data).hexdigest()


def check_preflight(
    *,
    active_branch: str,
    work_branch: str,
    collector_path: str,
    expected_collector_blob: str,
    active_start_command: str,
    expected_start_command: str,
) -> dict:
    required = {
        "active_branch": active_branch,
        "work_branch": work_branch,
        "collector_path": collector_path,
        "expected_collector_blob": expected_collector_blob,
        "active_start_command": active_start_command,
        "expected_start_command": expected_start_command,
    }
    missing = [name for name, value in required.items() if not str(value).strip()]
    if missing:
        raise PreflightError("missing required provenance: " + ", ".join(missing))

    if active_branch.strip() == work_branch.strip():
        raise PreflightError(
            f"unsafe branch: work branch {work_branch!r} is the active Railway source branch"
        )

    data = Path(collector_path).read_bytes()
    observed_blob = git_blob_sha(data)
    if observed_blob != expected_collector_blob.strip():
        raise PreflightError(
            "frozen collector drift: "
            f"expected {expected_collector_blob.strip()}, observed {observed_blob}"
        )

    if active_start_command.strip() != expected_start_command.strip():
        raise PreflightError(
            "start-command drift: "
            f"expected {expected_start_command!r}, observed {active_start_command!r}"
        )

    return {
        "ok": True,
        "active_branch": active_branch.strip(),
        "work_branch": work_branch.strip(),
        "collector_blob_sha": observed_blob,
        "start_command": active_start_command.strip(),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--active-branch", required=True)
    p.add_argument("--work-branch", required=True)
    p.add_argument("--collector", required=True)
    p.add_argument("--expected-collector-blob", required=True)
    p.add_argument("--active-start-command", required=True)
    p.add_argument("--expected-start-command", required=True)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    try:
        result = check_preflight(
            active_branch=args.active_branch,
            work_branch=args.work_branch,
            collector_path=args.collector,
            expected_collector_blob=args.expected_collector_blob,
            active_start_command=args.active_start_command,
            expected_start_command=args.expected_start_command,
        )
    except (PreflightError, OSError) as exc:
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        else:
            print(f"BLOCKED: {exc}")
        return 2

    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(
            "SAFE: research branch is isolated; frozen collector and start command match."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
