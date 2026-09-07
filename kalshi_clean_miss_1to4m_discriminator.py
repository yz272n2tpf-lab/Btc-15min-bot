from pathlib import Path
import pandas as pd
import numpy as np
import csv

TARGET = "KXBTC15M-26AUG261615-15"
LAYER_B = Path("kalshi_layer_b_forward_only_results.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")
FLOW = Path("btc_large_flow_shadow_log.csv")

print("=== CLEAN MISS 1-4 MIN DISCRIMINATOR ===")
print("Target:", TARGET)
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
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

b = pd.read_csv(LAYER_B)
b["call_time"] = pd.to_datetime(b["call_time"], utc=True, errors="coerce")
clean = b[b["layer_a_state"].astype(str).str.upper() == "CLEAN"].copy()

print("Forward CLEAN calls:", len(clean))
print("Forward CLEAN correct:", int(clean["correct"].sum()))
print("Forward CLEAN wrong:", int((~clean["correct"]).sum()))
print()

def looks_like_header(row):
    low = [str(x).strip().lower() for x in row]
    return sum(any(k in x for k in ["ticker","timestamp","distance","preferred","fair","ask"]) >= 1 for x in low) >= 2

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
upask = pick(live.columns, ["up_ask","ask_up","up_ask_price"])
downask = pick(live.columns, ["down_ask","ask_down","down_ask_price"])

for c in [dc,fu,fd,upask,downask]:
    if c:
        live[c] = pd.to_numeric(live[c], errors="coerce")
live[ts] = pd.to_datetime(live[ts], utc=True, errors="coerce")
live[tc] = live[tc].astype(str)

flow = None
fts = imb = buy = sell = largest = None
if FLOW.exists():
    try:
        flow = pd.read_csv(FLOW, on_bad_lines="skip", low_memory=False)
        fts = pick(flow.columns, ["timestamp_utc","timestamp","time_utc"])
        imb = pick(flow.columns, ["imbalance","imb","imbalance_pct"])
        buy = pick(flow.columns, ["buy","buy_total","buy_volume"])
        sell = pick(flow.columns, ["sell","sell_total","sell_volume"])
        largest = pick(flow.columns, ["largest","largest_trade","largest_flow"])
        if fts:
            flow[fts] = pd.to_datetime(flow[fts], utc=True, errors="coerce")
        for c in [imb,buy,sell,largest]:
            if c:
                flow[c] = pd.to_numeric(flow[c], errors="coerce")
    except Exception:
        flow = None

def nearest_row(df, time_col, target_time, tolerance_sec=45):
    if df is None or df.empty:
        return None
    z = df[df[time_col].notna()].copy()
    if z.empty:
        return None
    delta = (z[time_col] - target_time).abs().dt.total_seconds()
    i = delta.idxmin()
    if float(delta.loc[i]) > tolerance_sec:
        return None
    return z.loc[i]

rows = []
for _, call in clean.iterrows():
    ticker = str(call["ticker"])
    side = str(call["call_side"]).upper()
    t0 = pd.to_datetime(call["call_time"], utc=True, errors="coerce")
    if pd.isna(t0):
        continue

    q = live[(live[tc] == ticker) & (live[ts] >= t0)].copy().sort_values(ts)
    if q.empty:
        continue

    initial_distance = float(call["initial_distance"])
    initial_signed = initial_distance if side == "UP" else -initial_distance
    initial_fair = float(call["initial_fair"])

    q["sec_after"] = (q[ts] - t0).dt.total_seconds()
    q["signed_dist"] = q[dc] if side == "UP" else -q[dc]
    q["dist_drop"] = np.maximum(0.0, initial_signed - q["signed_dist"])

    if side == "UP" and fu:
        q["side_fair"] = q[fu]
    elif side == "DOWN" and fd:
        q["side_fair"] = q[fd]
    else:
        q["side_fair"] = np.nan
    q["fair_drop"] = np.maximum(0.0, initial_fair - q["side_fair"])

    if side == "UP" and upask:
        q["side_ask"] = q[upask]
    elif side == "DOWN" and downask:
        q["side_ask"] = q[downask]
    else:
        q["side_ask"] = np.nan

    first_ask = q["side_ask"].dropna().iloc[0] if q["side_ask"].notna().any() else np.nan

    rec = {
        "ticker": ticker,
        "correct": bool(call["correct"]),
        "call_side": side,
        "initial_fair": initial_fair,
        "initial_distance": initial_distance,
    }

    for sec, label in [(60,"1m"),(120,"2m"),(180,"3m"),(240,"4m")]:
        h = q[(q["sec_after"] >= 0) & (q["sec_after"] <= sec)]
        rec[f"{label}_dist_maxdrop"] = float(h["dist_drop"].max()) if len(h) else np.nan
        rec[f"{label}_fair_maxdrop"] = float(h["fair_drop"].max()) if len(h) else np.nan

        nr = nearest_row(q, ts, t0 + pd.Timedelta(seconds=sec), tolerance_sec=45)
        if nr is not None:
            rec[f"{label}_ask_change"] = (
                float(nr["side_ask"] - first_ask)
                if pd.notna(nr["side_ask"]) and pd.notna(first_ask)
                else np.nan
            )
        else:
            rec[f"{label}_ask_change"] = np.nan

        if flow is not None and fts is not None:
            fr = nearest_row(flow, fts, t0 + pd.Timedelta(seconds=sec), tolerance_sec=45)
            if fr is not None:
                rec[f"{label}_imb"] = float(fr[imb]) if imb and pd.notna(fr[imb]) else np.nan

    rows.append(rec)

d = pd.DataFrame(rows)

print("=== TARGET CLEAN MISS ===")
t = d[d["ticker"] == TARGET]
print(t.to_string(index=False) if len(t) else "TARGET NOT FOUND")
print()

w = d[d["correct"]].copy()
m = d[~d["correct"]].copy()

print("=== CLEAN WINNER VS CLEAN MISS SUMMARY ===")
for label in ["1m","2m","3m","4m"]:
    for metric in [f"{label}_dist_maxdrop", f"{label}_fair_maxdrop", f"{label}_ask_change", f"{label}_imb"]:
        if metric not in d.columns:
            continue
        ws = pd.to_numeric(w[metric], errors="coerce").dropna()
        ms = pd.to_numeric(m[metric], errors="coerce").dropna()
        if len(ws) == 0 and len(ms) == 0:
            continue
        print(f"{metric:22s} | winners n={len(ws):2d} med={ws.median() if len(ws) else np.nan:9.4f} min={ws.min() if len(ws) else np.nan:9.4f} max={ws.max() if len(ws) else np.nan:9.4f} | misses={list(np.round(ms.values,4))}")

print()
print("=== CLEAN CALL DETAILS ===")
show = [
    "ticker","correct","call_side","initial_fair","initial_distance",
    "1m_dist_maxdrop","2m_dist_maxdrop","3m_dist_maxdrop","4m_dist_maxdrop",
    "1m_fair_maxdrop","2m_fair_maxdrop","3m_fair_maxdrop","4m_fair_maxdrop"
]
for c in ["1m_ask_change","2m_ask_change","3m_ask_change","4m_ask_change","1m_imb","2m_imb","3m_imb","4m_imb"]:
    if c in d.columns:
        show.append(c)

print(d[show].to_string(index=False))
d.to_csv("kalshi_clean_miss_1to4m_discriminator_details.csv", index=False)

print()
print("Saved: kalshi_clean_miss_1to4m_discriminator_details.csv")
print("=== DISCRIMINATOR COMPLETE ===")
print("Research only. No rule installed.")
