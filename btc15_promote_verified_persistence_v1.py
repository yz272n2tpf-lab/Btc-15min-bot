#!/usr/bin/env python3
"""
BTC15 PROMOTE VERIFIED PERSISTENCE V1

Promotes ONLY the two already-verified /data path changes from the candidate
into the live Railway entrypoint, while creating a backup first.

Does NOT deploy Railway.
Does NOT change thresholds.
Does NOT change trading/signal logic.
Does NOT place orders.
"""

from pathlib import Path
import hashlib
import py_compile
import shutil
import sys

LIVE = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
CAND = Path("bot_two_output_build_v4_13_profit_protection_shadow_persist_candidate.py")
BACKUP = Path("bot_two_output_build_v4_13_profit_protection_shadow_pre_persist_backup.py")

TARGET_LINES = {
    1183: '_ladder_state_path = Path("/data/kalshi_15m_ladder_state.json")',
    1781: '_snapshot_log = Path("/data/kalshi_two_output_live_log_v4_13.csv")',
}

print("="*94)
print("BTC15 PROMOTE VERIFIED PERSISTENCE V1")
print("="*94)

for p in (LIVE, CAND):
    if not p.exists():
        raise SystemExit(f"ABORT — MISSING: {p}")

a = LIVE.read_text()
b = CAND.read_text()
al = a.splitlines()
bl = b.splitlines()

if len(al) != len(bl):
    raise SystemExit("ABORT — live/candidate line counts differ.")

diffs=[(i,x,y) for i,(x,y) in enumerate(zip(al,bl),1) if x!=y]

print(f"Pre-promotion changed lines: {len(diffs)}")
for i,x,y in diffs:
    print(f"L{i}")
    print(f"  LIVE: {x}")
    print(f"  CAND: {y}")

if len(diffs) != 2 or {i for i,_,_ in diffs} != set(TARGET_LINES):
    raise SystemExit("ABORT — candidate no longer differs only at the two approved lines.")

for line_no, needle in TARGET_LINES.items():
    if needle not in bl[line_no-1]:
        raise SystemExit(f"ABORT — approved content missing at line {line_no}.")

# Prove everything except the two approved lines is identical.
fa="\n".join(x for i,x in enumerate(al,1) if i not in TARGET_LINES)
fb="\n".join(x for i,x in enumerate(bl,1) if i not in TARGET_LINES)
if hashlib.sha256(fa.encode()).digest() != hashlib.sha256(fb.encode()).digest():
    raise SystemExit("ABORT — non-target content differs.")

# Backup current live entrypoint before promotion.
shutil.copy2(LIVE, BACKUP)
print(f"\nBackup created: {BACKUP}")

# Promote exact verified candidate.
shutil.copy2(CAND, LIVE)

# Syntax check promoted live file.
try:
    py_compile.compile(str(LIVE), doraise=True)
except Exception as e:
    shutil.copy2(BACKUP, LIVE)
    raise SystemExit(f"PROMOTION SYNTAX FAIL — automatically restored backup.\n{e}")

# Final byte equality: promoted live must equal verified candidate.
if LIVE.read_bytes() != CAND.read_bytes():
    shutil.copy2(BACKUP, LIVE)
    raise SystemExit("PROMOTION VERIFY FAIL — automatically restored backup.")

print("Promoted live entrypoint syntax: PASS")
print("Promoted live == verified candidate: PASS")
print()
print("RESULT: PROMOTION PASS")
print("The source tree now contains the verified persistence hardening.")
print("RAILWAY HAS NOT BEEN REDEPLOYED OR RESTARTED.")
print("The currently running Railway test remains uninterrupted.")
print()
print("NEXT SAFE ACTION:")
print("Commit these source changes when ready; keep current Railway deployment running.")
print("="*94)
