from pathlib import Path
import csv
import subprocess
import sys
import pandas as pd
import numpy as np

MARKER = Path("layer_a_forward_validation_start_utc.txt")
OFFICIAL = Path("kalshi_official_settlement_check.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")
BASE = Path("kalshi_3min_distance_drop_full_history_details.csv")

print("=== LAYER A FORWARD-ONLY SCORER ===")
print("FROZEN RULES:")
print("EARLY WARNING = 4-minute deterioration >= $100")
print("LATE DANGER   = 6-minute deterioration >= $85")
print()
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

if not MARKER.exists():
    raise SystemExit("ERROR: layer_a_forward_validation_start_utc.txt not found.")

start = pd.to_datetime(MARKER.read_text().strip(), utc=True, errors="coerce")
if pd.isna(start):
    raise SystemExit("ERROR: invalid Layer A start marker.")

print("Layer A frozen start UTC:", start)
print()

# Refresh official settlements.
validator = Path("kalshi_official_settlement_validator.py")
if validator.exists():
    print("Refreshing official settlements...")
    subprocess.run([sys.executable, validator.name], check=False)
    print()

# Refresh baseline first >=80 supported call details.
full3 = Path("kalshi_3min_distance_drop_full_history_validator.py")
if full3.exists():
    print("Refreshing baseline qualifying-call details...")
    subprocess.run([sys.executable, full3.name], check=False)
    print()

if not BASE.exists():
    raise SystemExit("ERROR: baseline details file not found.")
if not LIVE.exists():
    raise SystemExit("ERROR: live fair-value log not found.")

b = pd.read_csv(BASE)

if b["correct"].dtype != bool:
    b["correct"] = (
        b["correct"].astype(str).str.lower()
        .map({"true": True, "false": False})
    )

b["call_time"] = pd.to_datetime(b["call_time"], utc=True, errors="coerce")

for c in [
    "initial_fair",
    "initial_remaining_min",
    "initial_distance",
    "initial_signed_distance",
]:
    if c in b.columns:
        b[c] = pd.to_numeric(b[c], errors="coerce")

fwd = b[
    (b["call_time"] >= start)
    & b["correct"].notna()
].copy().sort_values("call_time")

# Robust mixed-log reader.
def looks_like_header(row):
    low = [str(x).strip().lower() for x in row]
    hits = 0
    for key in ["ticker", "timestamp", "distance", "preferred", "fair"]:
        if any(key in x for x in low):
            hits += 1
    return hits >= 2

records = []
current_header = None

with LIVE.open("r", newline="", encoding="utf-8-sig", errors="replace") as fh:
    reader = csv.reader(fh)
    for line_no, row in enumerate(reader, start=1):
        if not row or all(not str(x).strip() for x in row):
            continue

        if looks_like_header(row):
            current_header = [str(x).strip() for x in row]
            continue

        if current_header is None:
            continue

        if len(row) < len(current_header):
            row = row + [""] * (len(current_header) - len(row))

        rec = dict(zip(current_header, row[:len(current_header)]))
        rec["_source_line"] = line_no
        records.append(rec)

live = pd.DataFrame(records)

def pick(cols, candidates):
    lower = {str(c).lower(): c for c in cols}
    for name in candidates:
        if name.lower() in lower:
            return lower[name.lower()]
    for c in cols:
        lc = str(c).lower()
        for name in candidates:
            if name.lower() in lc:
                return c
    return None

ticker_col = pick(live.columns, ["ticker","contract_ticker","market_ticker"])
time_col = pick(live.columns, ["timestamp_utc","timestamp","time_utc","snapshot_time"])
distance_col = pick(live.columns, [
    "distance_target",
    "distance_from_target",
    "distance_to_target",
    "target_distance",
    "distance",
])

if ticker_col is None or time_col is None or distance_col is None:
    raise SystemExit("ERROR: could not identify live-log ticker/time/distance columns.")

live[time_col] = pd.to_datetime(live[time_col], utc=True, errors="coerce")
live[distance_col] = pd.to_numeric(live[distance_col], errors="coerce")
live = live[
    live[time_col].notna()
    & live[distance_col].notna()
    & live[ticker_col].notna()
].copy()

rows = []

