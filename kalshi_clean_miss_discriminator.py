from pathlib import Path
import csv
import pandas as pd
import numpy as np

FWD = Path("kalshi_layer_a_forward_only_results.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")

print("=== KALSHI CLEAN-MISS DISCRIMINATOR ===")
print("Purpose: compare CLEAN forward winners vs CLEAN forward misses.")
print("Focus: FINAL 15-minute UP/DOWN only.")
print("Frozen Layer A rules changed: NO")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

if not FWD.exists():
    raise SystemExit("ERROR: kalshi_layer_a_forward_only_results.csv not found.")
if not LIVE.exists():
    raise SystemExit("ERROR: kalshi_live_fair_value_shadow_log.csv not found.")

f = pd.read_csv(FWD)
if f["correct"].dtype != bool:
    f["correct"] = f["correct"].astype(str).str.lower().map({"true": True, "false": False})

f["call_time"] = pd.to_datetime(f["call_time"], utc=True, errors="coerce")
for c in ["initial_fair","initial_remaining_min","initial_distance","drop_4m","drop_6m"]:
    if c in f.columns:
        f[c] = pd.to_numeric(f[c], errors="coerce")

clean = f[f["state"].astype(str).str.upper() == "CLEAN"].copy()

print("Forward calls total:", len(f))
print("CLEAN calls:", len(clean))
print("CLEAN correct:", int(clean["correct"].sum()))
print("CLEAN wrong:", int((~clean["correct"]).sum()))
print("CLEAN accuracy:", f"{clean['correct'].mean():.1%}" if len(clean) else "N/A")
print()

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

ticker_col = pick(live.columns, ["ticker","contract_ticker","market_ticker"])
time_col = pick(live.columns, ["timestamp_utc","timestamp","time_utc","snapshot_time"])
distance_col = pick(live.columns, ["distance_target","distance_from_target","distance_to_target","target_distance","distance"])
fair_up_col = pick(live.columns, ["fair_up","fair_up_probability","fair_up_prob"])
fair_down_col = pick(live.columns, ["fair_down","fair_down_probability","fair_down_prob"])
preferred_fair_col = pick(live.columns, ["preferred_fair","fair_value","preferred_side_fair"])
up_ask_col = pick(live.columns, ["up_ask","kalshi_up_ask","yes_ask"])
down_ask_col = pick(live.columns, ["down_ask","kalshi_down_ask","no_ask"])

if ticker_col is None or time_col is None or distance_col is None:
    print("Available live columns:", list(live.columns))
    raise SystemExit("ERROR: could not identify ticker/time/distance columns.")

live[time_col] = pd.to_datetime(live[time_col], utc=True, errors="coerce")
live[distance_col] = pd.to_numeric(live[distance_col], errors="coerce")
for c in [fair_up_col,fair_down_col,preferred_fair_col,up_ask_col,down_ask_col]:
    if c is not None:
        live[c] = pd.to_numeric(live[c], errors="coerce")

live = live[live[time_col].notna() & live[distance_col].notna() & live[ticker_col].notna()].copy()

print("Usable live snapshots:", len(live))
print("Distance column:", distance_col)
print("Fair UP:", fair_up_col or "not found")
print("Fair DOWN:", fair_down_col or "not found")
print("Preferred fair:", preferred_fair_col or "not found")
print("UP ask:", up_ask_col or "not found")
print("DOWN ask:", down_ask_col or "not found")
print()

def side_fair(row, side):
    c = fair_up_col if side == "UP" else fair_down_col
    if c is not None and pd.notna(row.get(c, np.nan)):
        return float(row[c])
    if preferred_fair_col is not None and pd.notna(row.get(preferred_fair_col, np.nan)):
        return float(row[preferred_fair_col])
    return np.nan

def side_ask(row, side):
    c = up_ask_col if side == "UP" else down_ask_col
    if c is not None and pd.notna(row.get(c, np.nan)):
        return float(row[c])
    return np.nan

rows = []

