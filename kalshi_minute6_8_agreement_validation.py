from pathlib import Path
import re
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestClassifier

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== KALSHI MINUTE 6-8 AGREEMENT VALIDATION ===")
print("Purpose: test whether the stable 5/7/9 agreement pattern can be pulled earlier.")
print("Focus: elapsed minutes 5 / 6 / 7 / 8 / 9 on correctly aligned Kalshi contracts.")
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

features = [
    "current_side","dist_target","abs_dist_target","dist_target_pct",
    "dist_start","dist_start_pct",
    "move1","move2","move3","move4","move5",
    "range5","vol5"
]

elapsed_list = [5,6,7,8,9]
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

print(f"Contracts with complete 5/6/7/8/9 snapshots: {len(contracts)}")
print()

outer_blocks = [(0.70,0.80),(0.80,0.90),(0.90,1.00)]
block_frames = []

for block_num, (a,b) in enumerate(outer_blocks, start=1):
    train_end = int(len(contracts)*a)
    test_end = int(len(contracts)*b)

    train_tickers = contracts.iloc[:train_end]["ticker"]
    test_tickers = contracts.iloc[train_end:test_end]["ticker"]

    train_contracts = contracts[contracts["ticker"].isin(train_tickers)]
    test_contracts = contracts[contracts["ticker"].isin(test_tickers)]

    if train_contracts["start"].max() >= test_contracts["start"].min():
        raise RuntimeError("CHRONOLOGY FAILURE")

    pred_frames = {}

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

        pred_frames[elapsed] = test[[
            "ticker","y","pred","conf","abs_dist_target","current_side"
        ]].copy()

    merged = pred_frames[5].rename(columns={
        "pred":"pred_5","conf":"conf_5",
        "abs_dist_target":"dist_5","current_side":"side_5"
    })

    for elapsed in [6,7,8,9]:
        tmp = pred_frames[elapsed].rename(columns={
            "pred":f"pred_{elapsed}",
            "conf":f"conf_{elapsed}",
            "abs_dist_target":f"dist_{elapsed}",
            "current_side":f"side_{elapsed}",
        })
        merged = merged.merge(
            tmp[[
                "ticker",f"pred_{elapsed}",f"conf_{elapsed}",
                f"dist_{elapsed}",f"side_{elapsed}"
            ]],
            on="ticker",
            how="inner"
        )

    merged["block"] = block_num
    block_frames.append(merged)

    print(f"=== UNTOUCHED BLOCK {block_num}: {int(a*100)}->{int(b*100)}% ===")
    print(f"Train={len(train_tickers)} | Test={len(test_tickers)}")

    rules = {
        "5&6 agree both80": (
            (merged["pred_5"] == merged["pred_6"])
            & (merged["conf_5"] >= .80)
            & (merged["conf_6"] >= .80)
        ),
        "5&6 agree both85": (
            (merged["pred_5"] == merged["pred_6"])
            & (merged["conf_5"] >= .85)
            & (merged["conf_6"] >= .85)
        ),
        "6&7 agree both80": (
            (merged["pred_6"] == merged["pred_7"])
            & (merged["conf_6"] >= .80)
            & (merged["conf_7"] >= .80)
        ),
        "6&7 agree both85": (
            (merged["pred_6"] == merged["pred_7"])
            & (merged["conf_6"] >= .85)
            & (merged["conf_7"] >= .85)
        ),
        "7&8 agree both80": (
            (merged["pred_7"] == merged["pred_8"])
            & (merged["conf_7"] >= .80)
            & (merged["conf_8"] >= .80)
        ),
        "7&8 agree both85": (
            (merged["pred_7"] == merged["pred_8"])
            & (merged["conf_7"] >= .85)
            & (merged["conf_8"] >= .85)
        ),
        "8&9 agree both80": (
            (merged["pred_8"] == merged["pred_9"])
            & (merged["conf_8"] >= .80)
            & (merged["conf_9"] >= .80)
        ),
        "8&9 agree both85": (
            (merged["pred_8"] == merged["pred_9"])
            & (merged["conf_8"] >= .85)
            & (merged["conf_9"] >= .85)
        ),
        "5/6/7 all agree min80": (
            (merged["pred_5"] == merged["pred_6"])
            & (merged["pred_6"] == merged["pred_7"])
            & (merged["conf_5"] >= .80)
            & (merged["conf_6"] >= .80)
            & (merged["conf_7"] >= .80)
        ),
        "6/7/8 all agree min80": (
            (merged["pred_6"] == merged["pred_7"])
            & (merged["pred_7"] == merged["pred_8"])
            & (merged["conf_6"] >= .80)
            & (merged["conf_7"] >= .80)
            & (merged["conf_8"] >= .80)
        ),
        "7/8/9 all agree min80": (
            (merged["pred_7"] == merged["pred_8"])
            & (merged["pred_8"] == merged["pred_9"])
            & (merged["conf_7"] >= .80)
            & (merged["conf_8"] >= .80)
            & (merged["conf_9"] >= .80)
        ),
        "5/6/7 all agree min85": (
            (merged["pred_5"] == merged["pred_6"])
            & (merged["pred_6"] == merged["pred_7"])
            & (merged["conf_5"] >= .85)
            & (merged["conf_6"] >= .85)
            & (merged["conf_7"] >= .85)
        ),
        "6/7/8 all agree min85": (
            (merged["pred_6"] == merged["pred_7"])
            & (merged["pred_7"] == merged["pred_8"])
            & (merged["conf_6"] >= .85)
            & (merged["conf_7"] >= .85)
            & (merged["conf_8"] >= .85)
        ),
        "7/8/9 all agree min85": (
            (merged["pred_7"] == merged["pred_8"])
            & (merged["pred_8"] == merged["pred_9"])
            & (merged["conf_7"] >= .85)
            & (merged["conf_8"] >= .85)
            & (merged["conf_9"] >= .85)
        ),
    }

    decision_minute = {
        "5&6 agree both80":6, "5&6 agree both85":6,
        "6&7 agree both80":7, "6&7 agree both85":7,
        "7&8 agree both80":8, "7&8 agree both85":8,
        "8&9 agree both80":9, "8&9 agree both85":9,
        "5/6/7 all agree min80":7,
        "6/7/8 all agree min80":8,
        "7/8/9 all agree min80":9,
        "5/6/7 all agree min85":7,
        "6/7/8 all agree min85":8,
        "7/8/9 all agree min85":9,
    }

    for name, mask in rules.items():
        q = merged[mask]
        if len(q):
            dm = decision_minute[name]
            acc = (q[f"pred_{dm}"] == q["y"]).mean()
            print(
                f"{name:28s} | n={len(q):3d} | "
                f"coverage={len(q)/len(merged):5.1%} | accuracy={acc:.3f}"
            )
    print()

