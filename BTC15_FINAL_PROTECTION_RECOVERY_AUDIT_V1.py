#!/usr/bin/env python3
"""
BTC15 FINAL PROTECTION RECOVERY AUDIT V1

Purpose:
- Recover/locate post-FINAL evidence from CSVs already saved overnight.
- Read-only: does NOT modify the bot, models, thresholds, or place orders.
- Automatically scans every CSV in the project so we avoid terminal scavenger hunts.

It reports:
1) Which files contain FINAL call fields.
2) Which files contain the time/contract/BTC/Kalshi/BRTI/reversal fields needed
   to reconstruct post-FINAL trajectories.
3) How many recent contracts can be reconstructed from saved data.
4) Whether we can build an offline HOLD/CAUTION/EXIT scorer now, or whether
   a short corrected live shadow collection is still required.
"""

from pathlib import Path
import csv
from datetime import datetime, timezone, timedelta

ROOT = Path(".")
WINDOW_HOURS = 12

FINAL_KEYS = {
    "final_side","final_status","final_confidence","final_call_source",
    "expected_final_outcome","legacy_final_ready","final_ready",
    "decisive_fair_ready"
}
TIME_KEYS = {"timestamp_utc","timestamp","time_utc","source_timestamp_utc"}
CONTRACT_KEYS = {"contract","ticker"}
FAIR_KEYS = {"fair_up","fair_down","fair_preferred","preferred_fair","fair"}
BTC_KEYS = {"btc_gap","btc_price"}
LEFT_KEYS = {"seconds_left","minutes_left","time_left"}
BRTI_KEYS = {"brti_side","brti_gap","brti_price","brti_ready","ready"}
REV_KEYS = {"reversal_state","reversal"}
KALSHI_KEYS = {"up_bid","up_ask","down_bid","down_ask"}

def header(path):
    try:
        with path.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
            return next(csv.reader(f))
    except Exception:
        return []

def parse_dt(s):
    s = str(s).strip()
    if not s:
        return None
    for v in (s, s.replace("Z","+00:00")):
        try:
            d = datetime.fromisoformat(v)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc)
        except Exception:
            pass
    return None

def find_col(h, keys):
    low = [x.lower() for x in h]
    for i,x in enumerate(low):
        if x in keys:
            return i
    return None

def contracts_and_recent_rows(path, h, start, end):
    tc = find_col(h, TIME_KEYS)
    cc = find_col(h, CONTRACT_KEYS)
    if tc is None or cc is None:
        return set(), 0
    cs = set()
    n = 0
    try:
        with path.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
            r = csv.reader(f)
            next(r, None)
            for row in r:
                if len(row) <= max(tc,cc):
                    continue
                dt = parse_dt(row[tc])
                if dt and start <= dt <= end:
                    n += 1
                    c = row[cc].strip()
                    if c:
                        cs.add(c)
    except Exception:
        pass
    return cs, n

# Anchor to latest timestamp found in any CSV with a recognizable time column.
latest = None
for p in ROOT.glob("*.csv"):
    h = header(p)
    tc = find_col(h, TIME_KEYS)
    if tc is None:
        continue
    try:
        with p.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
            r = csv.reader(f)
            next(r, None)
            for row in r:
                if len(row) <= tc:
                    continue
                dt = parse_dt(row[tc])
                if dt and (latest is None or dt > latest):
                    latest = dt
    except Exception:
        pass

if latest is None:
    print("STOP: no timestamped CSV data found.")
    raise SystemExit(2)

start = latest - timedelta(hours=WINDOW_HOURS)
end = latest

rows = []
for p in sorted(ROOT.glob("*.csv")):
    h = header(p)
    if not h:
        continue
    cols = {x.lower() for x in h}
    has_contract = bool(cols & CONTRACT_KEYS)
    has_time = bool(cols & TIME_KEYS)
    if not (has_contract and has_time):
        continue

    final_cols = sorted(cols & FINAL_KEYS)
    fair_cols = sorted(cols & FAIR_KEYS)
    btc_cols = sorted(cols & BTC_KEYS)
    left_cols = sorted(cols & LEFT_KEYS)
    brti_cols = sorted(cols & BRTI_KEYS)
    rev_cols = sorted(cols & REV_KEYS)
    kalshi_cols = sorted(cols & KALSHI_KEYS)

    cs, n = contracts_and_recent_rows(p, h, start, end)
    if n == 0:
        continue

    score = 0
    if final_cols: score += 8
    if fair_cols: score += 2
    if btc_cols: score += 2
    if left_cols: score += 2
    if brti_cols: score += 2
    if rev_cols: score += 1
    if kalshi_cols: score += 2

    rows.append({
        "file": p.name,
        "rows": n,
        "contracts": cs,
        "score": score,
        "final": final_cols,
        "fair": fair_cols,
        "btc": btc_cols,
        "left": left_cols,
        "brti": brti_cols,
        "rev": rev_cols,
        "kalshi": kalshi_cols,
    })

rows.sort(key=lambda x: (x["score"], len(x["contracts"]), x["rows"]), reverse=True)

print("="*86)
print("BTC15 FINAL PROTECTION RECOVERY AUDIT V1")
print("="*86)
print("Recent data window UTC:", start.isoformat(), "->", end.isoformat())
print()

print("TOP RECOVERY SOURCES")
for r in rows[:20]:
    flags=[]
    if r["final"]: flags.append("FINAL")
    if r["fair"]: flags.append("FAIR")
    if r["btc"]: flags.append("BTC")
    if r["left"]: flags.append("TIMELEFT")
    if r["brti"]: flags.append("BRTI")
    if r["rev"]: flags.append("REVERSAL")
    if r["kalshi"]: flags.append("KALSHI")
    print(f"{r['file']}: rows {r['rows']} | contracts {len(r['contracts'])} | score {r['score']} | {', '.join(flags)}")
    detail = r["final"] + r["fair"] + r["btc"] + r["left"] + r["brti"] + r["rev"] + r["kalshi"]
    if detail:
        print("  fields:", ", ".join(detail[:30]))
print()

final_sources = [r for r in rows if r["final"]]
trajectory_sources = [r for r in rows if r["btc"] and r["left"] and (r["fair"] or r["kalshi"])]

final_contracts = set()
for r in final_sources:
    final_contracts |= r["contracts"]

trajectory_contracts = set()
for r in trajectory_sources:
    trajectory_contracts |= r["contracts"]

reconstructable = final_contracts & trajectory_contracts

print("RECOVERY SUMMARY")
print("Recent contracts represented in FINAL-capable files:", len(final_contracts))
print("Recent contracts represented in trajectory-capable files:", len(trajectory_contracts))
print("Recent contracts with BOTH:", len(reconstructable))
print()

print("="*86)
if len(reconstructable) >= 8:
    print("RESULT: OFFLINE FINAL-PROTECTION RECONSTRUCTION IS FEASIBLE.")
    print("NEXT: build one offline HOLD/CAUTION/EXIT/FLIPPED scorer from these saved logs.")
elif len(reconstructable) >= 3:
    print("RESULT: PARTIAL RECOVERY.")
    print("There is some usable saved evidence, but sample is still small.")
    print("NEXT: build a recovery scorer AND continue corrected shadow collection in parallel.")
else:
    print("RESULT: SAVED LOGS DO NOT CONTAIN ENOUGH MATCHED POST-FINAL TRAJECTORIES.")
    print("NEXT: fix the shadow collector and run it beside the core during normal live use.")
    print("No extra overnight test is justified just for this.")
print("="*86)
