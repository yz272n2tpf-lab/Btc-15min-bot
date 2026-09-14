#!/usr/bin/env python3
"""
BTC15 protected main dashboard schema probe V1.

READ ONLY | KEY NAMES / TYPES ONLY | NO VALUES | NO ORDERS

Purpose: discover the exact public dashboard_state.json shape needed by the
cross-service adapter without logging signal values, credentials, or secrets.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
import requests

MAIN_STATE_URL = "https://btc-15min-bot-production.up.railway.app/dashboard_state.json"
MAX_DEPTH = 5
MAX_PATHS = 250


def type_name(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, Mapping):
        return "object"
    if isinstance(v, list):
        return "array"
    if isinstance(v, str):
        return "string"
    if isinstance(v, (int, float)):
        return "number"
    return type(v).__name__


def schema_paths(obj: Any, *, max_depth: int = MAX_DEPTH, max_paths: int = MAX_PATHS) -> list[str]:
    out: list[str] = []

    def walk(v: Any, path: str, depth: int) -> None:
        if len(out) >= max_paths:
            return
        if isinstance(v, Mapping):
            if depth >= max_depth:
                return
            for k in sorted(str(x) for x in v.keys()):
                child = v.get(k)
                p = f"{path}.{k}" if path else k
                out.append(f"{p}:{type_name(child)}")
                if len(out) >= max_paths:
                    return
                walk(child, p, depth + 1)
        elif isinstance(v, list):
            if depth >= max_depth or not v:
                return
            p = f"{path}[]" if path else "[]"
            out.append(f"{p}:{type_name(v[0])}")
            walk(v[0], p, depth + 1)

    walk(obj, "", 0)
    return out


def fetch_state() -> Any:
    r = requests.get(MAIN_STATE_URL, timeout=4.0, headers={"Cache-Control": "no-cache"})
    r.raise_for_status()
    return r.json()


def main() -> int:
    obj = fetch_state()
    paths = schema_paths(obj)
    print("MAIN_STATE_SCHEMA_V1 | KEY NAMES + TYPES ONLY | NO VALUES | NO ORDERS", flush=True)
    print("MAIN_STATE_SCHEMA_PATHS | " + " | ".join(paths), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
