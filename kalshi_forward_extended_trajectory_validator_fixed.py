from pathlib import Path
import csv
import pandas as pd
import numpy as np

FWD = Path("kalshi_frozen_forward_only_results.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")

print("=== FORWARD EXTENDED TRAJECTORY VALIDATOR - MIXED LOG FIX ===")
print("Purpose: inspect what happens AFTER the first 3 minutes on frozen forward calls.")
print("Frozen rules changed: NO")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

if not FWD.exists():
    raise SystemExit("ERROR: kalshi_frozen_forward_only_results.csv not found.")
if not LIVE.exists():
    raise SystemExit("ERROR: kalshi_live_fair_value_shadow_log.csv not found.")

f = pd.read_csv(FWD)

if f["correct"].dtype != bool:
    f["correct"] = (
        f["correct"].astype(str).str.lower()
        .map({"true": True, "false": False})
    )

# ------------------------------------------------------------
# Robust loader for live CSV containing historical schema changes.
# It treats repeated header rows as schema switches and preserves
# every row that can be mapped to a known header.
# ------------------------------------------------------------
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
bad_rows = 0

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
            bad_rows += 1
            continue

        # Exact-width rows are ideal.
        if len(row) == len(current_header):
            rec = dict(zip(current_header, row))
            rec["_source_line"] = line_no
            records.append(rec)
            continue

        # If row is wider, preserve known columns and put extras aside.
        if len(row) > len(current_header):
            rec = dict(zip(current_header, row[:len(current_header)]))
            rec["_extra_fields"] = "|".join(row[len(current_header):])
            rec["_source_line"] = line_no
            records.append(rec)
            continue

        # If row is shorter, pad with blanks.
        padded = row + [""] * (len(current_header) - len(row))
        rec = dict(zip(current_header, padded))
        rec["_source_line"] = line_no
        records.append(rec)

if not records:
    raise SystemExit("ERROR: no usable live-log rows could be parsed.")

live = pd.DataFrame(records)

print("Mixed-log parse complete.")
print("Header/schema sections detected:", header_switches)
print("Usable rows:", len(live))
print("Unusable pre-header rows:", bad_rows)
print()

def pick(cols, candidates):
    cols = list(cols)

    # Prefer exact lowercase matches first.
    lower = {str(c).lower(): c for c in cols}
    for name in candidates:
        if name.lower() in lower:
            return lower[name.lower()]

    # Then prefer substring matches.
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
    "distance_from_target",
    "distance_to_target",
    "target_distance",
    "distance"
])

if ticker_col is None or time_col is None or distance_col is None:
    print("Available live-log columns:")
    print(list(live.columns))
    raise SystemExit(
        "ERROR: could not identify ticker/time/distance columns in mixed live log."
    )

live[time_col] = pd.to_datetime(live[time_col], utc=True, errors="coerce")
live[distance_col] = pd.to_numeric(live[distance_col], errors="coerce")

live = live[
    live[time_col].notna()
    & live[distance_col].notna()
    & live[ticker_col].notna()
].copy()

f["call_time"] = pd.to_datetime(f["call_time"], utc=True, errors="coerce")

for c in [
    "initial_fair",
    "initial_remaining_min",
    "initial_distance",
    "initial_signed_distance",
]:
    if c in f.columns:
        f[c] = pd.to_numeric(f[c], errors="coerce")

print("Using ticker column:", ticker_col)
print("Using timestamp column:", time_col)
print("Using distance column:", distance_col)
print("Clean live rows available:", len(live))
print()

rows = []

for _, r in f.iterrows():
    ticker = str(r["ticker"])
    call_time = r["call_time"]
    call_side = str(r.get("call_side", "")).upper()

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

    # Do not accidentally include a later contract or absurdly late rows.
    q = q[q["mins_after_call"] <= 12.5].copy()
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
        drop = max(0.0, initial_signed - min_signed)
        end_signed = float(h.iloc[-1]["signed_distance"])
        flipped = bool((h["signed_distance"] < 0).any())
        return drop, end_signed, flipped

    rec = {
        "ticker": ticker,
        "correct": bool(r["correct"]),
        "call_side": call_side,
        "official_side": r.get("official_side", ""),
        "initial_fair": r.get("initial_fair", np.nan),
        "initial_distance": r.get("initial_distance", np.nan),
        "initial_signed_distance": initial_signed,
        "initial_remaining_min": r.get("initial_remaining_min", np.nan),
    }

    for mins in [3, 4, 5, 6]:
        drop, end_signed, flipped = horizon_stats(mins)
        rec[f"drop_{mins}m"] = drop
        rec[f"end_signed_{mins}m"] = end_signed
        rec[f"flip_{mins}m"] = flipped

    rec["drop_rest"] = max(
        0.0,
        initial_signed - float(q["signed_distance"].min())
    )
    rec["min_signed_rest"] = float(q["signed_distance"].min())
    rec["flip_rest"] = bool((q["signed_distance"] < 0).any())

    rows.append(rec)

