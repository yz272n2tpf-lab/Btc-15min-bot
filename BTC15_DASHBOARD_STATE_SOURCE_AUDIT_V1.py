#!/usr/bin/env python3
"""Read-only source audit for packed BTC15_DASHBOARD_STATE_V2.py.

Imports the production dashboard installer as data, decodes its embedded state
module, and prints small source windows around contract-discovery/rollover code.
No network calls, no service mutations, no signal changes, no orders.
"""
from __future__ import annotations

import base64
import gzip

import BTC15_INSTALL_LIVE_DASHBOARD_V13 as installer

TARGET = "BTC15_DASHBOARD_STATE_V2.py"
NEEDLES = (
    "NO ACTIVE KXBTC15M CONTRACT",
    "KXBTC15M",
    "active contract",
    "get_markets",
    "/markets",
    "status=",
    "status\":",
    "open_time",
    "close_time",
    "retrying",
)


def decoded_source() -> str:
    raw = installer.PAYLOADS.get(TARGET)
    if not raw:
        raise RuntimeError(f"packed payload missing: {TARGET}")
    return gzip.decompress(base64.b64decode(raw)).decode("utf-8", errors="replace")


def audit_windows(radius: int = 10) -> list[tuple[int, int, list[str]]]:
    src = decoded_source()
    lines = src.splitlines()
    hit_lines: set[int] = set()
    for i, line in enumerate(lines):
        low = line.lower()
        if any(n.lower() in low for n in NEEDLES):
            hit_lines.add(i)
    if not hit_lines:
        raise RuntimeError("no contract-discovery source anchors found")

    ranges: list[tuple[int, int]] = []
    for i in sorted(hit_lines):
        a, b = max(0, i - radius), min(len(lines), i + radius + 1)
        if ranges and a <= ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], max(ranges[-1][1], b))
        else:
            ranges.append((a, b))
    return [(a + 1, b, lines[a:b]) for a, b in ranges]


def print_audit() -> None:
    src = decoded_source()
    print("=" * 92)
    print("BTC15 DASHBOARD STATE SOURCE AUDIT V1 | READ ONLY | NO ORDERS")
    print(f"decoded_target={TARGET} | chars={len(src)} | lines={len(src.splitlines())}")
    for start, end, rows in audit_windows():
        print(f"--- SOURCE WINDOW L{start}-L{end} ---")
        for off, row in enumerate(rows, start=start):
            print(f"L{off:04d} | {row}")
    print("RESULT=PASS")
    print("=" * 92)


def main() -> int:
    src = decoded_source()
    assert "NO ACTIVE KXBTC15M CONTRACT" in src
    assert "KXBTC15M" in src
    print_audit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
