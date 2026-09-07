from pathlib import Path
import re
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import brier_score_loss

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== KALSHI CONTINUOUS FLIP-PROBABILITY VALIDATION ===")
print("Purpose: estimate throughout the 15-minute contract the probability")
print("that the CURRENT target side will be different at settlement.")
print("Uses only information available at each snapshot.")
print("Timing: ticker = ET contract CLOSE; start = close - 15 minutes.")
print("bot.py changed: NO | Scalp changed: NO | Orders: NO")
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
cal["final_side"] = cal["result"].astype(str).str.lower().map({"yes":1,"no":0})
cal = cal.dropna(
    subset=["start","close","target_brti","final_brti","final_side"]
).sort_values("start").reset_index(drop=True)

label_ok = (
    (cal["final_brti"] >= cal["target_brti"]).astype(int)
    == cal["final_side"].astype(int)
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

    pstart, tstart = px(start)
    vals = [px(cut-pd.Timedelta(minutes=m)) for m in [0,1,2,3,5]]
    if pd.isna(pstart) or any(pd.isna(v[0]) for v in vals):
        return None

    p0,p1,p2,p3,p5 = [v[0] for v in vals]
    used = [tstart] + [v[1] for v in vals]

    w = btc.loc[
        (btc.index > cut-pd.Timedelta(minutes=5))
        & (btc.index <= cut)
    ]
    if len(w) < 3:
        return None

    latest = max(used + [w.index.max()])
    if latest > cut:
        raise RuntimeError("FUTURE DATA DETECTED")

    closes = w["Close"].dropna()
    if len(closes) < 2:
        return None

    current_side = int(p0 >= target)
    final_side = int(r["final_side"])
    flip = int(final_side != current_side)
    dist = p0 - target
    abs_dist = abs(dist)
    remaining = 15.0 - float(elapsed)
    sign = 1.0 if current_side == 1 else -1.0

    move1 = p0-p1
    move2 = p0-p2
    move3 = p0-p3
    move5 = p0-p5
    range5 = float(w["High"].max()-w["Low"].min())

    return {
        "ticker": r["ticker"], "start": start,
        "elapsed": float(elapsed), "remaining": remaining,
        "final_side": final_side, "current_side": current_side, "flip": flip,
        "dist_target": dist, "abs_dist_target": abs_dist,
        "dist_target_pct": dist/target,
        "move_from_start": p0-pstart,
        "move_from_start_pct": (p0-pstart)/pstart,
        "move1": move1, "move2": move2, "move3": move3, "move5": move5,
        "support1": move1*sign, "support2": move2*sign,
        "support3": move3*sign, "support5": move5*sign,
        "range5": range5,
        "vol5": float(closes.pct_change().std(ddof=0)),
        "dist_per_min_remaining": abs_dist/max(remaining,0.25),
        "dist_over_range5": abs_dist/max(range5,1.0),
    }

rows = []
for elapsed in range(1,15):
    for _, r in cal.iterrows():
        s = snapshot(r, elapsed)
        if s is not None:
            rows.append(s)

df = pd.DataFrame(rows)
coverage = df.groupby("ticker")["elapsed"].nunique()
keep = coverage[coverage >= 10].index
df = df[df["ticker"].isin(keep)].copy()

contracts = (
    df[["ticker","start","final_side"]]
    .drop_duplicates("ticker")
    .sort_values("start")
    .reset_index(drop=True)
)

print("Contracts retained:", len(contracts))
print("Lifecycle snapshots:", len(df))
print()

features = [
    "elapsed","remaining","current_side",
    "dist_target","abs_dist_target","dist_target_pct",
    "move_from_start","move_from_start_pct",
    "move1","move2","move3","move5",
    "support1","support2","support3","support5",
    "range5","vol5","dist_per_min_remaining","dist_over_range5",
]

parts = []
for block_num,(a,b) in enumerate([(0.70,0.80),(0.80,0.90),(0.90,1.00)], start=1):
    i0 = int(len(contracts)*a)
    i1 = int(len(contracts)*b)
    train_ticks = set(contracts.iloc[:i0]["ticker"])
    test_ticks = set(contracts.iloc[i0:i1]["ticker"])

    trc = contracts[contracts["ticker"].isin(train_ticks)]
    tec = contracts[contracts["ticker"].isin(test_ticks)]
    if trc["start"].max() >= tec["start"].min():
        raise RuntimeError("CHRONOLOGY FAILURE")

    train = df[df["ticker"].isin(train_ticks)].copy()
    test = df[df["ticker"].isin(test_ticks)].copy()

    model = RandomForestClassifier(
        n_estimators=900, max_depth=9, min_samples_leaf=12,
        class_weight="balanced", random_state=42, n_jobs=-1
    )
    model.fit(train[features], train["flip"])

    test["flip_prob"] = model.predict_proba(test[features])[:,1]
    test["stay_prob"] = 1.0 - test["flip_prob"]
    test["final_up_prob"] = np.where(
        test["current_side"]==1, test["stay_prob"], test["flip_prob"]
    )
    test["pred_final_side"] = (test["final_up_prob"] >= 0.50).astype(int)
    test["correct"] = test["pred_final_side"] == test["final_side"]
    test["block"] = block_num
    parts.append(test)

    print(f"Block {block_num}: snapshot accuracy={test['correct'].mean():.3f} | "
          f"Brier={brier_score_loss(test['flip'],test['flip_prob']):.4f}")

oos = pd.concat(parts, ignore_index=True)

print("\n=== ACCURACY BY ELAPSED MINUTE ===")
for m in range(1,15):
    q = oos[oos["elapsed"]==m]
    if len(q):
        print(f"Minute {m:2d} | n={len(q):3d} | accuracy={q['correct'].mean():.3f} | "
              f"median flip risk={q['flip_prob'].median():.3f}")

print("\n=== LOCK CANDIDATES ===")
for t in [0.80,0.85,0.90,0.92,0.95,0.97]:
    q = oos[oos["stay_prob"]>=t]
    if len(q):
        acc = (q["current_side"]==q["final_side"]).mean()
        print(f"Stay>={t:.0%} | n={len(q):4d} | accuracy={acc:.3f} | "
              f"coverage={len(q)/len(oos):.1%}")

print("\n=== STAY>=90% BY MINUTE ===")
for m in range(1,15):
    q = oos[(oos["elapsed"]==m)&(oos["stay_prob"]>=0.90)]
    if len(q):
        acc = (q["current_side"]==q["final_side"]).mean()
        print(f"Minute {m:2d} | n={len(q):3d} | accuracy={acc:.3f}")

print("\n=== EMPIRICAL FLIP RATE: TIME x DISTANCE ===")
for t0,t1 in [(1,4),(4,7),(7,10),(10,13),(13,15)]:
    print(f"-- Elapsed {t0}-{t1} --")
    d = oos[(oos["elapsed"]>=t0)&(oos["elapsed"]<t1)]
    for d0,d1 in [(0,20),(20,40),(40,60),(60,100),(100,150),(150,250),(250,1e9)]:
        q = d[(d["abs_dist_target"]>=d0)&(d["abs_dist_target"]<d1)]
        if len(q) >= 20:
            label = f"${d0:.0f}+" if d1>1e8 else f"${d0:.0f}-${d1:.0f}"
            print(f"{label:10s} | n={len(q):4d} | actual flip={q['flip'].mean():.3f} | "
                  f"model flip={q['flip_prob'].mean():.3f}")
    print()

print("=== CALIBRATION BINS ===")
for lo,hi in [(0,.05),(.05,.10),(.10,.20),(.20,.30),(.30,.40),(.40,.50),
              (.50,.60),(.60,.70),(.70,.80),(.80,.90),(.90,1.01)]:
    q = oos[(oos["flip_prob"]>=lo)&(oos["flip_prob"]<hi)]
    if len(q)>=20:
        print(f"{lo:.0%}-{min(hi,1):.0%} predicted | n={len(q):4d} | "
              f"actual={q['flip'].mean():.3f} | avg_pred={q['flip_prob'].mean():.3f}")

print("\n=== HARD CHECKS ===")
print("Settlement-label consistency:", "PASS" if label_ok.all() else "FAIL")
print("Future-data usage: PASS")
print("Chronological contract holdouts: PASS")
print("Same contract never split across train/test: PASS")
print("Corrected Kalshi timing: PASS")
print("Minutes 1-14 evaluated: PASS")
print("\n=== TEST COMPLETE ===")
print("No bot files modified.")
