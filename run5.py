from pathlib import Path
import subprocess
import sys
import pandas as pd

MARKER_FILE = Path("kalshi_frozen_5m_guard_start_utc.txt")
LAYER_FILE = Path("kalshi_official_truth_layer_a_rescore_details.csv")
PRECURSOR_FILE = Path("kalshi_official_truth_late_reversal_precursor_details.csv")
THRESHOLD = 75.0

print("=== ONE-TAP 5M FROZEN GUARD TEST ===")
print("Refreshing official results + forward scoring files first...\n")

steps = [
    "kalshi_official_settlement_validator.py",
    "kalshi_official_truth_layer_a_rescorer.py",
    "kalshi_official_truth_late_reversal_precursor_audit.py",
]

for script in steps:
    p = Path(script)
    if not p.exists():
        raise SystemExit(f"ERROR: missing {script}")
    print(f"Running {script}...")
    subprocess.run([sys.executable, script], check=False)
    print()

for req in [MARKER_FILE, LAYER_FILE, PRECURSOR_FILE]:
    if not req.exists():
        raise SystemExit(f"ERROR: missing {req.name}")

marker = pd.to_datetime(
    MARKER_FILE.read_text(encoding="utf-8").strip(),
    utc=True,
    errors="coerce",
)
if pd.isna(marker):
    raise SystemExit("ERROR: invalid 5m frozen-test marker.")

layer = pd.read_csv(LAYER_FILE, low_memory=False)
prec = pd.read_csv(PRECURSOR_FILE, low_memory=False)

if "timestamp_utc" not in layer.columns:
    raise SystemExit("ERROR: timestamp_utc missing from Layer A rescore file.")
if "layer_a_state" not in layer.columns:
    raise SystemExit("ERROR: layer_a_state missing from Layer A rescore file.")
if "correct" not in layer.columns:
    raise SystemExit("ERROR: correct missing from Layer A rescore file.")
if "ticker" not in layer.columns or "ticker" not in prec.columns:
    raise SystemExit("ERROR: ticker missing from required files.")
if "dist_5p0" not in prec.columns:
    raise SystemExit("ERROR: dist_5p0 missing from precursor details.")

layer["timestamp_utc"] = pd.to_datetime(
    layer["timestamp_utc"], errors="coerce", utc=True
)

clean = layer[
    (layer["timestamp_utc"] >= marker)
    & layer["layer_a_state"].astype(str).str.upper().str.contains("CLEAN", na=False)
].copy()

if clean["correct"].dtype == bool:
    clean["correct_bool"] = clean["correct"]
else:
    clean["correct_bool"] = (
        clean["correct"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map({
            "true": True, "1": True, "yes": True,
            "false": False, "0": False, "no": False,
        })
    )

prec_small = prec[["ticker", "dist_5p0"]].copy()
prec_small["dist_5p0"] = pd.to_numeric(
    prec_small["dist_5p0"], errors="coerce"
)

x = clean.merge(prec_small, on="ticker", how="left")
x["warn"] = x["dist_5p0"].notna() & (x["dist_5p0"] <= THRESHOLD)

usable = x[
    x["dist_5p0"].notna() & x["correct_bool"].notna()
].copy()
kept = usable[~usable["warn"]].copy()

total = len(usable)
wins = int(usable["correct_bool"].sum()) if total else 0
misses = int((~usable["correct_bool"]).sum()) if total else 0
warned = int(usable["warn"].sum()) if total else 0
misses_caught = int((usable["warn"] & ~usable["correct_bool"]).sum()) if total else 0
good_warned = int((usable["warn"] & usable["correct_bool"]).sum()) if total else 0
kept_n = len(kept)
kept_wins = int(kept["correct_bool"].sum()) if kept_n else 0

raw_acc = (100.0 * wins / total) if total else None
capture = (100.0 * misses_caught / misses) if misses else None
kept_acc = (100.0 * kept_wins / kept_n) if kept_n else None

print("\n=== FROZEN 5M GUARD FORWARD VALIDATION ===")
print("Official Kalshi settlement truth only.")
print("Cohort: post-freeze Layer A CLEAN calls only.")
print(f"Frozen rule: WARN if 5m signed distance <= ${THRESHOLD:.0f}")
print(f"Frozen start UTC: {marker.isoformat()}")
print()
print(f"Post-freeze CLEAN calls with usable 5m snapshot: {total}")
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

cols = [
    "timestamp_utc", "ticker", "call_side", "official_side",
    "correct_bool", "dist_5p0", "warn"
]
cols = [c for c in cols if c in usable.columns]

print("\n=== POST-FREEZE DETAILS ===")
if total:
    print(usable[cols].sort_values("timestamp_utc").to_string(index=False))
    usable.to_csv("kalshi_frozen_5m_guard_forward_results.csv", index=False)
    print("\nSaved: kalshi_frozen_5m_guard_forward_results.csv")
else:
    print("No post-freeze CLEAN calls with a usable 5-minute snapshot were found.")

print("\nNo bot.py changes. No scalp changes. No orders.")
print("=== 5M TEST COMPLETE ===")
