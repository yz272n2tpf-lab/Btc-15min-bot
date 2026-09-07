#!/usr/bin/env python3
"""
BTC15 RAILWAY PERSISTENCE PATCH V1
==================================
Creates a candidate copy of the live Railway entrypoint and changes ONLY:
- kalshi_15m_ladder_state.json -> /data/kalshi_15m_ladder_state.json
- kalshi_two_output_live_log_v4_13.csv -> /data/kalshi_two_output_live_log_v4_13.csv

Then:
- verifies exactly two replacements
- compiles the candidate
- prints a concise diff-style confirmation

It does NOT overwrite the live entrypoint.
It does NOT deploy.
It does NOT change thresholds.
It does NOT place orders.
"""

from pathlib import Path
import py_compile
import sys

SRC = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
DST = Path("bot_two_output_build_v4_13_profit_protection_shadow_persist_candidate.py")

REPLACEMENTS = {
    'Path("kalshi_15m_ladder_state.json")':
        'Path("/data/kalshi_15m_ladder_state.json")',
    "Path('kalshi_15m_ladder_state.json')":
        "Path('/data/kalshi_15m_ladder_state.json')",

    'Path("kalshi_two_output_live_log_v4_13.csv")':
        'Path("/data/kalshi_two_output_live_log_v4_13.csv")',
    "Path('kalshi_two_output_live_log_v4_13.csv')":
        "Path('/data/kalshi_two_output_live_log_v4_13.csv')",
}

print("=" * 92)
print("BTC15 RAILWAY PERSISTENCE PATCH V1")
print("=" * 92)

if not SRC.exists():
    raise SystemExit(f"MISSING SOURCE: {SRC}")

text = SRC.read_text(errors="strict")
original = text

changed = []

# Handle either quote style, but enforce exactly one occurrence per logical path.
logical = [
    ("LADDER_STATE",
     ['Path("kalshi_15m_ladder_state.json")',
      "Path('kalshi_15m_ladder_state.json')"],
     'Path("/data/kalshi_15m_ladder_state.json")'),

    ("LIVE_LOG",
     ['Path("kalshi_two_output_live_log_v4_13.csv")',
      "Path('kalshi_two_output_live_log_v4_13.csv')"],
     'Path("/data/kalshi_two_output_live_log_v4_13.csv")'),
]

for label, variants, replacement in logical:
    matches = sum(text.count(v) for v in variants)
    print(f"{label}: source matches found = {matches}")
    if matches != 1:
        raise SystemExit(
            f"ABORT: expected exactly 1 {label} path occurrence, found {matches}. "
            "No candidate written."
        )

    for v in variants:
        if v in text:
            text = text.replace(v, replacement, 1)
            changed.append((label, v, replacement))
            break

if text == original:
    raise SystemExit("ABORT: no changes made.")

DST.write_text(text)

print()
print(f"Candidate written: {DST}")
print()

# Syntax compile
try:
    py_compile.compile(str(DST), doraise=True)
    print("SYNTAX: PASS")
except Exception as e:
    try:
        DST.unlink()
    except Exception:
        pass
    raise SystemExit(f"SYNTAX: FAIL — candidate removed\n{e}")

# Verify old paths absent from candidate and new paths present exactly once.
checks = [
    ("old ladder path", "kalshi_15m_ladder_state.json", "/data/kalshi_15m_ladder_state.json"),
    ("old live log", "kalshi_two_output_live_log_v4_13.csv", "/data/kalshi_two_output_live_log_v4_13.csv"),
]

print()
print("PATCH VERIFICATION")
print("-" * 92)

ok = True

# More direct verification by exact new strings.
new1 = '/data/kalshi_15m_ladder_state.json'
new2 = '/data/kalshi_two_output_live_log_v4_13.csv'

for label, newp in [("LADDER_STATE", new1), ("LIVE_LOG", new2)]:
    c = text.count(newp)
    print(f"{label}: {newp} | count={c}")
    if c != 1:
        ok = False

# Ensure the 35-day cache was not touched.
cache_old = 'btc_35d_live_cache.csv'
cache_before = original.count(cache_old)
cache_after = text.count(cache_old)
print(f"35D_CACHE untouched: before={cache_before} after={cache_after}")
if cache_before != cache_after:
    ok = False

# Ensure only the intended two source lines changed.
old_lines = original.splitlines()
new_lines = text.splitlines()
diffs = []
for i, (a, b) in enumerate(zip(old_lines, new_lines), 1):
    if a != b:
        diffs.append((i, a, b))

print(f"Changed source lines: {len(diffs)}")
for line_no, before, after in diffs:
    print(f"L{line_no}:")
    print(f"  BEFORE: {before}")
    print(f"  AFTER : {after}")

if len(diffs) != 2:
    ok = False

print()
if ok:
    print("RESULT: PASS — candidate is ready for read-only verification.")
    print("LIVE ENTRYPOINT WAS NOT OVERWRITTEN.")
    print("NO DEPLOYMENT OCCURRED.")
else:
    print("RESULT: FAIL — do not deploy this candidate.")
    sys.exit(1)

print()
print("GUARDRAILS")
print("-" * 92)
print("No FINAL/Tier-1/Strong Scalp logic changed.")
print("No Rescue V2 logic changed.")
print("No thresholds changed.")
print("No orders.")
print("=" * 92)
