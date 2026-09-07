from pathlib import Path
import csv
import pandas as pd
import numpy as np

TARGET = "KXBTC15M-26AUG251630-30"

LIVE = Path("kalshi_live_fair_value_shadow_log.csv")
FWD = Path("kalshi_layer_a_forward_only_results.csv")

print("=== KALSHI TRAJECTORY TIMESTAMP AUDIT ===")
print("Target:", TARGET)
print("Purpose: reconcile forward scorer vs full-history 30s validator timing.")
print("Rules changed: NO")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

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

# ------------------------------------------------------------
# Forward record
# ------------------------------------------------------------
if not FWD.exists():
    raise SystemExit(f"ERROR: {FWD.name} not found.")

fwd = pd.read_csv(FWD)
fticker = pick(fwd.columns, ["ticker","contract_ticker","market_ticker"])
fcall = pick(fwd.columns, ["call_time","timestamp_utc","timestamp"])
fside = pick(fwd.columns, ["call_side","preferred_side","side"])
finitial_dist = pick(fwd.columns, ["initial_distance","distance_target","distance"])
fdrop4 = pick(fwd.columns, ["drop_4m","4m_drop"])
fdrop6 = pick(fwd.columns, ["drop_6m","6m_drop"])
fstate = pick(fwd.columns, ["state","layer_a_state"])

z = fwd[fwd[fticker].astype(str) == TARGET].copy()
if z.empty:
    raise SystemExit("ERROR: target missing from forward results.")

fr = z.iloc[0]
call_time = pd.to_datetime(fr[fcall], utc=True, errors="coerce")
side = str(fr[fside]).upper().strip()
initial_dist_raw = float(fr[finitial_dist])

print("=== FORWARD RECORD ===")
print("call_time:", call_time)
print("side:", side)
print("initial_distance:", initial_dist_raw)
print("forward drop_4m:", fr[fdrop4] if fdrop4 else "N/A")
print("forward drop_6m:", fr[fdrop6] if fdrop6 else "N/A")
print("forward state:", fr[fstate] if fstate else "N/A")
print()

# ------------------------------------------------------------
# Robust live parser
# ------------------------------------------------------------
if not LIVE.exists():
    raise SystemExit(f"ERROR: {LIVE.name} not found.")

def looks_like_header(row):
    low = [str(x).strip().lower() for x in row]
    return sum(any(k in x for x in low) for k in ["ticker","timestamp","distance","preferred","fair"]) >= 2

records = []
header = None
with LIVE.open("r", newline="", encoding="utf-8-sig", errors="replace") as fh:
    for line_no, row in enumerate(csv.reader(fh), 1):
        if not row or all(not str(x).strip() for x in row):
            continue
        if looks_like_header(row):
            header = [str(x).strip() for x in row]
            continue
        if header is None:
            continue
        if len(row) < len(header):
            row += [""] * (len(header)-len(row))
        rec = dict(zip(header, row[:len(header)]))
        rec["_source_line"] = line_no
        records.append(rec)

live = pd.DataFrame(records)

ticker_col = pick(live.columns, ["ticker","contract_ticker","market_ticker"])
time_col = pick(live.columns, ["timestamp_utc","timestamp","time_utc","snapshot_time"])
remaining_col = pick(live.columns, ["remaining_min","minutes_left","time_left_min","time_remaining_min"])
distance_col = pick(live.columns, ["distance_target","distance_from_target","distance_to_target","target_distance","distance"])
side_col = pick(live.columns, ["preferred_side","model_side","side"])
fair_up_col = pick(live.columns, ["fair_up","fair_up_probability","fair_up_prob"])
fair_down_col = pick(live.columns, ["fair_down","fair_down_probability","fair_down_prob"])
signal_col = pick(live.columns, ["signal_status","quality_tier","status"])

for c in [remaining_col, distance_col, fair_up_col, fair_down_col]:
    if c:
        live[c] = pd.to_numeric(live[c], errors="coerce")

live[time_col] = pd.to_datetime(live[time_col], utc=True, errors="coerce")
live[ticker_col] = live[ticker_col].astype(str)

q = live[live[ticker_col] == TARGET].copy().sort_values(time_col)
if q.empty:
    raise SystemExit("ERROR: no live snapshots for target.")

q["sec_from_call"] = (q[time_col] - call_time).dt.total_seconds()
q["orig_side_signed_distance"] = q[distance_col] if side == "UP" else -q[distance_col]
initial_signed = initial_dist_raw if side == "UP" else -initial_dist_raw
q["deterioration_from_forward_initial"] = np.maximum(
    0.0, initial_signed - q["orig_side_signed_distance"]
)

if side == "UP" and fair_up_col:
    q["orig_side_fair"] = q[fair_up_col]
