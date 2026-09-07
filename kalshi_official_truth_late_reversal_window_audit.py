from pathlib import Path
import csv
import math
import numpy as np
import pandas as pd

TARGET = "KXBTC15M-26AUG270615-15"
RESCORE = Path("kalshi_official_truth_layer_a_rescore_details.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")

print("=== KALSHI LATE-REVERSAL WINDOW AUDIT ===")
print("Purpose: isolate the stubborn CLEAN miss and compare its FINAL 3 minutes against CLEAN winners.")
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print("Target:", TARGET)

def first_col(cols, names):
    lower = {str(c).lower(): c for c in cols}
    for n in names:
        if n.lower() in lower:
            return lower[n.lower()]
    for c in cols:
        cl = str(c).lower()
        for n in names:
            if n.lower() in cl:
                return c
    return None

def read_mixed_csv(path):
    rows = []
    with open(path, "r", newline="", encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f)
        for r in rdr:
            if r:
                rows.append(r)
    if not rows:
        raise SystemExit(f"ERROR: {path} is empty.")

    header = rows[0]
    maxlen = max(len(r) for r in rows)
    names = list(header) + [f"__extra_{i}" for i in range(len(header), maxlen)]

    data = []
    for r in rows[1:]:
        if len(r) < maxlen:
            r = r + [""] * (maxlen - len(r))
        elif len(r) > maxlen:
            r = r[:maxlen]
        data.append(r)

    return pd.DataFrame(data, columns=names)

if not RESCORE.exists():
    raise SystemExit(f"ERROR: missing {RESCORE}")
if not LIVE.exists():
    raise SystemExit(f"ERROR: missing {LIVE}")

r = pd.read_csv(RESCORE, low_memory=False)
live = read_mixed_csv(LIVE)

# ---------- rescore columns ----------
rticker = first_col(r.columns, ["ticker"])
rstate = first_col(r.columns, ["state", "layer_a_state"])
rcorrect = first_col(r.columns, ["correct"])
rcall = first_col(r.columns, ["call_side"])
rtime = first_col(r.columns, ["ts", "call_time", "timestamp"])
rfair = first_col(r.columns, ["fair_pref_num", "initial_fair", "fair"])
rdist = first_col(r.columns, ["initial_signed_distance", "rescore_initial_signed_distance"])

need = {"ticker": rticker, "state": rstate, "correct": rcorrect, "call_side": rcall, "time": rtime}
missing = [k for k,v in need.items() if v is None]
if missing:
    print("Rescore columns:", list(r.columns))
    raise SystemExit("ERROR: missing rescore columns: " + ", ".join(missing))

r["_ticker"] = r[rticker].astype(str)
r["_state"] = r[rstate].astype(str).str.upper()
r["_correct"] = r[rcorrect].astype(str).str.lower().isin(["true","1","yes"])
r["_call_side"] = r[rcall].astype(str).str.upper()
r["_call_time"] = pd.to_datetime(r[rtime], utc=True, errors="coerce")

clean = r[r["_state"].str.contains("CLEAN", na=False)].copy()
clean_winners = clean[clean["_correct"]].copy()
target_row = clean[clean["_ticker"] == TARGET]

if target_row.empty:
    raise SystemExit("ERROR: target CLEAN miss not found in rescore details.")
target_row = target_row.iloc[0]

print(f"\nCLEAN calls in rescore: {len(clean)}")
print(f"CLEAN winners: {len(clean_winners)}")
print(f"CLEAN misses: {len(clean) - len(clean_winners)}")

# ---------- live columns ----------
lticker = first_col(live.columns, ["ticker"])
ltime = first_col(live.columns, ["timestamp_utc", "timestamp"])
lrem = first_col(live.columns, ["remaining_min", "remaining"])
ldist = first_col(live.columns, ["distance_target", "distance_from_target", "distance"])
lpref = first_col(live.columns, ["preferred_side", "current_side"])
lfair_up = first_col(live.columns, ["fair_up"])
lfair_down = first_col(live.columns, ["fair_down"])
lfair_pref = first_col(live.columns, ["fair_preferred", "fair_pref"])
lask = first_col(live.columns, ["preferred_ask"])
lupask = first_col(live.columns, ["up_ask"])
ldownask = first_col(live.columns, ["down_ask"])
lstatus = first_col(live.columns, ["signal_status", "status"])

need_live = {"ticker": lticker, "time": ltime, "remaining": lrem, "distance": ldist}
missing_live = [k for k,v in need_live.items() if v is None]
if missing_live:
    print("Live columns:", list(live.columns))
    raise SystemExit("ERROR: missing live columns: " + ", ".join(missing_live))

