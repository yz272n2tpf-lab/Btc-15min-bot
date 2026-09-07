from pathlib import Path
import csv
import pandas as pd
import numpy as np

LIVE = Path("kalshi_live_fair_value_shadow_log.csv")
OFFICIAL = Path("kalshi_official_settlement_check.csv")

print("=== KALSHI 30-SECOND EARLY-SHOCK FULL-HISTORY VALIDATOR ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Pre-specified candidate after clean-forward miss:")
print("  SHOCK_DISTANCE = 30s deterioration >= $30")
print("  SHOCK_FAIR     = 30s original-side fair drop >= 5 percentage points")
print("  SHOCK_EITHER   = either condition")
print()
print("Layer A rules changed: NO")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

if not LIVE.exists():
    raise SystemExit("ERROR: kalshi_live_fair_value_shadow_log.csv not found.")
if not OFFICIAL.exists():
    raise SystemExit("ERROR: kalshi_official_settlement_check.csv not found.")

official = pd.read_csv(OFFICIAL)

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

oticker = pick(official.columns, ["ticker","contract_ticker","market_ticker"])
owinner = pick(official.columns, ["official_side","winner","result","market_result"])
if oticker is None or owinner is None:
    raise SystemExit(f"ERROR: official columns not found. Available: {list(official.columns)}")

official = official[[oticker, owinner]].copy()
official.columns = ["ticker","winner"]
official["ticker"] = official["ticker"].astype(str)
official["winner"] = official["winner"].astype(str).str.upper().str.strip()
official = official[official["winner"].isin(["UP","DOWN"])].drop_duplicates("ticker")

def looks_like_header(row):
    low = [str(x).strip().lower() for x in row]
    return sum(any(k in x for x in low) for k in ["ticker","timestamp","distance","preferred","fair"]) >= 2

records = []
current_header = None
with LIVE.open("r", newline="", encoding="utf-8-sig", errors="replace") as fh:
    for line_no, row in enumerate(csv.reader(fh), start=1):
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

ticker_col = pick(live.columns, ["ticker","contract_ticker","market_ticker"])
time_col = pick(live.columns, ["timestamp_utc","timestamp","time_utc","snapshot_time"])
remaining_col = pick(live.columns, ["remaining_min","minutes_left","time_left_min","time_remaining_min"])
distance_col = pick(live.columns, ["distance_target","distance_from_target","distance_to_target","target_distance","distance"])
preferred_side_col = pick(live.columns, ["preferred_side","side","model_side"])
preferred_fair_col = pick(live.columns, ["preferred_fair","fair_value","preferred_side_fair"])
fair_up_col = pick(live.columns, ["fair_up","fair_up_probability","fair_up_prob"])
fair_down_col = pick(live.columns, ["fair_down","fair_down_probability","fair_down_prob"])
signal_col = pick(live.columns, ["signal_status","quality_tier","status"])

required = [ticker_col,time_col,remaining_col,distance_col,preferred_side_col]
if any(c is None for c in required):
    print("Available live columns:", list(live.columns))
    raise SystemExit("ERROR: required live columns could not be identified.")

live[time_col] = pd.to_datetime(live[time_col], utc=True, errors="coerce")
for c in [remaining_col,distance_col,preferred_fair_col,fair_up_col,fair_down_col]:
    if c is not None:
        live[c] = pd.to_numeric(live[c], errors="coerce")

live = live[
    live[time_col].notna()
    & live[remaining_col].notna()
    & live[distance_col].notna()
    & live[ticker_col].notna()
].copy()

live[ticker_col] = live[ticker_col].astype(str)
live[preferred_side_col] = live[preferred_side_col].astype(str).str.upper().str.strip()

def row_side_fair(row, side):
    if side == "UP" and fair_up_col is not None and pd.notna(row.get(fair_up_col, np.nan)):
        return float(row[fair_up_col])
    if side == "DOWN" and fair_down_col is not None and pd.notna(row.get(fair_down_col, np.nan)):
        return float(row[fair_down_col])
    if preferred_fair_col is not None and pd.notna(row.get(preferred_fair_col, np.nan)):
        return float(row[preferred_fair_col])
    return np.nan

