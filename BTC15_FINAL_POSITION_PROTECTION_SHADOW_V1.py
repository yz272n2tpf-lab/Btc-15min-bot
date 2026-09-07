#!/usr/bin/env python3
"""
BTC15 FINAL POSITION-PROTECTION SHADOW COLLECTOR V1

Purpose
-------
Run beside the locked V4.13 bot in a SECOND terminal.
It does NOT change the bot and does NOT place orders.

It watches the live V4.13 log and, after a FINAL call appears, records the
post-call trajectory needed to validate a future FINAL HOLD / CAUTION / EXIT /
FLIPPED policy:
- FINAL side
- FINAL confidence / fair if available
- time left
- BTC gap / distance if available
- direct BRTI side/gap if available
- reversal state if available
- Kalshi UP/DOWN bid/ask if available

Output
------
kalshi_final_position_protection_shadow_v1.csv

This is a DATA COLLECTION shadow only. It intentionally does not invent or
enforce an exit threshold.
"""

from pathlib import Path
import csv
import time
from datetime import datetime, timezone

ROOT = Path(".")
SOURCE = ROOT / "kalshi_two_output_live_log_v4_13.csv"
OUT = ROOT / "kalshi_final_position_protection_shadow_v1.csv"
POLL_SECONDS = 2.0

def lower_map(header):
    return {c.lower(): i for i, c in enumerate(header)}

def pick(header, names):
    lm = lower_map(header)
    for n in names:
        if n.lower() in lm:
            return lm[n.lower()]
    for i,c in enumerate(header):
        cl = c.lower()
        for n in names:
            if n.lower() in cl:
                return i
    return None

def val(row, idx):
    return "" if idx is None or idx >= len(row) else row[idx].strip()

def read_all(path):
    with path.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
        rows = list(csv.reader(f))
    if not rows:
        return [], []
    return rows[0], rows[1:]

def normalize_side(s):
    x = str(s).strip().upper()
    if x in ("UP","YES","HIGHER"): return "UP"
    if x in ("DOWN","NO","LOWER"): return "DOWN"
    return x

def looks_final(status, side):
    s = str(status).upper()
    sd = normalize_side(side)
    if sd not in ("UP","DOWN"):
        return False
    if "PASS" in s:
        return False
    # Most logs mark FINAL explicitly; if status field is absent, require side.
    return ("FINAL" in s) or ("LOCK" in s) or (s in ("UP","DOWN","CALL","READY","QUALIFIED",""))

print("="*78)
print("BTC15 FINAL POSITION-PROTECTION SHADOW COLLECTOR V1")
print("="*78)
print("SHADOW ONLY — NO ORDERS — NO CORE LOGIC CHANGES")
print("Source:", SOURCE.name)
print("Output:", OUT.name)
print("This collector records post-FINAL behavior for later exit-rule validation.")
print("="*78)

while not SOURCE.exists():
    print("Waiting for live V4.13 log...")
    time.sleep(POLL_SECONDS)

last_count = 0
seen_keys = set()

# Preserve existing output if restarting.
if OUT.exists():
    try:
        oh, orows = read_all(OUT)
        for r in orows:
            if len(r) >= 4:
                seen_keys.add((r[1], r[2], r[3]))
    except Exception:
        pass

out_header = [
    "collector_timestamp_utc",
    "source_timestamp_utc",
    "contract",
    "final_side",
    "final_status",
    "final_confidence",
    "fair_up",
    "fair_down",
    "seconds_left",
    "btc_gap",
    "brti_side",
    "brti_gap",
    "reversal_state",
    "up_bid",
    "up_ask",
    "down_bid",
    "down_ask",
]

if not OUT.exists():
    with OUT.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(out_header)

active_contract = None
active_side = None

while True:
    try:
        header, rows = read_all(SOURCE)
        if not header:
            time.sleep(POLL_SECONDS)
            continue

        idx_ts = pick(header, ["timestamp_utc","timestamp","time_utc"])
        idx_contract = pick(header, ["contract","ticker"])
        idx_final_side = pick(header, ["final_side","expected_final_outcome","final_call","final"])
        idx_final_status = pick(header, ["final_status","status","final_ready"])
        idx_conf = pick(header, ["final_confidence","confidence","fair_confidence"])
        idx_fair_up = pick(header, ["fair_up"])
        idx_fair_down = pick(header, ["fair_down"])
        idx_left = pick(header, ["seconds_left","time_left_seconds"])
        idx_gap = pick(header, ["btc_gap","gap"])
        idx_brti_side = pick(header, ["brti_side"])
        idx_brti_gap = pick(header, ["brti_gap"])
        idx_rev = pick(header, ["reversal_state","reversal"])
        idx_up_bid = pick(header, ["up_bid"])
        idx_up_ask = pick(header, ["up_ask"])
        idx_dn_bid = pick(header, ["down_bid"])
        idx_dn_ask = pick(header, ["down_ask"])

        for row in rows[last_count:]:
            ts = val(row, idx_ts)
            contract = val(row, idx_contract)
            side = normalize_side(val(row, idx_final_side))
            status = val(row, idx_final_status)

            if contract and side in ("UP","DOWN") and looks_final(status, side):
                active_contract = contract
                active_side = side

            # Once a FINAL is active, continue recording all later rows for that contract
            # even if subsequent rows don't repeat the FINAL label.
            if contract and active_contract == contract and active_side in ("UP","DOWN"):
                key = (ts, contract, active_side)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                out_row = [
                    datetime.now(timezone.utc).isoformat(),
                    ts,
                    contract,
                    active_side,
                    status,
                    val(row, idx_conf),
                    val(row, idx_fair_up),
                    val(row, idx_fair_down),
                    val(row, idx_left),
                    val(row, idx_gap),
                    val(row, idx_brti_side),
                    val(row, idx_brti_gap),
                    val(row, idx_rev),
                    val(row, idx_up_bid),
                    val(row, idx_up_ask),
                    val(row, idx_dn_bid),
                    val(row, idx_dn_ask),
                ]
                with OUT.open("a", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(out_row)

        last_count = len(rows)

        if active_contract:
            print(f"Tracking FINAL shadow: {active_contract} {active_side} | rows saved {len(seen_keys)}", end="\r", flush=True)

    except KeyboardInterrupt:
        print("\nStopped. Shadow data safely saved to", OUT.name)
        break
    except Exception as e:
        print("\nCollector warning:", e)
        time.sleep(POLL_SECONDS)

    time.sleep(POLL_SECONDS)
