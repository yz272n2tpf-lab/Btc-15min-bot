from pathlib import Path
import pandas as pd
import numpy as np

MARKER = Path("layer_b_forward_validation_start_utc.txt")
LAYER_A_RESULTS = Path("kalshi_layer_a_forward_only_results.csv")
LIVE_LOG = Path("kalshi_live_fair_value_shadow_log.csv")

print("=== LAYER B FORWARD-ONLY SCORER ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print()
print("Frozen Layer A:")
print("  4m max deterioration >= $100")
print("  6m max deterioration >= $85")
print("Frozen Layer B research:")
print("  first real post-call sample <=60s")
print("  distance deterioration >= $30")
print("  original-side fair drop >= 5 percentage points")
print("  either condition")
print()
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

if not MARKER.exists():
    raise SystemExit("Missing layer_b_forward_validation_start_utc.txt")
if not LAYER_A_RESULTS.exists():
    raise SystemExit("Missing kalshi_layer_a_forward_only_results.csv. Run score_layer_a_forward_validation.py first.")
if not LIVE_LOG.exists():
    raise SystemExit("Missing kalshi_live_fair_value_shadow_log.csv")

start_utc = pd.to_datetime(MARKER.read_text().strip(), utc=True, errors="coerce")
if pd.isna(start_utc):
    raise SystemExit("Could not parse Layer B forward marker.")

# ---------- Layer A forward calls ----------
a = pd.read_csv(LAYER_A_RESULTS)
if "call_time" not in a.columns:
    raise SystemExit("Layer A results are missing call_time.")
a["call_time"] = pd.to_datetime(a["call_time"], utc=True, errors="coerce")
a = a[a["call_time"] >= start_utc].copy()

if a.empty:
    print("No Layer A forward calls after the Layer B marker yet.")
    raise SystemExit(0)

# Normalize expected columns.
for c in ["ticker", "call_side", "correct", "state", "initial_distance", "initial_fair"]:
    if c not in a.columns:
        raise SystemExit(f"Layer A results missing required column: {c}")

# ---------- Robust-ish live-log read ----------
# The current live log is expected to be parseable after the prior mixed-log fixes.
try:
    live = pd.read_csv(LIVE_LOG, on_bad_lines="skip", low_memory=False)
except Exception as e:
    raise SystemExit(f"Could not read live log: {e}")

# Column aliases seen in this project.
def first_col(candidates):
    for c in candidates:
        if c in live.columns:
            return c
    return None

ticker_col = first_col(["ticker", "contract", "market_ticker"])
ts_col = first_col(["timestamp_utc", "timestamp", "ts"])
dist_col = first_col(["distance_target", "distance_from_target", "distance"])
pref_col = first_col(["preferred_side", "side"])
fair_up_col = first_col(["fair_up"])
fair_down_col = first_col(["fair_down"])
pref_fair_col = first_col(["preferred_fair", "fair_value", "side_fair"])

need = {"ticker": ticker_col, "timestamp": ts_col, "distance": dist_col}
missing = [k for k,v in need.items() if v is None]
if missing:
    raise SystemExit(f"Live log missing required columns/aliases: {missing}")

live["_ts"] = pd.to_datetime(live[ts_col], utc=True, errors="coerce")
live["_dist"] = pd.to_numeric(live[dist_col], errors="coerce")
live = live.dropna(subset=["_ts", ticker_col, "_dist"]).copy()

def side_fair(row, side):
    if pref_fair_col is not None and pref_col is not None:
        if str(row.get(pref_col, "")).upper() == side:
            x = pd.to_numeric(pd.Series([row.get(pref_fair_col)]), errors="coerce").iloc[0]
            if pd.notna(x):
                return float(x)
    if side == "UP" and fair_up_col is not None:
        x = pd.to_numeric(pd.Series([row.get(fair_up_col)]), errors="coerce").iloc[0]
        return float(x) if pd.notna(x) else np.nan
    if side == "DOWN" and fair_down_col is not None:
        x = pd.to_numeric(pd.Series([row.get(fair_down_col)]), errors="coerce").iloc[0]
        return float(x) if pd.notna(x) else np.nan
    return np.nan

rows = []

for _, r in a.iterrows():
    ticker = str(r["ticker"])
    call_side = str(r["call_side"]).upper()
    call_time = r["call_time"]
    if pd.isna(call_time):
        continue

    x = live[(live[ticker_col].astype(str) == ticker) & (live["_ts"] > call_time)].copy()
    if x.empty:
        continue

    x["_delay"] = (x["_ts"] - call_time).dt.total_seconds()
    x = x[(x["_delay"] > 0) & (x["_delay"] <= 60)].sort_values("_ts")
    if x.empty:
        continue

    p = x.iloc[0]
    delay = float(p["_delay"])

    initial_distance = float(r["initial_distance"])
    initial_signed = initial_distance if call_side == "UP" else -initial_distance
    post_signed = float(p["_dist"]) if call_side == "UP" else -float(p["_dist"])
    distance_drop = max(0.0, initial_signed - post_signed)

    initial_fair = pd.to_numeric(pd.Series([r["initial_fair"]]), errors="coerce").iloc[0]
    post_fair = side_fair(p, call_side)
    fair_drop = np.nan
    if pd.notna(initial_fair) and pd.notna(post_fair):
        fair_drop = max(0.0, float(initial_fair) - float(post_fair))

    shock_distance = distance_drop >= 30.0
    shock_fair = pd.notna(fair_drop) and fair_drop >= 0.05
    shock_either = shock_distance or shock_fair

    rows.append({
        "ticker": ticker,
        "call_time": call_time,
        "call_side": call_side,
        "correct": bool(r["correct"]),
        "layer_a_state": r["state"],
        "initial_fair": initial_fair,
        "initial_distance": initial_distance,
        "first_post_sec": delay,
        "first_post_distance_drop": distance_drop,
        "first_post_fair_drop": fair_drop,
        "shock_distance": shock_distance,
        "shock_fair": shock_fair,
        "shock_either": shock_either,
    })

d = pd.DataFrame(rows)

if d.empty:
    print("No forward calls yet with a usable first post-call sample <=60s.")
    raise SystemExit(0)

out = Path("kalshi_layer_b_forward_only_results.csv")
d.to_csv(out, index=False)

print(f"Forward calls with usable <=60s sample: {len(d)}")
print()

clean = d[d["layer_a_state"].astype(str).str.upper() == "CLEAN"].copy()
print("=== LAYER A CLEAN FORWARD POPULATION ===")
print("CLEAN calls:", len(clean))
if len(clean):
    print(f"CLEAN accuracy: {clean['correct'].mean()*100:.1f}%")
    print("CLEAN wrong:", int((~clean["correct"]).sum()))
print()

def report(name, col):
    if clean.empty:
        return
    flagged = clean[clean[col]]
    kept = clean[~clean[col]]
    misses = clean[~clean["correct"]]
    caught = flagged[~flagged["correct"]]
    good_flagged = flagged[flagged["correct"]]
    print(
        f"{name} | flagged={len(flagged)} | "
        f"mistakes_caught={len(caught)}/{len(misses)} | "
        f"good_flagged={len(good_flagged)} | kept={len(kept)} | "
        f"kept_acc={(kept['correct'].mean()*100 if len(kept) else float('nan')):.1f}%"
    )

print("=== FROZEN LAYER B CHECK INSIDE CLEAN ===")
report("<=60s distance drop >= $30", "shock_distance")
report("<=60s fair drop >= 5pt", "shock_fair")
report("either <=60s shock", "shock_either")
print()

print("=== FORWARD CALL DETAILS ===")
cols = [
    "ticker","layer_a_state","correct","call_side","initial_fair",
    "first_post_sec","first_post_distance_drop","first_post_fair_drop",
    "shock_distance","shock_fair","shock_either"
]
print(d[cols].to_string(index=False))

print()
print("Saved:", out)
print("Frozen rules unchanged.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print("=== LAYER B FORWARD SCORING COMPLETE ===")
