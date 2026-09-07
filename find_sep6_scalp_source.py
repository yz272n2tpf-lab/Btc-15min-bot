#!/usr/bin/env python3
import csv
from pathlib import Path
from datetime import datetime, timezone

UFILE = Path("kalshi_subminute_unified_v1_1.csv")
START = datetime.fromisoformat("2026-09-06T04:00:00+00:00")
END   = datetime.fromisoformat("2026-09-06T18:00:00+00:00")

def parse_dt(x):
    try:
        d=datetime.fromisoformat(str(x).strip().replace("Z","+00:00"))
        if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except:
        return None

def read_dicts(p):
    try:
        with p.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []

u = read_dicts(UFILE)
contracts=set()
for r in u:
    t=parse_dt(r.get("timestamp_utc"))
    c=str(r.get("contract") or r.get("ticker") or "").strip()
    if t and START<=t<=END and c:
        contracts.add(c)

print("="*78)
print("SEP 6 SCALP SOURCE FINDER")
print("="*78)
print("Target contracts:", len(contracts))
print()

hits=[]
for p in sorted(Path(".").glob("*.csv")):
    rows=read_dicts(p)
    if not rows:
        continue
    overlap_rows=0
    overlap_contracts=set()
    for r in rows:
        c=str(r.get("contract") or r.get("ticker") or "").strip()
        if c in contracts:
            overlap_rows += 1
            overlap_contracts.add(c)
    if overlap_rows:
        hits.append((len(overlap_contracts), overlap_rows, p.name, list(rows[0].keys())[:12]))

hits.sort(reverse=True)
for nc,nr,name,cols in hits:
    print(f"{name}")
    print(f"  overlapping contracts: {nc}")
    print(f"  overlapping rows:      {nr}")
    print(f"  first columns:         {cols}")
    print()

print("="*78)
print("Done. No files changed. No bot logic changed.")
