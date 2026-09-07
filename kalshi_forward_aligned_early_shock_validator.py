from pathlib import Path
import csv
import pandas as pd
import numpy as np

LIVE = Path("kalshi_live_fair_value_shadow_log.csv")
OFFICIAL = Path("kalshi_official_settlement_check.csv")

print("=== KALSHI FORWARD-ALIGNED EARLY-SHOCK VALIDATOR ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Qualification: includes STRONG, matching forward scorer.")
print("Layer A timing: MAX deterioration observed within 4m / 6m horizons.")
print("Early shock timing: FIRST post-call snapshot, only if <= 60 seconds after call.")
print()
print("Frozen Layer A:")
print("  EARLY WARNING = max deterioration within 4m >= $100")
print("  LATE DANGER  = max deterioration within 6m >= $85")
print()
print("Early-shock candidates:")
print("  first <=60s distance deterioration >= $30")
print("  first <=60s original-side fair drop >= 5 percentage points")
print("  either condition")
print()
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
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

# Official settlements
official = pd.read_csv(OFFICIAL)
ot = pick(official.columns, ["ticker","contract_ticker","market_ticker"])
ow = pick(official.columns, ["official_side","winner","result","market_result"])
if ot is None or ow is None:
    raise SystemExit("ERROR: official settlement columns not found.")
official = official[[ot,ow]].copy()
official.columns = ["ticker","winner"]
official["ticker"] = official["ticker"].astype(str)
official["winner"] = official["winner"].astype(str).str.upper().str.strip()
official = official[official["winner"].isin(["UP","DOWN"])].drop_duplicates("ticker")

# Robust live-log parser
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

tc = pick(live.columns, ["ticker","contract_ticker","market_ticker"])
ts = pick(live.columns, ["timestamp_utc","timestamp","time_utc","snapshot_time"])
rm = pick(live.columns, ["remaining_min","minutes_left","time_left_min","time_remaining_min"])
dc = pick(live.columns, ["distance_target","distance_from_target","distance_to_target","target_distance","distance"])
sc = pick(live.columns, ["preferred_side","model_side","side"])
fu = pick(live.columns, ["fair_up","fair_up_probability","fair_up_prob"])
fd = pick(live.columns, ["fair_down","fair_down_probability","fair_down_prob"])
pf = pick(live.columns, ["preferred_fair","fair_value","preferred_side_fair"])
sig = pick(live.columns, ["signal_status","quality_tier","status"])

required = [tc,ts,rm,dc,sc]
if any(c is None for c in required):
    raise SystemExit(f"ERROR: required live columns missing. Available: {list(live.columns)}")

live[ts] = pd.to_datetime(live[ts], utc=True, errors="coerce")
for c in [rm,dc,fu,fd,pf]:
    if c is not None:
        live[c] = pd.to_numeric(live[c], errors="coerce")

live[tc] = live[tc].astype(str)
live[sc] = live[sc].astype(str).str.upper().str.strip()
live = live[live[ts].notna() & live[rm].notna() & live[dc].notna()].copy()

def sfair(row, side):
    if side == "UP" and fu is not None and pd.notna(row.get(fu, np.nan)):
        return float(row[fu])
    if side == "DOWN" and fd is not None and pd.notna(row.get(fd, np.nan)):
        return float(row[fd])
    if pf is not None and pd.notna(row.get(pf, np.nan)):
        return float(row[pf])
    return np.nan

def qualified_status(df):
    if sig is None:
        return pd.Series(True, index=df.index)
    s = df[sig].astype(str).str.upper().str.strip()
    return s.str.contains(r"STRONG|SUPPORTED|HIGH_QUALITY|EARLY_LOCK|LOCK", regex=True, na=False)

