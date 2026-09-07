from pathlib import Path
import csv
import re
import math
import pandas as pd
import numpy as np

LIVE = Path("kalshi_live_fair_value_shadow_log.csv")
OFFICIAL = Path("kalshi_official_settlement_check.csv")
OUT = Path("kalshi_official_truth_layer_a_rescore_details.csv")

print("=== KALSHI OFFICIAL-TRUTH LAYER A RESCORER ===")
print("Purpose: re-score frozen Layer A against OFFICIAL Kalshi settlement only.")
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

def read_mixed_csv(path: Path) -> pd.DataFrame:
    """
    Handles a CSV whose schema/header changed during collection.
    Every repeated header beginning with timestamp_utc starts a new schema block.
    """
    rows = []
    header = None
    with path.open("r", newline="", encoding="utf-8-sig", errors="replace") as f:
        rd = csv.reader(f)
        for raw in rd:
            if not raw:
                continue
            first = str(raw[0]).strip()
            if first == "timestamp_utc":
                header = [str(x).strip() for x in raw]
                continue
            if header is None:
                continue
            if len(raw) < 2:
                continue
            # tolerate extra/missing fields without throwing away the whole line
            vals = list(raw[:len(header)])
            if len(vals) < len(header):
                vals += [""] * (len(header) - len(vals))
            rows.append(dict(zip(header, vals)))
    if not rows:
        raise SystemExit(f"ERROR: no usable rows parsed from {path}")
    return pd.DataFrame(rows)

def pick(cols, names):
    for n in names:
        if n in cols:
            return n
    return None

def norm_side(x):
    s = str(x).strip().upper()
    if s in {"UP","YES","Y","TRUE","1"}:
        return "UP"
    if s in {"DOWN","NO","N","FALSE","0"}:
        return "DOWN"
    return None

def num(s):
    return pd.to_numeric(s, errors="coerce")

def first_official_side(df):
    result_col = pick(df.columns, ["result","official_result","winner","settlement_result","official_side","side"])
    if result_col is None:
        raise SystemExit("ERROR: official result column not found.")
    out = df.copy()
    out["official_side"] = out[result_col].map(norm_side)
    # keep finalized rows if a status column exists
    status_col = pick(out.columns, ["status","market_status"])
    if status_col:
        st = out[status_col].astype(str).str.lower()
        finalized = st.str.contains("final|settled|closed", regex=True, na=False)
        if finalized.any():
            out = out[finalized].copy()
    tick = pick(out.columns, ["ticker","market_ticker","symbol"])
    if tick is None:
        raise SystemExit("ERROR: ticker column not found in official file.")
    out[tick] = out[tick].astype(str)
    out = out[out["official_side"].notna()].copy()
    return out.groupby(tick, as_index=False).tail(1)[[tick,"official_side"]].rename(columns={tick:"ticker"})

if not LIVE.exists():
    raise SystemExit(f"ERROR: missing {LIVE}")
if not OFFICIAL.exists():
    raise SystemExit(f"ERROR: missing {OFFICIAL}")

live = read_mixed_csv(LIVE)
official_raw = pd.read_csv(OFFICIAL, low_memory=False)
official = first_official_side(official_raw)

ticker_col = pick(live.columns, ["ticker","market_ticker","symbol"])
time_col = pick(live.columns, ["timestamp_utc","timestamp","time"])
dist_col = pick(live.columns, ["distance_target","distance_from_target","distance_to_target","target_distance","distance"])
side_col = pick(live.columns, ["preferred_side","current_target_side","current_side"])
status_col = pick(live.columns, ["signal_status","entry_status","status"])
remaining_col = pick(live.columns, ["remaining_min","time_left_min","minutes_left"])
fair_up_col = pick(live.columns, ["fair_up"])
fair_down_col = pick(live.columns, ["fair_down"])
fair_pref_col = pick(live.columns, ["fair_preferred","preferred_fair"])

