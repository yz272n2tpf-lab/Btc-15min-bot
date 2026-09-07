from pathlib import Path
import re
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestClassifier

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== KALSHI EARLY-WINDOW ERROR AUDIT ===")
print("Purpose: find what separates correct vs wrong predictions at minutes 3/5/7.")
print("Timing: ticker = ET contract CLOSE; contract start = close - 15 minutes.")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

cal = pd.read_csv(CAL)
btc = pd.read_csv(BTC)

btc["Datetime"] = pd.to_datetime(btc["Datetime"], utc=True, errors="coerce")
btc = btc.dropna(subset=["Datetime"]).sort_values("Datetime").set_index("Datetime")
for c in ["Open","High","Low","Close","Volume"]:
    if c in btc.columns:
        btc[c] = pd.to_numeric(btc[c], errors="coerce")

MONTHS = {m:i+1 for i,m in enumerate(
    ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
)}

def parse_times(ticker):
    m = re.search(
        r"KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-",
        str(ticker).upper()
    )
    if not m:
        return pd.NaT, pd.NaT
    yy, mon, dd, hh, mm = m.groups()
    wall = pd.Timestamp(
        year=2000+int(yy), month=MONTHS[mon], day=int(dd),
        hour=int(hh), minute=int(mm)
    )
    close_utc = wall.tz_localize(
        ZoneInfo("America/New_York")
    ).tz_convert("UTC")
    return close_utc - pd.Timedelta(minutes=15), close_utc

pairs = cal["ticker"].map(parse_times)
cal["start"] = [x[0] for x in pairs]
cal["close"] = [x[1] for x in pairs]
cal["target_brti"] = pd.to_numeric(cal["target_brti"], errors="coerce")
cal["final_brti"] = pd.to_numeric(cal["final_brti"], errors="coerce")
cal["y"] = cal["result"].astype(str).str.lower().map({"yes":1,"no":0})
cal = cal.dropna(subset=["start","target_brti","final_brti","y"]).sort_values("start").reset_index(drop=True)

def px(ts):
    i = btc.index.searchsorted(ts, side="right") - 1
    if i < 0:
        return np.nan, pd.NaT
    ti = btc.index[i]
    if ts - ti > pd.Timedelta(minutes=2):
        return np.nan, pd.NaT
    return float(btc.iloc[i]["Close"]), ti

def snapshot(r, elapsed):
    start = r["start"]
    cut = start + pd.Timedelta(minutes=elapsed)
    target = float(r["target_brti"])

    vals = [
        px(start),
        px(cut),
        px(cut-pd.Timedelta(minutes=1)),
        px(cut-pd.Timedelta(minutes=3)),
        px(cut-pd.Timedelta(minutes=5)),
    ]
    if any(pd.isna(v[0]) for v in vals):
        return None

    p0,p1,pm1,pm3,pm5 = [v[0] for v in vals]
    used = [v[1] for v in vals]

    w = btc.loc[
        (btc.index > cut-pd.Timedelta(minutes=5))
        & (btc.index <= cut)
    ]
    if len(w) < 3:
        return None
    if max(used + [w.index.max()]) > cut:
        raise RuntimeError("FUTURE DATA DETECTED")

    closes = w["Close"].dropna()
    if len(closes) < 2:
        return None

    dist = p1 - target

    return {
        "ticker": r["ticker"],
        "start": start,
        "elapsed": elapsed,
        "y": int(r["y"]),
        "current_side": int(dist >= 0),
        "dist_target": dist,
        "abs_dist_target": abs(dist),
        "dist_target_pct": dist/target,
        "dist_start": p1-p0,
        "dist_start_pct": (p1-p0)/p0,
        "move1": p1-pm1,
        "move3": p1-pm3,
        "move5": p1-pm5,
        "range5": float(w["High"].max()-w["Low"].min()),
        "vol5": float(closes.pct_change().std(ddof=0)),
    }

features = [
    "current_side","dist_target","abs_dist_target","dist_target_pct",
    "dist_start","dist_start_pct","move1","move3","move5","range5","vol5"
]

all_oos = []

