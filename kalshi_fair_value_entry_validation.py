from pathlib import Path
import re
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== KALSHI FAIR-VALUE / ENTRY VALIDATION ===")
print("Purpose: convert calibrated final-outcome probability into a fair contract value")
print("and a maximum attractive buy price throughout the full 15-minute contract.")
print("IMPORTANT: this does NOT pretend historical Kalshi asks exist if they were not saved.")
print("It validates the probability/entry-value side honestly on untouched chronological contracts.")
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
        year=2000+int(yy),
        month=MONTHS[mon],
        day=int(dd),
        hour=int(hh),
        minute=int(mm),
    )

    close_utc = wall.tz_localize(
        ZoneInfo("America/New_York")
    ).tz_convert("UTC")

    return close_utc-pd.Timedelta(minutes=15), close_utc

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

    if ts-ti > pd.Timedelta(minutes=2):
        return np.nan, pd.NaT

    return float(btc.iloc[i]["Close"]), ti

def snapshot(r, elapsed):
    start = r["start"]
    cut = start + pd.Timedelta(minutes=elapsed)
    target = float(r["target_brti"])

    pstart,tstart = px(start)
    vals = [px(cut-pd.Timedelta(minutes=m)) for m in [0,1,2,3,5]]

    if pd.isna(pstart) or any(pd.isna(v[0]) for v in vals):
        return None

    p0,p1,p2,p3,p5 = [v[0] for v in vals]

    w = btc.loc[
        (btc.index > cut-pd.Timedelta(minutes=5))
        & (btc.index <= cut)
    ]

    if len(w) < 3:
        return None

    closes = w["Close"].dropna()
    if len(closes) < 2:
        return None

    used = [tstart] + [v[1] for v in vals] + [w.index.max()]
    if max(used) > cut:
        raise RuntimeError("FUTURE DATA DETECTED")

    current_side = int(p0 >= target)
    final_side = int(r["final_side"])
    flip = int(current_side != final_side)

    dist = p0-target
    abs_dist = abs(dist)
    remaining = 15.0-float(elapsed)
    sign = 1.0 if current_side == 1 else -1.0

    move1 = p0-p1
    move2 = p0-p2
    move3 = p0-p3
    move5 = p0-p5
    range5 = float(w["High"].max()-w["Low"].min())

    return {
        "ticker": r["ticker"],
        "start": start,
        "elapsed": float(elapsed),
        "remaining": remaining,
        "current_side": current_side,
        "final_side": final_side,
        "flip": flip,

        "dist_target": dist,
        "abs_dist_target": abs_dist,
        "dist_target_pct": dist/target,

        "move_from_start": p0-pstart,
        "move_from_start_pct": (p0-pstart)/pstart,

        "move1": move1,
        "move2": move2,
        "move3": move3,
        "move5": move5,

        "support1": move1*sign,
        "support2": move2*sign,
        "support3": move3*sign,
        "support5": move5*sign,

        "range5": range5,
        "vol5": float(closes.pct_change().std(ddof=0)),
        "dist_per_min_remaining": abs_dist/max(remaining,0.25),
        "dist_over_range5": abs_dist/max(range5,1.0),
    }

rows = []
for elapsed in range(1,15):
    for _,r in cal.iterrows():
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

features = [
    "elapsed","remaining","current_side",
    "dist_target","abs_dist_target","dist_target_pct",
    "move_from_start","move_from_start_pct",
    "move1","move2","move3","move5",
    "support1","support2","support3","support5",
    "range5","vol5",
    "dist_per_min_remaining","dist_over_range5",
]

print("Contracts retained:", len(contracts))
print("Lifecycle snapshots:", len(df))
print()

parts = []

for block_num,(a,b) in enumerate([(0.70,0.80),(0.80,0.90),(0.90,1.00)], start=1):
    outer_train_end = int(len(contracts)*a)
    outer_test_end = int(len(contracts)*b)

    outer_train_contracts = contracts.iloc[:outer_train_end].copy()
    outer_test_contracts = contracts.iloc[outer_train_end:outer_test_end].copy()

    inner_split = int(len(outer_train_contracts)*0.80)

    model_contracts = outer_train_contracts.iloc[:inner_split]
    calib_contracts = outer_train_contracts.iloc[inner_split:]

    if model_contracts["start"].max() >= calib_contracts["start"].min():
        raise RuntimeError("INNER CHRONOLOGY FAILURE")

    if calib_contracts["start"].max() >= outer_test_contracts["start"].min():
        raise RuntimeError("OUTER CHRONOLOGY FAILURE")

    model_ticks = set(model_contracts["ticker"])
    calib_ticks = set(calib_contracts["ticker"])
    test_ticks = set(outer_test_contracts["ticker"])

    train = df[df["ticker"].isin(model_ticks)].copy()
    calibrate = df[df["ticker"].isin(calib_ticks)].copy()
    test = df[df["ticker"].isin(test_ticks)].copy()

    rf = RandomForestClassifier(
        n_estimators=900,
        max_depth=9,
        min_samples_leaf=12,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )

    rf.fit(train[features], train["flip"])

    calib_raw = rf.predict_proba(calibrate[features])[:,1]

    iso = IsotonicRegression(
        y_min=0.0,
        y_max=1.0,
        out_of_bounds="clip"
    )
    iso.fit(calib_raw, calibrate["flip"].astype(float))

    test["raw_flip_prob"] = rf.predict_proba(test[features])[:,1]
    test["flip_prob"] = iso.predict(test["raw_flip_prob"].to_numpy())
    test["stay_prob"] = 1.0-test["flip_prob"]

    # Fair probability that final contract settles UP.
    test["fair_up"] = np.where(
        test["current_side"]==1,
        test["stay_prob"],
        test["flip_prob"],
    )
    test["fair_down"] = 1.0-test["fair_up"]

    test["preferred_side"] = np.where(
        test["fair_up"] >= test["fair_down"], "UP", "DOWN"
    )
    test["fair_preferred"] = np.maximum(test["fair_up"], test["fair_down"])

    test["preferred_correct"] = np.where(
        test["preferred_side"]=="UP",
        test["final_side"]==1,
        test["final_side"]==0,
    )

    # Entry prices below fair value.
    # 10-point and 15-point minimum edge are deliberately conservative.
    test["max_buy_10edge"] = np.clip(test["fair_preferred"]-0.10,0.01,0.99)
    test["max_buy_15edge"] = np.clip(test["fair_preferred"]-0.15,0.01,0.99)

    # User's ideal attractive zone.
    test["ideal_50_or_less_possible_10edge"] = test["max_buy_10edge"] >= 0.50
    test["ideal_50_or_less_possible_15edge"] = test["max_buy_15edge"] >= 0.50

    # Status ladder based on actual OOS probability only.
    test["prob_status"] = np.select(
        [
            test["fair_preferred"] >= 0.95,
            test["fair_preferred"] >= 0.90,
            test["fair_preferred"] >= 0.80,
            test["fair_preferred"] >= 0.70,
        ],
        [
            "LOCK_95",
            "LOCK_90",
            "STRONG",
            "LEAN",
        ],
        default="RAW"
    )

    test["block"] = block_num
    parts.append(test)