for _, r in clean.iterrows():
    ticker = str(r["ticker"])
    side = str(r.get("call_side","")).upper()
    call_time = r["call_time"]
    if side not in ("UP","DOWN") or pd.isna(call_time):
        continue

    q = live[(live[ticker_col].astype(str) == ticker) & (live[time_col] >= call_time)].copy()
    if q.empty:
        continue

    q = q.sort_values(time_col)
    q["sec_after"] = (q[time_col] - call_time).dt.total_seconds()
    q = q[(q["sec_after"] >= 0) & (q["sec_after"] <= 390)].copy()
    if q.empty:
        continue

    q["signed_distance"] = q[distance_col] if side == "UP" else -q[distance_col]
    q["side_fair"] = q.apply(lambda z: side_fair(z, side), axis=1)
    q["side_ask"] = q.apply(lambda z: side_ask(z, side), axis=1)

    initial_signed = float(r["initial_distance"]) if side == "UP" else -float(r["initial_distance"])
    start_fair = q.iloc[0]["side_fair"]
    start_ask = q.iloc[0]["side_ask"]

    rec = {
        "ticker": ticker,
        "correct": bool(r["correct"]),
        "call_side": side,
        "winner": r.get("official_side",""),
        "initial_fair": r.get("initial_fair", np.nan),
        "initial_remaining_min": r.get("initial_remaining_min", np.nan),
        "initial_distance": r.get("initial_distance", np.nan),
        "drop_4m": r.get("drop_4m", np.nan),
        "drop_6m": r.get("drop_6m", np.nan),
    }

    for seconds, label in [(30,"30s"),(60,"60s"),(90,"90s"),(120,"2m"),(180,"3m")]:
        idx = (q["sec_after"] - seconds).abs().idxmin()
        rr = q.loc[idx]
        if abs(float(rr["sec_after"]) - seconds) > 45:
            rec[f"distance_drop_{label}"] = np.nan
            rec[f"fair_drop_{label}"] = np.nan
            rec[f"ask_change_{label}"] = np.nan
            continue

        signed = float(rr["signed_distance"])
        rec[f"distance_drop_{label}"] = max(0.0, initial_signed - signed)

        sf = rr["side_fair"]
        rec[f"fair_drop_{label}"] = (
            max(0.0, float(start_fair) - float(sf))
            if pd.notna(start_fair) and pd.notna(sf) else np.nan
        )

        sa = rr["side_ask"]
        rec[f"ask_change_{label}"] = (
            float(sa) - float(start_ask)
            if pd.notna(start_ask) and pd.notna(sa) else np.nan
        )

    rows.append(rec)

x = pd.DataFrame(rows)
good = x[x["correct"]]
bad = x[~x["correct"]]

print("CLEAN calls with detailed trajectory:", len(x))
print()

print("=== CLEAN MISSES ===")
if bad.empty:
    print("No CLEAN misses.")
else:
    for _, r in bad.iterrows():
        print(
            r["ticker"],
            "| call=", r["call_side"],
            "| winner=", r["winner"],
            "| fair=", f"{float(r['initial_fair']):.1%}" if pd.notna(r["initial_fair"]) else "NA",
            "| left=", f"{float(r['initial_remaining_min']):.2f}" if pd.notna(r["initial_remaining_min"]) else "NA",
            "| dist=", f"${float(r['initial_distance']):+.2f}",
            "| 30s_drop=", f"${float(r['distance_drop_30s']):.2f}" if pd.notna(r["distance_drop_30s"]) else "NA",
            "| 60s_drop=", f"${float(r['distance_drop_60s']):.2f}" if pd.notna(r["distance_drop_60s"]) else "NA",
            "| 90s_drop=", f"${float(r['distance_drop_90s']):.2f}" if pd.notna(r["distance_drop_90s"]) else "NA",
            "| 2m_drop=", f"${float(r['distance_drop_2m']):.2f}" if pd.notna(r["distance_drop_2m"]) else "NA",
            "| fair2m_drop=", f"{float(r['fair_drop_2m']):.1%}" if pd.notna(r["fair_drop_2m"]) else "NA",
            "| ask2m_change=", f"{float(r['ask_change_2m']):+.3f}" if pd.notna(r["ask_change_2m"]) else "NA",
            "| 4m=", f"${float(r['drop_4m']):.2f}",
            "| 6m=", f"${float(r['drop_6m']):.2f}",
        )

