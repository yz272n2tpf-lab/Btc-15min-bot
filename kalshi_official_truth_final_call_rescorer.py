from pathlib import Path
import pandas as pd
import numpy as np

print("=== KALSHI OFFICIAL-TRUTH FINAL-CALL RESCORER ===")
print("Purpose: re-score qualified FINAL 15-minute calls against OFFICIAL Kalshi settlement,")
print("         and isolate near-strike proxy disagreements without using them as truth.")
print()
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

LIVE = Path("kalshi_live_fair_value_shadow_log.csv")
OFFICIAL = Path("kalshi_official_settlement_check.csv")
OUT = Path("kalshi_official_truth_final_call_rescore_details.csv")

if not LIVE.exists():
    raise SystemExit(f"ERROR: missing {LIVE}")
if not OFFICIAL.exists():
    raise SystemExit(f"ERROR: missing {OFFICIAL}")

def read_mixed_csv(path):
    # The live file has had schema changes over time. Keep malformed historical rows
    # from crashing the audit, while preserving normal rows.
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return pd.read_csv(path, low_memory=False, engine="python", on_bad_lines="skip")

def pick(cols, names, required=True):
    low = {str(c).lower(): c for c in cols}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    if required:
        raise SystemExit(f"ERROR: none of these columns found: {names}")
    return None

live = read_mixed_csv(LIVE)
off = read_mixed_csv(OFFICIAL)

lticker = pick(live.columns, ["ticker","market_ticker","contract_ticker"])
lts = pick(live.columns, ["timestamp_utc","timestamp","time","datetime"])
lrem = pick(live.columns, ["remaining_min","remaining","minutes_left"])
ldist = pick(live.columns, ["distance_target","distance_from_target","distance_to_target","target_distance","distance"])
lfair_up = pick(live.columns, ["fair_up"], required=False)
lfair_down = pick(live.columns, ["fair_down"], required=False)
lpref = pick(live.columns, ["preferred_side","current_target_side","current_side"], required=False)
lstatus = pick(live.columns, ["signal_status","status"], required=False)
ltarget = pick(live.columns, ["target","target_price","strike","contract_target","start_price"], required=False)
lbtc = pick(live.columns, ["coinbase_close","btc_price","bitcoin_price","underlying_price","spot_price"], required=False)

oticker = pick(off.columns, ["ticker","market_ticker","contract_ticker"])
ores = pick(off.columns, ["result","official_result","winner","settlement_result","outcome","side"])

live[lts] = pd.to_datetime(live[lts], utc=True, errors="coerce")
live[lrem] = pd.to_numeric(live[lrem], errors="coerce")
live[ldist] = pd.to_numeric(live[ldist], errors="coerce")
for c in [lfair_up, lfair_down, ltarget, lbtc]:
    if c:
        live[c] = pd.to_numeric(live[c], errors="coerce")

def norm_side(x):
    s = str(x).strip().upper()
    if s in {"UP","YES","Y","1","TRUE"}:
        return "UP"
    if s in {"DOWN","NO","N","0","FALSE"}:
        return "DOWN"
    return np.nan

off["_official_side"] = off[ores].map(norm_side)
off = off.dropna(subset=[oticker,"_official_side"]).copy()
off[oticker] = off[oticker].astype(str)
off = off.drop_duplicates(subset=[oticker], keep="last")
omap = dict(zip(off[oticker], off["_official_side"]))

live = live[live[lticker].astype(str).isin(omap)].copy()
live = live.dropna(subset=[lts,lrem,ldist])
live[lticker] = live[lticker].astype(str)

# Build the same style of early qualified call used in our forward research:
# first snapshot in the 8-12 minute window with fair >=80%.
# Signal-status is retained for diagnostics, but qualification is based on fair/distance
# so old naming changes (STRONG/SUPPORTED/etc.) cannot silently drop contracts.
rows = []
for ticker, g in live.groupby(lticker):
    g = g.sort_values(lts).copy()
    w = g[(g[lrem] >= 8.0) & (g[lrem] <= 12.0)].copy()
    if w.empty:
        continue

    if lfair_up and lfair_down:
        w["_call_side"] = np.where(w[lfair_up] >= w[lfair_down], "UP", "DOWN")
        w["_fair"] = np.where(w["_call_side"].eq("UP"), w[lfair_up], w[lfair_down])
    elif lpref:
        w["_call_side"] = w[lpref].map(norm_side)
        w["_fair"] = np.nan
    else:
        continue

    # Qualified FINAL call research baseline: >=80% fair and at least $20 from strike.
    q = w[(w["_fair"] >= 0.80) & (w[ldist].abs() >= 20)].copy()
    if q.empty:
        continue

    call = q.iloc[0]
    side = call["_call_side"]
    official_side = omap.get(ticker)
    if pd.isna(side) or official_side not in {"UP","DOWN"}:
        continue

    # Last usable snapshot is diagnostic ONLY, never the truth label.
    last = g.iloc[-1]
    last_side = "UP" if float(last[ldist]) >= 0 else "DOWN"
    last_abs = abs(float(last[ldist]))
    proxy_disagrees = last_side != official_side

    if last_abs < 25:
        band = "$0-$25"
    elif last_abs < 50:
        band = "$25-$50"
    elif last_abs < 100:
        band = "$50-$100"
    else:
        band = "$100+"

    rows.append({
        "ticker": ticker,
        "call_time": call[lts],
        "call_side": side,
        "official_side": official_side,
        "correct": side == official_side,
        "initial_fair": float(call["_fair"]),
        "initial_remaining_min": float(call[lrem]),
        "initial_distance": float(call[ldist]),
        "initial_abs_distance": abs(float(call[ldist])),
        "signal_status": str(call[lstatus]) if lstatus else "",
        "last_timestamp": last[lts],
        "last_remaining_min": float(last[lrem]),
        "last_distance": float(last[ldist]),
        "last_abs_distance": last_abs,
        "last_proxy_side": last_side,
        "proxy_disagrees_official": proxy_disagrees,
        "final_proxy_distance_band": band,
    })

