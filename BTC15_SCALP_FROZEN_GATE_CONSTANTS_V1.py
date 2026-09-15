#!/usr/bin/env python3
"""Read-only AST extraction of frozen generalized-SCALP gate constants. NO ORDERS."""
from __future__ import annotations

import ast
import json

from BTC15_SCALP_COLLECTOR_FIELD_SOURCE_MAP_V1 import decode_frozen_source

VERSION = "BTC15_SCALP_FROZEN_GATE_CONSTANTS_V1"
NAMES = (
    "BTC5_MIN",
    "BTC15_MIN",
    "BTC30_FLOOR",
    "BRTI15_FLOOR",
    "BTC5_STRONG",
    "BTC15_STRONG",
    "BRTI5_STRONG",
    "MIN_ACCEL",
    "MIN_LEFT",
    "CONFIRM_WINDOW",
    "CONFIRM_N",
    "CONFIRM_COUNT",
    "MIN_CONFIRM",
    "REQUIRED_CONFIRMATIONS",
)


def extract(source: str) -> dict[str, object]:
    tree = ast.parse(source)
    out: dict[str, object] = {}
    wanted = set(NAMES)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            value = ast.literal_eval(node.value)
        except Exception:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in wanted:
                out[target.id] = value
    return out


def main() -> int:
    values = extract(decode_frozen_source())
    print(
        "SCALP FROZEN GATE CONSTANTS | "
        f"values={json.dumps(values, sort_keys=True, separators=(',', ':'))} | "
        "READ ONLY | NO RULE CHANGE | NO ORDERS",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
