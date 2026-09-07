#!/usr/bin/env python3
"""
BTC15 THREE-PATH DEPENDENCY AUDIT V1
Read-only. No bot logic changes. No orders.

Audits only:
- btc_35d_live_cache.csv
- kalshi_15m_ladder_state.json
- kalshi_two_output_live_log_v4_13.csv

Shows:
- every literal occurrence
- nearby source lines
- probable read/write/init behavior
- restart/persistence recommendation
"""

from pathlib import Path
import re

SRC = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")

TARGETS = {
    "btc_35d_live_cache.csv": "35D_CACHE",
    "kalshi_15m_ladder_state.json": "LADDER_STATE",
    "kalshi_two_output_live_log_v4_13.csv": "LIVE_LOG",
}

print("=" * 96)
print("BTC15 THREE-PATH DEPENDENCY AUDIT V1")
print("=" * 96)
print(f"Source: {SRC}")
print()

if not SRC.exists():
    raise SystemExit(f"MISSING: {SRC}")

lines = SRC.read_text(errors="replace").splitlines()

def classify(window):
    txt = "\n".join(window).lower()
    tags = []
    if "read_csv" in txt or ".read_text" in txt or "json.load" in txt or "open(" in txt and "'r'" in txt:
        tags.append("READ")
    if "to_csv" in txt or ".write_text" in txt or "json.dump" in txt or "'w'" in txt or "'a'" in txt:
        tags.append("WRITE")
    if "exists(" in txt:
        tags.append("EXISTS-CHECK")
    if "unlink(" in txt or "remove(" in txt:
        tags.append("DELETE")
    if "mkdir(" in txt:
        tags.append("MKDIR")
    return ",".join(tags) if tags else "REFERENCE"

for target, label in TARGETS.items():
    print("-" * 96)
    print(f"{label}: {target}")
    print("-" * 96)

    matches = []
    for i, line in enumerate(lines):
        if target in line:
            matches.append(i)

    if not matches:
        print("No literal occurrence found.")
        print()
        continue

    for n, i in enumerate(matches, 1):
        start = max(0, i - 8)
        end = min(len(lines), i + 13)
        window = lines[start:end]
        print(f"\nOccurrence {n} | source line {i+1} | behavior: {classify(window)}")
        print("." * 96)
        for j in range(start, end):
            marker = ">>" if j == i else "  "
            print(f"{marker} {j+1:5d}: {lines[j]}")

    print()

print("=" * 96)
print("AUTOMATIC RESTART / PERSISTENCE INTERPRETATION")
print("=" * 96)
print("""
1) LADDER_STATE
   If this file is written during runtime AND read on startup to restore contract/ladder state,
   it should normally live on /data so a Railway restart does not erase state.

2) LIVE_LOG
   If this is append/write-only runtime history and later used for scoring/debugging,
   it should normally live on /data so redeploys do not erase the current run history.

3) 35D_CACHE
   Do NOT move automatically.
   If it is a rebuildable/bootstrap cache or repository input, relative storage may be intentional.
   Move it only if the surrounding code proves it is continuously updated runtime state that must
   survive Railway restarts.
""")

print("READ-ONLY AUDIT. No source files changed. No thresholds changed. No orders.")
print("=" * 96)
