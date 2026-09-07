
from pathlib import Path
import pandas as pd
import numpy as np

print("=== KALSHI OFFICIAL-TRUTH / NEAR-STRIKE VALIDATOR ===")
print("Purpose: make official Kalshi settlement the truth label and audit Coinbase proxy disagreement near the strike.")
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

OFFICIAL = Path("kalshi_official_settlement_check.csv")
LIVE_CANDIDATES = [
    Path("kalshi_live_fair_value_shadow_log.csv"),
    Path("x.csv"),
    Path("kalshi_flow_matched_snapshots.csv"),
]

if not OFFICIAL.exists():
    raise SystemExit("ERROR: kalshi_official_settlement_check.csv not found.")

live_path = next((p for p in LIVE_CANDIDATES if p.exists()), None)
if live_path is None:
    raise SystemExit("ERROR: no live snapshot file found.")

def read_mixed_schema_csv(path):
    """
    Read append-only CSV logs even if a later logger version added columns.
    Keeps the original header-width fields and truncates extra trailing fields
    instead of throwing ParserError.
    """
    import csv
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
    width = len(header)

    def repair_bad_line(fields):
        if len(fields) >= width:
            return fields[:width]
        return fields + [None] * (width - len(fields))

    return pd.read_csv(
        path,
        engine="python",
        on_bad_lines=repair_bad_line
    )

official = read_mixed_schema_csv(OFFICIAL)
live = read_mixed_schema_csv(live_path)

print(f"Loaded official file: {OFFICIAL}")
print(f"Loaded live file: {live_path}")
print("Mixed-schema CSV protection: ON")
print()

def pick(cols, names):
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

# --- identify columns ---
ot = pick(official.columns, ["ticker", "market_ticker", "contract_ticker"])
oside = pick(official.columns, ["official_side", "winner", "result", "official_result", "settlement_result"])
ostatus = pick(official.columns, ["status", "settlement_status"])

lt = pick(live.columns, ["ticker", "market_ticker", "contract_ticker"])
lts = pick(live.columns, ["timestamp_utc", "timestamp", "time", "datetime"])
lrem = pick(live.columns, ["remaining_min", "minutes_remaining", "time_remaining"])
ldist = pick(live.columns, ["distance_target", "distance_from_target", "target_distance", "distance"])
ltarget = pick(live.columns, ["target", "target_price", "strike", "contract_target"])
lpx = pick(live.columns, ["coinbase_close", "btc_price", "coinbase_price", "spot_price", "underlying_price"])

if ot is None or oside is None:
    raise SystemExit(f"ERROR: could not identify official ticker/side columns.\nOfficial columns: {list(official.columns)}")
if lt is None or lts is None:
    raise SystemExit(f"ERROR: could not identify live ticker/time columns.\nLive columns: {list(live.columns)}")

# Normalize official side to UP/DOWN.
def norm_side(x):
    s = str(x).strip().upper()
    if s in {"UP", "YES", "Y", "1", "TRUE"}:
        return "UP"
    if s in {"DOWN", "NO", "N", "0", "FALSE"}:
        return "DOWN"
    return np.nan

official = official.copy()
official["official_truth"] = official[oside].map(norm_side)
if ostatus is not None:
    # Keep rows that look finalized/settled, but do not discard if status is blank.
    st = official[ostatus].astype(str).str.lower()
    final_mask = st.str.contains("final|settled|closed|resolved", regex=True, na=False)
    if final_mask.any():
        official = official[final_mask].copy()

official = official.dropna(subset=["official_truth"])
official = official.drop_duplicates(subset=[ot], keep="last")

live = live.copy()
live["_ts"] = pd.to_datetime(live[lts], errors="coerce", utc=True)
live = live.dropna(subset=["_ts"])
live[lt] = live[lt].astype(str)

if ldist is not None:
    live["_distance"] = pd.to_numeric(live[ldist], errors="coerce")
elif lpx is not None and ltarget is not None:
    live["_distance"] = pd.to_numeric(live[lpx], errors="coerce") - pd.to_numeric(live[ltarget], errors="coerce")
else:
    raise SystemExit("ERROR: cannot derive Coinbase-vs-target distance from live file.")

if lrem is not None:
    live["_remaining_min"] = pd.to_numeric(live[lrem], errors="coerce")
else:
    live["_remaining_min"] = np.nan