def supported_mask(df):
    if signal_col is None:
        return pd.Series(True, index=df.index)
    s = df[signal_col].astype(str).str.upper()
    return s.str.contains("SUPPORTED|HIGH_QUALITY|EARLY_LOCK|LOCK", regex=True, na=False)

# First >=80% supported call in 8-12 minute zone.
calls = []
for ticker, q in live.groupby(ticker_col):
    q = q.sort_values(time_col).copy()
    q = q[(q[remaining_col] >= 8) & (q[remaining_col] <= 12)]
    if q.empty:
        continue

    q["side_fair"] = q.apply(lambda r: row_side_fair(r, r[preferred_side_col]), axis=1)
    q = q[
        q[preferred_side_col].isin(["UP","DOWN"])
        & (q["side_fair"] >= 0.80)
        & supported_mask(q)
    ].copy()

    if q.empty:
        continue

    # Direction must agree with signed target distance.
    q["signed_distance"] = np.where(
        q[preferred_side_col] == "UP",
        q[distance_col],
        -q[distance_col]
    )
    q = q[q["signed_distance"] > 0]
    if q.empty:
        continue

    calls.append(q.iloc[0])

if not calls:
    raise SystemExit("ERROR: no first >=80% supported calls identified.")

calls = pd.DataFrame(calls).reset_index(drop=True)
calls = calls.merge(official, left_on=ticker_col, right_on="ticker", how="inner")
calls["correct"] = calls[preferred_side_col] == calls["winner"]

details = []

for _, call in calls.iterrows():
    ticker = str(call[ticker_col])
    side = str(call[preferred_side_col])
    call_time = call[time_col]
    initial_signed = float(call[distance_col]) if side == "UP" else -float(call[distance_col])
    initial_fair = row_side_fair(call, side)

    q = live[
        (live[ticker_col] == ticker)
        & (live[time_col] >= call_time)
    ].copy().sort_values(time_col)

    q["sec_after"] = (q[time_col] - call_time).dt.total_seconds()
    q = q[(q["sec_after"] >= 0) & (q["sec_after"] <= 390)]
    if q.empty:
        continue

    q["signed_distance"] = np.where(
        side == "UP",
        q[distance_col],
        -q[distance_col]
    )
    q["side_fair"] = q.apply(lambda r: row_side_fair(r, side), axis=1)

    def nearest(seconds):
        idx = (q["sec_after"] - seconds).abs().idxmin()
        r = q.loc[idx]
        if abs(float(r["sec_after"]) - seconds) > 45:
            return None
        return r

    r30 = nearest(30)
    r4 = nearest(240)
    r6 = nearest(360)

    if r30 is None:
        continue

    d30 = max(0.0, initial_signed - float(r30["signed_distance"]))
    f30 = (
        max(0.0, float(initial_fair) - float(r30["side_fair"]))
        if pd.notna(initial_fair) and pd.notna(r30["side_fair"]) else np.nan
    )

    d4 = (
        max(0.0, initial_signed - float(r4["signed_distance"]))
        if r4 is not None else np.nan
    )
    d6 = (
        max(0.0, initial_signed - float(r6["signed_distance"]))
        if r6 is not None else np.nan
    )

    # Frozen Layer A:
    early_warning = pd.notna(d4) and d4 >= 100
    late_danger = pd.notna(d6) and d6 >= 85

    if early_warning and late_danger:
        layer_a_state = "CONFIRMED_DANGER"
    elif early_warning:
        layer_a_state = "EARLY_WARNING_ONLY"
    elif late_danger:
        layer_a_state = "LATE_DANGER_ONLY"
    else:
        layer_a_state = "CLEAN"

    details.append({
        "ticker": ticker,
        "call_time": call_time,
        "call_side": side,
        "winner": call["winner"],
        "correct": bool(call["correct"]),
        "initial_fair": initial_fair,
        "initial_remaining_min": call[remaining_col],
        "initial_distance": call[distance_col],
        "drop_30s": d30,
        "fair_drop_30s": f30,
        "drop_4m": d4,
        "drop_6m": d6,
        "layer_a_state": layer_a_state,
        "shock_distance": d30 >= 30,
        "shock_fair": (pd.notna(f30) and f30 >= 0.05),
        "shock_either": (d30 >= 30) or (pd.notna(f30) and f30 >= 0.05),
    })

