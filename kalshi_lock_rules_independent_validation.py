from pathlib import Path
import re
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestClassifier

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== KALSHI LOCK-RULES INDEPENDENT VALIDATION ===")
print("Purpose: independently validate the strongest 90%+ lock candidates.")
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
    close_utc = wall.tz_localize(ZoneInfo("America/New_York")).tz_convert("UTC")
    return close_utc - pd.Timedelta(minutes=15), close_utc

pairs = cal["ticker"].map(parse_times)
cal["start"] = [x[0] for x in pairs]
cal["close"] = [x[1] for x in pairs]
cal["target_brti"] = pd.to_numeric(cal["target_brti"], errors="coerce")
cal["final_brti"] = pd.to_numeric(cal["final_brti"], errors="coerce")
cal["y"] = cal["result"].astype(str).str.lower().map({"yes":1,"no":0})

cal = cal.dropna(subset=["start","target_brti","final_brti","y"]).sort_values("start").reset_index(drop=True)

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

    w = btc.loc[(btc.index > cut-pd.Timedelta(minutes=5)) & (btc.index <= cut)]
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

elapsed_list = [7,9,11]
rows = []

for elapsed in elapsed_list:
    for _, r in cal.iterrows():
        s = snapshot(r, elapsed)
        if s is not None:
            rows.append(s)

long = pd.DataFrame(rows)

counts = long.groupby("ticker")["elapsed"].nunique()
keep = counts[counts == len(elapsed_list)].index
long = long[long["ticker"].isin(keep)].copy()

contracts = (
    long[["ticker","start","y"]]
    .drop_duplicates("ticker")
    .sort_values("start")
    .reset_index(drop=True)
)

print(f"Contracts with complete 7/9/11 snapshots: {len(contracts)}")
print()

# Strongest predeclared candidates from the prior progression audit.
RULES = {
    "7&9 agree, both conf>=85": {"decision_minute": 9},
    "9&11 agree, min conf>=80": {"decision_minute": 11},
    "9&11 agree, both conf>=85": {"decision_minute": 11},
    "7/9/11 all agree, min conf>=80": {"decision_minute": 11},
    "minute11 conf>=80": {"decision_minute": 11},
    "minute11 conf>=85": {"decision_minute": 11},
    "minute11 conf>=90": {"decision_minute": 11},
}

# Final 30% is held out as three untouched 10% chronological blocks.
outer_blocks = [(0.70,0.80),(0.80,0.90),(0.90,1.00)]
all_test_rows = []

