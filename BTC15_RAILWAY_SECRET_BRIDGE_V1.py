#!/usr/bin/env python3
"""
BTC15 RAILWAY SECRET BRIDGE V1

Adds Railway environment-variable support for the existing Kalshi credentials
while preserving the current local ~/.kalshi file fallback.

NO trading logic changes.
NO signal changes.
NO order execution changes.

Railway variables used:
- KALSHI_KEY_ID
- KALSHI_PRIVATE_KEY_B64  (base64 of the existing PEM file)
"""

from pathlib import Path
import re
import subprocess

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
if not BOT.exists():
    raise SystemExit(f"STOP: missing {BOT}")

text = BOT.read_text(encoding="utf-8", errors="ignore")

if "_btc15_read_secret(" in text:
    print("Secret bridge already present; nothing to patch.")
else:
    # Find direct ~/.kalshi read_text() assignments.
    pat = re.compile(
        r'^(?P<indent>\s*)(?P<lhs>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*'
        r'Path\.home\(\)\.joinpath\((?P<q>[\'"])(?P<path>\.kalshi/[^\'"]+)(?P=q)\)'
        r'\.read_text\(\)(?P<strip>\.strip\(\))?\s*$',
        re.MULTILINE,
    )
    matches = list(pat.finditer(text))
    if not matches:
        print("STOP: could not find any direct ~/.kalshi credential reads.")
        print("No file changed.")
        raise SystemExit(2)

    helper = 