for elapsed in [3,5,7]:
    rows = []
    for _, r in cal.iterrows():
        s = snapshot(r, elapsed)
        if s is not None:
            rows.append(s)

    df = pd.DataFrame(rows).sort_values("start").reset_index(drop=True)

    for a,b in [(0.50,0.60),(0.60,0.70),(0.70,0.80),(0.80,0.90),(0.90,1.00)]:
        train_end = int(len(df)*a)
        test_end = int(len(df)*b)
        train = df.iloc[:train_end]
        test = df.iloc[train_end:test_end].copy()

        if len(train) < 100 or len(test) == 0:
            continue

        model = RandomForestClassifier(
            n_estimators=400,
            max_depth=7,
            min_samples_leaf=8,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1
        )
        model.fit(train[features], train["y"])

        pred = model.predict(test[features])
        prob = model.predict_proba(test[features])
        conf = prob.max(axis=1)

        test["pred"] = pred
        test["conf"] = conf
        test["correct"] = (pred == test["y"].to_numpy())
        test["model_agrees_current_side"] = (pred == test["current_side"].to_numpy())
        all_oos.append(test)

oos = pd.concat(all_oos, ignore_index=True)

print("Out-of-sample predictions:", len(oos))
print()

for elapsed in [3,5,7]:
    d = oos[oos["elapsed"] == elapsed].copy()

    print(f"=== ELAPSED MINUTE {elapsed} ===")
    print(f"Overall accuracy: {d['correct'].mean():.3f} | n={len(d)}")

    print("-- Confidence bands --")
    bins = [
        (0.50,0.60),(0.60,0.65),(0.65,0.70),
        (0.70,0.75),(0.75,0.80),(0.80,1.01)
    ]
    for lo,hi in bins:
        q = d[(d["conf"] >= lo) & (d["conf"] < hi)]
        if len(q):
            print(
                f"{int(lo*100)}-{int(min(hi,1.0)*100)}% | "
                f"n={len(q):3d} | acc={q['correct'].mean():.3f}"
            )

    print("-- Model agrees with current target side --")
    for flag in [True, False]:
        q = d[d["model_agrees_current_side"] == flag]
        if len(q):
            print(
                f"agree={str(flag):5s} | n={len(q):3d} | "
                f"acc={q['correct'].mean():.3f}"
            )

    print("-- Predeclared candidate gates --")
    # Fixed, simple gates only. No exhaustive threshold fishing.
    gates = [
        ("conf>=70", d["conf"] >= 0.70),
        ("conf>=75", d["conf"] >= 0.75),
        ("conf>=80", d["conf"] >= 0.80),
        ("agree + conf>=70",
         d["model_agrees_current_side"] & (d["conf"] >= 0.70)),
        ("agree + conf>=75",
         d["model_agrees_current_side"] & (d["conf"] >= 0.75)),
        ("agree + conf>=80",
         d["model_agrees_current_side"] & (d["conf"] >= 0.80)),
        ("agree + conf>=70 + $20 away",
         d["model_agrees_current_side"] & (d["conf"] >= 0.70)
         & (d["abs_dist_target"] >= 20)),
        ("agree + conf>=75 + $20 away",
         d["model_agrees_current_side"] & (d["conf"] >= 0.75)
         & (d["abs_dist_target"] >= 20)),
        ("agree + conf>=80 + $20 away",
         d["model_agrees_current_side"] & (d["conf"] >= 0.80)
         & (d["abs_dist_target"] >= 20)),
        ("agree + conf>=75 + $30 away",
         d["model_agrees_current_side"] & (d["conf"] >= 0.75)
         & (d["abs_dist_target"] >= 30)),
        ("agree + conf>=80 + $30 away",
         d["model_agrees_current_side"] & (d["conf"] >= 0.80)
         & (d["abs_dist_target"] >= 30)),
    ]

    for name, mask in gates:
        q = d[mask]
        if len(q):
            print(
                f"{name:30s} | n={len(q):3d} | "
                f"coverage={len(q)/len(d):.1%} | "
                f"accuracy={q['correct'].mean():.3f}"
            )
        else:
            print(f"{name:30s} | n=0")

    wrong = d[~d["correct"]]
    right = d[d["correct"]]

    print("-- Correct vs wrong medians --")
    for col in ["conf","abs_dist_target","move1","move3","move5","range5"]:
        print(
            f"{col:16s} | correct={right[col].median():8.3f} | "
            f"wrong={wrong[col].median():8.3f}"
        )
    print()

print("=== AUDIT COMPLETE ===")
print("No bot files modified.")
print("Use this only to identify robust early qualification rules for a separate validation test.")
