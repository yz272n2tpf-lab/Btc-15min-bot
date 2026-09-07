from pathlib import Path
import subprocess
import sys
import pandas as pd

MARKER = Path("frozen_forward_validation_start_utc.txt")
DETAILS = Path("kalshi_3min_distance_drop_full_history_details.csv")

print("=== FROZEN FORWARD-ONLY RESULTS ===")
print("Rules remain frozen:")
print("SAFE      < $100 deterioration")
print("WEAKENING = $100 to $149.99")
print("DANGER    >= $150")
print()

if not MARKER.exists():
    raise SystemExit("ERROR: frozen_forward_validation_start_utc.txt not found.")

start = pd.to_datetime(MARKER.read_text().strip(), utc=True, errors="coerce")
if pd.isna(start):
    raise SystemExit("ERROR: could not parse frozen forward-test start timestamp.")

print("Frozen start UTC:", start)
print()

official_validator = Path("kalshi_official_settlement_validator.py")
if official_validator.exists():
    print("Refreshing official Kalshi settlements...")
    subprocess.run([sys.executable, official_validator.name], check=False)
    print()

full_validator = Path("kalshi_3min_distance_drop_full_history_validator.py")
if full_validator.exists():
    print("Refreshing 3-minute deterioration details...")
    subprocess.run([sys.executable, full_validator.name], check=False)
    print()

if not DETAILS.exists():
    raise SystemExit("ERROR: kalshi_3min_distance_drop_full_history_details.csv not found.")

df = pd.read_csv(DETAILS)
df["call_time"] = pd.to_datetime(df["call_time"], utc=True, errors="coerce")

if df["correct"].dtype != bool:
    df["correct"] = df["correct"].astype(str).str.lower().map({"true": True, "false": False})

df["three_min_max_distance_drop"] = pd.to_numeric(
    df["three_min_max_distance_drop"], errors="coerce"
)

fwd = df[
    (df["call_time"] >= start)
    & df["correct"].notna()
    & df["three_min_max_distance_drop"].notna()
].copy().sort_values("call_time")

def tier(x):
    if x < 100:
        return "SAFE"
    if x < 150:
        return "WEAKENING"
    return "DANGER"

fwd["tier"] = fwd["three_min_max_distance_drop"].apply(tier)

print("=== FORWARD SAMPLE ===")
print("Officially settled qualifying calls:", len(fwd))

if fwd.empty:
    print("No officially settled qualifying forward calls are available yet.")
    print("That can happen if the run was short or recent contracts have not settled/refreshed.")
    raise SystemExit(0)

correct = int(fwd["correct"].sum())
wrong = len(fwd) - correct
print("Baseline correct:", correct)
print("Baseline wrong:", wrong)
print("Baseline accuracy:", f"{fwd['correct'].mean():.1%}")
print()

for name in ["SAFE", "WEAKENING", "DANGER"]:
    q = fwd[fwd["tier"] == name]
    if q.empty:
        print(name, "| n=0")
        continue
    c = int(q["correct"].sum())
    w = len(q) - c
    print(name, "| n=", len(q), "| correct=", c, "| wrong=", w, "| accuracy=", f"{q['correct'].mean():.1%}")

print()

misses = fwd[~fwd["correct"]]
danger = fwd[fwd["tier"] == "DANGER"]
danger_misses = danger[~danger["correct"]]
danger_good = danger[danger["correct"]]

print("=== DANGER CHECK ===")
print("Total baseline misses:", len(misses))
print("Danger flags:", len(danger))
print("Misses caught by DANGER:", len(danger_misses))
print("Miss capture:", f"{(len(danger_misses)/len(misses)):.1%}" if len(misses) else "N/A")
print("Winning calls falsely flagged DANGER:", len(danger_good))
print()

clean = fwd[fwd["tier"] != "DANGER"]
if len(clean):
    print("Non-DANGER accuracy:", f"{clean['correct'].mean():.1%}", f"({int(clean['correct'].sum())}/{len(clean)})")
print()

print("=== FORWARD CALL DETAILS ===")
for _, r in fwd.iterrows():
    fair_txt = ""
    if "initial_fair" in r and pd.notna(r["initial_fair"]):
        fair_txt = f"{float(r['initial_fair']):.1%}"
    print(
        r["ticker"],
        "|", r["tier"],
        "| correct=", bool(r["correct"]),
        "| call=", r.get("call_side", ""),
        "| winner=", r.get("official_side", ""),
        "| fair=", fair_txt,
        "| deterioration=", f"${float(r['three_min_max_distance_drop']):.2f}",
    )

fwd.to_csv("kalshi_frozen_forward_only_results.csv", index=False)

print()
print("Saved: kalshi_frozen_forward_only_results.csv")
print("No thresholds changed.")
print("No bot.py changes.")
print("No orders placed.")
