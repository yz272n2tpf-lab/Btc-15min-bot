from pathlib import Path
import re
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== KALSHI TICKER TIMING DIAGNOSTIC ===")
print("Purpose: determine whether KXBTC15M ticker time is OPEN or CLOSE, and whether it is ET or UTC.")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

if not CAL.exists():
    raise SystemExit("ERROR: brti_calibration_results.csv not found.")
if not BTC.exists():
    raise SystemExit("ERROR: btc_35d_live_cache.csv not found.")

cal = pd.read_csv(CAL)
btc = pd.read_csv(BTC)

required = {
    "ticker", "target_brti", "final_brti", "result",
    "target_cb_close", "target_cb_ohlc4", "target_cb_hl2",
    "final_cb_close", "final_cb_ohlc4", "final_cb_hl2",
}
missing = required - set(cal.columns)
if missing:
    raise SystemExit(f"ERROR: missing calibration columns: {sorted(missing)}")

btc["Datetime"] = pd.to_datetime(btc["Datetime"], utc=True, errors="coerce")
btc = btc.dropna(subset=["Datetime"]).sort_values("Datetime").set_index("Datetime")
btc["Close"] = pd.to_numeric(btc["Close"], errors="coerce")

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
    "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8,
    "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

def parse_wall_clock(ticker):
    # Example: KXBTC15M-26AUG221545-45
    # Captures 2026-08-22 15:45 as a wall clock with no timezone assumption.
    m = re.search(r"KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-", str(ticker).upper())
    if not m:
        return None
    yy, mon, dd, hh, mm = m.groups()
    if mon not in MONTHS:
        return None
    return pd.Timestamp(
        year=2000 + int(yy),
        month=MONTHS[mon],
        day=int(dd),
        hour=int(hh),
        minute=int(mm),
    )

def as_utc(ts):
    return ts.tz_localize("UTC")

def as_et_to_utc(ts):
    # Kalshi market display/ticker convention is tested as America/New_York local time.
    return ts.tz_localize(ZoneInfo("America/New_York")).tz_convert("UTC")

def close_at_or_before(ts, tolerance_minutes=2):
    pos = btc.index.searchsorted(ts, side="right") - 1
    if pos < 0:
        return np.nan
    idx = btc.index[pos]
    if ts - idx > pd.Timedelta(minutes=tolerance_minutes):
        return np.nan
    return float(btc.iloc[pos]["Close"])

# Candidate interpretations:
# A: ticker wall-clock is UTC OPEN
# B: ticker wall-clock is UTC CLOSE
# C: ticker wall-clock is ET OPEN
# D: ticker wall-clock is ET CLOSE  <-- suspected correct
candidates = {
    "UTC_OPEN": lambda wall: (as_utc(wall), as_utc(wall) + pd.Timedelta(minutes=15)),
    "UTC_CLOSE": lambda wall: (as_utc(wall) - pd.Timedelta(minutes=15), as_utc(wall)),
    "ET_OPEN": lambda wall: (as_et_to_utc(wall), as_et_to_utc(wall) + pd.Timedelta(minutes=15)),
    "ET_CLOSE": lambda wall: (as_et_to_utc(wall) - pd.Timedelta(minutes=15), as_et_to_utc(wall)),
}

rows = []
for _, r in cal.iterrows():
    wall = parse_wall_clock(r["ticker"])
    if wall is None:
        continue

    actual_yes = 1 if str(r["result"]).lower() == "yes" else 0
    target_brti = float(r["target_brti"])
    final_brti = float(r["final_brti"])

    # Sanity check: Kalshi settlement label should match BRTI final-vs-target.
    brti_side = 1 if final_brti >= target_brti else 0

    for name, fn in candidates.items():
        start_ts, end_ts = fn(wall)
        px_start = close_at_or_before(start_ts)
        px_end = close_at_or_before(end_ts)

        if pd.isna(px_start) or pd.isna(px_end):
            continue

        rows.append({
            "ticker": r["ticker"],
            "candidate": name,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "actual_yes": actual_yes,
            "brti_side": brti_side,
            "px_start": px_start,
            "px_end": px_end,
            "target_cb_close": float(r["target_cb_close"]),
            "final_cb_close": float(r["final_cb_close"]),
            "start_abs_error_vs_saved_cb": abs(px_start - float(r["target_cb_close"])),
            "end_abs_error_vs_saved_cb": abs(px_end - float(r["final_cb_close"])),
            "coinbase_target_side": 1 if px_end >= target_brti else 0,
        })

diag = pd.DataFrame(rows)

print("Calibration contracts:", len(cal))
print("Parsed diagnostic rows:", len(diag))
print()

# First prove the settlement label itself.
label_match = (
    (pd.to_numeric(cal["final_brti"], errors="coerce") >= pd.to_numeric(cal["target_brti"], errors="coerce"))
    == (cal["result"].astype(str).str.lower() == "yes")
)
print("=== SETTLEMENT LABEL SANITY CHECK ===")
print(f"BRTI final-vs-target agrees with result: {label_match.mean():.3%} ({int(label_match.sum())}/{len(label_match)})")
print()

print("=== TIMESTAMP CANDIDATE COMPARISON ===")
summary = []
for name in candidates:
    d = diag[diag["candidate"] == name].copy()
    if d.empty:
        continue

    start_mae = d["start_abs_error_vs_saved_cb"].mean()
    start_med = d["start_abs_error_vs_saved_cb"].median()
    end_mae = d["end_abs_error_vs_saved_cb"].mean()
    end_med = d["end_abs_error_vs_saved_cb"].median()
    side_acc = (d["coinbase_target_side"] == d["actual_yes"]).mean()

    summary.append({
        "candidate": name,
        "rows": len(d),
        "start_MAE": start_mae,
        "start_median": start_med,
        "end_MAE": end_mae,
        "end_median": end_med,
        "end_side_vs_Kalshi_result": side_acc,
    })

summary_df = pd.DataFrame(summary).sort_values(
    ["start_MAE", "end_MAE"],
    ascending=[True, True]
)

print(summary_df.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
print()

best = summary_df.iloc[0]["candidate"] if len(summary_df) else "UNKNOWN"
print("=== BEST TIMING MATCH ===")
print("Best candidate by saved Coinbase alignment:", best)

if best == "ET_CLOSE":
    print("VERDICT: ticker time behaves like CONTRACT CLOSE in America/New_York time.")
    print("Correct contract start = ticker time converted from ET to UTC, minus 15 minutes.")
elif best != "UNKNOWN":
    print("VERDICT: use the best candidate above; prior parser assumption was not validated.")
else:
    print("VERDICT: insufficient data.")

print()
print("=== SAMPLE: BEST CANDIDATE ===")
if best != "UNKNOWN":
    d = diag[diag["candidate"] == best].head(8)
    cols = [
        "ticker", "start_ts", "end_ts",
        "px_start", "target_cb_close",
        "px_end", "final_cb_close",
        "actual_yes",
    ]
    print(d[cols].to_string(index=False))

print()
print("=== DIAGNOSTIC COMPLETE ===")
print("No files modified.")
print("NEXT: if ET_CLOSE wins, repair only the historical test timestamp parser and rerun walk-forward.")