d = pd.DataFrame(rows).sort_values("call_time").reset_index(drop=True)
if d.empty:
    raise SystemExit("ERROR: no qualifying calls found.")

def pct(a,b):
    return 100.0*a/b if b else float("nan")

print(f"Officially settled qualified final calls: {len(d)}")
print(f"Correct: {int(d.correct.sum())}")
print(f"Wrong: {int((~d.correct).sum())}")
print(f"Official-truth accuracy: {pct(int(d.correct.sum()), len(d)):.1f}%")
print()

print("=== BY INITIAL FAIR ===")
for t in [0.80,0.85,0.90,0.92,0.95]:
    z = d[d.initial_fair >= t]
    if len(z):
        print(f">={int(t*100)}% fair | n={len(z):3d} | correct={int(z.correct.sum()):3d} | accuracy={pct(int(z.correct.sum()),len(z)):.1f}%")
print()

print("=== BY INITIAL ABS DISTANCE ===")
bands = [
    ("$20-$50", 20, 50),
    ("$50-$100", 50, 100),
    ("$100-$200", 100, 200),
    ("$200+", 200, np.inf),
]
for name, lo, hi in bands:
    z = d[(d.initial_abs_distance >= lo) & (d.initial_abs_distance < hi)]
    if len(z):
        print(f"{name:10s} | n={len(z):3d} | correct={int(z.correct.sum()):3d} | accuracy={pct(int(z.correct.sum()),len(z)):.1f}%")
print()

print("=== OFFICIAL TRUTH VS FINAL COINBASE PROXY ===")
for band in ["$0-$25","$25-$50","$50-$100","$100+"]:
    z = d[d.final_proxy_distance_band == band]
    if len(z):
        disagreements = int(z.proxy_disagrees_official.sum())
        print(f"{band:8s} | n={len(z):3d} | proxy disagreements={disagreements:3d} | rate={pct(disagreements,len(z)):.1f}%")
print()

near = d[d.last_abs_distance < 100]
far = d[d.last_abs_distance >= 100]
print("=== CALL ACCURACY, SPLIT BY FINAL PROXY DISTANCE (DIAGNOSTIC ONLY) ===")
for name,z in [("final proxy < $100",near),("final proxy >= $100",far)]:
    if len(z):
        print(f"{name:20s} | n={len(z):3d} | accuracy={pct(int(z.correct.sum()),len(z)):.1f}%")
print("NOTE: final proxy distance is POST-CALL information. Do NOT use this split as a live entry rule.")
print()

# Chronological holdout: last 40% of qualifying calls.
cut = max(1, int(np.floor(len(d)*0.60)))
h = d.iloc[cut:].copy()
print("=== CHRONOLOGICAL HOLDOUT: LAST 40% ===")
print(f"Holdout calls: {len(h)}")
print(f"Correct: {int(h.correct.sum())}")
print(f"Wrong: {int((~h.correct).sum())}")
print(f"Accuracy: {pct(int(h.correct.sum()),len(h)):.1f}%")
for t in [0.80,0.85,0.90]:
    z = h[h.initial_fair >= t]
    if len(z):
        print(f"  >={int(t*100)}% fair | n={len(z):3d} | accuracy={pct(int(z.correct.sum()),len(z)):.1f}%")
print()

print("=== PROXY-MISMATCH CALLS ===")
m = d[d.proxy_disagrees_official].copy()
if len(m):
    cols = ["ticker","call_side","official_side","correct","initial_fair",
            "initial_abs_distance","last_remaining_min","last_distance",
            "final_proxy_distance_band"]
    print(m[cols].to_string(index=False))
else:
    print("None.")

d.to_csv(OUT, index=False)
print()
print(f"Saved: {OUT}")
print("=== RESCORE COMPLETE ===")
print("Official Kalshi settlement is the ONLY truth label in this audit.")
print("No live rule installed. No bot.py changes.")