live["_ticker"] = live[lticker].astype(str)
live["_time"] = pd.to_datetime(live[ltime], utc=True, errors="coerce")
live["_remaining"] = pd.to_numeric(live[lrem], errors="coerce")
live["_distance"] = pd.to_numeric(live[ldist], errors="coerce")

def numcol(c):
    if c is None:
        return pd.Series(np.nan, index=live.index)
    return pd.to_numeric(live[c], errors="coerce")

live["_fair_up"] = numcol(lfair_up)
live["_fair_down"] = numcol(lfair_down)
live["_fair_pref_logged"] = numcol(lfair_pref)
live["_preferred_ask"] = numcol(lask)
live["_up_ask"] = numcol(lupask)
live["_down_ask"] = numcol(ldownask)

def path_for(row):
    tick = str(row["_ticker"])
    side = str(row["_call_side"]).upper()
    ct = row["_call_time"]
    q = live[(live["_ticker"] == tick) & live["_time"].notna() & live["_remaining"].notna()].copy()
    q = q.sort_values("_time")
    if pd.notna(ct):
        q = q[q["_time"] >= ct - pd.Timedelta(seconds=5)]
    if q.empty:
        return q

    # signed distance in ORIGINAL CALL direction
    if side == "DOWN":
        q["_signed_distance"] = -q["_distance"]
    else:
        q["_signed_distance"] = q["_distance"]

    # fair value in ORIGINAL CALL direction
    if side == "DOWN":
        q["_call_fair"] = q["_fair_down"]
        q["_call_ask"] = q["_down_ask"]
    else:
        q["_call_fair"] = q["_fair_up"]
        q["_call_ask"] = q["_up_ask"]

    # fallbacks
    q["_call_fair"] = q["_call_fair"].where(q["_call_fair"].notna(), q["_fair_pref_logged"])
    q["_call_ask"] = q["_call_ask"].where(q["_call_ask"].notna(), q["_preferred_ask"])
    q["_call_side"] = side
    q["_status"] = live.loc[q.index, lstatus].astype(str) if lstatus else ""
    return q

def nearest_remaining(q, target_min, tol=0.70):
    if q.empty:
        return None
    z = q.copy()
    z["_err"] = (z["_remaining"] - target_min).abs()
    z = z.sort_values(["_err", "_time"])
    if z.empty or float(z.iloc[0]["_err"]) > tol:
        return None
    return z.iloc[0]

def metric_row(row):
    q = path_for(row)
    out = {
        "ticker": row["_ticker"],
        "correct": bool(row["_correct"]),
        "call_side": row["_call_side"],
        "initial_fair": pd.to_numeric(pd.Series([row[rfair] if rfair else np.nan]), errors="coerce").iloc[0],
        "initial_signed_distance": pd.to_numeric(pd.Series([row[rdist] if rdist else np.nan]), errors="coerce").iloc[0],
        "snapshots": len(q),
    }
    if q.empty:
        return out

    marks = [3.0, 2.0, 1.5, 1.0, 0.5]
    for m in marks:
        s = nearest_remaining(q, m)
        tag = str(m).replace(".","p")
        out[f"rem_{tag}"] = np.nan if s is None else float(s["_remaining"])
        out[f"dist_{tag}"] = np.nan if s is None else float(s["_signed_distance"])
        out[f"fair_{tag}"] = np.nan if s is None else float(s["_call_fair"]) if pd.notna(s["_call_fair"]) else np.nan
        out[f"ask_{tag}"] = np.nan if s is None else float(s["_call_ask"]) if pd.notna(s["_call_ask"]) else np.nan

    # first actual side flip versus original call side
    flip = q[q["_signed_distance"] < 0]
    out["first_flip_remaining"] = np.nan if flip.empty else float(flip.iloc[0]["_remaining"])

    # first late fair breaks
    for th in [0.75, 0.60, 0.50, 0.25]:
        z = q[q["_call_fair"] < th]
        out[f"first_fair_below_{int(th*100)}_remaining"] = np.nan if z.empty else float(z.iloc[0]["_remaining"])

    late3 = q[q["_remaining"] <= 3.2].copy()
    if not late3.empty:
        out["late3_min_distance"] = float(late3["_signed_distance"].min())
        out["late3_max_distance"] = float(late3["_signed_distance"].max())
        out["late3_min_fair"] = float(late3["_call_fair"].min()) if late3["_call_fair"].notna().any() else np.nan
        out["late3_max_fair"] = float(late3["_call_fair"].max()) if late3["_call_fair"].notna().any() else np.nan

    # drops between named late checkpoints
    for a,b in [(3.0,2.0),(2.0,1.0),(1.5,0.5),(1.0,0.5)]:
        sa, sb = nearest_remaining(q,a), nearest_remaining(q,b)
        key = f"{str(a).replace('.','p')}_to_{str(b).replace('.','p')}"
        if sa is not None and sb is not None:
            out[f"distance_change_{key}"] = float(sb["_signed_distance"] - sa["_signed_distance"])
            if pd.notna(sa["_call_fair"]) and pd.notna(sb["_call_fair"]):
                out[f"fair_change_{key}"] = float(sb["_call_fair"] - sa["_call_fair"])
            if pd.notna(sa["_call_ask"]) and pd.notna(sb["_call_ask"]):
                out[f"ask_change_{key}"] = float(sb["_call_ask"] - sa["_call_ask"])
    return out

