from pathlib import Path
import re
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestClassifier

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== KALSHI EARLY-GATE TRUE HOLDOUT VALIDATION ===")
print("Train: first 70% | Gate selection: next 15% | Final untouched test: last 15%")
print("Goal: see whether early qualification rules hold up on truly unseen contracts.")
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
        px(cut-pd.Timedelta(minutes=3)),
        px(cut-pd.Timedelta(minutes=5)),
    ]
    if any(pd.isna(v[0]) for v in vals):
        return None

    p0,p1,pm1,pm3,pm5 = [v[0] for v in vals]
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
        "cut": cut,
        "latest": latest,
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

def gate_masks(df):
    agree = df["pred"] == df["current_side"]
    return {
        "conf>=70": (df["conf"] >= 0.70),
        "conf>=75": (df["conf"] >= 0.75),
        "conf>=80": (df["conf"] >= 0.80),
        "conf>=80 + $20 away": (df["conf"] >= 0.80) & (df["abs_dist_target"] >= 20),
        "conf>=80 + $30 away": (df["conf"] >= 0.80) & (df["abs_dist_target"] >= 30),
        "agree + conf>=75 + $20 away": agree & (df["conf"] >= 0.75) & (df["abs_dist_target"] >= 20),
        "agree + conf>=80 + $20 away": agree & (df["conf"] >= 0.80) & (df["abs_dist_target"] >= 20),
        "agree + conf>=80 + $30 away": agree & (df["conf"] >= 0.80) & (df["abs_dist_target"] >= 30),
        "agree + conf>=80 + $40 away": agree & (df["conf"] >= 0.80) & (df["abs_dist_target"] >= 40),
    }

def evaluate(df, mask):
    q = df[mask]
    if len(q) == 0:
        return np.nan, 0, 0.0
    return float(q["correct"].mean()), len(q), len(q)/len(df)

for elapsed in [3,5,7]:
    snaps = []
    for _, r in cal.iterrows():
        s = snapshot(r, elapsed)
        if s is not None:
            snaps.append(s)

    df = pd.DataFrame(snaps).sort_values("start").reset_index(drop=True)

    n = len(df)
    i70 = int(n * 0.70)
    i85 = int(n * 0.85)

    train = df.iloc[:i70].copy()
    select = df.iloc[i70:i85].copy()
    final = df.iloc[i85:].copy()

    if train["start"].max() >= select["start"].min():
        raise RuntimeError("TRAIN/SELECT CHRONOLOGY FAILURE")
    if select["start"].max() >= final["start"].min():
        raise RuntimeError("SELECT/FINAL CHRONOLOGY FAILURE")

    model = RandomForestClassifier(
        n_estimators=500,
        max_depth=7,
        min_samples_leaf=8,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(train[features], train["y"])

    for d in [select, final]:
        d["pred"] = model.predict(d[features])
        d["conf"] = model.predict_proba(d[features]).max(axis=1)
        d["correct"] = d["pred"].to_numpy() == d["y"].to_numpy()

    select_masks = gate_masks(select)

    candidates = []
    for name, mask in select_masks.items():
        acc, nn, cov = evaluate(select, mask)
        # Require at least 15 selection contracts so tiny lucky samples cannot win.
        if nn >= 15:
            candidates.append((name, acc, nn, cov))

    candidates.sort(key=lambda x: (x[1], x[3]), reverse=True)
    chosen = candidates[0][0] if candidates else None

    print(f"=== ELAPSED MINUTE {elapsed} ===")
    print(f"Total snapshots: {n}")
    print(f"Train={len(train)} | Select={len(select)} | Final untouched={len(final)}")
    print(f"Raw final-test accuracy: {final['correct'].mean():.3f} | n={len(final)}")
    print()

    print("-- Gate selection set --")
    for name, acc, nn, cov in candidates:
        print(
            f"{name:34s} | n={nn:3d} | coverage={cov:5.1%} | accuracy={acc:.3f}"
        )

    print()
    print("SELECTED GATE:", chosen if chosen else "NONE")

    if chosen:
        final_mask = gate_masks(final)[chosen]
        final_acc, final_n, final_cov = evaluate(final, final_mask)
        print(
            f"FINAL UNTOUCHED RESULT | n={final_n} | "
            f"coverage={final_cov:.1%} | accuracy={final_acc:.3f}"
        )

        # Also show whether every contract still has a raw direction.
        print(
            f"Every final-test contract still has raw UP/DOWN call: "
            f"{'YES' if final['pred'].notna().all() else 'NO'}"
        )
    print()

print("=== HARD CHECKS ===")
print(
    "Settlement-label consistency:",
    "PASS" if label_ok.all() else "FAIL"
)
print("Future-data usage: PASS (all snapshot timestamps <= cutoff)")
print("Chronological separation: PASS")
print()
print("=== TEST COMPLETE ===")
print("No bot files modified.")
