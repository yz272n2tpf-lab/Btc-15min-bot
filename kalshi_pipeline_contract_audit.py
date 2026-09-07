from pathlib import Path
import csv
import pandas as pd
import numpy as np

TARGET = "KXBTC15M-26AUG251630-30"

FWD = Path("kalshi_layer_a_forward_only_results.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")
OFFICIAL = Path("kalshi_official_settlement_check.csv")
SHOCK = Path("kalshi_30s_early_shock_full_history_details.csv")

print("=== KALSHI PIPELINE CONTRACT AUDIT ===")
print("Target contract:", TARGET)
print("Purpose: reconcile forward scorer vs full-history 30s validator.")
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

# -------------------------
# 1) Forward scorer record
# -------------------------
print("=== FORWARD-SCORER RECORD ===")
if FWD.exists():
    f = pd.read_csv(FWD)
    fticker = pick(f.columns, ["ticker","contract_ticker","market_ticker"])
    if fticker is None:
        print("Could not identify ticker column in forward file.")
    else:
        z = f[f[fticker].astype(str) == TARGET].copy()
        if z.empty:
            print("TARGET NOT FOUND in", FWD.name)
        else:
            print(z.to_string(index=False))
else:
    print(FWD.name, "not found.")
print()

# -------------------------
# 2) Official result
# -------------------------
print("=== OFFICIAL RESULT ===")
if OFFICIAL.exists():
    o = pd.read_csv(OFFICIAL)
    oticker = pick(o.columns, ["ticker","contract_ticker","market_ticker"])
    if oticker is None:
        print("Could not identify ticker column in official file.")
    else:
        z = o[o[oticker].astype(str) == TARGET].copy()
        if z.empty:
            print("TARGET NOT FOUND in", OFFICIAL.name)
        else:
            print(z.to_string(index=False))
else:
    print(OFFICIAL.name, "not found.")
print()

# -------------------------
# 3) 30s validator output
# -------------------------
print("=== 30S FULL-HISTORY OUTPUT RECORD ===")
if SHOCK.exists():
    s = pd.read_csv(SHOCK)
    sticker = pick(s.columns, ["ticker","contract_ticker","market_ticker"])
    if sticker is None:
        print("Could not identify ticker column in shock details file.")
    else:
        z = s[s[sticker].astype(str) == TARGET].copy()
        if z.empty:
            print("TARGET NOT FOUND in", SHOCK.name)
        else:
            print(z.to_string(index=False))
else:
    print(SHOCK.name, "not found.")
print()

# -------------------------
# 4) Robust live-log parse
# -------------------------
print("=== LIVE LOG AUDIT ===")

if not LIVE.exists():
    raise SystemExit(f"ERROR: {LIVE.name} not found.")

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

needed = [ticker_col,time_col,remaining_col,distance_col,preferred_side_col]
if any(c is None for c in needed):
    print("Available columns:")
    print(list(live.columns))
    raise SystemExit("ERROR: could not identify required live-log columns.")

live[time_col] = pd.to_datetime(live[time_col], utc=True, errors="coerce")
for c in [remaining_col,distance_col,preferred_fair_col,fair_up_col,fair_down_col]:
    if c is not None:
        live[c] = pd.to_numeric(live[c], errors="coerce")

live[ticker_col] = live[ticker_col].astype(str)
live[preferred_side_col] = live[preferred_side_col].astype(str).str.upper().str.strip()

q = live[live[ticker_col] == TARGET].copy().sort_values(time_col)

print("Raw parsed snapshots for target:", len(q))
if q.empty:
    raise SystemExit("TARGET has no parsed live snapshots.")

def side_fair(row):
    side = row[preferred_side_col]
    if side == "UP" and fair_up_col is not None and pd.notna(row.get(fair_up_col, np.nan)):
        return float(row[fair_up_col])
    if side == "DOWN" and fair_down_col is not None and pd.notna(row.get(fair_down_col, np.nan)):
        return float(row[fair_down_col])
    if preferred_fair_col is not None and pd.notna(row.get(preferred_fair_col, np.nan)):
        return float(row[preferred_fair_col])
    return np.nan

q["side_fair"] = q.apply(side_fair, axis=1)
q["signed_distance"] = np.where(
    q[preferred_side_col] == "UP",
    q[distance_col],
    -q[distance_col]
)