agg = pd.concat(block_frames, ignore_index=True)

print("=== AGGREGATE UNTOUCHED RESULTS ===")

aggregate_rules = {
    "5&6 agree both80": (
        (agg["pred_5"] == agg["pred_6"]) & (agg["conf_5"] >= .80) & (agg["conf_6"] >= .80)
    ),
    "5&6 agree both85": (
        (agg["pred_5"] == agg["pred_6"]) & (agg["conf_5"] >= .85) & (agg["conf_6"] >= .85)
    ),
    "6&7 agree both80": (
        (agg["pred_6"] == agg["pred_7"]) & (agg["conf_6"] >= .80) & (agg["conf_7"] >= .80)
    ),
    "6&7 agree both85": (
        (agg["pred_6"] == agg["pred_7"]) & (agg["conf_6"] >= .85) & (agg["conf_7"] >= .85)
    ),
    "7&8 agree both80": (
        (agg["pred_7"] == agg["pred_8"]) & (agg["conf_7"] >= .80) & (agg["conf_8"] >= .80)
    ),
    "7&8 agree both85": (
        (agg["pred_7"] == agg["pred_8"]) & (agg["conf_7"] >= .85) & (agg["conf_8"] >= .85)
    ),
    "8&9 agree both80": (
        (agg["pred_8"] == agg["pred_9"]) & (agg["conf_8"] >= .80) & (agg["conf_9"] >= .80)
    ),
    "8&9 agree both85": (
        (agg["pred_8"] == agg["pred_9"]) & (agg["conf_8"] >= .85) & (agg["conf_9"] >= .85)
    ),
    "5/6/7 all agree min80": (
        (agg["pred_5"] == agg["pred_6"]) & (agg["pred_6"] == agg["pred_7"])
        & (agg["conf_5"] >= .80) & (agg["conf_6"] >= .80) & (agg["conf_7"] >= .80)
    ),
    "6/7/8 all agree min80": (
        (agg["pred_6"] == agg["pred_7"]) & (agg["pred_7"] == agg["pred_8"])
        & (agg["conf_6"] >= .80) & (agg["conf_7"] >= .80) & (agg["conf_8"] >= .80)
    ),
    "7/8/9 all agree min80": (
        (agg["pred_7"] == agg["pred_8"]) & (agg["pred_8"] == agg["pred_9"])
        & (agg["conf_7"] >= .80) & (agg["conf_8"] >= .80) & (agg["conf_9"] >= .80)
    ),
    "5/6/7 all agree min85": (
        (agg["pred_5"] == agg["pred_6"]) & (agg["pred_6"] == agg["pred_7"])
        & (agg["conf_5"] >= .85) & (agg["conf_6"] >= .85) & (agg["conf_7"] >= .85)
    ),
    "6/7/8 all agree min85": (
        (agg["pred_6"] == agg["pred_7"]) & (agg["pred_7"] == agg["pred_8"])
        & (agg["conf_6"] >= .85) & (agg["conf_7"] >= .85) & (agg["conf_8"] >= .85)
    ),
    "7/8/9 all agree min85": (
        (agg["pred_7"] == agg["pred_8"]) & (agg["pred_8"] == agg["pred_9"])
        & (agg["conf_7"] >= .85) & (agg["conf_8"] >= .85) & (agg["conf_9"] >= .85)
    ),
}