for _, r in fwd.iterrows():
    ticker = str(r["ticker"])
    call_time = r["call_time"]
    call_side = str(r.get("call_side","")).upper()

    q = live[
        (live[ticker_col].astype(str) == ticker)
        & (live[time_col] >= call_time)
    ].copy()

    if q.empty:
        continue

    q = q.sort_values(time_col)
    q["mins_after_call"] = (
        (q[time_col] - call_time).dt.total_seconds() / 60.0
    )
    q = q[
        (q["mins_after_call"] >= 0)
        & (q["mins_after_call"] <= 12.5)
    ].copy()

    if q.empty:
        continue

    if call_side == "UP":
        q["signed_distance"] = q[distance_col]
    elif call_side == "DOWN":
        q["signed_distance"] = -q[distance_col]
    else:
        continue

    initial_signed = r.get("initial_signed_distance", np.nan)
    if pd.isna(initial_signed):
        init_dist = r.get("initial_distance", np.nan)
        if pd.notna(init_dist):
            initial_signed = float(init_dist) if call_side == "UP" else -float(init_dist)

    if pd.isna(initial_signed):
        continue

    initial_signed = float(initial_signed)

    def max_drop(minutes):
        h = q[q["mins_after_call"] <= minutes]
        if h.empty:
            return np.nan
        return max(
            0.0,
            initial_signed - float(h["signed_distance"].min())
        )

    drop4 = max_drop(4)
    drop6 = max_drop(6)

    if pd.isna(drop4) or pd.isna(drop6):
        continue

    early = drop4 >= 100
    late = drop6 >= 85

    if early and late:
        state = "CONFIRMED_DANGER"
    elif early:
        state = "EARLY_WARNING_ONLY"
    elif late:
        state = "LATE_DANGER_ONLY"
    else:
        state = "CLEAN"

    rows.append({
        "ticker": ticker,
        "call_time": call_time,
        "correct": bool(r["correct"]),
        "call_side": call_side,
        "official_side": r.get("official_side",""),
        "initial_fair": r.get("initial_fair", np.nan),
        "initial_remaining_min": r.get("initial_remaining_min", np.nan),
        "initial_distance": r.get("initial_distance", np.nan),
        "drop_4m": drop4,
        "drop_6m": drop6,
        "state": state,
    })

x = pd.DataFrame(rows).sort_values("call_time").reset_index(drop=True)

print("=== FORWARD SAMPLE ===")
print("Officially settled qualifying calls with usable Layer A trajectory:", len(x))

if x.empty:
    print("No usable forward calls yet.")
    raise SystemExit(0)

print("Baseline correct:", int(x["correct"].sum()))
print("Baseline wrong:", int((~x["correct"]).sum()))
print("Baseline accuracy:", f"{x['correct'].mean():.1%}")
print()

for state in [
    "CLEAN",
    "EARLY_WARNING_ONLY",
    "LATE_DANGER_ONLY",
    "CONFIRMED_DANGER",
]:
    q = x[x["state"] == state]
    if q.empty:
        print(state, "| n=0")
        continue

    print(
        state,
        "| n=", len(q),
        "| correct=", int(q["correct"].sum()),
        "| wrong=", int((~q["correct"]).sum()),
        "| accuracy=", f"{q['correct'].mean():.1%}",
    )

print()

warned = x[x["state"] != "CLEAN"]
clean = x[x["state"] == "CLEAN"]
misses = x[~x["correct"]]

caught = int((~warned["correct"]).sum()) if len(warned) else 0
good_flagged = int(warned["correct"].sum()) if len(warned) else 0

print("=== LAYER A CHECK ===")
print("Total misses:", len(misses))
print("Warned calls:", len(warned))
print("Misses caught:", caught)
print(
    "Miss capture:",
    f"{caught/len(misses):.1%}" if len(misses) else "N/A"
)
print("Good calls warned:", good_flagged)
print(
    "Clean accuracy:",
    f"{clean['correct'].mean():.1%} ({int(clean['correct'].sum())}/{len(clean)})"
    if len(clean) else "N/A"
)
print()

print("=== FORWARD CALL DETAILS ===")
for _, r in x.iterrows():
    print(
        r["ticker"],
        "| state=", r["state"],
        "| correct=", bool(r["correct"]),
        "| call=", r["call_side"],
        "| winner=", r["official_side"],
        "| fair=", (
            f"{float(r['initial_fair']):.1%}"
            if pd.notna(r["initial_fair"]) else "NA"
        ),
        "| 4m_drop=", f"${r['drop_4m']:.2f}",
        "| 6m_drop=", f"${r['drop_6m']:.2f}",
    )

x.to_csv("kalshi_layer_a_forward_only_results.csv", index=False)

print()
print("Saved: kalshi_layer_a_forward_only_results.csv")
print("Frozen Layer A rules unchanged.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print("=== LAYER A FORWARD SCORING COMPLETE ===")