missing = [n for n,v in {
    "ticker":ticker_col, "time":time_col, "distance":dist_col, "side":side_col,
    "status":status_col, "remaining_min":remaining_col
}.items() if v is None]
if missing:
    raise SystemExit("ERROR: missing live columns: " + ", ".join(missing))

live = live.copy()
live["ticker"] = live[ticker_col].astype(str)
live["ts"] = pd.to_datetime(live[time_col], utc=True, errors="coerce")
live["distance_target_num"] = num(live[dist_col])
live["remaining_num"] = num(live[remaining_col])
live["call_side_candidate"] = live[side_col].map(norm_side)
live["signal_status_norm"] = live[status_col].astype(str).str.upper().str.strip()

if fair_pref_col:
    live["fair_pref_num"] = num(live[fair_pref_col])
else:
    if fair_up_col is None or fair_down_col is None:
        raise SystemExit("ERROR: need fair_preferred OR fair_up/fair_down columns.")
    live["fair_up_num"] = num(live[fair_up_col])
    live["fair_down_num"] = num(live[fair_down_col])
    live["fair_pref_num"] = np.where(
        live["call_side_candidate"].eq("UP"),
        live["fair_up_num"],
        np.where(live["call_side_candidate"].eq("DOWN"), live["fair_down_num"], np.nan)
    )

# Normalize percentages accidentally logged as 80 instead of .80, if any.
live.loc[live["fair_pref_num"] > 1.5, "fair_pref_num"] /= 100.0

live = live.dropna(subset=["ticker","ts","distance_target_num","remaining_num","call_side_candidate","fair_pref_num"])
live = live.sort_values(["ticker","ts"]).reset_index(drop=True)

# Forward-aligned qualifying status family.
supported_like = live["signal_status_norm"].str.contains(
    r"STRONG|SUPPORTED|HIGH_QUALITY|EARLY_LOCK|LOCK", regex=True, na=False
)

# Final-call qualification: first >=80% supported-like call in the 8-12 minute zone.
qual = live[
    supported_like
    & live["fair_pref_num"].ge(0.80)
    & live["remaining_num"].between(8.0, 12.0, inclusive="both")
].copy()

if qual.empty:
    raise SystemExit("ERROR: no qualifying calls found.")

qual = qual.sort_values(["ticker","ts"]).groupby("ticker", as_index=False).head(1).copy()

official_map = dict(zip(official["ticker"], official["official_side"]))
qual["official_side"] = qual["ticker"].map(official_map)
qual = qual[qual["official_side"].notna()].copy()

def signed_distance(distance, side):
    return distance if side == "UP" else -distance

def trajectory_metrics(callrow):
    ticker = callrow["ticker"]
    call_time = callrow["ts"]
    side = callrow["call_side_candidate"]
    init_signed = signed_distance(float(callrow["distance_target_num"]), side)

    q = live[(live["ticker"] == ticker) & (live["ts"] >= call_time)].copy()
    if q.empty:
        return pd.Series({"initial_signed_distance":init_signed,
                          "drop_4m":np.nan, "drop_6m":np.nan})

    q["sec_from_call"] = (q["ts"] - call_time).dt.total_seconds()
    q["signed_distance"] = np.where(side == "UP",
                                    q["distance_target_num"],
                                    -q["distance_target_num"])

    def max_deterioration(sec):
        z = q[(q["sec_from_call"] >= 0) & (q["sec_from_call"] <= sec)]
        if z.empty:
            return np.nan
        # Frozen Layer A meaning: maximum deterioration observed WITHIN horizon.
        return max(0.0, init_signed - float(z["signed_distance"].min()))

    return pd.Series({
        "initial_signed_distance": init_signed,
        "drop_4m": max_deterioration(240),
        "drop_6m": max_deterioration(360),
    })

metrics = qual.apply(trajectory_metrics, axis=1)
d = pd.concat([qual.reset_index(drop=True), metrics.reset_index(drop=True)], axis=1)
d = d.dropna(subset=["drop_4m","drop_6m"]).copy()

d["call_side"] = d["call_side_candidate"]
d["correct"] = d["call_side"].eq(d["official_side"])

