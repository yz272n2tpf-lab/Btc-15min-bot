#!/usr/bin/env python3
from pathlib import Path
import csv, math

ROOT = Path(".")
SNAP = ROOT / "kalshi_scalp_shadow_snapshots_v1.csv"
EVENT = ROOT / "kalshi_scalp_shadow_events_v1.csv"
UNIFIED = ROOT / "kalshi_subminute_unified_v1_1.csv"

def get_header(path):
    try:
        with path.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
            return next(csv.reader(f))
    except Exception:
        return []

def contract_set(path):
    h = get_header(path)
    if "contract" not in h:
        return set()
    i = h.index("contract")
    out = set()
    try:
        with path.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
            r = csv.reader(f); next(r, None)
            for row in r:
                if len(row) > i and row[i].strip():
                    out.add(row[i].strip())
    except Exception:
        pass
    return out

def norm(s):
    return str(s).strip().lower()

def truthy(s):
    return norm(s) in {"1","true","yes","y"}

def fnum(s):
    try:
        return float(s)
    except Exception:
        return math.nan

if not (SNAP.exists() and EVENT.exists() and UNIFIED.exists()):
    print("Required source files are missing.")
    raise SystemExit(2)

snap_contracts = contract_set(SNAP)
unified_contracts = contract_set(UNIFIED)
old_contracts = snap_contracts - unified_contracts

print("="*78)
print("BTC15 HISTORICAL UNION RECON QUALIFIER V1")
print("="*78)
print(f"Older/outside-unified contracts: {len(old_contracts)}")
print()

# ---- Scan every CSV for overlap and useful FINAL/settlement fields ----
final_keys = {
    "final_side","final_status","final_confidence","final_call_source",
    "expected_final_outcome","legacy_final_ready","final_ready"
}
settle_keys = {
    "settled_side","settlement_side","official_result","result","outcome",
    "settled","winner","actual_side","label"
}
fair_keys = {"fair_up","fair_down","fair_preferred","preferred_fair","fair"}
timing_keys = {"seconds_left","time_left","minutes_left"}
gap_keys = {"btc_gap","gap","distance"}
range_keys = {"range5","range_5m","dist_range","dist_over_range5","distance_range5"}
brti_keys = {"brti_side","brti_gap","brti_price","brti","brti_ready"}

rows = []
for p in sorted(ROOT.glob("*.csv")):
    h = get_header(p)
    if not h or "contract" not in h:
        continue
    cols = set(h)
    overlap = len(contract_set(p) & old_contracts)
    if overlap <= 0:
        continue
    final_cols = sorted(cols & final_keys)
    settle_cols = sorted(cols & settle_keys)
    fair_cols = sorted(cols & fair_keys)
    timing_cols = sorted(cols & timing_keys)
    gap_cols = sorted(cols & gap_keys)
    range_cols = sorted(cols & range_keys)
    brti_cols = sorted(cols & brti_keys)
    rows.append((overlap,p.name,final_cols,settle_cols,fair_cols,timing_cols,gap_cols,range_cols,brti_cols))

rows.sort(reverse=True)

print("TOP OLD-POOL OVERLAPPING CSV SOURCES")
for overlap,name,fc,sc,fairc,tc,gc,rc,bc in rows[:20]:
    flags = []
    if fc: flags.append("FINAL")
    if sc: flags.append("SETTLEMENT")
    if fairc: flags.append("FAIR")
    if tc: flags.append("TIME")
    if gc: flags.append("GAP")
    if rc: flags.append("RANGE")
    if bc: flags.append("BRTI")
    print(f"{name}: overlap {overlap} | {', '.join(flags) if flags else 'no replay-critical fields'}")
    details = fc + sc + fairc + tc + gc + rc + bc
    if details:
        print("  fields:", ", ".join(details[:24]))
print()

# Decide whether exact historical frozen-FINAL replay is supported.
# We require either logged FINAL output, or enough ingredients to replay:
# fair + time + gap + range. BRTI is noted separately because current production
# validation depends on direct parity/safety logic.
logged_final_candidates = [r for r in rows if r[2]]
replay_candidates = [r for r in rows if r[4] and r[5] and r[6] and r[7]]
settle_candidates = [r for r in rows if r[3]]

max_logged = max([r[0] for r in logged_final_candidates], default=0)
max_replay = max([r[0] for r in replay_candidates], default=0)
max_settle = max([r[0] for r in settle_candidates], default=0)

print("FROZEN FINAL RECONSTRUCTION READINESS")
print(f"Old contracts with any overlapping logged-FINAL source (best file): {max_logged}")
print(f"Old contracts with fair+time+gap+range replay ingredients (best file): {max_replay}")
print(f"Old contracts with settlement-label source (best file): {max_settle}")
print()

# ---- Event-level 18% ROI feasibility in the old pool ----
eh = get_header(EVENT)
ei = {c:i for i,c in enumerate(eh)}
need = {"contract","entry_ask","max_future_bid"}
event_feasible = set()
event_contracts = set()
event_rows = 0
if need.issubset(ei):
    with EVENT.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
        r = csv.reader(f); next(r, None)
        for row in r:
            if len(row) <= max(ei[x] for x in need):
                continue
            c = row[ei["contract"]].strip()
            if c not in old_contracts:
                continue
            event_contracts.add(c)
            event_rows += 1
            ask = fnum(row[ei["entry_ask"]])
            mx = fnum(row[ei["max_future_bid"]])
            if ask > 0 and math.isfinite(mx) and mx >= ask * 1.18:
                event_feasible.add(c)

print("OLD-POOL TEMPORARY-MOVE FEASIBILITY (EVENT-LEVEL)")
print(f"Old contracts represented in event log: {len(event_contracts)}")
print(f"Old-pool event rows scanned: {event_rows:,}")
print(f"Contracts with at least one observed 18%+ event opportunity: {len(event_feasible)}")
if event_contracts:
    print(f"Observed event-opportunity rate: {100*len(event_feasible)/len(event_contracts):.1f}%")
print("NOTE: This is NOT union coverage. It only says an event row later reached +18% ROI.")
print()

print("="*78)
if max_logged >= 30 and max_settle >= 30:
    print("RESULT: Enough old-pool FINAL + settlement coverage exists to build a true")
    print("        historical union-gap holdout scorer next.")
elif max_replay >= 30 and max_settle >= 30:
    print("RESULT: Exact-ish frozen FINAL replay looks feasible on a meaningful old sample.")
    print("        Build the historical union-gap holdout scorer next.")
else:
    print("RESULT: The 61-contract old pool is valuable for scalp/chop research, but the")
    print("        evidence shown here does NOT support calling all 61 'union gaps'.")
    print("        Do not manufacture historical FINAL labels from partial early-conf logs.")
    print("        Use the old pool as independent chop/scalp feasibility evidence, while")
    print("        current 54-contract data remains the trusted same-contract union sample.")
print("="*78)
