#!/usr/bin/env python3
"""Deterministic, read-only evidence manifests for V6 replay/audit artifacts.

The manifest records only file metadata (relative path, SHA-256, byte count,
line count). It never embeds evidence contents and never follows symlinks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Iterable

SCHEMA = "v6-replay-evidence-manifest/v1"


class ManifestError(ValueError):
    pass


def _root(root: str | os.PathLike[str]) -> Path:
    p = Path(root).expanduser().resolve()
    if not p.is_dir():
        raise ManifestError(f"root is not a directory: {root}")
    return p


def _evidence_entry(path: str | os.PathLike[str], root: Path) -> dict:
    raw = Path(path).expanduser()
    candidate = raw if raw.is_absolute() else root / raw

    # Reject symlinks before resolve(), including any symlinked parent below root.
    try:
        rel_lexical = candidate.absolute().relative_to(root)
    except ValueError as exc:
        raise ManifestError(f"path escapes root: {path}") from exc

    cursor = root
    for part in rel_lexical.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ManifestError(f"symlink evidence path is not allowed: {path}")

    resolved = candidate.resolve(strict=True)
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise ManifestError(f"path escapes root: {path}") from exc

    if not resolved.is_file():
        raise ManifestError(f"evidence path is not a regular file: {path}")
    if any(part in ("", ".", "..") for part in rel.parts):
        raise ManifestError(f"invalid evidence path: {path}")

    data = resolved.read_bytes()
    line_count = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
    return {
        "path": rel.as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "line_count": line_count,
    }


def build_manifest(
    paths: Iterable[str | os.PathLike[str]],
    *,
    root: str | os.PathLike[str] = ".",
) -> dict:
    root_path = _root(root)
    entries = [_evidence_entry(path, root_path) for path in paths]
    if not entries:
        raise ManifestError("at least one evidence file is required")

    names = [entry["path"] for entry in entries]
    if len(names) != len(set(names)):
        raise ManifestError("duplicate evidence path")

    entries.sort(key=lambda entry: entry["path"])
    return {"schema": SCHEMA, "files": entries}


def canonical_json(manifest: dict) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def verify_manifest(
    manifest: dict,
    *,
    root: str | os.PathLike[str] = ".",
) -> list[str]:
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        return ["unsupported or missing manifest schema"]

    expected = manifest.get("files")
    if not isinstance(expected, list) or not expected:
        return ["manifest must contain a non-empty files list"]

    errors: list[str] = []
    seen: set[str] = set()
    root_path = _root(root)

    for item in expected:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            errors.append("malformed manifest file entry")
            continue

        logical = item["path"]
        if logical in seen:
            errors.append(f"duplicate manifest path: {logical}")
            continue
        seen.add(logical)

        try:
            actual = _evidence_entry(logical, root_path)
        except (ManifestError, FileNotFoundError) as exc:
            errors.append(f"{logical}: {exc}")
            continue

        for field in ("sha256", "size_bytes", "line_count"):
            if item.get(field) != actual[field]:
                errors.append(
                    f"{logical}: {field} mismatch "
                    f"(expected {item.get(field)!r}, got {actual[field]!r})"
                )
    return errors


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="create a deterministic evidence manifest")
    create.add_argument("files", nargs="+", help="evidence files under --root")
    create.add_argument("--root", default=".", help="evidence root (default: current directory)")
    create.add_argument("--output", required=True, help="manifest output path")

    verify = sub.add_parser("verify", help="verify files against an existing manifest")
    verify.add_argument("manifest", help="manifest JSON path")
    verify.add_argument("--root", default=".", help="evidence root (default: current directory)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "create":
            manifest = build_manifest(args.files, root=args.root)
            _write_atomic(Path(args.output), canonical_json(manifest))
            print(f"PASS: wrote {len(manifest['files'])} evidence entries")
            return 0

        with open(args.manifest, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        errors = verify_manifest(manifest, root=args.root)
        if errors:
            for error in errors:
                print(f"FAIL: {error}", file=sys.stderr)
            return 1
        print(f"PASS: verified {len(manifest['files'])} evidence entries")
        return 0
    except (ManifestError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