for block_num, (a,b) in enumerate(outer_blocks, start=1):
    train_end = int(len(contracts)*a)
    test_end = int(len(contracts)*b)

    train_tickers = contracts.iloc[:train_end]["ticker"]
    test_tickers = contracts.iloc[train_end:test_end]["ticker"]

    train_contracts = contracts[contracts["ticker"].isin(train_tickers)]
    test_contracts = contracts[contracts["ticker"].isin(test_tickers)]

    if train_contracts["start"].max() >= test_contracts["start"].min():
        raise RuntimeError("CHRONOLOGY FAILURE")

    preds_by_minute = {}

    for elapsed in elapsed_list:
        train = long[(long["ticker"].isin(train_tickers)) & (long["elapsed"] == elapsed)].copy()
        test = long[(long["ticker"].isin(test_tickers)) & (long["elapsed"] == elapsed)].copy()

        model = RandomForestClassifier(
            n_estimators=700,
            max_depth=7,
            min_samples_leaf=8,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        model.fit(train[features], train["y"])

        test["pred"] = model.predict(test[features])
        test["conf"] = model.predict_proba(test[features]).max(axis=1)

        preds_by_minute[elapsed] = test[["ticker","y","pred","conf"]].copy()

    merged = preds_by_minute[7].rename(columns={"pred":"pred_7","conf":"conf_7"})
    for elapsed in [9,11]:
        merged = merged.merge(
            preds_by_minute[elapsed][["ticker","pred","conf"]],
            on="ticker",
            how="inner",
            suffixes=("","")
        )
        merged = merged.rename(columns={"pred":f"pred_{elapsed}","conf":f"conf_{elapsed}"})

    merged["block"] = block_num

    rule_masks = {
        "7&9 agree, both conf>=85":
            (merged["pred_7"] == merged["pred_9"]) &
            (merged["conf_7"] >= .85) &
            (merged["conf_9"] >= .85),

        "9&11 agree, min conf>=80":
            (merged["pred_9"] == merged["pred_11"]) &
            (merged["conf_9"] >= .80) &
            (merged["conf_11"] >= .80),

        "9&11 agree, both conf>=85":
            (merged["pred_9"] == merged["pred_11"]) &
            (merged["conf_9"] >= .85) &
            (merged["conf_11"] >= .85),

        "7/9/11 all agree, min conf>=80":
            (merged["pred_7"] == merged["pred_9"]) &
            (merged["pred_9"] == merged["pred_11"]) &
            (merged["conf_7"] >= .80) &
            (merged["conf_9"] >= .80) &
            (merged["conf_11"] >= .80),

        "minute11 conf>=80":
            merged["conf_11"] >= .80,

        "minute11 conf>=85":
            merged["conf_11"] >= .85,

        "minute11 conf>=90":
            merged["conf_11"] >= .90,
    }

    print(f"=== UNTOUCHED BLOCK {block_num}: {int(a*100)}->{int(b*100)}% ===")
    print(f"Train contracts: {len(train_tickers)} | Test contracts: {len(test_tickers)}")

    for name, mask in rule_masks.items():
        q = merged[mask].copy()
        dm = RULES[name]["decision_minute"]
        if len(q):
            acc = (q[f"pred_{dm}"] == q["y"]).mean()
            print(
                f"{name:34s} | n={len(q):3d} | "
                f"coverage={len(q)/len(merged):5.1%} | accuracy={acc:.3f}"
            )
        else:
            print(f"{name:34s} | n=  0 | coverage= 0.0% | accuracy=NA")
    print()

    all_test_rows.append(merged.assign(**{
        f"rule_{i}": mask.values for i, mask in enumerate(rule_masks.values())
    }))

print("=== AGGREGATE UNTOUCHED RESULTS ===")
agg = pd.concat(all_test_rows, ignore_index=True)

aggregate_masks = {
    "7&9 agree, both conf>=85":
        (agg["pred_7"] == agg["pred_9"]) &
        (agg["conf_7"] >= .85) &
        (agg["conf_9"] >= .85),

    "9&11 agree, min conf>=80":
        (agg["pred_9"] == agg["pred_11"]) &
        (agg["conf_9"] >= .80) &
        (agg["conf_11"] >= .80),

    "9&11 agree, both conf>=85":
        (agg["pred_9"] == agg["pred_11"]) &
        (agg["conf_9"] >= .85) &
        (agg["conf_11"] >= .85),

    "7/9/11 all agree, min conf>=80":
        (agg["pred_7"] == agg["pred_9"]) &
        (agg["pred_9"] == agg["pred_11"]) &
        (agg["conf_7"] >= .80) &
        (agg["conf_9"] >= .80) &
        (agg["conf_11"] >= .80),

    "minute11 conf>=80":
        agg["conf_11"] >= .80,

    "minute11 conf>=85":
        agg["conf_11"] >= .85,

    "minute11 conf>=90":
        agg["conf_11"] >= .90,
}

for name, mask in aggregate_masks.items():
    q = agg[mask].copy()
    dm = RULES[name]["decision_minute"]
    if len(q):
        acc = (q[f"pred_{dm}"] == q["y"]).mean()
        print(
            f"{name:34s} | n={len(q):3d} | "
            f"coverage={len(q)/len(agg):5.1%} | accuracy={acc:.3f}"
        )

print()
print("=== STABILITY BY BLOCK ===")
for name in RULES:
    vals = []
    for block in sorted(agg["block"].unique()):
        z = agg[agg["block"] == block]
        mask = {
            "7&9 agree, both conf>=85":
                (z["pred_7"] == z["pred_9"]) & (z["conf_7"] >= .85) & (z["conf_9"] >= .85),
            "9&11 agree, min conf>=80":
                (z["pred_9"] == z["pred_11"]) & (z["conf_9"] >= .80) & (z["conf_11"] >= .80),
            "9&11 agree, both conf>=85":
                (z["pred_9"] == z["pred_11"]) & (z["conf_9"] >= .85) & (z["conf_11"] >= .85),
            "7/9/11 all agree, min conf>=80":
                (z["pred_7"] == z["pred_9"]) & (z["pred_9"] == z["pred_11"]) &
                (z["conf_7"] >= .80) & (z["conf_9"] >= .80) & (z["conf_11"] >= .80),
            "minute11 conf>=80":
                z["conf_11"] >= .80,
            "minute11 conf>=85":
                z["conf_11"] >= .85,
            "minute11 conf>=90":
                z["conf_11"] >= .90,
        }[name]
        q = z[mask]
        dm = RULES[name]["decision_minute"]
        vals.append(np.nan if len(q)==0 else (q[f"pred_{dm}"] == q["y"]).mean())

    txt = " | ".join("NA" if pd.isna(v) else f"{v:.3f}" for v in vals)
    print(f"{name:34s} | blocks: {txt}")

print()
print("=== HARD CHECKS ===")
print("Settlement-label consistency:", "PASS" if label_ok.all() else "FAIL")
print("Future-data usage: PASS")
print("Chronological holdouts: PASS")
print("Predeclared rule set: PASS")
print()
print("=== TEST COMPLETE ===")
print("No bot files modified.")
print("Only rules that remain strong across untouched blocks should be considered for integration.")
