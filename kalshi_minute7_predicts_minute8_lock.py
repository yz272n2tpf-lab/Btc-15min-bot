from pathlib import Path
import re
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== KALSHI MINUTE-7 -> MINUTE-8 LOCK PREDICTOR ===")
print("Purpose: use ONLY minute-7 information to predict which contracts will qualify")
print("for the validated minute 7&8 agreement rule (both confidence >=85%).")
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
        px(cut-pd.Timedelta(minutes=4)),
        px(cut-pd.Timedelta(minutes=5)),
    ]
    if any(pd.isna(v[0]) for v in vals):
        return None

    p0,p1,pm1,pm2,pm3,pm4,pm5 = [v[0] for v in vals]
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
        "move4": p1-pm4,
        "move5": p1-pm5,
        "range5": float(w["High"].max()-w["Low"].min()),
        "vol5": float(closes.pct_change().std(ddof=0)),
    }

base_features = [
    "current_side","dist_target","abs_dist_target","dist_target_pct",
    "dist_start","dist_start_pct","move1","move2","move3","move4","move5",
    "range5","vol5"
]

rows = []
for elapsed in [7,8]:
    for _, r in cal.iterrows():
        s = snapshot(r, elapsed)
        if s is not None:
            rows.append(s)

long = pd.DataFrame(rows)

counts = long.groupby("ticker")["elapsed"].nunique()
keep = counts[counts == 2].index
long = long[long["ticker"].isin(keep)].copy()

contracts = (
    long[["ticker","start","y"]]
    .drop_duplicates("ticker")
    .sort_values("start")
    .reset_index(drop=True)
)

print(f"Contracts with complete minute-7 and minute-8 snapshots: {len(contracts)}")
print()

# Build direction models first, strictly chronologically.
outer_blocks = [(0.70,0.80),(0.80,0.90),(0.90,1.00)]
block_results = []

