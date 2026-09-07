#!/usr/bin/env python3
"""
BTC15 RAILWAY PERSISTENCE PATCH V2
==================================
Creates a candidate copy of the live Railway entrypoint and changes ONLY
the assignments for:
- _ladder_state_path
- _snapshot_log

Safer than V1 because it matches assignment variable names rather than
fragile exact quote formatting.

It does NOT overwrite the live entrypoint.
It does NOT deploy.
It does NOT change thresholds.
It does NOT place orders.
"""

from pathlib import Path
import ast
import py_compile
import sys

SRC = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
DST = Path("bot_two_output_build_v4_13_profit_protection_shadow_persist_candidate.py")

TARGETS = {
    "_ladder_state_path": "/data/kalshi_15m_ladder_state.json",
    "_snapshot_log": "/data/kalshi_two_output_live_log_v4_13.csv",
}

print("=" * 92)
print("BTC15 RAILWAY PERSISTENCE PATCH V2")
print("=" * 92)

if not SRC.exists():
    raise SystemExit(f"MISSING SOURCE: {SRC}")

text = SRC.read_text(errors="strict")
tree = ast.parse(text)

# Find exact assignment lines by variable name.
assignments = {}
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        for name in names:
            if name in TARGETS:
                assignments.setdefault(name, []).append(node)

for name in TARGETS:
    found = assignments.get(name, [])
    print(f"{name}: assignments found = {len(found)}")
    if len(found) != 1:
        raise SystemExit(
            f"ABORT: expected exactly 1 assignment for {name}, found {len(found)}. "
            "No candidate written."
        )

lines = text.splitlines()

# Replace whole assignment line only.
changed = []
new_lines = lines[:]

for name, new_path in TARGETS.items():
    node = assignments[name][0]
    lineno = node.lineno
    old_line = lines[lineno - 1]
    indent = old_line[:len(old_line) - len(old_line.lstrip())]
    new_line = f'{indent}{name} = Path("{new_path}")'
    new_lines[lineno - 1] = new_line
    changed.append((lineno, old_line, new_line))

new_text = "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")

# Safety: verify exactly two line changes.
diffs = []
for i, (a, b) in enumerate(zip(lines, new_lines), 1):
    if a != b:
        diffs.append((i, a, b))

if len(diffs) != 2:
    raise SystemExit(f"ABORT: expected exactly 2 changed lines, found {len(diffs)}.")

# Ensure 35d cache untouched.
before_35 = text.count("btc_35d_live_cache.csv")
after_35 = new_text.count("btc_35d_live_cache.csv")
if before_35 != after_35:
    raise SystemExit("ABORT: 35D cache reference changed unexpectedly.")

DST.write_text(new_text)

# Compile candidate.
try:
    py_compile.compile(str(DST), doraise=True)
except Exception as e:
    try:
        DST.unlink()
    except Exception:
        pass
    raise SystemExit(f"SYNTAX FAIL — candidate removed\n{e}")

print()
print(f"Candidate written: {DST}")
print("SYNTAX: PASS")
print()
print("PATCH VERIFICATION")
print("-" * 92)
for lineno, before, after in diffs:
    print(f"L{lineno}:")
    print(f"  BEFORE: {before}")
    print(f"  AFTER : {after}")

print()
print(f"35D cache references unchanged: {before_35}")
print()
print("RESULT: PASS — candidate ready for verification.")
print("LIVE ENTRYPOINT WAS NOT OVERWRITTEN.")
print("NO DEPLOYMENT OCCURRED.")
print()
print("GUARDRAILS")
print("-" * 92)
print("No FINAL/Tier-1/Strong Scalp logic changed.")
print("No Rescue V2 logic changed.")
print("No thresholds changed.")
print("No orders.")
print("=" * 92)
