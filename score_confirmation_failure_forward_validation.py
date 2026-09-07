from pathlib import Path
import pandas as pd
import numpy as np
import csv

MARKER = Path("confirmation_failure_forward_start_utc.txt")
LAYER_A = Path("kalshi_layer_a_forward_only_results.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")

print("=== CONFIRMATION-FAILURE FORWARD-ONLY SCORER ===")
print("Frozen rule:")
print("  4m distance gain < +$10 AND 4m fair-value gain < 0")
print("  warning only")
print()
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

if not MARKER.exists():
    raise SystemExit("Missing confirmation_failure_forward_start_utc.txt")
if not LAYER_A.exists():
    raise SystemExit("Missing kalshi_layer_a_forward_only_results.csv. Refresh Layer A first.")
if not LIVE.exists():
    raise SystemExit("Missing kalshi_live_fair_value_shadow_log.csv")

start_utc = pd.to_datetime(MARKER.read_text().strip(), utc=True, errors="coerce")
if pd.isna(start_utc):
    raise SystemExit("Could not parse forward marker.")

a = pd.read_csv(LAYER_A)
a["call_time"] = pd.to_datetime(a["call_time"], utc=True, errors="coerce")
a = a[a["call_time"] >= start_utc].copy()

if a.empty:
    print("No Layer A forward calls after this marker yet.")
    raise SystemExit(0)

clean = a[a["state"].astype(str).str.upper() == "CLEAN"].copy()

print("Layer A forward calls after marker:", len(a))
print("Layer A CLEAN calls after marker:", len(clean))
print()

def pick(cols, candidates):
    lower = {str(c).lower(): c for c in cols}
    for x in candidates:
        if x.lower() in lower:
            return lower[x.lower()]
    for c in cols:
        lc = str(c).lower()
        for x in candidates:
            if x.lower() in lc:
                return c
    return None

def looks_like_header(row):
    low = [str(x).strip().lower() for x in row]
    keys = ["ticker","timestamp","distance","fair","ask","preferred"]
    return sum(any(k in x for k in keys) for x in low) >= 2

records, header = [], None
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

tc = pick(live.columns, ["ticker","contract_ticker","market_ticker"])
ts = pick(live.columns, ["timestamp_utc","timestamp","time_utc","snapshot_time"])
dc = pick(live.columns, ["distance_target","distance_from_target","distance_to_target","target_distance","distance"])
fu = pick(live.columns, ["fair_up","fair_up_probability","fair_up_prob"])
fd = pick(live.columns, ["fair_down","fair_down_probability","fair_down_prob"])

for c in [dc,fu,fd]:
    if c:
        live[c] = pd.to_numeric(live[c], errors="coerce")
live[ts] = pd.to_datetime(live[ts], utc=True, errors="coerce")
live[tc] = live[tc].astype(str)

def nearest(df, target_time, tolerance=45):
    if df.empty:
        return None
    delta = (df[ts] - target_time).abs().dt.total_seconds()
    i = delta.idxmin()
    if float(delta.loc[i]) > tolerance:
        return None
    return df.loc[i]

rows = []

for _, call in clean.iterrows():
    ticker = str(call["ticker"])
    side = str(call["call_side"]).upper()
    t0 = call["call_time"]
    if pd.isna(t0):
        continue

    q = live[(live[tc] == ticker) & (live[ts] >= t0)].copy().sort_values(ts)
    if q.empty:
        continue

    nr = nearest(q, t0 + pd.Timedelta(minutes=4), tolerance=45)
    if nr is None:
        continue

    initial_distance = float(call["initial_distance"])
    initial_signed = initial_distance if side == "UP" else -initial_distance
    four_signed = float(nr[dc]) if side == "UP" else -float(nr[dc])
    distance_gain = four_signed - initial_signed

    initial_fair = float(call["initial_fair"])
    if side == "UP" and fu:
        four_fair = float(nr[fu]) if pd.notna(nr[fu]) else np.nan
    elif side == "DOWN" and fd:
        four_fair = float(nr[fd]) if pd.notna(nr[fd]) else np.nan
    else:
        four_fair = np.nan

    fair_gain = four_fair - initial_fair if pd.notna(four_fair) else np.nan

    warning = (
        pd.notna(distance_gain) and pd.notna(fair_gain)
        and distance_gain < 10
        and fair_gain < 0
    )

    rows.append({
        "ticker": ticker,
        "call_time": t0,
        "call_side": side,
        "correct": bool(call["correct"]),
        "initial_fair": initial_fair,
        "initial_distance": initial_distance,
        "four_min_actual_sec": float((nr[ts] - t0).total_seconds()),
        "four_min_distance_gain": distance_gain,
        "four_min_fair_gain": fair_gain,
        "confirmation_failure_warning": warning,
    })

d = pd.DataFrame(rows)

if d.empty:
    print("No forward CLEAN calls yet with usable 4-minute checkpoint.")
    raise SystemExit(0)

warned = d[d["confirmation_failure_warning"]]
kept = d[~d["confirmation_failure_warning"]]
misses = d[~d["correct"]]
caught = warned[~warned["correct"]]
good_warned = warned[warned["correct"]]

print("=== FORWARD RESULT ===")
print("CLEAN calls with usable 4m checkpoint:", len(d))
print("CLEAN correct:", int(d["correct"].sum()))
print("CLEAN wrong:", int((~d["correct"]).sum()))
print("CLEAN accuracy:", f"{d['correct'].mean():.1%}")
print()
print("Warnings:", len(warned))
print("Misses caught:", f"{len(caught)}/{len(misses)}")
print("Good winners warned:", len(good_warned))
print("Kept calls:", len(kept))
print("Kept accuracy:", f"{kept['correct'].mean():.1%}" if len(kept) else "N/A")
print()

print("=== FORWARD DETAILS ===")
print(d.to_string(index=False))

d.to_csv("kalshi_confirmation_failure_forward_results.csv", index=False)

print()
print("Saved: kalshi_confirmation_failure_forward_results.csv")
print("Frozen rule unchanged.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print("=== SCORING COMPLETE ===")
