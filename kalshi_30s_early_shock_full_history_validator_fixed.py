from pathlib import Path
import csv
import pandas as pd
import numpy as np

LIVE = Path("kalshi_live_fair_value_shadow_log.csv")
OFFICIAL = Path("kalshi_official_settlement_check.csv")

print("=== KALSHI 30S EARLY-SHOCK FULL-HISTORY VALIDATOR — FORWARD-ALIGNED FIX ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Fix: STRONG now qualifies exactly as in the forward scorer.")
print("Candidate rules unchanged:")
print("  30s distance deterioration >= $30")
print("  30s original-side fair drop >= 5 percentage points")
print("  either condition")
print()
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

if not LIVE.exists():
    raise SystemExit("ERROR: kalshi_live_fair_value_shadow_log.csv not found.")
if not OFFICIAL.exists():
    raise SystemExit("ERROR: kalshi_official_settlement_check.csv not found.")

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

# Official
official = pd.read_csv(OFFICIAL)
oticker = pick(official.columns, ["ticker","contract_ticker","market_ticker"])
owinner = pick(official.columns, ["official_side","winner","result","market_result"])
if oticker is None or owinner is None:
    raise SystemExit(f"ERROR: official columns not found: {list(official.columns)}")

official = official[[oticker,owinner]].copy()
official.columns = ["ticker","winner"]
official["ticker"] = official["ticker"].astype(str)
official["winner"] = official["winner"].astype(str).str.upper().str.strip()
official = official[official["winner"].isin(["UP","DOWN"])].drop_duplicates("ticker")

# Robust mixed live parser
def looks_like_header(row):
    low = [str(x).strip().lower() for x in row]
    return sum(any(k in x for x in low) for k in ["ticker","timestamp","distance","preferred","fair"]) >= 2

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

ticker_col = pick(live.columns, ["ticker","contract_ticker","market_ticker"])
time_col = pick(live.columns, ["timestamp_utc","timestamp","time_utc","snapshot_time"])
remaining_col = pick(live.columns, ["remaining_min","minutes_left","time_left_min","time_remaining_min"])
distance_col = pick(live.columns, ["distance_target","distance_from_target","distance_to_target","target_distance","distance"])
side_col = pick(live.columns, ["preferred_side","model_side","side"])
fair_up_col = pick(live.columns, ["fair_up","fair_up_probability","fair_up_prob"])
fair_down_col = pick(live.columns, ["fair_down","fair_down_probability","fair_down_prob"])
pref_fair_col = pick(live.columns, ["preferred_fair","fair_value","preferred_side_fair"])
signal_col = pick(live.columns, ["signal_status","quality_tier","status"])

if any(c is None for c in [ticker_col,time_col,remaining_col,distance_col,side_col]):
    raise SystemExit(f"ERROR: required live columns missing. Available: {list(live.columns)}")

live[time_col] = pd.to_datetime(live[time_col], utc=True, errors="coerce")
for c in [remaining_col,distance_col,fair_up_col,fair_down_col,pref_fair_col]:
    if c is not None:
        live[c] = pd.to_numeric(live[c], errors="coerce")

live[ticker_col] = live[ticker_col].astype(str)
live[side_col] = live[side_col].astype(str).str.upper().str.strip()
live = live[live[time_col].notna() & live[remaining_col].notna() & live[distance_col].notna()].copy()

def side_fair(row, side):
    if side == "UP" and fair_up_col is not None and pd.notna(row.get(fair_up_col, np.nan)):
        return float(row[fair_up_col])
    if side == "DOWN" and fair_down_col is not None and pd.notna(row.get(fair_down_col, np.nan)):
        return float(row[fair_down_col])
    if pref_fair_col is not None and pd.notna(row.get(pref_fair_col, np.nan)):
        return float(row[pref_fair_col])
    return np.nan

