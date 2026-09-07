#!/usr/bin/env python3
from pathlib import Path
import csv, sys

ROOT = Path(".")
SNAP = ROOT / "kalshi_scalp_shadow_snapshots_v1.csv"
EVENT = ROOT / "kalshi_scalp_shadow_events_v1.csv"
UNIFIED = ROOT / "kalshi_subminute_unified_v1_1.csv"

CANDIDATES = [
    ROOT / "kalshi_live_shadow_log.csv",
    ROOT / "kalshi_live_fair_value_shadow_log.csv",
    ROOT / "kalshi_two_output_live_log_v4_13.csv",
    ROOT / "kalshi_early_conf_shadow_v1.csv",
    ROOT / "kalshi_early_conf_shadow_v1_1.csv",
    ROOT / "kalshi_early_conf_shadow_v1_2.csv",
]

def header(path):
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            return next(csv.reader(f))
    except Exception:
        return []

def contract_set(path):
    h = header(path)
    if not h or "contract" not in h:
        return set()
    idx = h.index("contract")
    out = set()
    with path.open(newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            if len(row) > idx and row[idx]:
                out.add(row[idx].strip())
    return out

def row_count(path):
    with path.open(encoding="utf-8-sig", errors="ignore") as f:
        return max(0, sum(1 for _ in f) - 1)

def truthy(v):
    return str(v).strip().lower() in ("1","true","yes")

def event_stats(path, old_contracts):
    h = header(path)
    idx = {k:i for i,k in enumerate(h)}
    old_rows = hit10 = stop10 = 0
    old_contract_set = set()
    with path.open(newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            c = row[idx["contract"]].strip() if len(row) > idx["contract"] else ""
            if c in old_contracts:
                old_rows += 1
                old_contract_set.add(c)
                if "hit_10c" in idx and len(row) > idx["hit_10c"] and truthy(row[idx["hit_10c"]]):
                    hit10 += 1
                if "stop_10c_hit" in idx and len(row) > idx["stop_10c_hit"] and truthy(row[idx["stop_10c_hit"]]):
                    stop10 += 1
    return old_rows, len(old_contract_set), hit10, stop10

def interesting(cols):
    keys = ("final","fair","result","settle","outcome","brti","side","call","signal")
    return [c for c in cols if any(k in c.lower() for k in keys)]

print("="*72)
print("BTC15 OLD GAP POOL AUDIT V1")
print("="*72)

missing = [str(p) for p in (SNAP, EVENT, UNIFIED) if not p.exists()]
if missing:
    print("MISSING REQUIRED FILE(S):")
    for m in missing:
        print(" -", m)
    sys.exit(2)

snap_contracts = contract_set(SNAP)
event_contracts = contract_set(EVENT)
unified_contracts = contract_set(UNIFIED)
old_contracts = snap_contracts - unified_contracts

print(f"Snapshot rows:                 {row_count(SNAP):,}")
print(f"Snapshot unique contracts:     {len(snap_contracts)}")
print(f"Unified unique contracts:      {len(unified_contracts)}")
print(f"Older/outside unified pool:    {len(old_contracts)}")
print(f"Event unique contracts:        {len(event_contracts)}")
print(f"Old contracts with events:     {len(event_contracts & old_contracts)}")
print()

old_rows, old_event_contracts, hit10, stop10 = event_stats(EVENT, old_contracts)
print("OLD-POOL EVENT AVAILABILITY")
print(f"Event rows in old pool:         {old_rows:,}")
print(f"Old contracts represented:      {old_event_contracts}")
print(f"Rows marked hit +10c:           {hit10:,}")
print(f"Rows marked stop -10c:          {stop10:,}")
print()

print("POSSIBLE FINAL / SETTLEMENT SOURCES OVERLAPPING OLD POOL")
best_overlap = 0
best_file = None
for p in CANDIDATES:
    if not p.exists():
        continue
    cols = header(p)
    cset = contract_set(p)
    overlap = len(cset & old_contracts)
    useful = interesting(cols)
    if overlap > best_overlap:
        best_overlap = overlap
        best_file = p.name
    print(p.name)
    print(f"  contracts: {len(cset)} | overlap old pool: {overlap}")
    print("  signal/final-ish columns:", ", ".join(useful[:20]) if useful else "NONE")

print()
print("="*72)
if len(old_contracts) == 0:
    print("RESULT: No extra historical pool exists.")
elif len(event_contracts & old_contracts) == 0:
    print("RESULT: Extra contracts exist, but old event coverage is missing.")
elif best_overlap == 0:
    print("RESULT: Old snapshots/events can help scalp/chop research,")
    print("        but no overlapping FINAL-capable log was found.")
    print("        Do NOT call these union gaps yet.")
else:
    print("RESULT: Historical reconstruction looks feasible.")
    print(f"Best overlapping FINAL-capable candidate: {best_file} ({best_overlap} old contracts)")
    print("NEXT: build one offline historical union-gap scorer.")
print("="*72)
