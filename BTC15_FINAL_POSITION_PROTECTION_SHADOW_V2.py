#!/usr/bin/env python3
"""
BTC15 FINAL POSITION-PROTECTION SHADOW V2

Why V2 exists
-------------
V1 watched kalshi_two_output_live_log_v4_13.csv, but the overnight audit proved
that file did not continuously receive FINAL rows. V2 instead watches the
continuously-written unified 5-second log and reconstructs the frozen FINAL
qualification from the locked production rules, then records every post-call
5-second state for later HOLD / CAUTION / EXIT / FLIPPED validation.

READ-ONLY / SHADOW ONLY:
- no orders
- no edits to V4.13
- no production threshold changes
- writes only: kalshi_final_position_protection_shadow_v2.csv

Frozen FINAL shadow qualification used here
-------------------------------------------
- preferred fair >= 90%
- time left <= 8 minutes
- BTC gap >= $75 when >6m left, else >= $50
- 5-minute BTC distance/range >= 1.0
- preferred side agrees with BTC side vs target
- direct BRTI ready
- direct BRTI side agrees with preferred side

The collector records the FINAL trigger and every subsequent unified row for
that contract until rollover.
"""

from pathlib import Path
import csv, math, time
from collections import deque, defaultdict
from datetime import datetime, timezone, timedelta

ROOT = Path(".")
SOURCE = ROOT / "kalshi_subminute_unified_v1_1.csv"
OUT = ROOT / "kalshi_final_position_protection_shadow_v2.csv"

POLL_SECONDS = 2.0
FAIR_MIN = 0.90
MAX_MINUTES_LEFT = 8.0
GAP_EARLY = 75.0
GAP_LATE = 50.0
DIST_RANGE_MIN = 1.0

def header_rows(path):
    with path.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
        rows = list(csv.reader(f))
    if not rows:
        return [], []
    return rows[0], rows[1:]

def cmap(h):
    return {c.lower(): i for i,c in enumerate(h)}

def idx(h, names):
    m = cmap(h)
    for n in names:
        if n.lower() in m:
            return m[n.lower()]
    for i,c in enumerate(h):
        cl = c.lower()
        for n in names:
            if n.lower() in cl:
                return i
    return None

def get(row, i):
    return "" if i is None or i >= len(row) else row[i].strip()

def fnum(x):
    try:
        return float(x)
    except Exception:
        return math.nan

def truthy(x):
    return str(x).strip().lower() in {"1","true","yes","y"}

def side_norm(x):
    s = str(x).strip().upper()
    if s in {"UP","YES","HIGHER"}: return "UP"
    if s in {"DOWN","NO","LOWER"}: return "DOWN"
    return ""

def parse_dt(s):
    s = str(s).strip()
    if not s: return None
    for v in (s, s.replace("Z","+00:00")):
        try:
            d = datetime.fromisoformat(v)
            if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc)
        except Exception:
            pass
    return None

def fair_to_prob(v):
    x = fnum(v)
    if not math.isfinite(x): return math.nan
    if x > 1.5: x /= 100.0
    return x

print("="*86)
print("BTC15 FINAL POSITION-PROTECTION SHADOW V2")
print("="*86)
print("SHADOW ONLY — NO ORDERS — NO CORE LOGIC CHANGES")
print("Source:", SOURCE.name)
print("Output:", OUT.name)
print("V2 uses the continuously-written unified 5-second log.")
print("="*86)

while not SOURCE.exists():
    print("Waiting for unified source log...")
    time.sleep(POLL_SECONDS)

h, rows = header_rows(SOURCE)

I = {
    "ts": idx(h, ["timestamp_utc","timestamp"]),
    "contract": idx(h, ["contract","ticker"]),
    "btc_price": idx(h, ["btc_price"]),
    "btc_gap": idx(h, ["btc_gap"]),
    "seconds_left": idx(h, ["seconds_left"]),
    "minutes_left": idx(h, ["minutes_left"]),
    "preferred_side": idx(h, ["preferred_side","fair_preferred_side","current_side"]),
    "preferred_fair": idx(h, ["preferred_fair","fair_preferred"]),
    "fair_up": idx(h, ["fair_up"]),
    "fair_down": idx(h, ["fair_down"]),
    "brti_ready": idx(h, ["brti_ready","ready"]),
    "brti_side": idx(h, ["brti_side"]),
    "brti_gap": idx(h, ["brti_gap"]),
    "reversal": idx(h, ["reversal_state","reversal"]),
    "up_bid": idx(h, ["up_bid"]),
    "up_ask": idx(h, ["up_ask"]),
    "down_bid": idx(h, ["down_bid"]),
    "down_ask": idx(h, ["down_ask"]),
}