def forward_qualifying_status(df):
    # Critical fix: STRONG is part of the forward qualifying population.
    if signal_col is None:
        return pd.Series(True, index=df.index)
    s = df[signal_col].astype(str).str.upper().str.strip()
    return s.str.contains(
        r"STRONG|SUPPORTED|HIGH_QUALITY|EARLY_LOCK|LOCK",
        regex=True, na=False
    )

# Rebuild first qualifying calls
calls = []
for ticker, q in live.groupby(ticker_col):
    q = q.sort_values(time_col).copy()
    q = q[(q[remaining_col] >= 8) & (q[remaining_col] <= 12)]
    if q.empty:
        continue

    q["side_fair"] = q.apply(lambda r: side_fair(r, r[side_col]), axis=1)
    q["signed_distance"] = np.where(q[side_col] == "UP", q[distance_col], -q[distance_col])

    q = q[
        q[side_col].isin(["UP","DOWN"])
        & (q["side_fair"] >= 0.80)
        & forward_qualifying_status(q)
        & (q["signed_distance"] > 0)
    ].copy()

    if not q.empty:
        calls.append(q.iloc[0])

calls = pd.DataFrame(calls)
calls = calls.merge(official, left_on=ticker_col, right_on="ticker", how="inner")
calls["correct"] = calls[side_col] == calls["winner"]

details = []

for _, call in calls.iterrows():
    ticker = str(call[ticker_col])
    side = str(call[side_col])
    t0 = call[time_col]
    initial_signed = float(call["signed_distance"])
    initial_fair = float(call["side_fair"])

    q = live[(live[ticker_col] == ticker) & (live[time_col] >= t0)].copy().sort_values(time_col)
    q["sec_after"] = (q[time_col] - t0).dt.total_seconds()
    q = q[(q["sec_after"] >= 0) & (q["sec_after"] <= 390)].copy()
    if q.empty:
        continue

    q["orig_signed_distance"] = q[distance_col] if side == "UP" else -q[distance_col]
    if side == "UP" and fair_up_col is not None:
        q["orig_fair"] = q[fair_up_col]
    elif side == "DOWN" and fair_down_col is not None:
        q["orig_fair"] = q[fair_down_col]
    else:
        q["orig_fair"] = np.nan

    def nearest(sec):
        idx = (q["sec_after"] - sec).abs().idxmin()
        r = q.loc[idx]
        return None if abs(float(r["sec_after"]) - sec) > 45 else r

    r30, r4, r6 = nearest(30), nearest(240), nearest(360)
    if r30 is None:
        continue

    d30 = max(0.0, initial_signed - float(r30["orig_signed_distance"]))
    f30 = (
        max(0.0, initial_fair - float(r30["orig_fair"]))
        if pd.notna(r30["orig_fair"]) else np.nan
    )
    d4 = max(0.0, initial_signed - float(r4["orig_signed_distance"])) if r4 is not None else np.nan
    d6 = max(0.0, initial_signed - float(r6["orig_signed_distance"])) if r6 is not None else np.nan

    early = pd.notna(d4) and d4 >= 100
    late = pd.notna(d6) and d6 >= 85

    if early and late:
        state = "CONFIRMED_DANGER"
    elif early:
        state = "EARLY_WARNING_ONLY"
    elif late:
        state = "LATE_DANGER_ONLY"
    else:
        state = "CLEAN"

    details.append({
        "ticker": ticker,
        "call_time": t0,
        "call_side": side,
        "winner": call["winner"],
        "correct": bool(call["correct"]),
        "signal_status": call[signal_col] if signal_col is not None else "",
        "initial_fair": initial_fair,
        "initial_remaining_min": call[remaining_col],
        "initial_distance": call[distance_col],
        "drop_30s": d30,
        "fair_drop_30s": f30,
        "drop_4m": d4,
        "drop_6m": d6,
        "layer_a_state": state,
        "shock_distance": d30 >= 30,
        "shock_fair": pd.notna(f30) and f30 >= 0.05,
        "shock_either": (d30 >= 30) or (pd.notna(f30) and f30 >= 0.05),
    })

