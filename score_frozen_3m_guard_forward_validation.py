import pandas as pd
from pathlib import Path

MARKER_FILE = "kalshi_frozen_3m_guard_start_utc.txt"
LAYER_FILE = "kalshi_official_truth_layer_a_rescore_details.csv"
PRECURSOR_FILE = "kalshi_official_truth_late_reversal_precursor_details.csv"
THRESHOLD = 75.0

print("=== FROZEN 3M GUARD FORWARD VALIDATION ===")
print("Official Kalshi settlement truth only.")
print("Cohort: post-freeze Layer A CLEAN calls only.")
print(f"Frozen rule: WARN if 3m signed distance <= ${THRESHOLD:.0f}")
print("No thresholds changed. No bot.py changes. No orders.\n")

marker = pd.to_datetime(
    Path(MARKER_FILE).read_text(encoding="utf-8").strip(),
    utc=True
)

layer = pd.read_csv(LAYER_FILE, low_memory=False)
prec = pd.read_csv(PRECURSOR_FILE, low_memory=False)

layer["timestamp_utc"] = pd.to_datetime(layer["timestamp_utc"], errors="coerce", utc=True)

clean = layer[
    (layer["timestamp_utc"] >= marker)
    & layer["layer_a_state"].astype(str).str.upper().str.contains("CLEAN", na=False)
].copy()

if clean["correct"].dtype == bool:
    clean["correct_bool"] = clean["correct"]
else:
    clean["correct_bool"] = (
        clean["correct"].astype(str).str.strip().str.lower()
        .map({"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False})
    )

prec_small = prec[["ticker", "dist_3p0"]].copy()
prec_small["dist_3p0"] = pd.to_numeric(prec_small["dist_3p0"], errors="coerce")

x = clean.merge(prec_small, on="ticker", how="left")
x["warn"] = x["dist_3p0"].notna() & (x["dist_3p0"] <= THRESHOLD)

usable = x[x["dist_3p0"].notna() & x["correct_bool"].notna()].copy()
kept = usable[~usable["warn"]].copy()

total = len(usable)
wins = int(usable["correct_bool"].sum())
misses = int((~usable["correct_bool"]).sum())
warned = int(usable["warn"].sum())
misses_caught = int((usable["warn"] & ~usable["correct_bool"]).sum())
good_warned = int((usable["warn"] & usable["correct_bool"]).sum())
kept_n = len(kept)
kept_wins = int(kept["correct_bool"].sum())

raw_acc = (100.0 * wins / total) if total else None
capture = (100.0 * misses_caught / misses) if misses else None
kept_acc = (100.0 * kept_wins / kept_n) if kept_n else None

print(f"Frozen start UTC: {marker.isoformat()}")
print(f"Post-freeze CLEAN calls with usable 3m snapshot: {total}")
print(f"Raw winners: {wins}")
print(f"Raw misses: {misses}")
print(f"Raw CLEAN accuracy: {raw_acc:.1f}%" if raw_acc is not None else "Raw CLEAN accuracy: N/A")
print()
print(f"WARNED by frozen <=$75 rule: {warned}")
print(f"Misses caught: {misses_caught}/{misses}" if misses else "Misses caught: 0/0")
print(f"Miss capture: {capture:.1f}%" if capture is not None else "Miss capture: N/A (no misses)")
print(f"Good calls warned: {good_warned}")
print()
print(f"KEPT / unflagged calls: {kept_n}")
print(f"KEPT winners: {kept_wins}")
print(f"KEPT accuracy: {kept_acc:.1f}%" if kept_acc is not None else "KEPT accuracy: N/A")

print("\n=== POST-FREEZE DETAILS ===")
cols = ["timestamp_utc", "ticker", "call_side", "official_side", "correct_bool", "dist_3p0", "warn"]
cols = [c for c in cols if c in usable.columns]
if total:
    print(usable[cols].sort_values("timestamp_utc").to_string(index=False))
else:
    print("No post-freeze CLEAN calls with a usable 3-minute snapshot were found.")
