from pathlib import Path
import pandas as pd
import numpy as np
import csv

LAYER_A = Path("kalshi_layer_a_forward_only_results.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")

KNOWN_MISSES = {
    "KXBTC15M-26AUG251630-30",
    "KXBTC15M-26AUG261615-15",
}

print("=== KALSHI CONFIRMATION-FAILURE AUDIT ===")
print("Purpose: compare Layer A CLEAN winners vs known CLEAN misses.")
print("Question: after the call, did the predicted side CONFIRM by strengthening, or fail to strengthen?")
print()
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

if not LAYER_A.exists():
    raise SystemExit("Missing kalshi_layer_a_forward_only_results.csv")
if not LIVE.exists():
    raise SystemExit("Missing kalshi_live_fair_value_shadow_log.csv")

a = pd.read_csv(LAYER_A)
a["call_time"] = pd.to_datetime(a["call_time"], utc=True, errors="coerce")
clean = a[a["state"].astype(str).str.upper() == "CLEAN"].copy()

print("Layer A CLEAN calls:", len(clean))
print("CLEAN correct:", int(clean["correct"].sum()))
print("CLEAN wrong:", int((~clean["correct"]).sum()))
print()

# Robust mixed-log parser
def looks_like_header(row):
    low = [str(x).strip().lower() for x in row]
    keys = ["ticker","timestamp","distance","fair","ask","preferred"]
    return sum(any(k in x for k in keys) for x in low) >= 2

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
ua = pick(live.columns, ["up_ask","ask_up","up_ask_price"])
da = pick(live.columns, ["down_ask","ask_down","down_ask_price"])

for c in [dc, fu, fd, ua, da]:
    if c:
        live[c] = pd.to_numeric(live[c], errors="coerce")
live[ts] = pd.to_datetime(live[ts], utc=True, errors="coerce")
live[tc] = live[tc].astype(str)

def nearest(df, target_time, tolerance=45):
    if df.empty:
        return None
    delta = (df[ts] - target_time).abs().dt.total_seconds()
    i = delta.idxmin()
    if float(delta.loc[i]) > tolerance:
        return None
    return df.loc[i]

rows = []

for _, call in clean.iterrows():
    ticker = str(call["ticker"])
    side = str(call["call_side"]).upper()
    t0 = call["call_time"]
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

    if side == "UP" and fu:
        q["side_fair"] = q[fu]
    elif side == "DOWN" and fd:
        q["side_fair"] = q[fd]
    else:
        q["side_fair"] = np.nan

    if side == "UP" and ua:
        q["side_ask"] = q[ua]
    elif side == "DOWN" and da:
        q["side_ask"] = q[da]
    else:
        q["side_ask"] = np.nan

    rec = {
        "ticker": ticker,
        "correct": bool(call["correct"]),
        "call_side": side,
        "initial_fair": initial_fair,
        "initial_signed_distance": initial_signed,
        "is_known_miss": ticker in KNOWN_MISSES,
    }

    # Track exact-ish path at 1m..6m
    signed_vals = []
    fair_vals = []
    ask_vals = []

    for sec, label in [(60,"1m"),(120,"2m"),(180,"3m"),(240,"4m"),(300,"5m"),(360,"6m")]:
        nr = nearest(q, t0 + pd.Timedelta(seconds=sec), tolerance=45)
        if nr is None:
            rec[f"{label}_signed_distance"] = np.nan
            rec[f"{label}_distance_gain"] = np.nan
            rec[f"{label}_fair"] = np.nan
            rec[f"{label}_fair_gain"] = np.nan
            rec[f"{label}_ask"] = np.nan
            rec[f"{label}_ask_gain"] = np.nan
            continue

        sd = float(nr["signed_dist"]) if pd.notna(nr["signed_dist"]) else np.nan
        sf = float(nr["side_fair"]) if pd.notna(nr["side_fair"]) else np.nan
        sa = float(nr["side_ask"]) if pd.notna(nr["side_ask"]) else np.nan

        rec[f"{label}_signed_distance"] = sd
        rec[f"{label}_distance_gain"] = sd - initial_signed if pd.notna(sd) else np.nan
        rec[f"{label}_fair"] = sf
        rec[f"{label}_fair_gain"] = sf - initial_fair if pd.notna(sf) else np.nan
        rec[f"{label}_ask"] = sa

        signed_vals.append((sec, sd))
        fair_vals.append((sec, sf))
        ask_vals.append((sec, sa))

    # Simple confirmation summaries: strongest improvement and time-to-first-confirmation
    dist_gains = [rec.get(f"{m}_distance_gain") for m in ["1m","2m","3m","4m","5m","6m"]]
    fair_gains = [rec.get(f"{m}_fair_gain") for m in ["1m","2m","3m","4m","5m","6m"]]

    dist_clean = [x for x in dist_gains if pd.notna(x)]
    fair_clean = [x for x in fair_gains if pd.notna(x)]

    rec["best_distance_gain_6m"] = max(dist_clean) if dist_clean else np.nan
    rec["worst_distance_gain_6m"] = min(dist_clean) if dist_clean else np.nan
    rec["best_fair_gain_6m"] = max(fair_clean) if fair_clean else np.nan
    rec["worst_fair_gain_6m"] = min(fair_clean) if fair_clean else np.nan

    # Area-like average path relative to start: captures "stalled vs strengthening"
    rec["avg_distance_gain_1to6m"] = np.nanmean(dist_clean) if dist_clean else np.nan
    rec["avg_fair_gain_1to6m"] = np.nanmean(fair_clean) if fair_clean else np.nan

    # Did it ever materially confirm?
    rec["ever_plus25_distance"] = any(pd.notna(x) and x >= 25 for x in dist_gains)
    rec["ever_plus50_distance"] = any(pd.notna(x) and x >= 50 for x in dist_gains)
    rec["ever_plus5pt_fair"] = any(pd.notna(x) and x >= 0.05 for x in fair_gains)
    rec["ever_plus10pt_fair"] = any(pd.notna(x) and x >= 0.10 for x in fair_gains)

    rows.append(rec)

