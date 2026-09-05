
import warnings
from pathlib import Path
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

SCALP = Path("kalshi_true_scalp_forward_shadow_v1.csv")
PROFIT = Path("kalshi_profit_protection_forward_shadow_v1.csv")
SNAPS = Path("kalshi_scalp_shadow_snapshots_v1.csv")
UNIFIED = Path("kalshi_subminute_unified_v1_1.csv")

BASE_SCALP_ROWS = 17
BASE_UNIFIED_ROWS = 4716

def truthy(s):
    return s.astype(str).str.strip().str.lower().isin(["true","1","yes"])

def pct(n, d):
    return 0.0 if d == 0 else 100.0*n/d

print("=" * 72)
print("V4.13 FORWARD RUN SCORECARD")
print("=" * 72)

if not SCALP.exists():
    raise SystemExit("ERROR: scalp forward log missing")

d = pd.read_csv(SCALP)
new = d.iloc[BASE_SCALP_ROWS:].copy()

print(f"NEW SCALP SIGNALS: {len(new)}")
if len(new):
    w = truthy(new["result_10c_before_stop"])
    h15 = truthy(new["hit_15c"])
    h20 = truthy(new["hit_20c"])
    print(f"+10c BEFORE -10c: {int(w.sum())}/{len(new)} = {pct(int(w.sum()),len(new)):.1f}%")
    print(f"+15c HIT:          {int(h15.sum())}/{len(new)} = {pct(int(h15.sum()),len(new)):.1f}%")
    print(f"+20c HIT:          {int(h20.sum())}/{len(new)} = {pct(int(h20.sum()),len(new)):.1f}%")
    print(f"AVG ENTRY:         {new['entry_ask'].mean()*100:.1f}c")
    print(f"MEDIAN ENTRY:      {new['entry_ask'].median()*100:.1f}c")
    print(f"AVG TIME LEFT:     {new['minutes_left'].mean():.2f}m")
    x = pd.to_numeric(new["seconds_to_10c"], errors="coerce").dropna()
    if len(x):
        print(f"MEDIAN +10c TIME:  {x.median():.1f}s")
    print(f"CONTRACTS HIT:     {new['contract'].nunique()}")
else:
    print("No new completed scalp signals after the prior 17-signal baseline.")

print("-" * 72)

if PROFIT.exists():
    p = pd.read_csv(PROFIT)
else:
    p = pd.DataFrame()

print(f"PROFIT-PROTECTION EXITS: {len(p)}")

if len(p):
    p["profit_c"] = pd.to_numeric(p["profit_c"], errors="coerce")
    p["roi_pct"] = pd.to_numeric(p["roi_pct"], errors="coerce")
    p["peak_profit_c"] = pd.to_numeric(p["peak_profit_c"], errors="coerce")

    print(f"ARMED/COMPLETED:      {len(p)}")
    if len(new):
        print(f"ARM RATE VS NEW SCALPS:{100*len(p)/len(new):.1f}%")

    print(f"18%+ ROI EXITS:       {(p['roi_pct'] >= 18).sum()}/{len(p)} = {(p['roi_pct'] >= 18).mean()*100:.1f}%")
    print(f"AVG EXIT PROFIT:      +{p['profit_c'].mean():.1f}c")
    print(f"MEDIAN EXIT PROFIT:   +{p['profit_c'].median():.1f}c")
    print(f"AVG EXIT ROI:         {p['roi_pct'].mean():.1f}%")
    print(f"MEDIAN EXIT ROI:      {p['roi_pct'].median():.1f}%")
    print(f"WORST EXIT PROFIT:    {p['profit_c'].min():+.1f}c")
    print(f"BEST EXIT PROFIT:     {p['profit_c'].max():+.1f}c")

    reasons = p["exit_reason"].value_counts()
    print("EXIT REASONS:")
    for k, v in reasons.items():
        print(f"  {k}: {v}")

    if SNAPS.exists() and len(new):
        sn = pd.read_csv(SNAPS)
        sn["timestamp_utc"] = pd.to_datetime(sn["timestamp_utc"], errors="coerce", utc=True)
        new["signal_timestamp_utc"] = pd.to_datetime(new["signal_timestamp_utc"], errors="coerce", utc=True)

        bank_rows = []
        profit_ids = set(p["signal_id"].astype(str))
        for _, r in new.iterrows():
            sid = str(r["signal_id"])
            if sid not in profit_ids:
                continue

            side = str(r["side"]).upper()
            contract = str(r["contract"])
            ts = r["signal_timestamp_utc"]
            entry = float(r["entry_ask"])
            bid_col = f"{side.lower()}_bid"

            if bid_col not in sn.columns:
                continue

            path = sn[
                (sn["contract"].astype(str) == contract)
                & (sn["timestamp_utc"] >= ts)
                & (sn["timestamp_utc"] <= ts + pd.Timedelta(seconds=180))
            ].copy()

            if path.empty:
                continue

            path[bid_col] = pd.to_numeric(path[bid_col], errors="coerce")
            hit = path[path[bid_col] >= entry + 0.10]
            if hit.empty:
                continue

            bid = float(hit.iloc[0][bid_col])
            bank_rows.append({
                "signal_id": sid,
                "bank_profit_c": (bid-entry)*100
            })

        if bank_rows:
            b = pd.DataFrame(bank_rows)
            joined = p.merge(b, on="signal_id", how="inner")
            if len(joined):
                print("-" * 72)
                print("SAME-TRADE COMPARISON VS BANK +10c")
                print(f"TRADES COMPARED:       {len(joined)}")
                print(f"BANK +10 AVG PROFIT:   +{joined['bank_profit_c'].mean():.1f}c")
                print(f"PROTECTION AVG PROFIT: +{joined['profit_c'].mean():.1f}c")
                print(f"EXTRA AVG PROFIT:      {joined['profit_c'].mean()-joined['bank_profit_c'].mean():+.1f}c")
                better = (joined["profit_c"] > joined["bank_profit_c"]).sum()
                equal = np.isclose(joined["profit_c"], joined["bank_profit_c"], atol=0.11).sum()
                print(f"BEAT BANK +10:         {better}/{len(joined)} = {100*better/len(joined):.1f}%")
                print(f"MATCHED ~BANK +10:     {equal}/{len(joined)} = {100*equal/len(joined):.1f}%")
else:
    print("No armed profit-protection exits were logged in this run.")

print("-" * 72)

if UNIFIED.exists():
    u = pd.read_csv(UNIFIED)
    new_u = u.iloc[BASE_UNIFIED_ROWS:].copy()
    print(f"NEW UNIFIED ROWS:      {len(new_u)}")
    print(f"NEW 5s SNAPSHOTS:      ~{len(new_u)//2}")
    print(f"APPROX NEW LIVE TIME:  ~{(len(new_u)//2)*5/3600:.2f} hours")
    if "contract" in new_u:
        print(f"NEW UNIFIED CONTRACTS: {new_u['contract'].nunique()}")
else:
    print("UNIFIED FILE: MISSING")

print("=" * 72)
print("REFERENCE BENCHMARKS")
print("Prior fresh scalp: 17/17 = 100% at +10c before -10c")
print("Offline exit candidate untouched block: avg +29.2c / 71.0% ROI")
print("V4.13 remains SHADOW until forward statistics justify promotion.")
print("=" * 72)