d = pd.DataFrame(details)
print("Official qualifying calls with usable 30s path:", len(d))
print("Baseline accuracy:", f"{d['correct'].mean():.1%}")
print()

def report(name, subset):
    print(f"=== {name} ===")
    print("n:", len(subset))
    if len(subset) == 0:
        print()
        return
    print("accuracy:", f"{subset['correct'].mean():.1%}")
    print("wrong:", int((~subset["correct"]).sum()))
    print()

report("ALL", d)
report("LAYER A CLEAN", d[d["layer_a_state"] == "CLEAN"])

clean = d[d["layer_a_state"] == "CLEAN"].copy()

print("=== 30S SHOCK TEST INSIDE LAYER A CLEAN ===")
for col, label in [
    ("shock_distance", "30s distance >= $30"),
    ("shock_fair", "30s fair drop >= 5pt"),
    ("shock_either", "either 30s shock"),
]:
    flagged = clean[clean[col]]
    kept = clean[~clean[col]]
    total_misses = int((~clean["correct"]).sum())
    caught = int((~flagged["correct"]).sum())
    good_flagged = int(flagged["correct"].sum())

    print(
        label,
        "| flagged=", len(flagged),
        "| mistakes_caught=", f"{caught}/{total_misses}",
        "| capture=", f"{caught/total_misses:.1%}" if total_misses else "N/A",
        "| good_flagged=", good_flagged,
        "| false_warn=", f"{good_flagged/int(clean['correct'].sum()):.1%}" if int(clean["correct"].sum()) else "N/A",
        "| kept=", len(kept),
        "| kept_acc=", f"{kept['correct'].mean():.1%}" if len(kept) else "N/A",
    )

print()
print("=== CHRONOLOGICAL HOLDOUT: LAST 40% OF QUALIFYING CALLS ===")
d = d.sort_values("call_time").reset_index(drop=True)
cut = int(np.floor(len(d) * 0.60))
hold = d.iloc[cut:].copy()
hold_clean = hold[hold["layer_a_state"] == "CLEAN"].copy()

print("Holdout calls:", len(hold))
print("Holdout baseline:", f"{hold['correct'].mean():.1%}" if len(hold) else "N/A")
print("Holdout Layer A CLEAN:", len(hold_clean),
      "| accuracy=", f"{hold_clean['correct'].mean():.1%}" if len(hold_clean) else "N/A")

for col, label in [
    ("shock_distance", "30s distance >= $30"),
    ("shock_fair", "30s fair drop >= 5pt"),
    ("shock_either", "either 30s shock"),
]:
    flagged = hold_clean[hold_clean[col]]
    kept = hold_clean[~hold_clean[col]]
    misses = int((~hold_clean["correct"]).sum())
    caught = int((~flagged["correct"]).sum())
    good_flagged = int(flagged["correct"].sum())

    print(
        label,
        "| flagged=", len(flagged),
        "| mistakes_caught=", f"{caught}/{misses}",
        "| good_flagged=", good_flagged,
        "| kept=", len(kept),
        "| kept_acc=", f"{kept['correct'].mean():.1%}" if len(kept) else "N/A",
    )

print()
print("=== SHOCKED CLEAN CALL DETAILS ===")
show = clean[clean["shock_either"]].copy()
if len(show):
    print(show[
        ["ticker","call_side","winner","correct","initial_fair",
         "initial_remaining_min","initial_distance","drop_30s",
         "fair_drop_30s","drop_4m","drop_6m"]
    ].to_string(index=False))
else:
    print("None")

d.to_csv("kalshi_30s_early_shock_full_history_details.csv", index=False)

print()
print("=== FILE CREATED ===")
print("kalshi_30s_early_shock_full_history_details.csv")
print()
print("IMPORTANT:")
print("Research validation only.")
print("No threshold installed into bot.py.")
print("Frozen Layer A remains unchanged.")
print("No scalp logic changed.")
print("No orders placed.")
print()
print("=== 30S EARLY-SHOCK FULL-HISTORY VALIDATION COMPLETE ===")
