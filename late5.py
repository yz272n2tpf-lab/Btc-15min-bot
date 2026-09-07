from pathlib import Path
import subprocess
import sys
import pandas as pd
import numpy as np

MARKER = Path("kalshi_frozen_5m_guard_start_utc.txt")
LAYER = Path("kalshi_official_truth_layer_a_rescore_details.csv")
PREC = Path("kalshi_official_truth_late_reversal_precursor_details.csv")
THRESHOLD = 75.0

print("=== LATE-REVERSAL CHECK AFTER STRONG 5M SUPPORT ===")
print("Diagnostic only. No bot.py changes. No scalp changes. No orders.\n")

# Refresh the same trusted official-truth files used by run5.py.
for script in [
    "kalshi_official_settlement_validator.py",
    "kalshi_official_truth_layer_a_rescorer.py",
    "kalshi_official_truth_late_reversal_precursor_audit.py",
]:
    if not Path(script).exists():
        raise SystemExit(f"ERROR: missing {script}")
    subprocess.run([sys.executable, script], check=False)

for p in [MARKER, LAYER, PREC]:
    if not p.exists():
        raise SystemExit(f"ERROR: missing {p.name}")

marker = pd.to_datetime(MARKER.read_text().strip(), utc=True, errors="coerce")
if pd.isna(marker):
    raise SystemExit("ERROR: invalid frozen 5m marker.")

a = pd.read_csv(LAYER, low_memory=False)
b = pd.read_csv(PREC, low_memory=False)

a["timestamp_utc"] = pd.to_datetime(a["timestamp_utc"], errors="coerce", utc=True)

if a["correct"].dtype == bool:
    a["correct_bool"] = a["correct"]
else:
    a["correct_bool"] = (
        a["correct"].astype(str).str.strip().str.lower()
        .map({"true":True,"1":True,"yes":True,"false":False,"0":False,"no":False})
    )

x = a[
    (a["timestamp_utc"] >= marker)
    & a["layer_a_state"].astype(str).str.upper().str.contains("CLEAN", na=False)
    & a["correct_bool"].notna()
].copy()

keep_cols = ["ticker"]
for cp in ["5p0","4p5","4p0","3p5","3p0","2p5","2p0","1p5"]:
    for kind in ["dist","fair","ask"]:
        c = f"{kind}_{cp}"
        if c in b.columns:
            keep_cols.append(c)
for c in ["min_signed_distance_5to2","min_fair_5to2"]:
    if c in b.columns:
        keep_cols.append(c)

b = b[keep_cols].drop_duplicates("ticker", keep="last").copy()
for c in b.columns:
    if c != "ticker":
        b[c] = pd.to_numeric(b[c], errors="coerce")

x = x.merge(b, on="ticker", how="left")
x = x[x["dist_5p0"].notna()].copy()
x["five_warn"] = x["dist_5p0"] <= THRESHOLD

survivors = x[~x["five_warn"]].copy()
strong_misses = survivors[~survivors["correct_bool"]].copy()
strong_winners = survivors[survivors["correct_bool"]].copy()

print("\n=== POST-FREEZE 5M-GUARD SURVIVORS ===")
print("Usable CLEAN calls:", len(x))
print("Warned at 5m:", int(x["five_warn"].sum()))
print("Kept after 5m guard:", len(survivors))
print("Kept winners:", len(strong_winners))
print("Kept misses:", len(strong_misses))
print()

base = [c for c in [
    "timestamp_utc","ticker","call_side","official_side","correct_bool","dist_5p0"
] if c in survivors.columns]

print("=== STRONG-AT-5M MISSES ===")
if strong_misses.empty:
    print("None.")
else:
    print(strong_misses[base].to_string(index=False))

# Changes from the 5m checkpoint.
for cp in ["4p5","4p0","3p5","3p0","2p5","2p0","1p5"]:
    if f"dist_{cp}" in survivors.columns:
        survivors[f"dist_change_5_to_{cp}"] = survivors[f"dist_{cp}"] - survivors["dist_5p0"]
    if "fair_5p0" in survivors.columns and f"fair_{cp}" in survivors.columns:
        survivors[f"fair_change_5_to_{cp}"] = survivors[f"fair_{cp}"] - survivors["fair_5p0"]

strong_misses = survivors[~survivors["correct_bool"]].copy()
strong_winners = survivors[survivors["correct_bool"]].copy()

traj_cols = ["ticker","correct_bool","dist_5p0"]
for cp in ["4p5","4p0","3p5","3p0","2p5","2p0","1p5"]:
    if f"dist_{cp}" in survivors.columns:
        traj_cols.append(f"dist_{cp}")
