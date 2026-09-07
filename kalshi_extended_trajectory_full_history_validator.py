from pathlib import Path
import csv
import pandas as pd
import numpy as np

DETAILS = Path("kalshi_3min_distance_drop_full_history_details.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")

print("=== EXTENDED TRAJECTORY FULL-HISTORY VALIDATOR ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Testing 4m / 5m / 6m deterioration after first >=80% supported call.")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

if not DETAILS.exists():
    raise SystemExit("ERROR: kalshi_3min_distance_drop_full_history_details.csv not found.")
if not LIVE.exists():
    raise SystemExit("ERROR: kalshi_live_fair_value_shadow_log.csv not found.")

d = pd.read_csv(DETAILS)

if d["correct"].dtype != bool:
    d["correct"] = (
        d["correct"].astype(str).str.lower()
        .map({"true": True, "false": False})
    )

for c in [
    "initial_fair",
    "initial_remaining_min",
    "initial_distance",
    "initial_signed_distance",
]:
    if c in d.columns:
        d[c] = pd.to_numeric(d[c], errors="coerce")

d["call_time"] = pd.to_datetime(d["call_time"], utc=True, errors="coerce")

# -------------------------
# Robust mixed-schema loader
# -------------------------
def looks_like_header(row):
    low = [str(x).strip().lower() for x in row]
    hits = 0
    for key in ["ticker", "timestamp", "distance", "preferred", "fair"]:
        if any(key in x for x in low):
            hits += 1
    return hits >= 2

records = []
current_header = None
header_switches = 0

with LIVE.open("r", newline="", encoding="utf-8-sig", errors="replace") as fh:
    reader = csv.reader(fh)

    for line_no, row in enumerate(reader, start=1):
        if not row or all(not str(x).strip() for x in row):
            continue

        if looks_like_header(row):
            current_header = [str(x).strip() for x in row]
            header_switches += 1
            continue

        if current_header is None:
            continue

        if len(row) < len(current_header):
            row = row + [""] * (len(current_header) - len(row))

        rec = dict(zip(current_header, row[:len(current_header)]))
        rec["_source_line"] = line_no
        records.append(rec)

if not records:
    raise SystemExit("ERROR: no usable live-log rows parsed.")

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

ticker_col = pick(live.columns, [
    "ticker", "contract_ticker", "market_ticker"
])

time_col = pick(live.columns, [
    "timestamp_utc", "timestamp", "time_utc", "snapshot_time"
])

distance_col = pick(live.columns, [
    "distance_target",
    "distance_from_target",
    "distance_to_target",
    "target_distance",
    "distance",
])

if ticker_col is None or time_col is None or distance_col is None:
    print("Available columns:")
    print(list(live.columns))
    raise SystemExit("ERROR: could not identify ticker/time/distance columns.")

live[time_col] = pd.to_datetime(live[time_col], utc=True, errors="coerce")
live[distance_col] = pd.to_numeric(live[distance_col], errors="coerce")

live = live[
    live[time_col].notna()
    & live[distance_col].notna()
    & live[ticker_col].notna()
].copy()

print("Historical qualifying calls:", len(d))
print("Mixed-log schema sections:", header_switches)
print("Usable live snapshots:", len(live))
print()

rows = []