rows = []
for ticker, g in live.groupby(lt, sort=False):
    g = g.sort_values("_ts")
    g = g.dropna(subset=["_distance"])
    if g.empty:
        continue

    # Last available proxy snapshot
    last = g.iloc[-1]
    last_dist = float(last["_distance"])
    last_side = "UP" if last_dist >= 0 else "DOWN"

    # Mean proxy distance in final time windows when remaining_min exists.
    rec = {
        "ticker": str(ticker),
        "last_timestamp": last["_ts"],
        "last_remaining_min": float(last["_remaining_min"]) if pd.notna(last["_remaining_min"]) else np.nan,
        "last_distance": last_dist,
        "last_proxy_side": last_side,
    }

    for sec in (60, 90, 120):
        if lrem is not None:
            w = g[(g["_remaining_min"] >= 0) & (g["_remaining_min"] <= sec/60.0)]
        else:
            w = pd.DataFrame()
        if len(w):
            m = float(w["_distance"].mean())
            rec[f"final{sec}_n"] = int(len(w))
            rec[f"final{sec}_mean_distance"] = m
            rec[f"final{sec}_proxy_side"] = "UP" if m >= 0 else "DOWN"
        else:
            rec[f"final{sec}_n"] = 0
            rec[f"final{sec}_mean_distance"] = np.nan
            rec[f"final{sec}_proxy_side"] = np.nan

    rows.append(rec)

proxy = pd.DataFrame(rows)
truth = official[[ot, "official_truth"]].rename(columns={ot: "ticker"})
truth["ticker"] = truth["ticker"].astype(str)

m = truth.merge(proxy, on="ticker", how="inner")
if m.empty:
    raise SystemExit("ERROR: no ticker overlap between official settlements and live snapshots.")

# Official Kalshi is ALWAYS the truth label.
m["last_proxy_correct"] = m["last_proxy_side"] == m["official_truth"]
for sec in (60, 90, 120):
    m[f"final{sec}_proxy_correct"] = m[f"final{sec}_proxy_side"] == m["official_truth"]

# Near-strike audit buckets based on last Coinbase proxy distance.
bins = [0, 25, 50, 100, 200, 500, np.inf]
labels = ["$0-$25", "$25-$50", "$50-$100", "$100-$200", "$200-$500", "$500+"]
m["abs_last_distance"] = m["last_distance"].abs()
m["distance_bucket"] = pd.cut(m["abs_last_distance"], bins=bins, labels=labels, right=False)

print(f"Official settled contracts with usable proxy data: {len(m)}")
print()

def show_agreement(label, col):
    usable = m[m[col].notna()]
    if not len(usable):
        print(f"{label:<28} n=0")
        return
    agree = usable[col].astype(bool).mean()
    print(f"{label:<28} n={len(usable):4d} agreement={agree*100:5.1f}% disagreement={(1-agree)*100:5.1f}%")

print("=== AGREEMENT WITH OFFICIAL KALSHI TRUTH ===")
show_agreement("Last Coinbase-distance side", "last_proxy_correct")
for sec in (60, 90, 120):
    show_agreement(f"Mean final <={sec} sec", f"final{sec}_proxy_correct")
print()

print("=== DISAGREEMENT BY LAST ABS DISTANCE ===")
for lab in labels:
    z = m[m["distance_bucket"].astype(str) == lab]
    if not len(z):
        continue
    bad = int((~z["last_proxy_correct"]).sum())
    print(f"{lab:<10} n={len(z):4d} disagreements={bad:3d} rate={bad/len(z)*100:5.1f}%")
print()

# Explicit research flag only. This does NOT alter any prediction or bot behavior.
m["near_strike_proxy_risk"] = m["abs_last_distance"] < 100
m["proxy_disagrees_with_official"] = ~m["last_proxy_correct"]

print("=== KEY CHECK ===")
near = m[m["near_strike_proxy_risk"]]
far = m[~m["near_strike_proxy_risk"]]
if len(near):
    print(f"Inside $100 of target: n={len(near)} | proxy disagreement={(~near['last_proxy_correct']).mean()*100:.1f}%")
if len(far):
    print(f"$100+ from target:      n={len(far)} | proxy disagreement={(~far['last_proxy_correct']).mean()*100:.1f}%")
print()

bad = m[m["proxy_disagrees_with_official"]].copy()
show_cols = [
    "ticker","official_truth","last_timestamp","last_remaining_min",
    "last_distance","last_proxy_side",
    "final60_n","final60_mean_distance","final60_proxy_side",
    "final90_n","final90_mean_distance","final90_proxy_side",
    "abs_last_distance","distance_bucket","near_strike_proxy_risk"
]
print("=== PROXY / OFFICIAL DISAGREEMENTS ===")
if len(bad):
    print(bad[show_cols].to_string(index=False))
else:
    print("None")

out = Path("kalshi_official_truth_near_strike_results.csv")
m.to_csv(out, index=False)
print()
print(f"Saved: {out}")
print("=== VALIDATION COMPLETE ===")
print("Official Kalshi settlement remains the truth label.")
print("No rule installed. No bot.py changes.")