for cp in ["5p0","4p0","3p0","2p0","1p5"]:
    if f"fair_{cp}" in survivors.columns:
        traj_cols.append(f"fair_{cp}")

print("\n=== STRONG MISS PATH: 5M -> 1.5M ===")
if strong_misses.empty:
    print("None.")
else:
    print(strong_misses[traj_cols].to_string(index=False))

print("\n=== KEPT WINNERS FOR COMPARISON ===")
if strong_winners.empty:
    print("None.")
else:
    print(strong_winners[traj_cols].to_string(index=False))

change_cols = ["ticker","correct_bool","dist_5p0"]
for cp in ["4p0","3p0","2p0","1p5"]:
    c = f"dist_change_5_to_{cp}"
    if c in survivors.columns:
        change_cols.append(c)
for cp in ["4p0","3p0","2p0","1p5"]:
    c = f"fair_change_5_to_{cp}"
    if c in survivors.columns:
        change_cols.append(c)
for c in ["min_signed_distance_5to2","min_fair_5to2"]:
    if c in survivors.columns:
        change_cols.append(c)

print("\n=== WHAT CHANGED AFTER 5M ===")
print(survivors[change_cols].to_string(index=False))

# Small predeclared scan only. This is diagnostic, not a fitted rule.
tests = []
def add_test(name, mask):
    mask = mask.fillna(False).astype(bool)
    misses = ~survivors["correct_bool"].astype(bool)
    wins = survivors["correct_bool"].astype(bool)
    flagged = int(mask.sum())
    caught = int((mask & misses).sum())
    good = int((mask & wins).sum())
    kept = survivors[~mask]
    acc = 100.0 * kept["correct_bool"].mean() if len(kept) else np.nan
    tests.append([name, flagged, caught, int(misses.sum()), good, len(kept), acc])

candidates = [
    ("5->4m distance drop >= $50", "dist_change_5_to_4p0", -50),
    ("5->4m distance drop >= $75", "dist_change_5_to_4p0", -75),
    ("5->3m distance drop >= $75", "dist_change_5_to_3p0", -75),
    ("5->3m distance drop >= $100", "dist_change_5_to_3p0", -100),
    ("5->2m distance drop >= $100", "dist_change_5_to_2p0", -100),
    ("5->2m distance drop >= $150", "dist_change_5_to_2p0", -150),
]
for name, col, cut in candidates:
    if col in survivors.columns:
        add_test(name, survivors[col] <= cut)

fair_candidates = [
    ("5->4m fair drop >= 5pt", "fair_change_5_to_4p0", -0.05),
    ("5->4m fair drop >= 10pt", "fair_change_5_to_4p0", -0.10),
    ("5->3m fair drop >= 10pt", "fair_change_5_to_3p0", -0.10),
    ("5->3m fair drop >= 15pt", "fair_change_5_to_3p0", -0.15),
    ("5->2m fair drop >= 15pt", "fair_change_5_to_2p0", -0.15),
    ("5->2m fair drop >= 20pt", "fair_change_5_to_2p0", -0.20),
]
for name, col, cut in fair_candidates:
    if col in survivors.columns:
        add_test(name, survivors[col] <= cut)

if "min_signed_distance_5to2" in survivors.columns:
    for cut in [75,50,25,0]:
        add_test(f"minimum support 5m->2m <= ${cut}", survivors["min_signed_distance_5to2"] <= cut)

print("\n=== SMALL PREDECLARED LATE-FAILURE SCAN ===")
if tests:
    out = pd.DataFrame(
        tests,
        columns=["candidate","flagged","misses_caught","total_misses",
                 "good_winners_flagged","kept","kept_accuracy_pct"]
    )
    out = out.sort_values(
        ["misses_caught","good_winners_flagged","kept_accuracy_pct"],
        ascending=[False,True,False]
    )
    print(out.to_string(index=False, float_format=lambda v:f"{v:.1f}"))
    out.to_csv("kalshi_strong5m_late_failure_scan.csv", index=False)
else:
    print("Not enough trajectory columns for scan.")

survivors.to_csv("kalshi_strong5m_survivor_paths.csv", index=False)

print("\nSaved: kalshi_strong5m_survivor_paths.csv")
print("Saved: kalshi_strong5m_late_failure_scan.csv")
print("\nIMPORTANT: diagnostic only. No threshold installed or changed.")
print("=== LATE-REVERSAL CHECK COMPLETE ===")
