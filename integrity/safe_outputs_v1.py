"""Offline derived-output creation. Never overwrite an existing filesystem entry."""

from pathlib import Path
from typing import Iterable


def validate_output_paths(
    inputs: Iterable[str | Path], outputs: Iterable[str | Path]
) -> list[Path]:
    """Preflight the entire write set before creating any directory or file.

    Resolution catches relative aliases and symlinked parents. Refusing every
    existing output also protects hard links, unrelated evidence, and devices.
    Exclusive creation at write time closes the final-file check/write race.
    """
    protected = {Path(p).resolve(strict=True) for p in inputs if p is not None}
    original = [Path(p) for p in outputs]
    targets = [p.resolve() for p in original]
    if len(set(targets)) != len(targets):
        raise ValueError("derived output paths overlap")
    for raw, target in zip(original, targets):
        if any(target == p or target in p.parents or p in target.parents for p in protected):
            raise ValueError(f"output overlaps protected input: {raw}")
        if raw.is_symlink() or target.exists():
            raise ValueError(f"output already exists; refusing overwrite: {raw}")
        if any(target in other.parents for other in targets if other != target):
            raise ValueError(f"derived output paths overlap: {raw}")
    return targets


def write_new_text(path: str | Path, text: str) -> None:
    """Create only; do not truncate, replace, unlink, or follow an existing file."""
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(text)
