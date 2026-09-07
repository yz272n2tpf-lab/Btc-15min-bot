from pathlib import Path
import re
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestClassifier

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== KALSHI MINUTE-7 FAILURE SIGNATURE AUDIT ===")
print("Purpose: isolate the unseen/OOS failure patterns at elapsed minute 7.")
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
        year=2000+int(yy),
        month=MONTHS[mon],
        day=int(dd),
        hour=int(hh),
        minute=int(mm),
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

cal = cal.dropna(
    subset=["start","target_brti","final_brti","y"]
).sort_values("start").reset_index(drop=True)

label_ok = (
    (cal["final_brti"] >= cal["target_brti"]).astype(int)
    == cal["y"].astype(int)
)

def px(ts):
    i = btc.index.searchsorted(ts, side="right") - 1
    if i < 0:
        return np.nan, pd.NaT

    ti = btc.index[i]
    if ts - ti > pd.Timedelta(minutes=2):
        return np.nan, pd.NaT

    return float(btc.iloc[i]["Close"]), ti

def snapshot(r):
    elapsed = 7
    start = r["start"]
    cut = start + pd.Timedelta(minutes=elapsed)
    target = float(r["target_brti"])

    vals = [
        px(start),
        px(cut),
        px(cut-pd.Timedelta(minutes=1)),
        px(cut-pd.Timedelta(minutes=2)),
        px(cut-pd.Timedelta(minutes=3)),
        px(cut-pd.Timedelta(minutes=5)),
    ]

    if any(pd.isna(v[0]) for v in vals):
        return None

    p0,p1,pm1,pm2,pm3,pm5 = [v[0] for v in vals]
    used_times = [v[1] for v in vals]

    w = btc.loc[
        (btc.index > cut-pd.Timedelta(minutes=5))
        & (btc.index <= cut)
    ]

    if len(w) < 3:
        return None

    latest = max(used_times + [w.index.max()])
    if latest > cut:
        raise RuntimeError("FUTURE DATA DETECTED")

    closes = w["Close"].dropna()
    if len(closes) < 2:
        return None

    dist = p1 - target

    return {
        "ticker": r["ticker"],
        "start": start,
        "y": int(r["y"]),
        "current_side": int(dist >= 0),
        "dist_target": dist,
        "abs_dist_target": abs(dist),
        "dist_target_pct": dist/target,
        "dist_start": p1-p0,
        "dist_start_pct": (p1-p0)/p0,
        "move1": p1-pm1,
        "move2": p1-pm2,
        "move3": p1-pm3,
        "move5": p1-pm5,
        "range5": float(w["High"].max()-w["Low"].min()),
        "vol5": float(closes.pct_change().std(ddof=0)),
    }

features = [
    "current_side","dist_target","abs_dist_target","dist_target_pct",
    "dist_start","dist_start_pct","move1","move2","move3","move5",
    "range5","vol5"
]

rows = []
for _, r in cal.iterrows():
    s = snapshot(r)
    if s is not None:
        rows.append(s)

df = pd.DataFrame(rows).sort_values("start").reset_index(drop=True)

# Same strict expanding chronological OOS framework used in prior validation.
oos_parts = []

for a,b in [(0.50,0.60),(0.60,0.70),(0.70,0.80),(0.80,0.90),(0.90,1.00)]:
    train_end = int(len(df)*a)
    test_end = int(len(df)*b)

    train = df.iloc[:train_end]
    test = df.iloc[train_end:test_end].copy()

    if len(train) < 100 or len(test) == 0:
        continue

    if train["start"].max() >= test["start"].min():
        raise RuntimeError("CHRONOLOGY FAILURE")

    model = RandomForestClassifier(
        n_estimators=500,
        max_depth=7,
        min_samples_leaf=8,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )

    model.fit(train[features], train["y"])

    pred = model.predict(test[features])
    conf = model.predict_proba(test[features]).max(axis=1)

    test["pred"] = pred
    test["conf"] = conf
    test["correct"] = pred == test["y"].to_numpy()

    # Prediction direction encoded as +1 UP, -1 DOWN.
    test["pred_sign"] = np.where(test["pred"] == 1, 1, -1)

    # Does each recent BTC move point the same way as the model prediction?
    for col in ["move1","move2","move3","move5"]:
        test[f"{col}_aligned"] = np.sign(test[col]) == test["pred_sign"]

    test["momentum_agreement_count"] = (
        test[["move1_aligned","move2_aligned","move3_aligned","move5_aligned"]]
        .sum(axis=1)
    )

    test["model_agrees_target_side"] = test["pred"] == test["current_side"]

    # Reversal pressure: very short-term move fights the model while 5m move supports it.
    test["short_term_fights"] = ~test["move1_aligned"]
    test["five_min_supports"] = test["move5_aligned"]

    oos_parts.append(test)

oos = pd.concat(oos_parts, ignore_index=True)

print(f"Minute-7 OOS predictions: {len(oos)}")
print(f"Overall OOS accuracy: {oos['correct'].mean():.3f}")
print()

