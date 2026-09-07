#!/usr/bin/env python3
from pathlib import Path
import hashlib
import sys

SRC = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
CAND = Path("bot_two_output_build_v4_13_profit_protection_shadow_persist_candidate.py")

print("="*92)
print("BTC15 PERSISTENCE CANDIDATE FINAL VERIFY V1")
print("="*92)

for p in (SRC, CAND):
    if not p.exists():
        raise SystemExit(f"MISSING: {p}")

a = SRC.read_text()
b = CAND.read_text()

al = a.splitlines()
bl = b.splitlines()

if len(al) != len(bl):
    raise SystemExit(f"FAIL: line count changed {len(al)} -> {len(bl)}")

diffs = []
for i,(x,y) in enumerate(zip(al,bl),1):
    if x != y:
        diffs.append((i,x,y))

print(f"Changed lines: {len(diffs)}")
for i,x,y in diffs:
    print(f"L{i}")
    print(f"  LIVE : {x}")
    print(f"  CAND : {y}")

expected = {
    1183: '_ladder_state_path = Path("/data/kalshi_15m_ladder_state.json")',
    1781: '_snapshot_log = Path("/data/kalshi_two_output_live_log_v4_13.csv")',
}

ok = True

if len(diffs) != 2:
    ok = False

for line_no, expected_substr in expected.items():
    if line_no > len(bl) or expected_substr not in bl[line_no-1]:
        print(f"FAIL: expected candidate content missing at line {line_no}")
        ok = False

# Make sure production logic markers are byte-identical outside two target lines.
filtered_a = "\n".join(x for i,x in enumerate(al,1) if i not in expected)
filtered_b = "\n".join(x for i,x in enumerate(bl,1) if i not in expected)

ha = hashlib.sha256(filtered_a.encode()).hexdigest()
hb = hashlib.sha256(filtered_b.encode()).hexdigest()

print()
print(f"Non-target SHA256 live : {ha}")
print(f"Non-target SHA256 cand : {hb}")

if ha != hb:
    print("FAIL: non-target content differs.")
    ok = False

# Explicit guardrails
for needle in [
    "btc_35d_live_cache.csv",
    "kalshi_true_scalp_forward_shadow_v1.csv",
    "kalshi_profit_protection_forward_shadow_v1.csv",
]:
    ca = a.count(needle)
    cb = b.count(needle)
    print(f"{needle}: live={ca} cand={cb}")
    if ca != cb:
        ok = False

print()
if ok:
    print("RESULT: PASS")
    print("Candidate differs from live file ONLY in the two intended persistence paths.")
    print("SAFE TO PROMOTE THOSE TWO LINES INTO THE LIVE ENTRYPOINT.")
else:
    print("RESULT: FAIL — DO NOT PROMOTE.")
    sys.exit(1)

print("="*92)
