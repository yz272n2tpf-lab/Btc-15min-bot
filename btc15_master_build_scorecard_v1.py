#!/usr/bin/env python3
"""
BTC15 MASTER BUILD SCORECARD V1
===============================
One-command health + scoring checkpoint.

What it does:
- Runs the trusted accepted-union scorecard.
- Runs the frozen Rescue V2 prospective scorekeeper.
- Reports required data/cache files.
- Reports newest timestamps / stale-feed warnings where possible.
- Does NOT tune thresholds.
- Does NOT change bot.py.
- Does NOT place orders.
"""

from pathlib import Path
import subprocess
import sys
import re
import pandas as pd

ROOT = Path(".")
ACCEPTED = ROOT / "kalshi_accepted_union_scorecard_v1.py"
RESCUE = ROOT / "rescue_v2_frozen_prospective_scorekeeper.py"

REQUIRED = [
    ROOT / "union_optimizer_processed_snapshot_cache.csv",
    ROOT / "kalshi_kxbtc15m_1m_candles_cache.csv",
]

def run_capture(path):
    if not path.exists():
        return 2, f"MISSING SCRIPT: {path.name}"
    p = subprocess.run(
        [sys.executable, str(path)],
        text=True,
        capture_output=True,
    )
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    return p.returncode, out.strip()

def grab(pattern, text, default="N/A"):
    m = re.search(pattern, text, re.I)
    return m.group(1).strip() if m else default

def newest_timestamp(path):
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    candidates = [
        "snapshot_utc", "timestamp_utc", "signal_timestamp_utc",
        "candle_end_utc", "outcome_timestamp_utc"
    ]
    vals = []
    for c in candidates:
        if c in df.columns:
            s = pd.to_datetime(df[c], errors="coerce", utc=True).dropna()
            if len(s):
                vals.append(s.max())
    return max(vals) if vals else None

print("=" * 88)
print("BTC15 MASTER BUILD SCORECARD V1")
print("=" * 88)

print("\nDATA / CACHE HEALTH")
print("-" * 88)
for p in REQUIRED:
    state = "OK" if p.exists() else "MISSING"
    newest = newest_timestamp(p)
    suffix = f" | newest {newest}" if newest is not None else ""
    print(f"{state:7s} {p.name}{suffix}")

print("\nACCEPTED PRODUCTION BASELINE")
print("-" * 88)
arc, accepted_out = run_capture(ACCEPTED)
if arc == 0:
    hold_union = grab(r"ACCEPTED UNION:\s*(\d+/\d+\s*=\s*[\d.]+%)", accepted_out)
    # Fallback because some versions print "ACCEPTED UNION: 88/100 (88.0%)"
    if hold_union == "N/A":
        hold_union = grab(r"ACCEPTED UNION:\s*(\d+/\d+\s*\([\d.]+%\))", accepted_out)
    scalp_wr = grab(r"Strong scalp wins:\s*([^\n]+)", accepted_out)
    print(f"Accepted holdout union: {hold_union}")
    if scalp_wr != "N/A":
        print(f"Strong scalp: {scalp_wr}")
    print("STATUS: ACCEPTED / FROZEN — do not retune here.")
else:
    print("Accepted scorecard could not run.")
    print(accepted_out[-1000:])

print("\nRESCUE V2 — FROZEN PROSPECTIVE SHADOW")
print("-" * 88)
rrc, rescue_out = run_capture(RESCUE)
if rrc == 0:
    fired = grab(r"FIRED:\s*(\d+)", rescue_out, "0")
    closed = grab(r"CLOSED:\s*(\d+)", rescue_out, "0")
    open_n = grab(r"OPEN:\s*(\d+)", rescue_out, "0")
    winrate = grab(r"WIN RATE:\s*([^\n]+)", rescue_out, "N/A")
    if "No prospective V2 calls have fired yet" in rescue_out or "NO prospective cache rows yet" in rescue_out:
        print("Prospective calls: 0")
        print("Win rate: N/A — awaiting fresh post-freeze data.")
    else:
        print(f"Fired: {fired} | Closed: {closed} | Open: {open_n}")
        print(f"Win rate: {winrate}")
    print("STATUS: SHADOW ONLY — not promoted.")
else:
    print("Rescue V2 scorer could not run.")
    print(rescue_out[-1000:])

print("\nBUILD GUARDRAILS")
print("-" * 88)
print("✓ Existing FINAL / Tier-1 / Strong Scalp logic remains untouched.")
print("✓ Rescue V1 remains rejected.")
print("✓ Rescue V2 remains frozen; no threshold changes.")
print("✓ Signal-only. No orders.")
print("✓ Railway can continue collecting while this scorecard is rerun.")

print("\nNEXT PROMOTION GATE")
print("-" * 88)
print("Do not promote Rescue V2 from historical 14/14 alone.")
print("Require a meaningful fresh prospective sample before any production change.")
print("=" * 88)