# First >=80 qualifying call, 8-12 min left
calls = []
for ticker, q in live.groupby(tc):
    q = q.sort_values(ts).copy()
    q = q[(q[rm] >= 8) & (q[rm] <= 12)]
    if q.empty:
        continue
    q["side_fair"] = q.apply(lambda r: sfair(r, r[sc]), axis=1)
    q["signed_distance"] = np.where(q[sc] == "UP", q[dc], -q[dc])
    q = q[
        q[sc].isin(["UP","DOWN"])
        & (q["side_fair"] >= 0.80)
        & qualified_status(q)
        & (q["signed_distance"] > 0)
    ]
    if not q.empty:
        calls.append(q.iloc[0])

calls = pd.DataFrame(calls)
calls = calls.merge(official, left_on=tc, right_on="ticker", how="inner")
calls["correct"] = calls[sc] == calls["winner"]

rows = []
for _, call in calls.iterrows():
    ticker = str(call[tc])
    side = str(call[sc])
    t0 = call[ts]
    initial_signed = float(call["signed_distance"])
    initial_fair = float(call["side_fair"])

    q = live[(live[tc] == ticker) & (live[ts] >= t0)].copy().sort_values(ts)
    q["sec_after"] = (q[ts] - t0).dt.total_seconds()
    q = q[(q["sec_after"] >= 0) & (q["sec_after"] <= 390)].copy()
    if q.empty:
        continue

    q["orig_signed"] = q[dc] if side == "UP" else -q[dc]
    q["deterioration"] = np.maximum(0.0, initial_signed - q["orig_signed"])

    if side == "UP" and fu is not None:
        q["orig_fair"] = q[fu]
    elif side == "DOWN" and fd is not None:
        q["orig_fair"] = q[fd]
    else:
        q["orig_fair"] = np.nan
    q["fair_drop"] = np.maximum(0.0, initial_fair - q["orig_fair"])

    # Forward scorer semantics: maximum deterioration inside horizon.
    q4 = q[q["sec_after"] <= 240]
    q6 = q[q["sec_after"] <= 360]
    drop4 = float(q4["deterioration"].max()) if len(q4) else np.nan
    drop6 = float(q6["deterioration"].max()) if len(q6) else np.nan

    early = pd.notna(drop4) and drop4 >= 100
    late = pd.notna(drop6) and drop6 >= 85

    if early and late:
        state = "CONFIRMED_DANGER"
    elif early:
        state = "EARLY_WARNING_ONLY"
    elif late:
        state = "LATE_DANGER_ONLY"
    else:
        state = "CLEAN"

    # First true post-call snapshot; no relabeling as "30 sec".
    post = q[q["sec_after"] > 0]
    if post.empty:
        continue
    first = post.iloc[0]
    first_sec = float(first["sec_after"])
    usable_early = first_sec <= 60.0

    first_drop = float(first["deterioration"]) if usable_early else np.nan
    first_fair_drop = float(first["fair_drop"]) if usable_early and pd.notna(first["fair_drop"]) else np.nan

    rows.append({
        "ticker": ticker,
        "call_time": t0,
        "call_side": side,
        "winner": call["winner"],
        "correct": bool(call["correct"]),
        "signal_status": call[sig] if sig is not None else "",
        "initial_fair": initial_fair,
        "initial_remaining_min": float(call[rm]),
        "initial_distance": float(call[dc]),
        "drop_4m_max": drop4,
        "drop_6m_max": drop6,
        "layer_a_state": state,
        "first_post_sec": first_sec,
        "early_sample_usable": usable_early,
        "first_post_distance_drop": first_drop,
        "first_post_fair_drop": first_fair_drop,
        "shock_distance": usable_early and first_drop >= 30,
        "shock_fair": usable_early and pd.notna(first_fair_drop) and first_fair_drop >= 0.05,
        "shock_either": usable_early and (
            first_drop >= 30 or (pd.notna(first_fair_drop) and first_fair_drop >= 0.05)
        )
    })

d = pd.DataFrame(rows).sort_values("call_time").reset_index(drop=True)

print("Official qualifying calls:", len(d))
print("Baseline accuracy:", f"{d['correct'].mean():.1%}")
print()