rows = [metric_row(target_row)] + [metric_row(x) for _,x in clean_winners.iterrows()]
m = pd.DataFrame(rows)
t = m[m["ticker"] == TARGET].iloc[0]
w = m[(m["ticker"] != TARGET) & (m["correct"] == True)].copy()

print("\n=== TARGET FINAL PATH ===")
tq = path_for(target_row)
show_cols = ["_time","_remaining","_signed_distance","_call_fair","_call_ask","_status"]
show_cols = [c for c in show_cols if c in tq.columns]
late = tq[tq["_remaining"] <= 3.5]
print(late[show_cols].to_string(index=False) if len(late) else "No target snapshots inside final 3.5 minutes.")

print("\n=== TARGET LATE-WINDOW METRICS ===")
for c in m.columns:
    if c in ("ticker","correct","call_side","snapshots"):
        continue
    v = t.get(c, np.nan)
    if pd.notna(v):
        print(f"{c}: {v}")

print("\n=== CLEAN WINNER COMPARISON ===")
metrics = [
    "dist_3p0","dist_2p0","dist_1p5","dist_1p0","dist_0p5",
    "fair_3p0","fair_2p0","fair_1p5","fair_1p0","fair_0p5",
    "first_flip_remaining","first_fair_below_75_remaining",
    "first_fair_below_60_remaining","first_fair_below_50_remaining",
    "late3_min_distance","late3_min_fair",
    "distance_change_3p0_to_2p0","distance_change_2p0_to_1p0",
    "distance_change_1p5_to_0p5","distance_change_1p0_to_0p5",
    "fair_change_3p0_to_2p0","fair_change_2p0_to_1p0",
    "fair_change_1p5_to_0p5","fair_change_1p0_to_0p5",
]
for c in metrics:
    if c not in m.columns:
        continue
    vals = pd.to_numeric(w[c], errors="coerce").dropna()
    tv = pd.to_numeric(pd.Series([t.get(c, np.nan)]), errors="coerce").iloc[0]
    if len(vals):
        print(f"{c:36s} winners n={len(vals):2d} med={vals.median():8.3f} min={vals.min():8.3f} max={vals.max():8.3f} | target={tv if pd.notna(tv) else np.nan}")

print("\n=== SIMPLE LATE-REVERSAL DIAGNOSTICS ===")
print("Diagnostic only. These are NOT live rules.")
candidates = []

# Candidate thresholds chosen from intuitive late-window breaks, not optimized for profit.
tests = [
    ("final side flipped by <=1.5m", lambda d: pd.to_numeric(d["first_flip_remaining"], errors="coerce").notna() & (pd.to_numeric(d["first_flip_remaining"], errors="coerce") <= 1.5)),
    ("final side flipped at all", lambda d: pd.to_numeric(d["first_flip_remaining"], errors="coerce").notna()),
    ("late3 min distance < $0", lambda d: pd.to_numeric(d["late3_min_distance"], errors="coerce") < 0),
    ("late3 min distance < -$25", lambda d: pd.to_numeric(d["late3_min_distance"], errors="coerce") < -25),
    ("late3 min fair < 50%", lambda d: pd.to_numeric(d["late3_min_fair"], errors="coerce") < 0.50),
    ("late3 min fair < 25%", lambda d: pd.to_numeric(d["late3_min_fair"], errors="coerce") < 0.25),
]

for name, fn in tests:
    try:
        flags = fn(m).fillna(False)
        target_flag = bool(flags[m["ticker"] == TARGET].iloc[0])
        good_flagged = int(flags[(m["ticker"] != TARGET) & (m["correct"] == True)].sum())
        print(f"{name:32s} | target_flag={target_flag} | clean_winners_flagged={good_flagged}/{len(w)}")
    except Exception as e:
        print(name, "| skipped:", e)

out = Path("kalshi_official_truth_late_reversal_window_audit.csv")
m.to_csv(out, index=False)
print("\nSaved:", out)
print("=== LATE-REVERSAL WINDOW AUDIT COMPLETE ===")
print("Research only. No rule installed.")
