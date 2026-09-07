from pathlib import Path
import pandas as pd

MARKER_5M = Path("kalshi_frozen_5m_guard_start_utc.txt")
LAYER = Path("kalshi_official_truth_layer_a_rescore_details.csv")
PREC = Path("kalshi_official_truth_late_reversal_precursor_details.csv")
THRESHOLD = 75.0

print("=== COMBINED FROZEN 5M + 3M GUARD FORWARD SCORE ===")
print("Common untouched sample starts at the frozen 5m marker.")
print("Rule A: WARN if 5m signed distance <= $75")
print("Rule B: WARN if 3m signed distance <= $75")
print("Combined: WARN if EITHER rule fires.")
print("Research only. No bot.py changes. No scalp changes. No orders.\n")

for p in [MARKER_5M, LAYER, PREC]:
    if not p.exists():
        raise SystemExit(f"ERROR: missing {p.name}")

marker = pd.to_datetime(MARKER_5M.read_text().strip(), utc=True, errors="coerce")
if pd.isna(marker):
    raise SystemExit("ERROR: invalid 5m frozen marker.")

a = pd.read_csv(LAYER, low_memory=False)
b = pd.read_csv(PREC, low_memory=False)

needed_a = ["timestamp_utc", "ticker", "layer_a_state", "correct"]
needed_b = ["ticker", "dist_5p0", "dist_3p0"]
for c in needed_a:
    if c not in a.columns:
        raise SystemExit(f"ERROR: missing {c} in {LAYER.name}")
for c in needed_b:
    if c not in b.columns:
        raise SystemExit(f"ERROR: missing {c} in {PREC.name}")

a["timestamp_utc"] = pd.to_datetime(a["timestamp_utc"], errors="coerce", utc=True)

if a["correct"].dtype == bool:
    a["correct_bool"] = a["correct"]
else:
    a["correct_bool"] = (
        a["correct"].astype(str).str.strip().str.lower()
        .map({"true":True,"1":True,"yes":True,"false":False,"0":False,"no":False})
    )

clean = a[
    (a["timestamp_utc"] >= marker)
    & a["layer_a_state"].astype(str).str.upper().str.contains("CLEAN", na=False)
    & a["correct_bool"].notna()
].copy()

p = b[["ticker", "dist_5p0", "dist_3p0"]].drop_duplicates("ticker", keep="last").copy()
p["dist_5p0"] = pd.to_numeric(p["dist_5p0"], errors="coerce")
p["dist_3p0"] = pd.to_numeric(p["dist_3p0"], errors="coerce")

x = clean.merge(p, on="ticker", how="left")
x = x[x["dist_5p0"].notna() & x["dist_3p0"].notna()].copy()

x["warn_5m"] = x["dist_5p0"] <= THRESHOLD
x["warn_3m"] = x["dist_3p0"] <= THRESHOLD
x["warn_combined"] = x["warn_5m"] | x["warn_3m"]

def summary(label, warn_col):
    total = len(x)
    misses = ~x["correct_bool"].astype(bool)
    wins = x["correct_bool"].astype(bool)
    warn = x[warn_col].astype(bool)
    kept = x[~warn].copy()

    caught = int((warn & misses).sum())
    total_misses = int(misses.sum())
    good = int((warn & wins).sum())
    kept_n = len(kept)
    kept_wins = int(kept["correct_bool"].sum())
    kept_acc = 100.0 * kept["correct_bool"].mean() if kept_n else None

    print(f"=== {label} ===")
    print(f"Usable calls: {total}")
    print(f"Warned: {int(warn.sum())}")
    print(f"Misses caught: {caught}/{total_misses}" if total_misses else "Misses caught: 0/0")
    print(f"Good winners warned: {good}")
    print(f"Kept: {kept_n}")
    print(f"Kept winners: {kept_wins}")
    print(f"Kept accuracy: {kept_acc:.1f}%" if kept_acc is not None else "Kept accuracy: N/A")
    print()

print(f"Common frozen start UTC: {marker.isoformat()}\n")
summary("5M GUARD ONLY", "warn_5m")
summary("3M GUARD ONLY", "warn_3m")
summary("COMBINED 5M + 3M", "warn_combined")

cols = [c for c in [
    "timestamp_utc","ticker","call_side","official_side","correct_bool",
    "dist_5p0","warn_5m","dist_3p0","warn_3m","warn_combined"
] if c in x.columns]

print("=== COMMON FORWARD DETAILS ===")
if len(x):
    print(x[cols].sort_values("timestamp_utc").to_string(index=False))
    x.to_csv("kalshi_combined_frozen_5m_3m_forward_results.csv", index=False)
    print("\nSaved: kalshi_combined_frozen_5m_3m_forward_results.csv")
else:
    print("No usable common forward calls.")

print("\nNo thresholds changed. No rule installed.")
print("=== COMBINED FORWARD SCORE COMPLETE ===")
