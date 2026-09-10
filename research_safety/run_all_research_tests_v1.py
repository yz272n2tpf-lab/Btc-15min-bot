#!/usr/bin/env python3
"""Run every research_safety unittest in one deterministic, fail-closed command.

This utility only discovers tests under its own research_safety directory. It
does not import or execute production collectors directly; any collector reads
remain controlled by the individual audit tests.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import unittest
from pathlib import Path


def discover_test_files(root: Path) -> list[str]:
    return sorted(p.name for p in root.glob("test_*.py") if p.is_file())


def run_tests(root: Path) -> dict:
    root = root.resolve()
    files = discover_test_files(root)
    if not files:
        return {
            "ok": False,
            "tests_run": 0,
            "failures": 0,
            "errors": 0,
            "skipped": 0,
            "test_files": [],
            "output": "BLOCKED: no research tests discovered",
        }

    root_text = str(root)
    inserted = root_text not in sys.path
    if inserted:
        sys.path.insert(0, root_text)

    stream = io.StringIO()
    try:
        suite = unittest.defaultTestLoader.discover(
            start_dir=root_text,
            pattern="test_*.py",
            top_level_dir=root_text,
        )
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    finally:
        if inserted:
            try:
                sys.path.remove(root_text)
            except ValueError:
                pass

    return {
        "ok": bool(result.wasSuccessful() and result.testsRun > 0),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "test_files": files,
        "output": stream.getvalue(),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent),
        help="Research safety directory to test (defaults to this script's directory).",
    )
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        result = {
            "ok": False,
            "tests_run": 0,
            "failures": 0,
            "errors": 0,
            "skipped": 0,
            "test_files": [],
            "output": f"BLOCKED: test root is not a directory: {root}",
        }
    else:
        result = run_tests(root)

    if args.json:
        print(json.dumps(result, sort_keys=True))
    elif result["ok"]:
        print(
            "PASS: "
            f"{result['tests_run']} tests across {len(result['test_files'])} files; "
            "0 failures, 0 errors."
        )
    else:
        print(result["output"].rstrip())
        print(
            "FAIL: "
            f"{result['tests_run']} tests; "
            f"{result['failures']} failures; {result['errors']} errors."
        )
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