d = pd.DataFrame(rows)

print("=== KNOWN CLEAN MISSES ===")
km = d[d["is_known_miss"]]
print(km.to_string(index=False) if len(km) else "Known misses not found in current CLEAN population.")
print()

w = d[d["correct"]].copy()
m = d[~d["correct"]].copy()

print("=== SUMMARY: WINNERS VS CLEAN MISSES ===")
metrics = [
    "best_distance_gain_6m",
    "worst_distance_gain_6m",
    "avg_distance_gain_1to6m",
    "best_fair_gain_6m",
    "worst_fair_gain_6m",
    "avg_fair_gain_1to6m",
]
for metric in metrics:
    ws = pd.to_numeric(w[metric], errors="coerce").dropna()
    ms = pd.to_numeric(m[metric], errors="coerce").dropna()
    print(
        f"{metric:28s} | "
        f"winners n={len(ws):2d} med={ws.median() if len(ws) else np.nan:9.4f} "
        f"min={ws.min() if len(ws) else np.nan:9.4f} max={ws.max() if len(ws) else np.nan:9.4f} | "
        f"misses={list(np.round(ms.values,4))}"
    )

print()
print("=== CONFIRMATION FREQUENCIES ===")
for col in ["ever_plus25_distance","ever_plus50_distance","ever_plus5pt_fair","ever_plus10pt_fair"]:
    print(
        col,
        "| winners", int(w[col].sum()), "/", len(w),
        "| misses", int(m[col].sum()), "/", len(m)
    )

print()
print("=== PATH DETAILS ===")
show = [
    "ticker","correct","call_side","initial_fair","initial_signed_distance",
    "1m_distance_gain","2m_distance_gain","3m_distance_gain","4m_distance_gain","5m_distance_gain","6m_distance_gain",
    "1m_fair_gain","2m_fair_gain","3m_fair_gain","4m_fair_gain","5m_fair_gain","6m_fair_gain",
    "best_distance_gain_6m","avg_distance_gain_1to6m",
    "best_fair_gain_6m","avg_fair_gain_1to6m",
    "ever_plus25_distance","ever_plus50_distance","ever_plus5pt_fair","ever_plus10pt_fair"
]
print(d[show].to_string(index=False))

d.to_csv("kalshi_confirmation_failure_audit_details.csv", index=False)

print()
print("Saved: kalshi_confirmation_failure_audit_details.csv")
print("=== AUDIT COMPLETE ===")
print("Research only. No rule installed.")