print()
print("=== CLEAN WINNER VS MISS SUMMARY ===")

fields = [
    "initial_fair","initial_remaining_min","initial_distance",
    "distance_drop_30s","distance_drop_60s","distance_drop_90s","distance_drop_2m","distance_drop_3m",
    "fair_drop_30s","fair_drop_60s","fair_drop_90s","fair_drop_2m","fair_drop_3m",
    "ask_change_30s","ask_change_60s","ask_change_90s","ask_change_2m","ask_change_3m",
    "drop_4m","drop_6m"
]

for c in fields:
    if c not in x.columns:
        continue
    g = pd.to_numeric(good[c], errors="coerce").dropna()
    b = pd.to_numeric(bad[c], errors="coerce").dropna()
    if len(g) == 0 and len(b) == 0:
        continue
    print(
        c,
        "| GOOD median=", f"{g.median():.4f}" if len(g) else "NA",
        "| GOOD min=", f"{g.min():.4f}" if len(g) else "NA",
        "| GOOD max=", f"{g.max():.4f}" if len(g) else "NA",
        "| BAD=", ",".join(f"{v:.4f}" for v in b.tolist()) if len(b) else "NA",
    )

print()
print("=== SIMPLE CLEAN-MISS WARNING SEARCH ===")
print("Diagnostic only. DO NOT install thresholds from this sample.")
print()

rules = []

def add_rule(name, mask):
    mask = mask.fillna(False)
    flagged = x[mask]
    clean2 = x[~mask]
    rules.append({
        "rule": name,
        "flagged": len(flagged),
        "mistakes_caught": int((~flagged["correct"]).sum()) if len(flagged) else 0,
        "good_flagged": int(flagged["correct"].sum()) if len(flagged) else 0,
        "clean_n": len(clean2),
        "clean_accuracy": clean2["correct"].mean() if len(clean2) else np.nan,
    })

for label in ["30s","60s","90s","2m","3m"]:
    c = f"distance_drop_{label}"
    if c in x.columns:
        for cut in [10,20,30,40,50,60,75]:
            add_rule(f"{label} distance_drop >= ${cut}", x[c] >= cut)

for label in ["30s","60s","90s","2m","3m"]:
    c = f"fair_drop_{label}"
    if c in x.columns and x[c].notna().any():
        for cut in [0.02,0.03,0.05,0.07,0.10]:
            add_rule(f"{label} fair_drop >= {cut:.0%}", x[c] >= cut)

for label in ["30s","60s","90s","2m","3m"]:
    c = f"ask_change_{label}"
    if c in x.columns and x[c].notna().any():
        for cut in [-0.03,-0.05,-0.08,-0.10,-0.15]:
            add_rule(f"{label} ask_change <= {cut:+.0%}", x[c] <= cut)

for lo, hi in [(0,50),(50,100),(100,150),(150,250),(250,9999)]:
    add_rule(
        f"abs(initial_distance) ${lo}-${hi}",
        x["initial_distance"].abs().between(lo, hi, inclusive="left")
    )

for lo, hi in [(8,9),(9,10),(10,11),(11,12)]:
    add_rule(
        f"initial remaining {lo}-{hi}m",
        x["initial_remaining_min"].between(lo, hi, inclusive="left")
    )

rr = pd.DataFrame(rules).sort_values(
    ["mistakes_caught","good_flagged","clean_accuracy"],
    ascending=[False,True,False]
)

print(rr.head(30)[[
    "rule","flagged","mistakes_caught","good_flagged","clean_n","clean_accuracy"
]].to_string(index=False))

x.to_csv("kalshi_clean_miss_discriminator_details.csv", index=False)
rr.to_csv("kalshi_clean_miss_discriminator_rules.csv", index=False)

print()
print("=== FILES CREATED ===")
print("kalshi_clean_miss_discriminator_details.csv")
print("kalshi_clean_miss_discriminator_rules.csv")
print()
print("IMPORTANT:")
print("Diagnostic only.")
print("Frozen Layer A thresholds remain unchanged.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()
print("=== CLEAN-MISS DISCRIMINATOR COMPLETE ===")
