#!/usr/bin/env python3
"""
BTC15 SCALP frozen-collector field source map V1.

READ-ONLY SOURCE INSPECTION | RESEARCH ONLY | NO ORDERS

Decodes the immutable packaged scalp_move_shadow_v1.py implementation without
executing it, then prints only source lines that define/reference a small,
predeclared set of existing candidate-strength fields. This is used to verify
field semantics before any holdout research is designed.
"""
from __future__ import annotations

import ast
import base64
import gzip
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

VERSION = "BTC15_SCALP_COLLECTOR_FIELD_SOURCE_MAP_V1"
BASE = Path(__file__).with_name("scalp_move_shadow_v1.py")
EXPECTED_SHA256 = "3fdb2ef60f184e1ce2cef306c1db2a9de03b3e7b1a27c32b6bfffabb2cf60c48"
FIELDS = (
    "accel",
    "btc5",
    "btc15",
    "btc5_norm",
    "btc15_norm",
    "brti5",
    "brti15",
    "confirm_count",
    "recent_btc_range60",
)


def decode_frozen_source(path: Path = BASE) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    payload = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "PAYLOAD" for t in node.targets
        ):
            payload = ast.literal_eval(node.value)
            break
    if payload is None:
        raw = text
    else:
        raw = gzip.decompress(base64.b64decode(payload)).decode("utf-8")
    sha = hashlib.sha256(raw.encode()).hexdigest()
    if sha != EXPECTED_SHA256:
        raise RuntimeError(f"frozen collector SHA mismatch: {sha}")
    return raw


def map_source(source: str, fields: Iterable[str] = FIELDS, max_matches: int = 8) -> dict:
    lines = source.splitlines()
    out: dict[str, list[dict[str, object]]] = {}
    for field in fields:
        pat = re.compile(rf"\b{re.escape(field)}\b")
        matches = []
        for i, line in enumerate(lines, 1):
            if pat.search(line):
                matches.append({"line": i, "source": line.strip()})
                if len(matches) >= max_matches:
                    break
        out[str(field)] = matches
    return {
        "version": VERSION,
        "research_only": True,
        "orders": False,
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "fields": out,
        "strategy_rule_selected": False,
        "auto_promote_allowed": False,
    }


def main() -> int:
    out = map_source(decode_frozen_source())
    for field in FIELDS:
        matches = out["fields"].get(field) or []
        print(
            f"SCALP FIELD SOURCE | field={field} | "
            f"matches={json.dumps(matches, separators=(',', ':'))} | "
            "READ ONLY | NO RULE SELECTED | NO ORDERS",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