hc = oos[oos["conf"] >= 0.80].copy()
print("=== PRIMARY GROUP: CONFIDENCE >= 80% ===")
print(f"n={len(hc)} | coverage={len(hc)/len(oos):.1%} | accuracy={hc['correct'].mean():.3f}")
print(f"wrong={int((~hc['correct']).sum())}")
print()

def report_group(title, series):
    print(title)
    for name, mask in series:
        q = hc[mask]
        if len(q):
            print(
                f"{name:34s} | n={len(q):3d} | "
                f"acc={q['correct'].mean():.3f} | "
                f"wrong={int((~q['correct']).sum()):2d}"
            )
    print()

report_group(
    "-- Distance from Kalshi/BRTI target --",
    [
        ("<$20", hc["abs_dist_target"] < 20),
        ("$20-$39.99", (hc["abs_dist_target"] >= 20) & (hc["abs_dist_target"] < 40)),
        ("$40-$59.99", (hc["abs_dist_target"] >= 40) & (hc["abs_dist_target"] < 60)),
        ("$60-$99.99", (hc["abs_dist_target"] >= 60) & (hc["abs_dist_target"] < 100)),
        ("$100+", hc["abs_dist_target"] >= 100),
    ]
)

report_group(
    "-- Momentum agreement count --",
    [
        ("0 of 4 aligned", hc["momentum_agreement_count"] == 0),
        ("1 of 4 aligned", hc["momentum_agreement_count"] == 1),
        ("2 of 4 aligned", hc["momentum_agreement_count"] == 2),
        ("3 of 4 aligned", hc["momentum_agreement_count"] == 3),
        ("4 of 4 aligned", hc["momentum_agreement_count"] == 4),
    ]
)

report_group(
    "-- Target-side agreement --",
    [
        ("model agrees current target side", hc["model_agrees_target_side"]),
        ("model fights current target side", ~hc["model_agrees_target_side"]),
    ]
)

report_group(
    "-- Short-term reversal pressure --",
    [
        ("1m supports prediction", hc["move1_aligned"]),
        ("1m fights prediction", ~hc["move1_aligned"]),
        ("1m fights, 5m supports",
         (~hc["move1_aligned"]) & hc["move5_aligned"]),
        ("1m + 2m both fight",
         (~hc["move1_aligned"]) & (~hc["move2_aligned"])),
    ]
)

report_group(
    "-- 5-minute range --",
    [
        ("range < $100", hc["range5"] < 100),
        ("range $100-$149.99", (hc["range5"] >= 100) & (hc["range5"] < 150)),
        ("range $150-$199.99", (hc["range5"] >= 150) & (hc["range5"] < 200)),
        ("range $200+", hc["range5"] >= 200),
    ]
)

print("=== CORRECT VS WRONG MEDIANS: CONF>=80 ===")
right = hc[hc["correct"]]
wrong = hc[~hc["correct"]]

for col in [
    "conf","abs_dist_target","move1","move2","move3","move5",
    "range5","vol5","momentum_agreement_count"
]:
    print(
        f"{col:26s} | "
        f"correct={right[col].median():10.4f} | "
        f"wrong={wrong[col].median():10.4f}"
    )

print()
print("=== FIXED RISK-FILTER AUDIT ===")
print("These are descriptive only. They are NOT approved bot rules.")

filters = [
    ("base conf>=80", pd.Series(True, index=hc.index)),
    ("require >=2/4 momentum aligned", hc["momentum_agreement_count"] >= 2),
    ("require >=3/4 momentum aligned", hc["momentum_agreement_count"] >= 3),
    ("require >=2/4 + $40 away",
     (hc["momentum_agreement_count"] >= 2) & (hc["abs_dist_target"] >= 40)),
    ("require >=3/4 + $40 away",
     (hc["momentum_agreement_count"] >= 3) & (hc["abs_dist_target"] >= 40)),
    ("require >=2/4 + $60 away",
     (hc["momentum_agreement_count"] >= 2) & (hc["abs_dist_target"] >= 60)),
    ("require >=3/4 + $60 away",
     (hc["momentum_agreement_count"] >= 3) & (hc["abs_dist_target"] >= 60)),
    ("exclude 1m+2m both fighting",
     ~((~hc["move1_aligned"]) & (~hc["move2_aligned"]))),
]

for name, mask in filters:
    q = hc[mask]
    if len(q):
        print(
            f"{name:34s} | n={len(q):3d} | "
            f"coverage_vs_all={len(q)/len(oos):.1%} | "
            f"accuracy={q['correct'].mean():.3f}"
        )

print()
print("=== HARD CHECKS ===")
print("Settlement-label consistency:", "PASS" if label_ok.all() else "FAIL")
print("Future-data usage: PASS")
print("Chronological walk-forward: PASS")
print()
print("=== AUDIT COMPLETE ===")
print("No bot files modified.")
print("Next step: validate any promising failure filter on a fresh nested/rolling test before integration.")