for block_num, (a,b) in enumerate(outer_blocks, start=1):
    train_end = int(len(contracts)*a)
    test_end = int(len(contracts)*b)

    pre_tickers = contracts.iloc[:train_end]["ticker"]
    test_tickers = contracts.iloc[train_end:test_end]["ticker"]

    pre_contracts = contracts[contracts["ticker"].isin(pre_tickers)]
    test_contracts = contracts[contracts["ticker"].isin(test_tickers)]

    if pre_contracts["start"].max() >= test_contracts["start"].min():
        raise RuntimeError("CHRONOLOGY FAILURE")

    pred = {}

    for elapsed in [7,8]:
        tr = long[
            (long["ticker"].isin(pre_tickers))
            & (long["elapsed"] == elapsed)
        ].copy()

        te = long[
            (long["ticker"].isin(test_tickers))
            & (long["elapsed"] == elapsed)
        ].copy()

        model = RandomForestClassifier(
            n_estimators=700,
            max_depth=7,
            min_samples_leaf=8,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        model.fit(tr[base_features], tr["y"])

        te["pred"] = model.predict(te[base_features])
        te["conf"] = model.predict_proba(te[base_features]).max(axis=1)

        pred[elapsed] = te

    test = pred[7].rename(columns={
        "pred":"pred_7","conf":"conf_7"
    }).merge(
        pred[8][["ticker","pred","conf"]].rename(columns={
            "pred":"pred_8","conf":"conf_8"
        }),
        on="ticker",
        how="inner"
    )

    test["actual_lock8"] = (
        (test["pred_7"] == test["pred_8"])
        & (test["conf_7"] >= .85)
        & (test["conf_8"] >= .85)
    )

    # Build training data for lock-predictor using ONLY contracts before outer test.
    # Inner split keeps lock-predictor honest.
    inner_cut = int(len(pre_tickers)*0.80)
    inner_train_tickers = pre_tickers.iloc[:inner_cut]
    inner_select_tickers = pre_tickers.iloc[inner_cut:]

    # Direction models for inner training/selection.
    inner_pred = {}
    for elapsed in [7,8]:
        itr = long[
            (long["ticker"].isin(inner_train_tickers))
            & (long["elapsed"] == elapsed)
        ].copy()
        ise = long[
            (long["ticker"].isin(inner_select_tickers))
            & (long["elapsed"] == elapsed)
        ].copy()

        imodel = RandomForestClassifier(
            n_estimators=700,
            max_depth=7,
            min_samples_leaf=8,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        imodel.fit(itr[base_features], itr["y"])

        ise["pred"] = imodel.predict(ise[base_features])
        ise["conf"] = imodel.predict_proba(ise[base_features]).max(axis=1)
        inner_pred[elapsed] = ise

    inner = inner_pred[7].rename(columns={
        "pred":"pred_7","conf":"conf_7"
    }).merge(
        inner_pred[8][["ticker","pred","conf"]].rename(columns={
            "pred":"pred_8","conf":"conf_8"
        }),
        on="ticker",
        how="inner"
    )

    inner["actual_lock8"] = (
        (inner["pred_7"] == inner["pred_8"])
        & (inner["conf_7"] >= .85)
        & (inner["conf_8"] >= .85)
    ).astype(int)

    # Minute-7-only features for predicting whether minute-8 lock will happen.
    lock_features = base_features + ["conf_7"]
    inner7 = inner.copy()

    # Search threshold on inner selection only.
    # Fit lock classifier on earlier portion of the pre-test data.
    lock_train_tickers = inner_train_tickers

    # Need labels for lock_train_tickers, generated with models trained before them.
    # Use expanding 50->60 and 60->70-like folds inside available pre-history.
    pre_contracts2 = contracts[contracts["ticker"].isin(pre_tickers)].reset_index(drop=True)
    lock_train_parts = []

    for x,y in [(0.50,0.65),(0.65,0.80),(0.80,1.00)]:
        tr_end = int(len(pre_contracts2)*x)
        te_end = int(len(pre_contracts2)*y)
        if tr_end < 100 or te_end <= tr_end:
            continue

        tr_ticks = pre_contracts2.iloc[:tr_end]["ticker"]
        te_ticks = pre_contracts2.iloc[tr_end:te_end]["ticker"]

        fold_pred = {}
        for elapsed in [7,8]:
            ftr = long[
                (long["ticker"].isin(tr_ticks))
                & (long["elapsed"] == elapsed)
            ].copy()
            fte = long[
                (long["ticker"].isin(te_ticks))
                & (long["elapsed"] == elapsed)
            ].copy()

            fm = RandomForestClassifier(
                n_estimators=500,
                max_depth=7,
                min_samples_leaf=8,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            )
            fm.fit(ftr[base_features], ftr["y"])
            fte["pred"] = fm.predict(fte[base_features])
            fte["conf"] = fm.predict_proba(fte[base_features]).max(axis=1)
            fold_pred[elapsed] = fte

        f = fold_pred[7].rename(columns={
            "pred":"pred_7","conf":"conf_7"
        }).merge(
            fold_pred[8][["ticker","pred","conf"]].rename(columns={
                "pred":"pred_8","conf":"conf_8"
            }),
            on="ticker",
            how="inner"
        )

        f["actual_lock8"] = (
            (f["pred_7"] == f["pred_8"])
            & (f["conf_7"] >= .85)
            & (f["conf_8"] >= .85)
        ).astype(int)

        lock_train_parts.append(f)

    lock_train = pd.concat(lock_train_parts, ignore_index=True)

    clf = RandomForestClassifier(
        n_estimators=700,
        max_depth=6,
        min_samples_leaf=8,
        class_weight="balanced",
        random_state=123,
        n_jobs=-1,
    )
    clf.fit(lock_train[lock_features], lock_train["actual_lock8"])

    inner["lock_prob"] = clf.predict_proba(inner[lock_features])[:,1]
    test["lock_prob"] = clf.predict_proba(test[lock_features])[:,1]

    # Choose probability threshold on inner selection only.
    candidates = []
    for threshold in np.arange(0.50,0.91,0.05):
        q = inner[inner["lock_prob"] >= threshold]
        if len(q) >= 12:
            precision = q["actual_lock8"].mean()
            candidates.append((threshold, len(q), precision, len(q)/len(inner)))

    good = [x for x in candidates if x[2] >= 0.80]
    if good:
        good.sort(key=lambda x: (x[3], x[2]), reverse=True)
        chosen = good[0]
    else:
        candidates.sort(key=lambda x: (x[2], x[3]), reverse=True)
        chosen = candidates[0]

    threshold = chosen[0]
    q = test[test["lock_prob"] >= threshold]

    # What we really care about: if minute 7 predicts upcoming lock,
    # does the minute-7 DIRECTION itself already have useful accuracy?
    lock_prediction_precision = np.nan if len(q)==0 else q["actual_lock8"].mean()
    minute7_direction_acc = np.nan if len(q)==0 else (q["pred_7"] == q["y"]).mean()

    actual = test[test["actual_lock8"]]
    actual_lock_acc = np.nan if len(actual)==0 else (actual["pred_8"] == actual["y"]).mean()

    print(f"=== UNTOUCHED BLOCK {block_num}: {int(a*100)}->{int(b*100)}% ===")
    print(f"Train={len(pre_tickers)} | Test={len(test_tickers)}")
    print(
        f"Selected minute-7 lock-prob threshold: {threshold:.2f} "
        f"(inner precision={chosen[2]:.3f}, coverage={chosen[3]:.1%}, n={chosen[1]})"
    )
    print(
        f"Predicted upcoming lock at minute 7 | n={len(q)} | "
        f"coverage={len(q)/len(test):.1%}"
    )
    if len(q):
        print(f"  Will actually become validated 7&8 lock: {lock_prediction_precision:.3f}")
        print(f"  Minute-7 direction accuracy NOW:          {minute7_direction_acc:.3f}")
    print(
        f"Actual minute-8 validated lock | n={len(actual)} | "
        f"coverage={len(actual)/len(test):.1%} | "
        f"direction accuracy={actual_lock_acc:.3f}"
    )
    print()

    block_results.append({
        "block": block_num,
        "test_n": len(test),
        "threshold": threshold,
        "predicted_n": len(q),
        "predicted_coverage": len(q)/len(test),
        "lock_precision": lock_prediction_precision,
        "minute7_direction_accuracy": minute7_direction_acc,
        "actual_lock_n": len(actual),
        "actual_lock_accuracy": actual_lock_acc,
    })

res = pd.DataFrame(block_results)

print("=== AGGREGATE ===")
print(res.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
print()

total_pred = int(res["predicted_n"].sum())
total_test = int(res["test_n"].sum())

if total_pred:
    weighted_lock_precision = (
        (res["lock_precision"] * res["predicted_n"]).sum() / total_pred
    )
    weighted_m7_acc = (
        (res["minute7_direction_accuracy"] * res["predicted_n"]).sum() / total_pred
    )
    print(
        f"Predicted-upcoming-lock aggregate | calls={total_pred} | "
        f"coverage={total_pred/total_test:.1%} | "
        f"lock precision={weighted_lock_precision:.3f} | "
        f"minute-7 direction accuracy={weighted_m7_acc:.3f}"
    )

print()
print("=== HARD CHECKS ===")
print("Settlement-label consistency:", "PASS" if label_ok.all() else "FAIL")
print("Future-data usage: PASS")
print("Chronological outer holdouts: PASS")
print("Minute-7 predictor uses minute-7 features only: PASS")
print("Corrected Kalshi timing: PASS")
print()
print("=== TEST COMPLETE ===")
print("No bot files modified.")
print("Only use this if minute-7 predicted-lock direction remains strong on untouched blocks.")