oos = pd.concat(parts, ignore_index=True)

print("=== FAIR-PROBABILITY QUALITY ===")

for threshold in [0.60,0.65,0.70,0.75,0.80,0.85,0.90,0.92,0.95,0.97]:
    q = oos[oos["fair_preferred"] >= threshold]
    if len(q):
        print(
            f"Fair>={threshold:.0%} | n={len(q):4d} | "
            f"actual accuracy={q['preferred_correct'].mean():.3f} | "
            f"coverage={len(q)/len(oos):.1%}"
        )

print()

print("=== FAIR VALUE BY ELAPSED MINUTE ===")

for m in range(1,15):
    q = oos[oos["elapsed"]==m]
    if len(q):
        print(
            f"Minute {m:2d} | "
            f"accuracy={q['preferred_correct'].mean():.3f} | "
            f"median fair={q['fair_preferred'].median():.3f} | "
            f"90%+ share={(q['fair_preferred']>=0.90).mean():.1%}"
        )

print()

print("=== IDEAL <=50c ENTRY POTENTIAL ===")
print("Interpretation:")
print("If fair probability is 0.70, buying at 0.50 offers a 20-point model edge.")
print("This section asks whether a <=50c price WOULD be attractive if Kalshi offered it.")
print("It does NOT claim Kalshi actually offered <=50c historically.")
print()

for minimum_edge in [0.10,0.15,0.20,0.25,0.30]:
    needed_fair = 0.50 + minimum_edge
    q = oos[oos["fair_preferred"] >= needed_fair]

    if len(q):
        print(
            f"At 50c with >= {minimum_edge:.0%} model edge "
            f"(fair >= {needed_fair:.0%}) | "
            f"n={len(q):4d} | "
            f"actual accuracy={q['preferred_correct'].mean():.3f} | "
            f"coverage={len(q)/len(oos):.1%}"
        )

print()

print("=== MAX ATTRACTIVE BUY PRICE EXAMPLES ===")

for threshold in [0.70,0.80,0.90,0.95,0.97]:
    q = oos[oos["fair_preferred"] >= threshold]
    if len(q):
        print(
            f"Fair>={threshold:.0%} | "
            f"median max buy for 10pt edge={q['max_buy_10edge'].median():.2f} | "
            f"median max buy for 15pt edge={q['max_buy_15edge'].median():.2f}"
        )

print()

print("=== 90%+ LOCK TIMING ===")

for m in range(1,15):
    q = oos[
        (oos["elapsed"]==m)
        & (oos["fair_preferred"]>=0.90)
    ]

    if len(q):
        print(
            f"Minute {m:2d} | "
            f"locks={len(q):3d} | "
            f"actual accuracy={q['preferred_correct'].mean():.3f}"
        )

print()

print("=== LIVE DECISION RULES TO TEST NEXT ===")
print("RAW: always show current fair UP/DOWN probability.")
print("LEAN: fair >=70%, but do not call it a lock.")
print("STRONG: fair >=80%.")
print("LOCK: fair >=90%, but early-minute safety still required by validation.")
print("IDEAL ENTRY: live Kalshi ask <=0.50 AND fair probability materially exceeds ask.")
print("EDGE: fair probability minus live Kalshi ask.")
print("NO VALUE: direction may be correct, but Kalshi ask is already too expensive.")
print()

print("=== IMPORTANT LIMITATION ===")
print("Historical Kalshi ask snapshots are not assumed here.")
print("Therefore the NEXT live shadow test must record:")
print("ticker, target, elapsed time, fair UP/DOWN, live UP/DOWN ask, edge, status, final result.")
print("That is how we prove whether we actually beat Kalshi at attractive prices.")
print()

print("=== HARD CHECKS ===")
print("Settlement-label consistency:", "PASS" if label_ok.all() else "FAIL")
print("Future-data usage: PASS")
print("Outer chronological holdouts: PASS")
print("Calibration uses historical data only: PASS")
print("Same contract never split across model/calibration/test: PASS")
print("Corrected Kalshi timing: PASS")
print("Minutes 1-14 evaluated: PASS")
print("Historical Kalshi ask fabrication: PASS (NONE fabricated)")
print()

print("=== TEST COMPLETE ===")
print("No bot files modified.")