d = pd.DataFrame(rows)

print("Forward calls with usable extended trajectories:", len(d))
print()

if d.empty:
    raise SystemExit("ERROR: no forward trajectories could be matched.")

print("=== CORRECT VS WRONG BY HORIZON ===")
for mins in [3, 4, 5, 6]:
    c = f"drop_{mins}m"
    good = d[d["correct"]][c].dropna()
    bad = d[~d["correct"]][c].dropna()

    print(
        f"{mins}m deterioration",
        "| good median=", f"${good.median():.2f}" if len(good) else "NA",
        "| good max=", f"${good.max():.2f}" if len(good) else "NA",
        "| bad median=", f"${bad.median():.2f}" if len(bad) else "NA",
        "| bad min=", f"${bad.min():.2f}" if len(bad) else "NA",
        "| bad max=", f"${bad.max():.2f}" if len(bad) else "NA",
    )

print()
print("=== FORWARD MISSES: EXTENDED PATH ===")

miss = d[~d["correct"]].copy()

if miss.empty:
    print("No forward misses have usable trajectories.")
else:
    for _, r in miss.iterrows():
        print(
            r["ticker"],
            "| call=", r["call_side"],
            "| winner=", r["official_side"],
            "| initial_dist=", f"${float(r['initial_distance']):+.2f}",
            "| 3m=", f"${r['drop_3m']:.2f}",
            "| 4m=", f"${r['drop_4m']:.2f}",
            "| 5m=", f"${r['drop_5m']:.2f}",
            "| 6m=", f"${r['drop_6m']:.2f}",
            "| rest=", f"${r['drop_rest']:.2f}",
            "| flip4=", r["flip_4m"],
            "| flip5=", r["flip_5m"],
            "| flip6=", r["flip_6m"],
            "| flip_rest=", r["flip_rest"],
        )

print()
print("=== EXTENDED THRESHOLD DIAGNOSTIC ===")
print("Diagnostic only. No rule will be installed from this small sample.")
print()

scan = []

for mins in [4, 5, 6]:
    col = f"drop_{mins}m"

    for cut in [50, 75, 100, 125, 150, 175, 200]:
        warned = d[d[col] >= cut]
        clean = d[d[col] < cut]

        scan.append({
            "horizon_min": mins,
            "threshold": cut,
            "flagged": len(warned),
            "mistakes_caught": (
                int((~warned["correct"]).sum()) if len(warned) else 0
            ),
            "good_flagged": (
                int(warned["correct"].sum()) if len(warned) else 0
            ),
            "clean_n": len(clean),
            "clean_accuracy": (
                clean["correct"].mean() if len(clean) else np.nan
            ),
        })

s = pd.DataFrame(scan)

interesting = s[
    s["mistakes_caught"] > 0
].sort_values(
    ["mistakes_caught", "good_flagged", "horizon_min", "threshold"],
    ascending=[False, True, True, False]
)

print(interesting.head(20).to_string(index=False))

print()
print("=== UP CALLS WITH INITIAL DISTANCE $100-$150 ===")

band = d[
    (d["call_side"] == "UP")
    & (pd.to_numeric(d["initial_distance"], errors="coerce") >= 100)
    & (pd.to_numeric(d["initial_distance"], errors="coerce") <= 150)
].copy()

if band.empty:
    print("No calls in band.")
else:
    for _, r in band.iterrows():
        print(
            r["ticker"],
            "| correct=", r["correct"],
            "| fair=", (
                f"{float(r['initial_fair']):.1%}"
                if pd.notna(r["initial_fair"]) else "NA"
            ),
            "| dist=", f"${float(r['initial_distance']):+.2f}",
            "| left=", (
                f"{float(r['initial_remaining_min']):.2f}"
                if pd.notna(r["initial_remaining_min"]) else "NA"
            ),
            "| 4m_drop=", f"${r['drop_4m']:.2f}",
            "| 5m_drop=", f"${r['drop_5m']:.2f}",
            "| 6m_drop=", f"${r['drop_6m']:.2f}",
            "| rest_drop=", f"${r['drop_rest']:.2f}",
        )

d.to_csv(
    "kalshi_forward_extended_trajectory_details.csv",
    index=False
)
s.to_csv(
    "kalshi_forward_extended_trajectory_scan.csv",
    index=False
)

print()
print("=== FILES CREATED ===")
print("kalshi_forward_extended_trajectory_details.csv")
print("kalshi_forward_extended_trajectory_scan.csv")
print()
print("Frozen rules remain unchanged.")
print("=== EXTENDED TRAJECTORY VALIDATION COMPLETE ===")
