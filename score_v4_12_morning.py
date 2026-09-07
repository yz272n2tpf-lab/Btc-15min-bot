
import pandas as pd
from pathlib import Path

SCALP = Path("kalshi_true_scalp_forward_shadow_v1.csv")
UNIFIED = Path("kalshi_subminute_unified_v1_1.csv")

def truthy(s):
    return s.astype(str).str.strip().str.lower().isin(["true","1","yes"])

print("=" * 64)
print("V4.12 MORNING SCORECARD")
print("=" * 64)

if not SCALP.exists():
    print("SCALP FILE: MISSING")
else:
    d = pd.read_csv(SCALP)
    print(f"SCALP SIGNALS: {len(d)}")
    if len(d):
        w = truthy(d["result_10c_before_stop"])
        h15 = truthy(d["hit_15c"])
        h20 = truthy(d["hit_20c"])

        print(f"+10c BEFORE -10c: {int(w.sum())}/{len(d)} = {w.mean()*100:.1f}%")
        print(f"+15c HIT:         {int(h15.sum())}/{len(d)} = {h15.mean()*100:.1f}%")
        print(f"+20c HIT:         {int(h20.sum())}/{len(d)} = {h20.mean()*100:.1f}%")

        if "entry_ask" in d:
            print(f"AVG ENTRY:        {d['entry_ask'].mean()*100:.1f}c")
            print(f"MEDIAN ENTRY:     {d['entry_ask'].median()*100:.1f}c")
        if "minutes_left" in d:
            print(f"AVG TIME LEFT:    {d['minutes_left'].mean():.2f}m")
        if "seconds_to_10c" in d:
            x = pd.to_numeric(d["seconds_to_10c"], errors="coerce").dropna()
            if len(x):
                print(f"MEDIAN +10c TIME: {x.median():.1f}s")
        if "contract" in d:
            print(f"CONTRACTS HIT:    {d['contract'].nunique()}")

print("-" * 64)

if not UNIFIED.exists():
    print("UNIFIED FILE: MISSING")
else:
    u = pd.read_csv(UNIFIED)
    rows = len(u)
    snaps = rows // 2
    mins = snaps * 5 / 60
    print(f"UNIFIED ROWS:     {rows}")
    print(f"5s SNAPSHOTS:     ~{snaps}")
    print(f"APPROX LIVE TIME: ~{mins/60:.2f} hours")
    if "contract" in u:
        print(f"UNIFIED CONTRACTS:{u['contract'].nunique()}")

print("=" * 64)
print("DEVELOPMENT SCALP BENCHMARK: 17/18 = 94.4%")
print("Compare the fresh forward score above against that benchmark.")
print("=" * 64)