required = ["ts","contract","btc_price","btc_gap","preferred_side","preferred_fair","brti_ready","brti_side"]
missing = [k for k in required if I[k] is None]
if missing:
    print("STOP: unified log is missing required field(s):", ", ".join(missing))
    print("Available columns:")
    print(", ".join(h))
    raise SystemExit(2)

out_header = [
    "collector_timestamp_utc","source_timestamp_utc","contract",
    "record_type","final_side","final_fair","minutes_left",
    "btc_price","btc_gap","range5","dist_over_range5",
    "brti_ready","brti_side","brti_gap","reversal_state",
    "up_bid","up_ask","down_bid","down_ask"
]
if not OUT.exists():
    with OUT.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(out_header)

last_count = 0
active_contract = None
active_side = None
price_history = defaultdict(deque)
saved = 0

def write_record(row, record_type, final_side, final_fair, minutes_left, range5, ratio):
    global saved
    rec = [
        datetime.now(timezone.utc).isoformat(),
        get(row, I["ts"]),
        get(row, I["contract"]),
        record_type,
        final_side,
        f"{final_fair:.6f}" if math.isfinite(final_fair) else "",
        f"{minutes_left:.4f}" if math.isfinite(minutes_left) else "",
        get(row, I["btc_price"]),
        get(row, I["btc_gap"]),
        f"{range5:.6f}" if math.isfinite(range5) else "",
        f"{ratio:.6f}" if math.isfinite(ratio) else "",
        get(row, I["brti_ready"]),
        get(row, I["brti_side"]),
        get(row, I["brti_gap"]),
        get(row, I["reversal"]),
        get(row, I["up_bid"]),
        get(row, I["up_ask"]),
        get(row, I["down_bid"]),
        get(row, I["down_ask"]),
    ]
    with OUT.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(rec)
    saved += 1

while True:
    try:
        h2, rows = header_rows(SOURCE)
        if h2 != h:
            print("\nSource header changed; restart V2 collector.")
            break

        new_rows = rows[last_count:]
        for row in new_rows:
            contract = get(row, I["contract"])
            ts = parse_dt(get(row, I["ts"]))
            price = fnum(get(row, I["btc_price"]))
            gap = fnum(get(row, I["btc_gap"]))

            sec_left = fnum(get(row, I["seconds_left"]))
            min_left = fnum(get(row, I["minutes_left"]))
            if not math.isfinite(min_left) and math.isfinite(sec_left):
                min_left = sec_left / 60.0

            if contract and ts and math.isfinite(price):
                dq = price_history[contract]
                dq.append((ts, price))
                cutoff = ts - timedelta(minutes=5)
                while dq and dq[0][0] < cutoff:
                    dq.popleft()
                vals = [p for _,p in dq]
                range5 = (max(vals)-min(vals)) if len(vals) >= 2 else math.nan
            else:
                range5 = math.nan

            ratio = abs(gap)/range5 if math.isfinite(gap) and math.isfinite(range5) and range5 > 0 else math.nan

            preferred_side = side_norm(get(row, I["preferred_side"]))
            preferred_fair = fair_to_prob(get(row, I["preferred_fair"]))
            brti_ready = truthy(get(row, I["brti_ready"]))
            brti_side = side_norm(get(row, I["brti_side"]))
            btc_side = "UP" if math.isfinite(gap) and gap > 0 else ("DOWN" if math.isfinite(gap) and gap < 0 else "")

            # If rollover occurs, previous active FINAL stops being tracked.
            if active_contract and contract and contract != active_contract:
                active_contract = None
                active_side = None

            # Frozen FINAL shadow trigger.
            gap_min = GAP_EARLY if math.isfinite(min_left) and min_left > 6.0 else GAP_LATE
            qualifies = (
                preferred_side in {"UP","DOWN"} and
                math.isfinite(preferred_fair) and preferred_fair >= FAIR_MIN and
                math.isfinite(min_left) and min_left <= MAX_MINUTES_LEFT and
                math.isfinite(gap) and abs(gap) >= gap_min and
                math.isfinite(ratio) and ratio >= DIST_RANGE_MIN and
                btc_side == preferred_side and
                brti_ready and
                brti_side == preferred_side
            )

            if active_contract is None and qualifies:
                active_contract = contract
                active_side = preferred_side
                write_record(row, "FINAL_TRIGGER", active_side, preferred_fair, min_left, range5, ratio)

            elif active_contract == contract and active_side:
                write_record(row, "POST_FINAL", active_side, preferred_fair, min_left, range5, ratio)

        last_count = len(rows)

        if active_contract:
            print(f"Tracking {active_contract} FINAL {active_side} | rows saved {saved}", end="\r", flush=True)
        else:
            print(f"Waiting for next frozen FINAL trigger | rows saved {saved}", end="\r", flush=True)

    except KeyboardInterrupt:
        print("\nStopped. Data saved:", OUT.name)
        break
    except Exception as e:
        print("\nCollector warning:", e)

    time.sleep(POLL_SECONDS)