elif side == "DOWN" and fair_down_col:
    q["orig_side_fair"] = q[fair_down_col]
else:
    q["orig_side_fair"] = np.nan

print("=== ALL SNAPSHOTS FROM 1 MIN BEFORE CALL THROUGH 7 MIN AFTER ===")
window = q[(q["sec_from_call"] >= -60) & (q["sec_from_call"] <= 420)].copy()

show_cols = [
    "_source_line", time_col, "sec_from_call", remaining_col,
    side_col, distance_col, "orig_side_signed_distance",
    "deterioration_from_forward_initial", "orig_side_fair"
]
if signal_col:
    show_cols.append(signal_col)

print(window[show_cols].to_string(index=False))
print()

# ------------------------------------------------------------
# Explicit nearest-point calculations
# ------------------------------------------------------------
def nearest(target_sec, tolerance=None):
    qq = q[q["sec_from_call"] >= 0].copy()
    idx = (qq["sec_from_call"] - target_sec).abs().idxmin()
    r = qq.loc[idx]
    delta = abs(float(r["sec_from_call"]) - target_sec)
    if tolerance is not None and delta > tolerance:
        return None, delta
    return r, delta

print("=== NEAREST-SNAPSHOT METHOD ===")
for sec, label in [(30,"30s"), (240,"4m"), (360,"6m")]:
    r, delta = nearest(sec)
    print(
        label,
        "| target_sec=", sec,
        "| actual_sec=", f"{float(r['sec_from_call']):.3f}",
        "| timing_error=", f"{delta:.3f}s",
        "| timestamp=", r[time_col],
        "| remaining_min=", r[remaining_col],
        "| raw_distance=", r[distance_col],
        "| signed_distance=", r["orig_side_signed_distance"],
        "| deterioration=", r["deterioration_from_forward_initial"],
        "| fair=", r["orig_side_fair"],
    )
print()

# ------------------------------------------------------------
# Alternative: last snapshot at-or-before horizon
# ------------------------------------------------------------
print("=== AT-OR-BEFORE HORIZON METHOD ===")
for sec, label in [(30,"30s"), (240,"4m"), (360,"6m")]:
    qq = q[(q["sec_from_call"] >= 0) & (q["sec_from_call"] <= sec)].copy()
    if qq.empty:
        print(label, "| no snapshot")
        continue
    r = qq.iloc[-1]
    print(
        label,
        "| actual_sec=", f"{float(r['sec_from_call']):.3f}",
        "| timestamp=", r[time_col],
        "| remaining_min=", r[remaining_col],
        "| deterioration=", r["deterioration_from_forward_initial"],
        "| fair=", r["orig_side_fair"],
    )
print()

# ------------------------------------------------------------
# Alternative: first snapshot at-or-after horizon
# ------------------------------------------------------------
print("=== AT-OR-AFTER HORIZON METHOD ===")
for sec, label in [(30,"30s"), (240,"4m"), (360,"6m")]:
    qq = q[q["sec_from_call"] >= sec].copy()
    if qq.empty:
        print(label, "| no snapshot")
        continue
    r = qq.iloc[0]
    print(
        label,
        "| actual_sec=", f"{float(r['sec_from_call']):.3f}",
        "| timestamp=", r[time_col],
        "| remaining_min=", r[remaining_col],
        "| deterioration=", r["deterioration_from_forward_initial"],
        "| fair=", r["orig_side_fair"],
    )
print()

# ------------------------------------------------------------
# Horizon max-deterioration method
# ------------------------------------------------------------
print("=== MAX DETERIORATION WITHIN HORIZON ===")
for sec, label in [(30,"30s"), (240,"4m"), (360,"6m")]:
    qq = q[(q["sec_from_call"] >= 0) & (q["sec_from_call"] <= sec)].copy()
    if qq.empty:
        print(label, "| no snapshot")
        continue
    idx = qq["deterioration_from_forward_initial"].idxmax()
    r = qq.loc[idx]
    print(
        label,
        "| max_deterioration=", r["deterioration_from_forward_initial"],
        "| occurred_sec=", f"{float(r['sec_from_call']):.3f}",
        "| timestamp=", r[time_col],
        "| remaining_min=", r[remaining_col],
        "| signed_distance=", r["orig_side_signed_distance"],
    )
print()

print("=== INTERPRETATION GUIDE ===")
print("Compare the forward scorer's stored drop_4m/drop_6m above to:")
print("1) nearest snapshot")
print("2) at-or-before horizon")
print("3) at-or-after horizon")
print("4) max deterioration within horizon")
print("Whichever reproduces 58.29 / 74.13 reveals the forward scorer's actual timing semantics.")
print()
print("=== AUDIT COMPLETE ===")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
