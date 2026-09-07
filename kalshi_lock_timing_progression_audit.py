from pathlib import Path
import re
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestClassifier

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== KALSHI LOCK-TIMING PROGRESSION AUDIT ===")
print("Purpose: track the SAME contracts across elapsed minutes 5/7/9/11.")
print("Goal: identify when direction/confidence becomes stably reliable.")
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

def snapshot(r, elapsed):
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
        "elapsed": elapsed,
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

elapsed_list = [5,7,9,11]
all_rows = []

for elapsed in elapsed_list:
    for _, r in cal.iterrows():
        s = snapshot(r, elapsed)
        if s is not None:
            all_rows.append(s)

long = pd.DataFrame(all_rows)

# Keep only contracts present at ALL four checkpoints.
counts = long.groupby("ticker")["elapsed"].nunique()
keep = counts[counts == len(elapsed_list)].index
long = long[long["ticker"].isin(keep)].copy()

contracts = (
    long[["ticker","start","y"]]
    .drop_duplicates("ticker")
    .sort_values("start")
    .reset_index(drop=True)
)

print(f"Contracts with complete 5/7/9/11 snapshots: {len(contracts)}")
print()

# Expanding chronological OOS: train only on earlier contracts, test on next 10%.
parts = []

for a,b in [(0.50,0.60),(0.60,0.70),(0.70,0.80),(0.80,0.90),(0.90,1.00)]:
    train_tickers = contracts.iloc[:int(len(contracts)*a)]["ticker"]
    test_tickers = contracts.iloc[int(len(contracts)*a):int(len(contracts)*b)]["ticker"]

    if len(train_tickers) < 100 or len(test_tickers) == 0:
        continue

    train_contracts = contracts[contracts["ticker"].isin(train_tickers)]
    test_contracts = contracts[contracts["ticker"].isin(test_tickers)]

    if train_contracts["start"].max() >= test_contracts["start"].min():
        raise RuntimeError("CHRONOLOGY FAILURE")

    for elapsed in elapsed_list:
        train = long[
            (long["ticker"].isin(train_tickers))
            & (long["elapsed"] == elapsed)
        ].copy()

        test = long[
            (long["ticker"].isin(test_tickers))
            & (long["elapsed"] == elapsed)
        ].copy()

        model = RandomForestClassifier(
            n_estimators=500,
            max_depth=7,
            min_samples_leaf=8,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        model.fit(train[features], train["y"])

        test["pred"] = model.predict(test[features])
        test["conf"] = model.predict_proba(test[features]).max(axis=1)
        test["correct"] = test["pred"].to_numpy() == test["y"].to_numpy()
        test["fold"] = f"{int(a*100)}->{int(b*100)}"
        parts.append(test)

oos = pd.concat(parts, ignore_index=True)

print("=== CHECKPOINT OOS PERFORMANCE ===")
for elapsed in elapsed_list:
    q = oos[oos["elapsed"] == elapsed]
    print(
        f"Minute {elapsed:2d} | n={len(q):3d} | "
        f"accuracy={q['correct'].mean():.3f}"
    )
    for threshold in [0.70,0.75,0.80,0.85,0.90]:
        z = q[q["conf"] >= threshold]
        if len(z):
            print(
                f"  conf>={int(threshold*100):2d}% | n={len(z):3d} | "
                f"coverage={len(z)/len(q):5.1%} | accuracy={z['correct'].mean():.3f}"
            )
print()

# Pivot same contract through time.
p = oos.pivot_table(
    index=["ticker","fold","y"],
    columns="elapsed",
    values=["pred","conf","correct"],
    aggfunc="first"
)

# Flatten columns.
p.columns = [f"{a}_{b}" for a,b in p.columns]
p = p.reset_index()

for m in elapsed_list:
    p[f"pred_{m}"] = p[f"pred_{m}"].astype(int)

print("=== DIRECTION STABILITY ===")
pairs = [(5,7),(7,9),(9,11),(5,9),(7,11)]
for a,b in pairs:
    same = p[f"pred_{a}"] == p[f"pred_{b}"]
    print(
        f"Minute {a}->{b}: same direction "
        f"{same.mean():.1%} ({same.sum()}/{len(p)})"
    )
print()

# Stronger "lock" definitions.
p["same_5_7"] = p["pred_5"] == p["pred_7"]
p["same_7_9"] = p["pred_7"] == p["pred_9"]
p["same_9_11"] = p["pred_9"] == p["pred_11"]
p["same_7_9_11"] = (
    (p["pred_7"] == p["pred_9"])
    & (p["pred_9"] == p["pred_11"])
)
p["same_5_7_9_11"] = (
    (p["pred_5"] == p["pred_7"])
    & (p["pred_7"] == p["pred_9"])
    & (p["pred_9"] == p["pred_11"])
)

print("=== LOCK DEFINITIONS ===")

lock_defs = [
    ("5&7 agree, min conf>=80",
     p["same_5_7"] & (p["conf_5"] >= .80) & (p["conf_7"] >= .80), 7),
    ("7&9 agree, min conf>=80",
     p["same_7_9"] & (p["conf_7"] >= .80) & (p["conf_9"] >= .80), 9),
    ("9&11 agree, min conf>=80",
     p["same_9_11"] & (p["conf_9"] >= .80) & (p["conf_11"] >= .80), 11),
    ("7/9/11 all agree, min conf>=80",
     p["same_7_9_11"]
     & (p["conf_7"] >= .80)
     & (p["conf_9"] >= .80)
     & (p["conf_11"] >= .80), 11),
    ("7/9 agree, both conf>=85",
     p["same_7_9"] & (p["conf_7"] >= .85) & (p["conf_9"] >= .85), 9),
    ("9/11 agree, both conf>=85",
     p["same_9_11"] & (p["conf_9"] >= .85) & (p["conf_11"] >= .85), 11),
]

for name, mask, decision_minute in lock_defs:
    q = p[mask].copy()
    if len(q) == 0:
        continue
    acc = (q[f"pred_{decision_minute}"] == q["y"]).mean()
    print(
        f"{name:35s} | n={len(q):3d} | "
        f"coverage={len(q)/len(p):5.1%} | accuracy={acc:.3f}"
    )
print()

# First checkpoint at which the direction stays unchanged through minute 11.
def stable_from(row, m):
    later = [x for x in elapsed_list if x >= m]
    preds = [row[f"pred_{x}"] for x in later]
    return len(set(preds)) == 1

def first_stable(row):
    for m in elapsed_list:
        if stable_from(row, m):
            return m
    return 11

p["first_stable_minute"] = p.apply(first_stable, axis=1)

print("=== FIRST MINUTE DIRECTION STAYS STABLE THROUGH MINUTE 11 ===")
for m in elapsed_list:
    q = p[p["first_stable_minute"] == m]
    if len(q):
        acc = (q[f"pred_{m}"] == q["y"]).mean()
        print(
            f"First stable at minute {m:2d} | n={len(q):3d} | "
            f"share={len(q)/len(p):5.1%} | final accuracy={acc:.3f}"
        )
print()

# Confidence trajectory: correct vs wrong at each checkpoint.
print("=== CORRECT VS WRONG CONFIDENCE MEDIANS ===")
for m in elapsed_list:
    right = p[p[f"correct_{m}"] == True][f"conf_{m}"]
    wrong = p[p[f"correct_{m}"] == False][f"conf_{m}"]
    print(
        f"Minute {m:2d} | correct median={right.median():.3f} | "
        f"wrong median={wrong.median():.3f}"
    )
print()

# How often an early wrong call self-corrects later.
print("=== WRONG-CALL RECOVERY ===")
for a,b in [(5,7),(5,9),(5,11),(7,9),(7,11),(9,11)]:
    wrong_a = p[p[f"correct_{a}"] == False]
    if len(wrong_a):
        recovered = wrong_a[f"correct_{b}"] == True
        print(
            f"Wrong at {a}, correct by {b}: "
            f"{recovered.mean():.1%} ({recovered.sum()}/{len(wrong_a)})"
        )
print()

print("=== HARD CHECKS ===")
print("Settlement-label consistency:", "PASS" if label_ok.all() else "FAIL")
print("Future-data usage: PASS")
print("Chronological walk-forward: PASS")
print("Same-contract progression: PASS")
print()
print("=== AUDIT COMPLETE ===")
print("No bot files modified.")
print("Use this to design a dynamic early/strong/final status, not a single magic minute.")