for _, r in d.iterrows():
    ticker = str(r["ticker"])
    call_time = r["call_time"]
    call_side = str(r.get("call_side", "")).upper()

    if pd.isna(call_time):
        continue

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

    # Keep only same-contract follow-up period.
    q = q[(q["mins_after_call"] >= 0) & (q["mins_after_call"] <= 12.5)].copy()

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
        initial_distance = r.get("initial_distance", np.nan)

        if pd.notna(initial_distance):
            initial_signed = (
                float(initial_distance)
                if call_side == "UP"
                else -float(initial_distance)
            )

    if pd.isna(initial_signed):
        continue

    initial_signed = float(initial_signed)

    def horizon_stats(minutes):
        h = q[q["mins_after_call"] <= minutes]

        if h.empty:
            return np.nan, np.nan, False

        min_signed = float(h["signed_distance"].min())
        max_drop = max(0.0, initial_signed - min_signed)
        end_signed = float(h.iloc[-1]["signed_distance"])
        flipped = bool((h["signed_distance"] < 0).any())

        return max_drop, end_signed, flipped

    rec = {
        "ticker": ticker,
        "call_time": call_time,
        "correct": bool(r["correct"]),
        "call_side": call_side,
        "official_side": r.get("official_side", ""),
        "initial_fair": r.get("initial_fair", np.nan),
        "initial_remaining_min": r.get("initial_remaining_min", np.nan),
        "initial_distance": r.get("initial_distance", np.nan),
        "initial_signed_distance": initial_signed,
    }

    for mins in [3, 4, 5, 6]:
        drop, end_signed, flipped = horizon_stats(mins)
        rec[f"drop_{mins}m"] = drop
        rec[f"end_signed_{mins}m"] = end_signed
        rec[f"flip_{mins}m"] = flipped

    rows.append(rec)

x = pd.DataFrame(rows).sort_values("call_time").reset_index(drop=True)

print("Calls with usable extended trajectories:", len(x))
print()

if x.empty:
    raise SystemExit("ERROR: no extended historical trajectories matched.")

print("=== CORRECT VS WRONG BY HORIZON ===")

for mins in [3, 4, 5, 6]:
    c = f"drop_{mins}m"
    good = x[x["correct"]][c].dropna()
    bad = x[~x["correct"]][c].dropna()

    print(
        f"{mins}m",
        "| good median=", f"${good.median():.2f}" if len(good) else "NA",
        "| good max=", f"${good.max():.2f}" if len(good) else "NA",
        "| bad median=", f"${bad.median():.2f}" if len(bad) else "NA",
        "| bad min=", f"${bad.min():.2f}" if len(bad) else "NA",
        "| bad max=", f"${bad.max():.2f}" if len(bad) else "NA",
    )

print()
print("=== FULL-HISTORY THRESHOLD SCAN ===")

thresholds = [50, 75, 85, 90, 100, 125, 150]
scan_rows = []

for mins in [4, 5, 6]:
    col = f"drop_{mins}m"

    for cut in thresholds:
        flagged = x[x[col] >= cut]
        clean = x[x[col] < cut]

        total_misses = int((~x["correct"]).sum())
        caught = int((~flagged["correct"]).sum()) if len(flagged) else 0
        good_flagged = int(flagged["correct"].sum()) if len(flagged) else 0

        scan_rows.append({
            "scope": "FULL",
            "horizon_min": mins,
            "threshold": cut,
            "calls": len(x),
            "flagged": len(flagged),
            "mistakes_caught": caught,
            "total_misses": total_misses,
            "capture": caught / total_misses if total_misses else np.nan,
            "good_flagged": good_flagged,
            "false_warn_rate": (
                good_flagged / int(x["correct"].sum())
                if int(x["correct"].sum()) else np.nan
            ),
            "clean_n": len(clean),
            "clean_accuracy": clean["correct"].mean() if len(clean) else np.nan,
        })

full_scan = pd.DataFrame(scan_rows)

show = full_scan.sort_values(
    ["mistakes_caught", "good_flagged", "clean_accuracy"],
    ascending=[False, True, False]
)

for _, r in show.head(25).iterrows():
    print(
        f"{int(r['horizon_min'])}m >= ${int(r['threshold'])}",
        "| flagged=", int(r["flagged"]),
        "| caught=", f"{int(r['mistakes_caught'])}/{int(r['total_misses'])}",
        "| capture=", f"{r['capture']:.1%}" if pd.notna(r["capture"]) else "NA",
        "| good_flagged=", int(r["good_flagged"]),
        "| false_warn=", f"{r['false_warn_rate']:.1%}" if pd.notna(r["false_warn_rate"]) else "NA",
        "| clean_n=", int(r["clean_n"]),
        "| clean_acc=", f"{r['clean_accuracy']:.1%}" if pd.notna(r["clean_accuracy"]) else "NA",
    )

print()
print("=== CHRONOLOGICAL HOLDOUT: LAST 40% ===")