# FROZEN LAYER A
d["early_warning"] = d["drop_4m"] >= 100.0
d["late_danger"] = d["drop_6m"] >= 85.0
d["layer_a_state"] = np.select(
    [
        (~d["early_warning"]) & (~d["late_danger"]),
        d["early_warning"] & (~d["late_danger"]),
        (~d["early_warning"]) & d["late_danger"],
        d["early_warning"] & d["late_danger"],
    ],
    ["CLEAN","EARLY_WARNING_ONLY","LATE_DANGER_ONLY","CONFIRMED_DANGER"],
    default="UNKNOWN"
)
d["warned"] = d["layer_a_state"].ne("CLEAN")

# Chronological ordering for holdout.
d = d.sort_values("ts").reset_index(drop=True)
hold_n = max(1, int(math.ceil(len(d) * 0.40)))
hold = d.tail(hold_n).copy()

def pct(a,b):
    return 100.0*a/b if b else float("nan")

def print_block(label, z):
    print(f"\n=== {label} ===")
    print(f"Calls: {len(z)}")
    print(f"Correct: {int(z.correct.sum())}")
    print(f"Wrong: {int((~z.correct).sum())}")
    print(f"Baseline accuracy: {pct(z.correct.sum(), len(z)):.1f}%")

    for state in ["CLEAN","EARLY_WARNING_ONLY","LATE_DANGER_ONLY","CONFIRMED_DANGER"]:
        s = z[z.layer_a_state.eq(state)]
        if len(s):
            print(f"{state:20s} n={len(s):3d} | correct={int(s.correct.sum()):3d} | "
                  f"wrong={int((~s.correct).sum()):3d} | accuracy={pct(s.correct.sum(),len(s)):.1f}%")

    misses = ~z.correct
    warned = z.warned
    caught = misses & warned
    good_warned = z.correct & warned
    clean = ~warned
    print("\n--- LAYER A CHECK ---")
    print(f"Total misses: {int(misses.sum())}")
    print(f"Warned calls: {int(warned.sum())}")
    print(f"Misses caught: {int(caught.sum())}")
    print(f"Miss capture: {pct(caught.sum(), misses.sum()):.1f}%")
    print(f"Good calls warned: {int(good_warned.sum())}")
    if clean.sum():
        print(f"CLEAN accuracy: {int((z.correct & clean).sum())}/{int(clean.sum())} "
              f"= {pct((z.correct & clean).sum(), clean.sum()):.1f}%")

    print("\n--- BY INITIAL FAIR ---")
    for th in [0.80,0.85,0.90,0.92,0.95]:
        s = z[z.fair_pref_num >= th]
        if len(s):
            print(f">={int(th*100)}% fair | n={len(s):3d} | "
                  f"correct={int(s.correct.sum()):3d} | accuracy={pct(s.correct.sum(),len(s)):.1f}%")
            sc = s[s.layer_a_state.eq("CLEAN")]
            if len(sc):
                print(f"   CLEAN only | n={len(sc):3d} | correct={int(sc.correct.sum()):3d} | "
                      f"accuracy={pct(sc.correct.sum(),len(sc)):.1f}%")

print(f"Officially settled qualifying calls with usable Layer A trajectory: {len(d)}")
print_block("FULL OFFICIAL-TRUTH SAMPLE", d)
print_block("CHRONOLOGICAL HOLDOUT: LAST 40%", hold)

print("\n=== CLEAN MISSES ===")
cm = d[(d.layer_a_state == "CLEAN") & (~d.correct)]
cols = ["ticker","ts","call_side","official_side","fair_pref_num",
        "remaining_num","initial_signed_distance","drop_4m","drop_6m"]
if len(cm):
    print(cm[cols].to_string(index=False))
else:
    print("None")

d.to_csv(OUT, index=False)
print(f"\nSaved: {OUT}")
print("=== RESCORE COMPLETE ===")
print("Official Kalshi settlement is the truth label.")
print("Frozen Layer A thresholds unchanged: 4m >= $100, 6m >= $85.")
print("No live rule installed. No bot.py changes.")