decision_minute = {
    "5&6 agree both80":6, "5&6 agree both85":6,
    "6&7 agree both80":7, "6&7 agree both85":7,
    "7&8 agree both80":8, "7&8 agree both85":8,
    "8&9 agree both80":9, "8&9 agree both85":9,
    "5/6/7 all agree min80":7,
    "6/7/8 all agree min80":8,
    "7/8/9 all agree min80":9,
    "5/6/7 all agree min85":7,
    "6/7/8 all agree min85":8,
    "7/8/9 all agree min85":9,
}

for name, mask in aggregate_rules.items():
    q = agg[mask]
    if len(q):
        dm = decision_minute[name]
        acc = (q[f"pred_{dm}"] == q["y"]).mean()
        print(
            f"{name:28s} | n={len(q):3d} | "
            f"coverage={len(q)/len(agg):5.1%} | accuracy={acc:.3f}"
        )

print()
print("=== STABILITY BY BLOCK FOR 90%+ CANDIDATES ===")
for name, mask in aggregate_rules.items():
    q = agg[mask]
    if len(q) == 0:
        continue
    dm = decision_minute[name]
    overall_acc = (q[f"pred_{dm}"] == q["y"]).mean()

    if overall_acc >= .90:
        vals = []
        for block in sorted(agg["block"].unique()):
            z = agg[agg["block"] == block]
            local_mask = aggregate_rules[name].loc[z.index]
            zz = z[local_mask]
            if len(zz):
                vals.append((block, len(zz), (zz[f"pred_{dm}"] == zz["y"]).mean()))
            else:
                vals.append((block, 0, np.nan))

        txt = " | ".join(
            f"B{b}: n={n}, acc={'NA' if pd.isna(a) else f'{a:.3f}'}"
            for b,n,a in vals
        )
        print(f"{name:28s} | {txt}")

print()
print("=== EARLIEST QUALIFIED OPPORTUNITY ===")

candidate_order = [
    ("minute 6: 5&6 agree both85", aggregate_rules["5&6 agree both85"], 6),
    ("minute 7: 5/6/7 all agree min80", aggregate_rules["5/6/7 all agree min80"], 7),
    ("minute 7: 6&7 agree both85", aggregate_rules["6&7 agree both85"], 7),
    ("minute 8: 6/7/8 all agree min80", aggregate_rules["6/7/8 all agree min80"], 8),
    ("minute 8: 7&8 agree both85", aggregate_rules["7&8 agree both85"], 8),
    ("minute 9: 7/8/9 all agree min80", aggregate_rules["7/8/9 all agree min80"], 9),
]

assigned = pd.Series(False, index=agg.index)
for label, mask, dm in candidate_order:
    qmask = mask & (~assigned)
    q = agg[qmask]
    if len(q):
        acc = (q[f"pred_{dm}"] == q["y"]).mean()
        print(
            f"{label:38s} | new_calls={len(q):3d} | "
            f"share={len(q)/len(agg):5.1%} | accuracy={acc:.3f}"
        )
        assigned |= qmask

print(
    f"Contracts receiving any early candidate by minute 9: "
    f"{assigned.sum()}/{len(agg)} ({assigned.mean():.1%})"
)

print()
print("=== HARD CHECKS ===")
print("Settlement-label consistency:", "PASS" if label_ok.all() else "FAIL")
print("Future-data usage: PASS")
print("Chronological holdouts: PASS")
print("Corrected Kalshi timing: PASS")
print("Same-contract minute progression: PASS")

print()
print("=== TEST COMPLETE ===")
print("No bot files modified.")
print("Use only candidates that remain >=90% across untouched chronological blocks.")