if signal_col is not None:
    q["signal_text"] = q[signal_col].astype(str).str.upper()
    q["supported_like"] = q["signal_text"].str.contains(
        "SUPPORTED|HIGH_QUALITY|EARLY_LOCK|LOCK", regex=True, na=False
    )
else:
    q["signal_text"] = "NO_SIGNAL_COLUMN"
    q["supported_like"] = True

cols = [
    "_source_line",
    time_col,
    remaining_col,
    preferred_side_col,
    distance_col,
    "signed_distance",
    "side_fair",
    "signal_text",
    "supported_like",
]

print()
print("All target snapshots:")
print(q[cols].to_string(index=False))
print()

# -------------------------
# 5) Rebuild full-history selection
# -------------------------
print("=== REBUILD FULL-HISTORY QUALIFYING SELECTION ===")

zone = q[
    q[remaining_col].notna()
    & (q[remaining_col] >= 8)
    & (q[remaining_col] <= 12)
].copy()

print("8-12m snapshots:", len(zone))

candidate = zone[
    zone[preferred_side_col].isin(["UP","DOWN"])
    & (zone["side_fair"] >= 0.80)
    & zone["supported_like"]
].copy()

print("After side + fair>=80 + supported-like:", len(candidate))

candidate = candidate[candidate["signed_distance"] > 0].copy()
print("After signed-distance > 0:", len(candidate))

if candidate.empty:
    print("RESULT: full-history selector EXCLUDES target contract.")
    print()
    print("Reason audit by snapshot:")
    audit = zone.copy()
    audit["pass_side"] = audit[preferred_side_col].isin(["UP","DOWN"])
    audit["pass_fair80"] = audit["side_fair"] >= 0.80
    audit["pass_supported"] = audit["supported_like"]
    audit["pass_signed_distance"] = audit["signed_distance"] > 0
    print(audit[
        ["_source_line",time_col,remaining_col,preferred_side_col,
         "side_fair","signal_text","signed_distance",
         "pass_side","pass_fair80","pass_supported","pass_signed_distance"]
    ].to_string(index=False))
else:
    first = candidate.sort_values(time_col).iloc[0]
    print("RESULT: full-history selector INCLUDES target contract.")
    print("Selected snapshot:")
    print(first[cols].to_string())
    print()

    # 30-second path from rebuilt selection
    call_time = first[time_col]
    side = first[preferred_side_col]
    initial_signed = float(first["signed_distance"])
    initial_fair = float(first["side_fair"]) if pd.notna(first["side_fair"]) else np.nan

    after = q[q[time_col] >= call_time].copy().sort_values(time_col)
    after["sec_after"] = (after[time_col] - call_time).dt.total_seconds()
    after = after[(after["sec_after"] >= 0) & (after["sec_after"] <= 390)].copy()

    if side == "UP":
        after["orig_side_signed_distance"] = after[distance_col]
        if fair_up_col is not None:
            after["orig_side_fair"] = after[fair_up_col]
        else:
            after["orig_side_fair"] = np.nan
    else:
        after["orig_side_signed_distance"] = -after[distance_col]
        if fair_down_col is not None:
            after["orig_side_fair"] = after[fair_down_col]
        else:
            after["orig_side_fair"] = np.nan

    idx30 = (after["sec_after"] - 30).abs().idxmin()
    r30 = after.loc[idx30]

    print("Nearest 30s snapshot delta:", float(r30["sec_after"]), "seconds")
    print("30s signed distance:", float(r30["orig_side_signed_distance"]))
    print("30s distance deterioration:", max(0.0, initial_signed - float(r30["orig_side_signed_distance"])))

    if pd.notna(initial_fair) and pd.notna(r30["orig_side_fair"]):
        print("30s original-side fair:", float(r30["orig_side_fair"]))
        print("30s fair drop:", max(0.0, initial_fair - float(r30["orig_side_fair"])))
    else:
        print("30s fair drop: unavailable")

print()
print("=== KEY COLUMN MAP ===")
print("ticker:", ticker_col)
print("timestamp:", time_col)
print("remaining:", remaining_col)
print("distance:", distance_col)
print("preferred_side:", preferred_side_col)
print("preferred_fair:", preferred_fair_col)
print("fair_up:", fair_up_col)
print("fair_down:", fair_down_col)
print("signal/status:", signal_col)
print()

print("=== AUDIT COMPLETE ===")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
