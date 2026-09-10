#!/usr/bin/env python3
"""Fail-closed diff-scope guard for isolated BTC15 research branches.

This tool is read-only. It checks a set of changed repository paths and blocks
any change outside explicitly allowed research-only prefixes, plus any exact
protected runtime/config path even if an allow-list is misconfigured.
"""
from __future__ import annotations

import argparse
import json
from pathlib import PurePosixPath
from typing import Iterable, Sequence

DEFAULT_ALLOWED_PREFIXES = ("research_safety/",)
DEFAULT_PROTECTED_PATHS = (
    "scalp_lead_shadow_v6.py",
    "scalp_lead_shadow_v5.py",
    "railway.toml",
    "Procfile",
    "Dockerfile",
    "requirements.txt",
)


class ScopeError(RuntimeError):
    pass


def _normalize(path: str) -> str:
    raw = str(path).strip().replace("\\", "/")
    if not raw:
        raise ScopeError("empty changed path")
    if raw.startswith("/"):
        raise ScopeError(f"absolute path is not allowed: {path!r}")
    parts = PurePosixPath(raw).parts
    if ".." in parts:
        raise ScopeError(f"path traversal is not allowed: {path!r}")
    while raw.startswith("./"):
        raw = raw[2:]
    return raw


def audit_changed_paths(
    changed_paths: Iterable[str],
    *,
    allowed_prefixes: Sequence[str] = DEFAULT_ALLOWED_PREFIXES,
    protected_paths: Sequence[str] = DEFAULT_PROTECTED_PATHS,
) -> dict:
    allowed = tuple(_normalize(p).rstrip("/") + "/" for p in allowed_prefixes)
    protected = {_normalize(p) for p in protected_paths}

    normalized = sorted({_normalize(p) for p in changed_paths})
    blocked = []
    accepted = []

    for path in normalized:
        reason = None
        if path in protected:
            reason = "protected runtime/config path"
        elif not any(path.startswith(prefix) for prefix in allowed):
            reason = "outside allowed research-only prefixes"

        if reason:
            blocked.append({"path": path, "reason": reason})
        else:
            accepted.append(path)

    return {
        "ok": not blocked,
        "changed_count": len(normalized),
        "allowed_prefixes": list(allowed),
        "accepted": accepted,
        "blocked": blocked,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--path", action="append", default=[], help="Changed repo path; repeatable")
    p.add_argument("--paths-file", help="Optional newline-delimited changed-path file")
    p.add_argument("--allow-prefix", action="append", default=[])
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    paths = list(args.path)
    if args.paths_file:
        with open(args.paths_file, "r", encoding="utf-8") as fh:
            paths.extend(line.rstrip("\n") for line in fh if line.strip())

    prefixes = tuple(args.allow_prefix) if args.allow_prefix else DEFAULT_ALLOWED_PREFIXES
    try:
        result = audit_changed_paths(paths, allowed_prefixes=prefixes)
    except (ScopeError, OSError) as exc:
        result = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            print(f"BLOCKED: {exc}")
        return 2

    if args.json:
        print(json.dumps(result, sort_keys=True))
    elif result["ok"]:
        print(f"SAFE: {result['changed_count']} changed path(s) are research-only.")
    else:
        for item in result["blocked"]:
            print(f"BLOCKED: {item['path']} - {item['reason']}")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