print("=== LAYER A STATE BREAKDOWN ===")
for state, g in d.groupby("layer_a_state"):
    print(state, "| n=",len(g),"| correct=",int(g["correct"].sum()),
          "| wrong=",int((~g["correct"]).sum()),
          "| accuracy=",f"{g['correct'].mean():.1%}")
print()

clean = d[d["layer_a_state"] == "CLEAN"].copy()
usable = clean[clean["early_sample_usable"]].copy()

print("=== CLEAN POPULATION ===")
print("CLEAN n:", len(clean))
print("CLEAN accuracy:", f"{clean['correct'].mean():.1%}" if len(clean) else "N/A")
print("CLEAN with first post-call sample <=60s:", len(usable))
print("Median first post-call delay:",
      f"{usable['first_post_sec'].median():.2f}s" if len(usable) else "N/A")
print()

TARGET = "KXBTC15M-26AUG251630-30"
print("=== TARGET CONTRACT ===")
tz = d[d["ticker"] == TARGET]
print(tz.to_string(index=False) if len(tz) else "TARGET MISSING")
print()

print("=== EARLY SHOCK TEST INSIDE TRUE FORWARD-ALIGNED CLEAN ===")
for col,label in [
    ("shock_distance","first <=60s distance drop >= $30"),
    ("shock_fair","first <=60s fair drop >= 5pt"),
    ("shock_either","either <=60s shock"),
]:
    flagged = usable[usable[col]]
    kept = clean[~clean["ticker"].isin(flagged["ticker"])]
    misses = int((~clean["correct"]).sum())
    caught = int((~flagged["correct"]).sum())
    good = int(flagged["correct"].sum())
    print(
        label,
        "| flagged=",len(flagged),
        "| mistakes_caught=",f"{caught}/{misses}",
        "| capture=",f"{caught/misses:.1%}" if misses else "N/A",
        "| good_flagged=",good,
        "| kept=",len(kept),
        "| kept_acc=",f"{kept['correct'].mean():.1%}" if len(kept) else "N/A"
    )
print()

print("=== CHRONOLOGICAL HOLDOUT: LAST 40% ===")
cut = int(np.floor(len(d)*0.60))
hold = d.iloc[cut:].copy()
hc = hold[hold["layer_a_state"] == "CLEAN"].copy()
hu = hc[hc["early_sample_usable"]].copy()
print("Holdout calls:", len(hold))
print("Holdout baseline accuracy:", f"{hold['correct'].mean():.1%}" if len(hold) else "N/A")
print("Holdout CLEAN:", len(hc), "| accuracy=", f"{hc['correct'].mean():.1%}" if len(hc) else "N/A")
print("Holdout CLEAN usable <=60s:", len(hu))
for col,label in [
    ("shock_distance","first <=60s distance drop >= $30"),
    ("shock_fair","first <=60s fair drop >= 5pt"),
    ("shock_either","either <=60s shock"),
]:
    flagged = hu[hu[col]]
    kept = hc[~hc["ticker"].isin(flagged["ticker"])]
    misses = int((~hc["correct"]).sum())
    caught = int((~flagged["correct"]).sum())
    good = int(flagged["correct"].sum())
    print(label,
          "| flagged=",len(flagged),
          "| mistakes_caught=",f"{caught}/{misses}",
          "| good_flagged=",good,
          "| kept=",len(kept),
          "| kept_acc=",f"{kept['correct'].mean():.1%}" if len(kept) else "N/A")
print()

print("=== FLAGGED CLEAN DETAILS ===")
flag = usable[usable["shock_either"]]
cols = [
    "ticker","call_side","winner","correct","signal_status","initial_fair",
    "initial_remaining_min","initial_distance","first_post_sec",
    "first_post_distance_drop","first_post_fair_drop",
    "drop_4m_max","drop_6m_max"
]
print(flag[cols].to_string(index=False) if len(flag) else "None")

d.to_csv("kalshi_forward_aligned_early_shock_details.csv", index=False)

print()
print("Saved: kalshi_forward_aligned_early_shock_details.csv")
print("Research validation only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print("=== VALIDATION COMPLETE ===")