split = int(len(x) * 0.60)
train = x.iloc[:split].copy()
hold = x.iloc[split:].copy()

print("Train calls:", len(train))
print("Holdout calls:", len(hold))
print("Holdout baseline accuracy:", f"{hold['correct'].mean():.1%}")
print("Holdout misses:", int((~hold["correct"]).sum()))
print()

hold_rows = []

for mins in [4, 5, 6]:
    col = f"drop_{mins}m"

    for cut in thresholds:
        flagged = hold[hold[col] >= cut]
        clean = hold[hold[col] < cut]

        total_misses = int((~hold["correct"]).sum())
        caught = int((~flagged["correct"]).sum()) if len(flagged) else 0
        good_flagged = int(flagged["correct"].sum()) if len(flagged) else 0

        hold_rows.append({
            "scope": "HOLDOUT",
            "horizon_min": mins,
            "threshold": cut,
            "calls": len(hold),
            "flagged": len(flagged),
            "mistakes_caught": caught,
            "total_misses": total_misses,
            "capture": caught / total_misses if total_misses else np.nan,
            "good_flagged": good_flagged,
            "false_warn_rate": (
                good_flagged / int(hold["correct"].sum())
                if int(hold["correct"].sum()) else np.nan
            ),
            "clean_n": len(clean),
            "clean_accuracy": clean["correct"].mean() if len(clean) else np.nan,
        })

hold_scan = pd.DataFrame(hold_rows)

show_h = hold_scan.sort_values(
    ["mistakes_caught", "good_flagged", "clean_accuracy"],
    ascending=[False, True, False]
)

for _, r in show_h.head(25).iterrows():
    print(
        f"{int(r['horizon_min'])}m >= ${int(r['threshold'])}",
        "| flagged=", int(r["flagged"]),
        "| caught=", f"{int(r['mistakes_caught'])}/{int(r['total_misses'])}",
        "| capture=", f"{r['capture']:.1%}" if pd.notna(r["capture"]) else "NA",
        "| good_flagged=", int(r["good_flagged"]),
        "| false_warn=", f"{r['false_warn_rate']:.1%}" if pd.notna(r["false_warn_rate"]) else "NA",
        "| clean_n=", int(r["clean_n"]),
        "| clean_acc=", f"{r['clean_accuracy']:.1%}" if pd.notna(r["clean_accuracy"]) else "NA",
    )

print()
print("=== FORWARD-INSPIRED CANDIDATES ===")
print("These were specified BEFORE this full-history scan:")
print("4m >= $100")
print("5m >= $100")
print("6m >= $85")
print("6m >= $90")
print("6m >= $100")
print()

for mins, cut in [(4,100),(5,100),(6,85),(6,90),(6,100)]:
    for scope_name, frame in [("FULL", x), ("HOLDOUT", hold)]:
        col = f"drop_{mins}m"
        flagged = frame[frame[col] >= cut]
        clean = frame[frame[col] < cut]

        total_misses = int((~frame["correct"]).sum())
        caught = int((~flagged["correct"]).sum()) if len(flagged) else 0
        good_flagged = int(flagged["correct"].sum()) if len(flagged) else 0

        print(
            scope_name,
            f"| {mins}m >= ${cut}",
            "| flagged=", len(flagged),
            "| caught=", f"{caught}/{total_misses}",
            "| good_flagged=", good_flagged,
            "| clean_acc=", f"{clean['correct'].mean():.1%}" if len(clean) else "NA",
        )

x.to_csv(
    "kalshi_extended_trajectory_full_history_details.csv",
    index=False
)

pd.concat([full_scan, hold_scan], ignore_index=True).to_csv(
    "kalshi_extended_trajectory_full_history_scan.csv",
    index=False
)

print()
print("=== FILES CREATED ===")
print("kalshi_extended_trajectory_full_history_details.csv")
print("kalshi_extended_trajectory_full_history_scan.csv")
print()
print("IMPORTANT:")
print("Research validation only.")
print("No rule installed into bot.py.")
print("No scalp logic changed.")
print("Signal-only remains intact.")
print()
print("=== EXTENDED FULL-HISTORY VALIDATION COMPLETE ===")