d = pd.DataFrame(details).sort_values("call_time").reset_index(drop=True)

print("Official qualifying calls with usable 30s path:", len(d))
print("Baseline accuracy:", f"{d['correct'].mean():.1%}")
print()

clean = d[d["layer_a_state"] == "CLEAN"].copy()
print("=== LAYER A CLEAN ===")
print("n:", len(clean))
print("correct:", int(clean["correct"].sum()))
print("wrong:", int((~clean["correct"]).sum()))
print("accuracy:", f"{clean['correct'].mean():.1%}" if len(clean) else "N/A")
print()

target = "KXBTC15M-26AUG251630-30"
print("=== TARGET CONTRACT PRESENCE CHECK ===")
tz = d[d["ticker"] == target]
if len(tz):
    print(tz.to_string(index=False))
else:
    print("ERROR: target still missing.")
print()

print("=== 30S SHOCK TEST INSIDE FORWARD-ALIGNED LAYER A CLEAN ===")
for col,label in [
    ("shock_distance","30s distance >= $30"),
    ("shock_fair","30s fair drop >= 5pt"),
    ("shock_either","either 30s shock"),
]:
    flagged = clean[clean[col]]
    kept = clean[~clean[col]]
    misses = int((~clean["correct"]).sum())
    caught = int((~flagged["correct"]).sum())
    good = int(flagged["correct"].sum())
    print(
        label,
        "| flagged=", len(flagged),
        "| mistakes_caught=", f"{caught}/{misses}",
        "| capture=", f"{caught/misses:.1%}" if misses else "N/A",
        "| good_flagged=", good,
        "| false_warn=", f"{good/int(clean['correct'].sum()):.1%}" if int(clean["correct"].sum()) else "N/A",
        "| kept=", len(kept),
        "| kept_acc=", f"{kept['correct'].mean():.1%}" if len(kept) else "N/A",
    )

print()
print("=== CHRONOLOGICAL HOLDOUT: LAST 40% ===")
cut = int(np.floor(len(d)*0.60))
hold = d.iloc[cut:].copy()
hc = hold[hold["layer_a_state"] == "CLEAN"].copy()
print("Holdout calls:", len(hold))
print("Holdout baseline accuracy:", f"{hold['correct'].mean():.1%}" if len(hold) else "N/A")
print("Holdout CLEAN:", len(hc), "| accuracy=", f"{hc['correct'].mean():.1%}" if len(hc) else "N/A")

for col,label in [
    ("shock_distance","30s distance >= $30"),
    ("shock_fair","30s fair drop >= 5pt"),
    ("shock_either","either 30s shock"),
]:
    flagged = hc[hc[col]]
    kept = hc[~hc[col]]
    misses = int((~hc["correct"]).sum())
    caught = int((~flagged["correct"]).sum())
    good = int(flagged["correct"].sum())
    print(
        label,
        "| flagged=", len(flagged),
        "| mistakes_caught=", f"{caught}/{misses}",
        "| good_flagged=", good,
        "| kept=", len(kept),
        "| kept_acc=", f"{kept['correct'].mean():.1%}" if len(kept) else "N/A",
    )

print()
print("=== FLAGGED CLEAN DETAILS ===")
print(clean[clean["shock_either"]][[
    "ticker","call_side","winner","correct","signal_status","initial_fair",
    "initial_remaining_min","initial_distance","drop_30s","fair_drop_30s","drop_4m","drop_6m"
]].to_string(index=False))

d.to_csv("kalshi_30s_early_shock_forward_aligned_details.csv", index=False)

print()
print("Saved: kalshi_30s_early_shock_forward_aligned_details.csv")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print("=== FORWARD-ALIGNED VALIDATION COMPLETE ===")
